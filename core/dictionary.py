"""Build a REDCap data dictionary from a form profile.

The same rows feed the mock's metadata export (API keys) and the dictionary CSV
a person uploads to set up a real project (human-readable headers, assumption
A15 in docs/REDCAP_ASSUMPTIONS.md).
"""

from __future__ import annotations

from core.profile import (
    PATIENT_ID_FIELD,
    RECORD_ID_FIELD,
    ColumnSpec,
    Profile,
    Role,
)

# (API key, CSV header), in the order of REDCap's dictionary template.
COLUMNS: list[tuple[str, str]] = [
    ("field_name", "Variable / Field Name"),
    ("form_name", "Form Name"),
    ("section_header", "Section Header"),
    ("field_type", "Field Type"),
    ("field_label", "Field Label"),
    ("select_choices_or_calculations", "Choices, Calculations, OR Slider Labels"),
    ("field_note", "Field Note"),
    ("text_validation_type_or_show_slider_number", "Text Validation Type OR Show Slider Number"),
    ("text_validation_min", "Text Validation Min"),
    ("text_validation_max", "Text Validation Max"),
    ("identifier", "Identifier?"),
    ("branching_logic", "Branching Logic (Show field only if...)"),
    ("required_field", "Required Field?"),
    ("custom_alignment", "Custom Alignment"),
    ("question_number", "Question Number (surveys only)"),
    ("matrix_group_name", "Matrix Group Name"),
    ("matrix_ranking", "Matrix Ranking?"),
    ("field_annotation", "Field Annotation"),
]
API_KEYS = [k for k, _ in COLUMNS]
CSV_HEADERS = [h for _, h in COLUMNS]
RADIO_MAX_CHOICES = 6  # longer lists become dropdowns


def _row(**values) -> dict[str, str]:
    row = {k: "" for k in API_KEYS}
    row.update({k: "" if v is None else str(v) for k, v in values.items()})
    return row


def _num(x: float | None) -> str:
    if x is None:
        return ""
    return str(int(x)) if float(x).is_integer() else str(x)


def column_row(col: ColumnSpec, profile: Profile) -> dict[str, str]:
    label = col.label_en if col.label_en else col.label
    note = col.label if col.label_en else ""
    common = dict(field_name=col.field, form_name=profile.instrument, field_label=label, field_note=note,
                  required_field="y" if col.required else "",
                  field_annotation=f"Source: column ({col.number}) {col.label_id}" if col.number else "")
    if col.role == Role.identifier_pseudonymise:
        common["field_note"] = "Pseudonym (keyed hash); not the original number"
        return _row(**common, field_type="text", identifier="y")
    if col.type == "choice":
        choices = profile.choices_for(col)
        text = " | ".join(f"{c.code}, {c.label_id}" for c in choices)
        kind = "radio" if len(choices) <= RADIO_MAX_CHOICES else "dropdown"
        return _row(**common, field_type=kind, select_choices_or_calculations=text)
    validation = {"integer": "integer", "number": "number", "date": "date_ymd"}.get(col.type, "")
    return _row(**common, field_type="text", text_validation_type_or_show_slider_number=validation,
                text_validation_min=_num(col.min), text_validation_max=_num(col.max))


def build_dictionary(profile: Profile) -> list[dict[str, str]]:
    """Dictionary rows in upload order: record_id, patient_pid, then the profile's uploaded fields."""
    rows = [_row(field_name=RECORD_ID_FIELD, form_name=profile.instrument, field_type="text",
                 field_label="Record ID (pseudonym of the patient register number)")]
    if any(c.role == Role.patient_id_source for c in profile.columns):
        rows.append(_row(field_name=PATIENT_ID_FIELD, form_name=profile.instrument, field_type="text",
                         field_label="Patient link (pseudonym of the NIK)", identifier="y"))
    rows += [column_row(c, profile) for c in profile.uploaded_columns()]
    return rows


def choices_from_row(row: dict[str, str]) -> dict[str, str]:
    """Code -> label for a radio/dropdown dictionary row."""
    out = {}
    for part in row.get("select_choices_or_calculations", "").split("|"):
        if "," in part:
            code, label = part.split(",", 1)
            out[code.strip()] = label.strip()
    return out
