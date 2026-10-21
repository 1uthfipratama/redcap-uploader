"""Turn the data rows of a grid into a table keyed by stable column keys.

Values are typed per the profile: dates become datetime.date, integers int,
numbers float, everything else trimmed text. Identifier columns are kept as the
raw cell object (core/identifiers.py cleans them next) and are never quoted in
an issue.

Call this only through core/pipeline.py, which applies identifier handling
straight after, so the raw table never leaves the core.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import pandas as pd

from core.grid import Grid, cell_text
from core.issues import Issue
from core.layout import Layout
from core.profile import IDENTIFIER_ROLES, ColumnSpec, Profile

ROW = "_row"  # 1-based spreadsheet row number, kept for messages


@dataclass
class ParseResult:
    frame: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)


def parse_rows(grid: Grid, layout: Layout, profile: Profile) -> ParseResult:
    """Read every data row. Generic profiles read all columns as text."""
    issues: list[Issue] = []
    specs = _column_specs(layout, profile)
    records = []
    for r in layout.data_rows:
        record: dict[str, object] = {ROW: r + 1}
        for sheet_col, key, spec in specs:
            raw = grid.value(r, sheet_col)
            record[key] = _convert(raw, spec, profile.layout.date_format, r + 1, issues)
        records.append(record)
    columns = [ROW] + [key for _, key, _ in specs]
    # dtype=object keeps None as None and whole numbers as int (no NaN, no 45.0).
    return ParseResult(frame=pd.DataFrame(records, columns=columns, dtype=object), issues=issues)


def convert_text(text: str, spec: ColumnSpec, date_format: str, row: int) -> tuple[object, list[Issue]]:
    """One typed value from text a person entered, with the issues parse_rows would have reported for it."""
    issues: list[Issue] = []
    return _convert(text, spec, date_format, row, issues), issues


def _column_specs(layout: Layout, profile: Profile) -> list[tuple[int, str, ColumnSpec | None]]:
    if profile.is_generic:
        return [(c.sheet_col, c.key, None) for c in layout.columns]
    out = []
    for col in layout.columns:
        spec = profile.column(col.key)
        if spec is not None:
            out.append((col.sheet_col, col.key, spec))
    return out


def _convert(raw: object, spec: ColumnSpec | None, date_format: str, row: int, issues: list[Issue]) -> object:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if spec is None:
        return cell_text(raw)
    if spec.role in IDENTIFIER_ROLES:
        return raw  # cleaned and hashed or dropped by core/identifiers.py; never echoed
    label = spec.field or spec.key
    if spec.type == "date":
        return _to_date(raw, date_format, row, label, issues)
    if spec.type in ("integer", "number"):
        return _to_number(raw, spec.type == "integer", row, label, issues)
    return cell_text(raw)


def _to_date(raw: object, date_format: str, row: int, label: str, issues: list[Issue]) -> dt.date | None:
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    text = cell_text(raw)
    try:
        return dt.datetime.strptime(text, date_format).date()
    except ValueError:
        issues.append(Issue("date_unreadable", row=row, field=label,
                            params={"value": text, "expected": human_format(date_format)}))
        return None


def _to_number(raw: object, integer: bool, row: int, label: str, issues: list[Issue]) -> float | int | None:
    if isinstance(raw, bool):
        raw = int(raw)
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = cell_text(raw).replace(",", ".")
        if not re.fullmatch(r"-?\d+(\.\d+)?", text):
            issues.append(Issue("not_a_number", row=row, field=label, params={"value": cell_text(raw)}))
            return None
        value = float(text)
    if integer:
        if not value.is_integer():
            issues.append(Issue("not_whole_number", row=row, field=label, params={"value": cell_text(raw)}))
            return None
        return int(value)
    return value


def human_format(date_format: str) -> str:
    return date_format.replace("%d", "dd").replace("%m", "mm").replace("%Y", "yyyy")
