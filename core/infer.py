"""Draft a form profile, and so a REDCap data dictionary, from a spreadsheet with one header row.

For each column the draft suggests a REDCap field name, a type (date, whole number, decimal,
answer list or text), the answers seen, and how the column is handled: uploaded, turned into
a pseudonym, or left out. Columns that look like identifiers, by their header or by their
contents, are left out or pseudonymised by default. The person reviews every column before
the draft becomes a profile (app/draft_dialog.py); from then on the file is handled like any
other form, with the same checks.

Privacy: a draft holds no cell values except the answers of answer-list columns, which become
the answer labels of the data dictionary. Identifier columns never contribute answers.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dc_field

import yaml

from core.grid import Grid, cell_text
from core.identifiers import clean_register_number
from core.layout import Layout, slug
from core.mapping import CONFIG_DIR, load_generic_config, looks_like_identifier
from core.normalise import spelling_key
from core.profile import (
    GENERATED_FIELDS,
    MAX_FIELD_NAME,
    Choice,
    ColumnSpec,
    Identity,
    LayoutSpec,
    Profile,
    Role,
    field_name_problem,
)

TYPES = ("date", "integer", "number", "choice", "text")
UPLOADED_ROLES = (Role.data, Role.identifier_pseudonymise)
NIK_RE = re.compile(r"^\d{16}$")
PHONE_RE = re.compile(r"^(\+?62|0)8\d{7,12}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_RE = re.compile(r"^[A-Za-z.'`-]+( [A-Za-z.'`-]+){1,4}$")
NUMBER_RE = re.compile(r"^-?\d+([.,]\d+)?$")  # a decimal comma (72,5) is read as a decimal point, as the reader does
MAX_FORM_CODE = 20


def load_settings() -> dict:
    with open(CONFIG_DIR / "draft.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class ColumnDraft:
    key: str
    header: str
    type: str  # one of TYPES, or "empty"
    role: Role
    field: str = ""  # suggested REDCap field name, used when the column is uploaded
    choices: list[Choice] = dc_field(default_factory=list)
    reason: str = ""  # why it is handled so: "nik", "phone", "email", "name", "identifier_header",
    #                   "free_text", "row_number", "unique_id", "empty", or "" for plain data
    filled: int = 0
    unique: bool = False  # every row filled and no value repeated

    def allowed_types(self) -> list[str]:
        """The types the person may switch this column to."""
        return {"choice": ["choice", "text"], "integer": ["integer", "number", "text"],
                "number": ["number", "text"], "date": ["date", "text"]}.get(self.type, ["text"])


@dataclass
class Draft:
    columns: list[ColumnDraft]
    date_format: str
    rows: int


# ---- drafting ------------------------------------------------------------------------

def draft_columns(grid: Grid, layout: Layout, settings: dict | None = None, date_format: str | None = None) -> Draft:
    """A draft for every column of a single-header layout. Text dates are read with `date_format` when it
    is given, else with the format that fits the most cells."""
    settings = settings or load_settings()
    generic = load_generic_config()
    values = {c.key: [grid.value(r, c.sheet_col) for r in layout.data_rows] for c in layout.columns}
    date_format = date_format or _best_date_format([v for vs in values.values() for v in vs], settings["date_formats"])
    columns = [_draft_column(c.key, c.label, values[c.key], date_format, settings, generic)
               for c in layout.columns]
    _choose_record_id(columns, settings)
    _choose_patient_link(columns)
    _name_fields(columns)
    return Draft(columns, date_format, len(layout.data_rows))


def date_formats(settings: dict | None = None) -> list[str]:
    """The text date formats the review screen offers, in the order they are tried."""
    return list((settings or load_settings())["date_formats"])


def _text(value: object) -> str:
    return cell_text(value).lstrip("'").strip()


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_date(text: str, date_format: str) -> bool:
    try:
        dt.datetime.strptime(text, date_format)
        return True
    except ValueError:
        return False


def _best_date_format(values: list[object], formats: list[str]) -> str:
    texts = [v.strip() for v in values if isinstance(v, str) and re.search(r"\d", v)]
    scores = [(sum(_is_date(t, f) for t in texts), -i) for i, f in enumerate(formats)]
    return formats[-max(scores)[1]] if texts else formats[0]


def _draft_column(key: str, header: str, values: list[object], date_format: str, settings: dict,
                  generic: dict) -> ColumnDraft:
    filled = [v for v in values if not _blank(v)]
    if not filled:
        return ColumnDraft(key, header, "empty", Role.ignore, reason="empty")
    texts = [_text(v) for v in filled]
    kind = _infer_type(filled, texts, date_format, settings)
    choices = _answers(texts, settings) if kind == "text" else []
    if choices:
        kind = "choice"
    unique = len(filled) == len(values) and len({clean_register_number(v) for v in filled}) == len(filled)
    role, reason = _role(header, texts, kind, settings, generic)
    if role != Role.data:
        choices = []  # identifier columns never keep their values
    return ColumnDraft(key, header, kind, role, choices=choices, reason=reason, filled=len(filled), unique=unique)


def _infer_type(filled: list[object], texts: list[str], date_format: str, settings: dict) -> str:
    need = settings["type_share"] * len(filled)
    dates = sum(isinstance(v, (dt.date, dt.datetime)) or (isinstance(v, str) and _is_date(v.strip(), date_format))
                for v in filled)
    if dates >= need:
        return "date"
    if any(re.match(r"^0\d", t) for t in texts):
        return "text"  # leading zeros: codes, IDs or phone numbers, not quantities
    numbers = [t for t in texts if NUMBER_RE.match(t)]
    if numbers and len(numbers) >= need:
        return "integer" if all(_number(t).is_integer() for t in numbers) else "number"
    return "text"


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def _answers(texts: list[str], settings: dict) -> list[Choice]:
    """An answer list, if the column repeats a few short values; else []."""
    groups: dict[str, Counter] = {}
    for t in texts:
        groups.setdefault(spelling_key(t), Counter())[t] += 1
    if (len(texts) < settings["choice_min_rows"] or len(groups) > settings["choice_max"]
            or len(groups) > len(texts) / 2 or any(len(k) > settings["choice_max_length"] for k in groups)):
        return []
    known = _known_answers(set(groups), settings)
    if known:
        return known
    ordered = sorted(groups.values(), key=lambda c: (-sum(c.values()), c.most_common(1)[0][0]))
    return [Choice(code=str(i), label_id=c.most_common(1)[0][0], label_en=c.most_common(1)[0][0])
            for i, c in enumerate(ordered, start=1)]


def _known_answers(seen: set[str], settings: dict) -> list[Choice]:
    """A standard answer set (yes/no, sex, positive/negative) when every value seen belongs to it."""
    for answer_set in settings["answer_sets"]:
        spellings = {spelling_key(s) for a in answer_set["answers"] for s in [a["label"], *a["spellings"]]}
        if seen <= spellings:
            return [Choice(code=a["code"], label_id=a["label"], label_en=a["label"], spellings=a["spellings"])
                    for a in answer_set["answers"]]
    return []


def _role(header: str, texts: list[str], kind: str, settings: dict, generic: dict) -> tuple[Role, str]:
    need = settings["content_share"] * len(texts)

    def most(pattern: re.Pattern, strip: str = "") -> bool:
        return sum(bool(pattern.match(re.sub(strip, "", t) if strip else t)) for t in texts) >= need

    if most(NIK_RE):
        return Role.identifier_drop, "nik"
    if most(PHONE_RE, r"[\s.()-]"):
        return Role.identifier_drop, "phone"
    if most(EMAIL_RE):
        return Role.identifier_drop, "email"
    if looks_like_identifier(header, generic):
        return Role.identifier_drop, "identifier_header"
    if kind == "text":
        if most(NAME_RE) and len(set(texts)) >= settings["content_share"] * len(texts):
            return Role.identifier_drop, "name"
        if sum(len(t) for t in texts) / len(texts) > settings["free_text_drop_length"]:
            return Role.identifier_drop, "free_text"
    if kind == "integer" and _is_row_counter(texts):
        return Role.ignore, "row_number"
    return Role.data, ""


def _is_row_counter(texts: list[str]) -> bool:
    """1, 2, 3, ... in row order: a row number, which changes from one export to the next."""
    try:
        return [int(_number(t)) for t in texts] == list(range(1, len(texts) + 1))
    except ValueError:
        return False


def _choose_record_id(columns: list[ColumnDraft], settings: dict) -> None:
    """The column that identifies each row becomes the pseudonymised record ID."""
    id_header = re.compile(settings["record_id_headers"])
    candidates = [(bool(id_header.search(slug(c.header))), c.reason != "nik", -i, c)
                  for i, c in enumerate(columns)
                  if c.unique and c.type in ("text", "integer")
                  and c.reason not in ("row_number", "phone", "email", "name", "free_text")]
    if candidates:
        chosen = max(candidates, key=lambda t: t[:3])[3]
        chosen.role, chosen.reason, chosen.choices = Role.record_id_source, "unique_id", []


def _choose_patient_link(columns: list[ColumnDraft]) -> None:
    """The first NIK column links a patient's rows, through a pseudonym (patient_pid)."""
    for c in columns:
        if c.reason == "nik" and c.role == Role.identifier_drop:
            c.role = Role.patient_id_source
            return


