"""Form profiles: everything specific to one source form, loaded from YAML.

A profile says how to recognise the form, where its header and data sit, what
each official column means, how it is handled (role), how its spellings map to
REDCap choice codes, and which rules it must pass. The core has no form-specific
constants; a new form needs a new profile, not new code.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_FIELD_NAME = 26
RECORD_ID_FIELD = "record_id"
PATIENT_ID_FIELD = "patient_pid"
GENERATED_FIELDS = (RECORD_ID_FIELD, PATIENT_ID_FIELD)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


class Role(str, Enum):
    record_id_source = "record_id_source"  # hashed into record_id; raw value dropped
    patient_id_source = "patient_id_source"  # NIK: cleaned, hashed into patient_pid; raw dropped
    identifier_drop = "identifier_drop"
    identifier_pseudonymise = "identifier_pseudonymise"  # hashed into its own field
    quasi_identifier = "quasi_identifier"  # dropped unless keep: true
    data = "data"
    ignore = "ignore"
    constant = "constant"  # same on every row (facility block); checked, not uploaded


IDENTIFIER_ROLES = {
    Role.record_id_source,
    Role.patient_id_source,
    Role.identifier_drop,
    Role.identifier_pseudonymise,
    Role.quasi_identifier,
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Choice(_Model):
    code: str
    label_id: str
    label_en: str
    spellings: list[str] = Field(default_factory=list)  # extra source spellings for this code


class RequiredWhen(_Model):
    """Required only when another field (by key) has one of these codes, or is filled at all."""

    field: str
    in_: list[str] | None = Field(default=None, alias="in")
    filled: bool | None = None


class ColumnSpec(_Model):
    key: str
    number: int | None = None
    sub_label: str = ""
    label: str  # the header text as the file shows it (last header part)
    role: Role
    field: str | None = None  # REDCap field name
    type: Literal["text", "integer", "number", "date", "choice"] = "text"
    choice_set: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    required: bool = False
    required_when: RequiredWhen | None = None
    min: float | None = None
    max: float | None = None
    not_future: bool = False
    keep: bool = False  # quasi-identifiers only
    label_id: str = ""
    label_en: str = ""
    note: str = ""


class Identity(_Model):
    form_code: str  # short code used in record_id hashing, e.g. tbc03_so
    name: str
    edition: str = ""
    recognition: list[str] = Field(default_factory=list)  # all must appear in the title text


class LayoutSpec(_Model):
    kind: Literal["numbered", "single_header"] = "numbered"
    first_data_row: int | None = None  # 1-based, informational; detection is automatic
    metadata_labels: dict[str, str] = Field(default_factory=dict)  # facility -> "Nama Fasyankes"
    case_count_label: str | None = None  # title-block label holding the number of data rows
    summary_pattern: str = r"^(jumlah|total)\b"
    date_format: str = "%d/%m/%Y"


class Profile(_Model):
    identity: Identity
    layout: LayoutSpec = Field(default_factory=LayoutSpec)
    instrument: str
    choice_sets: dict[str, list[Choice]] = Field(default_factory=dict)
    columns: list[ColumnSpec] = Field(default_factory=list)
    explore_defaults: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "Profile":
        problems = profile_problems(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    # ---- lookups -------------------------------------------------------------
    @property
    def is_generic(self) -> bool:
        return self.layout.kind == "single_header"

    def column(self, key: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.key == key), None)

    def column_for_field(self, field: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.field == field), None)

    def choices_for(self, col: ColumnSpec) -> list[Choice]:
        if col.choice_set:
            return self.choice_sets[col.choice_set]
        return col.choices

    def uploaded_columns(self) -> list[ColumnSpec]:
        """Columns whose values (or pseudonyms) go to REDCap, in profile order."""
        return [c for c in self.columns if is_uploaded(c)]

    def redcap_fields(self) -> list[str]:
        fields = [RECORD_ID_FIELD]
        if any(c.role == Role.patient_id_source for c in self.columns):
            fields.append(PATIENT_ID_FIELD)
        fields += [c.field for c in self.uploaded_columns() if c.field]
        return fields


def is_uploaded(col: ColumnSpec) -> bool:
    if col.role in (Role.data, Role.identifier_pseudonymise):
        return col.field is not None
    if col.role == Role.quasi_identifier:
        return col.keep and col.field is not None
    return False


def field_name_problem(name: str) -> str | None:
    if not FIELD_NAME_RE.match(name):
        return f"field name '{name}' must be lowercase letters, digits and underscores, starting with a letter"
    if len(name) > MAX_FIELD_NAME:
        return f"field name '{name}' is longer than {MAX_FIELD_NAME} characters"
    return None


def profile_problems(profile: Profile) -> list[str]:
    """Every structural problem in a profile, so a broken profile fails loudly at load time."""
    problems: list[str] = []
    keys = [c.key for c in profile.columns]
    if len(keys) != len(set(keys)):
        problems.append("column keys are not unique")
    fields = [c.field for c in profile.columns if c.field]
    for name in fields:
        if (p := field_name_problem(name)):
            problems.append(p)
        if name in GENERATED_FIELDS:
            problems.append(f"field name '{name}' is reserved")
    if len(fields) != len(set(fields)):
        dupes = sorted({f for f in fields if fields.count(f) > 1})
        problems.append(f"field names used twice: {', '.join(dupes)}")
    if (p := field_name_problem(profile.instrument)):
        problems.append(f"instrument: {p}")
    for col in profile.columns:
        if col.role in (Role.data, Role.identifier_pseudonymise) and not col.field:
            problems.append(f"{col.key}: role {col.role.value} needs a field name")
        if col.type == "choice":
            if col.choice_set and col.choice_set not in profile.choice_sets:
                problems.append(f"{col.key}: unknown choice set '{col.choice_set}'")
            elif not col.choice_set and not col.choices:
                problems.append(f"{col.key}: choice column without choices")
        if col.required_when and col.required_when.field not in keys:
            problems.append(f"{col.key}: required_when refers to unknown key '{col.required_when.field}'")
    for name, choices in profile.choice_sets.items():
        codes = [c.code for c in choices]
        if len(codes) != len(set(codes)):
            problems.append(f"choice set '{name}' repeats a code")
    if not profile.is_generic and sum(c.role == Role.record_id_source for c in profile.columns) != 1:
        problems.append("a register profile needs exactly one record_id_source column")
    return problems


def load_profile(path: str | Path) -> Profile:
    with open(path, encoding="utf-8") as fh:
        return Profile.model_validate(yaml.safe_load(fh))


def load_all_profiles(directory: str | Path = PROFILES_DIR) -> dict[str, Profile]:
    profiles = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        profile = load_profile(path)
        profiles[profile.identity.form_code] = profile
    return profiles
