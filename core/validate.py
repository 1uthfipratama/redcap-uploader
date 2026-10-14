"""Dry-run checks on the cleaned table. Nothing is sent anywhere.

Rules come from the profile: required fields (including required-when),
allowed choice codes, number ranges, dates not in the future, and unique record
IDs. Each problem is an Issue with a row, a field and a message key.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

import pandas as pd

from core.issues import ERROR, Issue
from core.normalise import UnmappedSpelling
from core.parse import ROW
from core.profile import RECORD_ID_FIELD, ColumnSpec, Profile


def validate(frame: pd.DataFrame, profile: Profile, unmapped: list[UnmappedSpelling] | None = None,
             today: dt.date | None = None) -> list[Issue]:
    today = today or dt.date.today()
    issues: list[Issue] = []
    issues += _duplicate_record_ids(frame)
    if RECORD_ID_FIELD not in frame.columns:
        issues.append(Issue("record_id_not_mapped", ERROR))
    unmapped_lookup = {(u.field, u.spelling) for u in (unmapped or [])}
    by_key = {c.key: c for c in profile.columns}
    for col in profile.columns:
        if not col.field or col.field not in frame.columns:
            continue
        codes = {c.code for c in profile.choices_for(col)} if col.type == "choice" else set()
        for idx, value in frame[col.field].items():
            row = int(frame.at[idx, ROW])
            if value is None:
                if col.required:
                    issues.append(Issue("required_missing", row=row, field=col.field))
                elif col.required_when and _condition_holds(frame, idx, col, by_key):
                    other = by_key[col.required_when.field]
                    issues.append(Issue("required_when_missing", row=row, field=col.field,
                                        params={"other": other.field or other.key}))
                continue
            issues += _check_value(value, col, codes, row, today, unmapped_lookup)
    return issues


def _check_value(value, col: ColumnSpec, codes: set[str], row: int, today: dt.date,
                 unmapped_lookup: set[tuple[str, str]]) -> list[Issue]:
    if col.type == "choice" and value not in codes:
        code = "spelling_unmapped" if (col.field, value) in unmapped_lookup else "choice_unknown"
        return [Issue(code, row=row, field=col.field, params={"value": value})]
    if col.type in ("integer", "number"):
        if col.min is not None and value < col.min:
            return [Issue("below_min", row=row, field=col.field, params={"value": _fmt(value), "min": _fmt(col.min)})]
        if col.max is not None and value > col.max:
            return [Issue("above_max", row=row, field=col.field, params={"value": _fmt(value), "max": _fmt(col.max)})]
    if col.type == "date" and col.not_future and value > today:
        return [Issue("date_in_future", row=row, field=col.field, params={"value": value.strftime("%d/%m/%Y")})]
    return []


def _condition_holds(frame: pd.DataFrame, idx, col: ColumnSpec, by_key: dict[str, ColumnSpec]) -> bool:
    cond = col.required_when
    other = by_key[cond.field]
    if not other.field or other.field not in frame.columns:
        return False
    value = frame.at[idx, other.field]
    if cond.filled is not None:
        return (value is not None) == cond.filled
    if cond.in_ is not None:
        return value is not None and str(value) in cond.in_
    return False


def _duplicate_record_ids(frame: pd.DataFrame) -> list[Issue]:
    """Rows sharing a record ID. The message names the rows, never the ID's source value."""
    if RECORD_ID_FIELD not in frame.columns:
        return []
    rows_by_id: dict[str, list[int]] = defaultdict(list)
    for rid, row in zip(frame[RECORD_ID_FIELD], frame[ROW]):
        if rid is not None:
            rows_by_id[rid].append(int(row))
    issues = []
    for rows in rows_by_id.values():
        if len(rows) > 1:
            others = ", ".join(str(r) for r in rows[1:])
            issues += [Issue("duplicate_record_id", row=rows[0], field=RECORD_ID_FIELD, params={"others": others})]
    return issues


def _fmt(x) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)
