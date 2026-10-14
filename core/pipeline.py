"""The whole path from a file to a validated, REDCap-ready table.

    layout -> layout check -> parse -> identifiers -> map -> normalise -> validate

This is the only public way to read a file: the raw parsed table (with
identifiers) exists only inside prepare() and is replaced before it returns.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core import identifiers as ids
from core.grid import Grid, read_grid
from core.issues import Issue, errors, warnings
from core.layout import Layout, detect_layout
from core.mapping import (
    Mapping,
    apply_mapping,
    check_case_count,
    check_layout,
    load_generic_config,
    looks_like_identifier,
    map_generic,
    map_profile,
    read_metadata,
    recognise,
)
from core.normalise import SpellingChange, UnmappedSpelling, normalise
from core.parse import ROW, parse_rows
from core.profile import Profile, load_all_profiles
from core.validate import validate

log = logging.getLogger("redcap_uploader.pipeline")


@dataclass
class Detected:
    grid: Grid
    layout: Layout
    form_code: str  # recognised profile, or "generic"


@dataclass
class Prepared:
    profile: Profile
    layout: Layout
    metadata: dict[str, str] = field(default_factory=dict)
    frame: pd.DataFrame | None = None  # REDCap field names + ROW; identifiers already handled
    mapping: Mapping | None = None
    identifier_report: ids.IdentifierReport | None = None
    changes: list[SpellingChange] = field(default_factory=list)
    unmapped: list[UnmappedSpelling] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    blocked: bool = False  # the layout did not match the profile, so nothing was read

    @property
    def errors(self) -> list[Issue]:
        return errors(self.issues)

    @property
    def warnings(self) -> list[Issue]:
        return warnings(self.issues)

    @property
    def ready(self) -> bool:
        return not self.blocked and self.frame is not None and not self.errors

    @property
    def skipped_rows(self) -> dict[str, int]:
        return {"blank": len(self.layout.blank_rows), "summary": len(self.layout.summary_rows)}


def detect(path: str | Path, profiles: dict[str, Profile] | None = None) -> Detected:
    grid = read_grid(path)
    profiles = profiles if profiles is not None else load_all_profiles()
    layout = detect_layout(grid)
    return Detected(grid=grid, layout=layout, form_code=recognise(layout, profiles))


def prepare(source: str | Path | Detected, profile: Profile, key: bytes | None = None, *,
            target_fields: list[str] | None = None, overrides: dict[str, str | None] | None = None,
            today: dt.date | None = None) -> Prepared:
    """Read, de-identify, map, normalise and validate one file.

    key: the pseudonym key (core.identifiers.load_key()); register profiles need it.
    target_fields / overrides: Generic mode only.
    """
    detected = source if isinstance(source, Detected) else detect(source, {})
    grid = detected.grid
    layout = detect_layout(grid, profile.layout.summary_pattern)
    result = Prepared(profile=profile, layout=layout, metadata=read_metadata(layout, profile))

    result.issues += check_layout(layout, profile)
    if result.errors:
        result.blocked = True
        log.info("layout does not match profile %s; file not read", profile.identity.form_code)
        return result
    result.issues += check_case_count(layout, profile)

    parsed = parse_rows(grid, layout, profile)
    result.issues += parsed.issues
    if profile.is_generic:
        frame = _drop_lookalike_identifiers(parsed.frame, layout)
        result.mapping = map_generic(layout, target_fields or [], overrides)
    else:
        if key is None:
            raise ids.PseudonymKeyMissing("a register profile needs the pseudonym key")
        frame, report, id_issues = ids.apply_identifiers(parsed.frame, profile, key)
        result.identifier_report = report
        result.issues += id_issues
        result.mapping = map_profile(list(frame.columns), profile)
    del parsed  # the raw table must not outlive this function

    frame = apply_mapping(frame, result.mapping)
    normalised = normalise(frame, profile)
    result.changes, result.unmapped = normalised.changes, normalised.unmapped
    result.frame = normalised.frame
    result.issues += validate(result.frame, profile, result.unmapped, today=today)
    log.info("prepared %d rows: %d errors, %d warnings, %d blank and %d summary rows skipped",
             len(result.frame), len(result.errors), len(result.warnings),
             len(layout.blank_rows), len(layout.summary_rows))
    return result


def _drop_lookalike_identifiers(frame: pd.DataFrame, layout: Layout) -> pd.DataFrame:
    config = load_generic_config()
    drop = [c.key for c in layout.columns if looks_like_identifier(c.label, config) and c.key in frame.columns]
    return frame.drop(columns=drop)


def to_redcap_records(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Rows as REDCap flat records: text values, dates as YYYY-MM-DD, blanks as ''."""
    records = []
    for _, row in frame.drop(columns=[ROW]).iterrows():
        records.append({k: _redcap_value(v) for k, v in row.items()})
    return records


def _redcap_value(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
