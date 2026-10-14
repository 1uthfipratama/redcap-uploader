"""A small local stand-in for the REDCap API, covering only the calls the app makes.

It speaks the same HTTP API PyCap uses (POST with a `content` parameter) and
follows docs/REDCAP_ASSUMPTIONS.md: imports are all-or-nothing per request,
values are checked against the data dictionary, blanks never erase stored
values (overwriteBehavior=normal), and errors come back as {"error": "..."}.
Data lives in memory and disappears when the server stops.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import threading
from dataclasses import dataclass, field

from flask import Flask, Response, request

from core.dictionary import choices_from_row

MOCK_VERSION = "14.5.0"


@dataclass
class MockProject:
    token: str
    dictionary: list[dict[str, str]]
    title: str = "Demo project (mock REDCap)"
    project_id: int = 1
    records: dict[str, dict[str, str]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def record_id_field(self) -> str:
        return self.dictionary[0]["field_name"]

    @property
    def field_names(self) -> list[str]:
        return [r["field_name"] for r in self.dictionary]

    @property
    def forms(self) -> list[str]:
        return list(dict.fromkeys(r["form_name"] for r in self.dictionary))


def _json(data, status: int = 200) -> Response:
    return Response(json.dumps(data), status=status, mimetype="application/json")


def _error(message: str, status: int = 400) -> Response:
    return _json({"error": message}, status)


def _listed(form, name: str) -> list[str]:
    """PyCap sends lists as name[0], name[1], ...; plain name=a,b also works."""
    values = [v for k, v in form.items() if k.startswith(f"{name}[")]
    if not values and form.get(name):
        values = [v.strip() for v in form[name].split(",") if v.strip()]
    return values


def create_app(project: MockProject) -> Flask:
    app = Flask("mock_redcap")

    @app.post("/api/")
    def api():
        form = request.form
        if form.get("token") != project.token:
            return _error("You do not have permissions to use the API", 403)
        content = form.get("content", "")
        handler = HANDLERS.get(content)
        if handler is None:
            return _error(f"The value of the parameter \"content\" is not valid: {content}")
        return handler(project, form)

    return app


def _version(project, form):
    return Response(MOCK_VERSION, mimetype="text/plain")


def _project_info(project, form):
    return _json({
        "project_id": project.project_id,
        "project_title": project.title,
        "creation_time": "2026-10-14 00:00:00",
        "in_production": 0,
        "is_longitudinal": 0,
        "has_repeating_instruments_or_events": 0,
        "surveys_enabled": 0,
        "record_autonumbering_enabled": 0,
        "project_language": "English",
        "purpose": 2,
    })


def _metadata(project, form):
    fields = set(_listed(form, "fields"))
    forms = set(_listed(form, "forms"))
    rows = [r for r in project.dictionary
            if (not fields or r["field_name"] in fields) and (not forms or r["form_name"] in forms)]
    return _json(rows)


def _field_names(project, form):
    return _json([{"original_field_name": f, "choice_value": "", "export_field_name": f}
                  for f in project.field_names])


def _form_event_mapping(project, form):
    # A07/A03: classic projects have no events.
    return _error("You cannot export form/event mappings for classic projects")


def _record(project, form):
    return _import(project, form) if "data" in form else _export(project, form)


def _export(project, form):
    wanted = _listed(form, "fields") or project.field_names
    ids = set(_listed(form, "records"))
    complete = {f"{f}_complete" for f in project.forms}
    unknown = [f for f in wanted if f not in project.field_names and f not in complete]
    if unknown:
        return _error(f"The following values in the parameter \"fields\" are not valid: {', '.join(unknown)}")
    rows = []
    with project.lock:
        for rid, rec in project.records.items():
            if ids and rid not in ids:
                continue
            rows.append({f: rec.get(f, "0" if f in complete else "") for f in wanted})
    if form.get("format", "json") == "csv":
        return Response(_to_csv(rows, wanted), mimetype="text/csv")
    return _json(rows)


def _import(project, form):
    try:
        records = _parse_records(form.get("data", ""), form.get("format", "json"))
    except ValueError as exc:
        return _error(f"The data you provided could not be parsed: {exc}")
    date_format = form.get("dateFormat", "YMD")
    errors = []
    rid_field = project.record_id_field
    by_name = {r["field_name"]: r for r in project.dictionary}
    complete = {f"{f}_complete" for f in project.forms}
    unknown = sorted({k for rec in records for k in rec if k not in by_name and k not in complete})
    if unknown:
        return _error("The following fields were not found in the project as real data fields: " + ", ".join(unknown))
    for rec in records:
        rid = str(rec.get(rid_field, "")).strip()
        if not rid:
            errors.append(_line("", rid_field, "", "The record ID is missing"))
            continue
        for name, value in rec.items():
            if name in complete or value in ("", None):
                continue
            problem = _check_value(by_name[name], str(value), date_format)
            if problem:
                errors.append(_line(rid, name, str(value), problem))
    if errors:
        # A06: all-or-nothing; nothing in this batch is saved.
        return _error("\n".join(errors))
    overwrite = form.get("overwriteBehavior", "normal") == "overwrite"
    saved = []
    with project.lock:
        for rec in records:
            rid = str(rec[rid_field]).strip()
            stored = project.records.setdefault(rid, {rid_field: rid})
            for name, value in rec.items():
                value = "" if value is None else str(value)
                if value != "" or overwrite:  # A10: blanks do not erase under "normal"
                    stored[name] = value
            saved.append(rid)
    if form.get("returnContent", "count") == "ids":
        return _json(saved)
    return _json({"count": len(saved)})


def _line(record: str, field_name: str, value: str, message: str) -> str:
    """A07: one problem per line, as "record","field","value","message"."""
    def q(s: str) -> str:
        return '"' + s.replace('"', '""') + '"'
    return ",".join(q(x) for x in (record, field_name, value, message))


def _check_value(row: dict[str, str], value: str, date_format: str) -> str | None:
    kind = row["field_type"]
    if kind in ("radio", "dropdown", "yesno", "truefalse"):
        allowed = choices_from_row(row) if kind in ("radio", "dropdown") else {"0": "", "1": ""}
        if value not in allowed:
            return f"The value is not a valid category for {row['field_name']}"
        return None
    validation = row.get("text_validation_type_or_show_slider_number", "")
    if validation == "integer":
        if not re.fullmatch(r"-?\d+", value):
            return "This field has a validation type of integer, but the value is not an integer"
        return _range(row, int(value))
    if validation == "number":
        try:
            number = float(value)
        except ValueError:
            return "This field has a validation type of number, but the value is not a number"
        return _range(row, number)
    if validation.startswith("date_"):
        if date_format != "YMD":
            return None  # the mock only checks the format the app sends (A08)
        try:
            dt.datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return "The value is not a valid date (YYYY-MM-DD)"
    return None


def _range(row: dict[str, str], number: float) -> str | None:
    low, high = row.get("text_validation_min", ""), row.get("text_validation_max", "")
    if (low and number < float(low)) or (high and number > float(high)):
        return f"The value is outside the allowed range ({low or '-'} to {high or '-'})"
    return None


def _parse_records(data: str, fmt: str) -> list[dict]:
    if fmt == "csv":
        return list(csv.DictReader(io.StringIO(data)))
    try:
        records = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(records, list):
        raise ValueError("expected a list of records")
    return records


def _to_csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


HANDLERS = {
    "version": _version,
    "project": _project_info,
    "metadata": _metadata,
    "exportFieldNames": _field_names,
    "formEventMapping": _form_event_mapping,
    "record": _record,
}
