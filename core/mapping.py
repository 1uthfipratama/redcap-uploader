"""Match file columns to REDCap fields, and check a file's layout against its profile.

Profile mode: official column numbers decide (a column's key is its number).
Generic mode: header names are compared with the project's field names; each
match carries a confidence score, and the user can override any match.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from core.issues import ERROR, WARNING, Issue
from core.layout import Layout, normalise_label, slug
from core.parse import ROW
from core.profile import (
    GENERATED_FIELDS,
    PATIENT_ID_FIELD,
    RECORD_ID_FIELD,
    Profile,
    Role,
    is_uploaded,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MIN_CONFIDENCE = 0.75


@dataclass
class FieldMatch:
    source_key: str
    source_label: str
    field: str | None  # None = not uploaded
    method: str  # "number", "name", "synonym", "override", "generated", "none"
    confidence: float = 1.0
    role: str = Role.data.value


@dataclass
class Mapping:
    matches: list[FieldMatch] = field(default_factory=list)
    unmatched_fields: list[str] = field(default_factory=list)  # target fields with no source column

    def field_for(self, key: str) -> str | None:
        return next((m.field for m in self.matches if m.source_key == key), None)

    def uploaded(self) -> list[FieldMatch]:
        return [m for m in self.matches if m.field]


# ---- layout check ------------------------------------------------------------

def check_layout(layout: Layout, profile: Profile) -> list[Issue]:
    """Differences between a file's layout and its profile. Errors block reading."""
    if profile.is_generic:
        return []
    issues: list[Issue] = []
    if layout.kind != profile.layout.kind:
        return [Issue("layout_kind_differs", ERROR)]
    file_keys = {c.key: c for c in layout.columns}
    for spec in profile.columns:
        col = file_keys.get(spec.key)
        if col is None:
            issues.append(Issue("column_missing", ERROR, params={"number": spec.number, "label": spec.label}))
        elif normalise_label(col.label) != normalise_label(spec.label):
            issues.append(Issue("label_changed", WARNING, params={
                "number": spec.number, "expected": spec.label, "found": col.label}))
    known = {s.key for s in profile.columns}
    for col in layout.columns:
        if col.key not in known:
            issues.append(Issue("column_extra", ERROR, params={"number": col.number, "label": col.label}))
    title = " ".join(layout.title_text).casefold()
    edition = profile.identity.edition
    if edition and edition.casefold() not in title:
        issues.append(Issue("edition_differs", WARNING, params={"expected": edition}))
    return issues


def recognise(layout: Layout, profiles: dict[str, Profile]) -> str:
    """The form code whose recognition phrases all appear in the title block, else 'generic'."""
    title = " ".join(layout.title_text).casefold()
    for code, profile in profiles.items():
        phrases = profile.identity.recognition
        if phrases and all(p.casefold() in title for p in phrases):
            return code
    return "generic"


def read_metadata(layout: Layout, profile: Profile) -> dict[str, str]:
    """Facility, period and similar from the title block, by the labels the profile names."""
    out = {}
    for name, label in profile.layout.metadata_labels.items():
        value = layout.metadata.get(normalise_label(label))
        if value:
            out[name] = value
    return out


def check_case_count(layout: Layout, profile: Profile) -> list[Issue]:
    label = profile.layout.case_count_label
    if not label:
        return []
    stated = layout.metadata.get(normalise_label(label))
    if stated is None:
        return []
    if stated != str(len(layout.data_rows)):
        return [Issue("case_count_mismatch", WARNING, params={"stated": stated, "read": len(layout.data_rows)})]
    return []


# ---- profile mode --------------------------------------------------------------

def map_profile(frame_keys: list[str], profile: Profile) -> Mapping:
    mapping = Mapping()
    for generated in GENERATED_FIELDS:
        if generated in frame_keys:
            mapping.matches.append(FieldMatch(generated, generated, generated, "generated"))
    for spec in profile.columns:
        if spec.key not in frame_keys:
            continue
        target = spec.field if is_uploaded(spec) else None
        mapping.matches.append(FieldMatch(spec.key, spec.label, target, "number" if target else "none",
                                          role=spec.role.value))
    return mapping


# ---- generic mode --------------------------------------------------------------

def load_generic_config() -> dict:
    with open(CONFIG_DIR / "generic_mapping.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def looks_like_identifier(header: str, config: dict | None = None) -> bool:
    config = config or load_generic_config()
    name = slug(header)
    return any(re.search(p, name) for p in config["identifier_patterns"])


def map_generic(layout: Layout, target_fields: list[str], overrides: dict[str, str | None] | None = None,
                config: dict | None = None) -> Mapping:
    """Match each header to the closest target field. Look-alike identifier columns are not uploaded."""
    config = config or load_generic_config()
    overrides = overrides or {}
    synonyms = {slug(k): v for k, v in config.get("synonyms", {}).items()}
    mapping = Mapping()
    taken: set[str] = set()
    for col in layout.columns:
        name = slug(col.label)
        if col.key in overrides:
            target = overrides[col.key]
            mapping.matches.append(FieldMatch(col.key, col.label, target, "override", 1.0))
            if target:
                taken.add(target)
            continue
        if looks_like_identifier(col.label, config):
            mapping.matches.append(FieldMatch(col.key, col.label, None, "none", 0.0, Role.identifier_drop.value))
            continue
        target, method, score = _best_field(name, target_fields, synonyms, taken)
        if target:
            taken.add(target)
        mapping.matches.append(FieldMatch(col.key, col.label, target, method, score))
    mapping.unmatched_fields = [f for f in target_fields if f not in taken]
    return mapping


def _best_field(name: str, targets: list[str], synonyms: dict[str, str], taken: set[str]) -> tuple[str | None, str, float]:
    free = [t for t in targets if t not in taken]
    if name in free:
        return name, "name", 1.0
    if synonyms.get(name) in free:
        return synonyms[name], "synonym", 0.95
    scored = sorted(((difflib.SequenceMatcher(None, name, t).ratio(), t) for t in free), reverse=True)
    if scored and scored[0][0] >= MIN_CONFIDENCE:
        return scored[0][1], "name", round(scored[0][0], 2)
    return None, "none", 0.0


# ---- apply -------------------------------------------------------------------

def apply_mapping(frame: pd.DataFrame, mapping: Mapping) -> pd.DataFrame:
    """Keep only mapped columns, renamed to their REDCap field names, plus the row number."""
    keep = {m.source_key: m.field for m in mapping.uploaded() if m.source_key in frame.columns}
    out = frame[[ROW, *keep]].rename(columns=keep)
    first = [f for f in (RECORD_ID_FIELD, PATIENT_ID_FIELD) if f in out.columns]
    rest = [c for c in out.columns if c not in first and c != ROW]
    return out[[ROW, *first, *rest]]