def _name_fields(columns: list[ColumnDraft]) -> None:
    used = set(GENERATED_FIELDS)
    for i, c in enumerate(columns, start=1):
        c.field = unique_name(slug(c.header) or f"col_{i}", used)
        used.add(c.field)


def unique_name(base: str, used: set[str], limit: int = MAX_FIELD_NAME) -> str:
    """A valid REDCap name from base: starts with a letter, at most `limit` characters, not in used."""
    base = base if base[:1].isalpha() else f"f_{base}"
    base = base[:limit].rstrip("_")
    name, k = base, 2
    while name in used:
        suffix = f"_{k}"
        name = base[:limit - len(suffix)].rstrip("_") + suffix
        k += 1
    return name


# ---- from draft to profile -----------------------------------------------------------

def draft_problems(columns: list[ColumnDraft]) -> list[tuple[str, dict]]:
    """What stops the draft from becoming a profile, as (code, params) for plain messages."""
    problems: list[tuple[str, dict]] = []
    record_ids = [c for c in columns if c.role == Role.record_id_source]
    if not record_ids:
        problems.append(("no_record_id", {}))
    elif len(record_ids) > 1:
        problems.append(("many_record_ids", {}))
    if sum(c.role == Role.patient_id_source for c in columns) > 1:
        problems.append(("many_patient_links", {}))
    uploaded = [c for c in columns if c.role in UPLOADED_ROLES]
    if not uploaded:
        problems.append(("nothing_uploaded", {}))
    names = [c.field for c in uploaded]
    for name in names:
        if field_name_problem(name) or name in GENERATED_FIELDS:
            problems.append(("field_name", {"field": name or "—"}))
    for name in sorted({n for n in names if names.count(n) > 1}):
        problems.append(("field_twice", {"field": name}))
    return problems


def form_code_for(name: str, taken: set[str] = frozenset()) -> str:
    """A short code for a new form, used as its REDCap instrument name and in record ID hashing."""
    return unique_name(slug(name) or "custom_form", set(taken), limit=MAX_FORM_CODE)


def profile_from_draft(name: str, columns: list[ColumnDraft], date_format: str, form_code: str) -> Profile:
    """The reviewed draft as a profile. Raises ValueError (pydantic) if it is not valid."""
    specs = []
    for c in columns:
        kind = c.type if c.role == Role.data and c.type in TYPES else "text"
        if kind == "choice" and not c.choices:
            kind = "text"
        specs.append(ColumnSpec(
            key=c.key, label=c.header, role=c.role,
            field=c.field if c.role in UPLOADED_ROLES else None,
            type=kind, choices=c.choices if kind == "choice" else [],
        ))
    return Profile(identity=Identity(form_code=form_code, name=name),
                   layout=LayoutSpec(kind="single_header", date_format=date_format),
                   instrument=form_code, columns=specs)
