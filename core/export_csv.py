"""Files for REDCap's own tools, for when the API is not available.

- the data dictionary CSV, to set up a project (A15);
- the import-ready CSV for the Data Import Tool (A16): record_id first, codes
  not labels, dates as YYYY-MM-DD, one row per record.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from core.dictionary import API_KEYS, CSV_HEADERS, choices_from_row
from core.pipeline import to_redcap_records


def write_dictionary_csv(dictionary: list[dict[str, str]], path: str | Path) -> Path:
    path = Path(path)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADERS)
        for row in dictionary:
            writer.writerow([row.get(k, "") for k in API_KEYS])
    return path


def read_dictionary_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != CSV_HEADERS:
            raise ValueError("not a REDCap data dictionary: the header differs")
        return [dict(zip(API_KEYS, row)) for row in reader]


def write_import_csv(frame: pd.DataFrame, dictionary: list[dict[str, str]], path: str | Path) -> Path:
    """Columns in dictionary order, limited to the fields present in the table."""
    path = Path(path)
    records = to_redcap_records(frame)
    present = set(frame.columns)
    fields = [r["field_name"] for r in dictionary if r["field_name"] in present]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return path


def check_import_csv(path: str | Path, dictionary: list[dict[str, str]]) -> list[str]:
    """Problems that REDCap's Data Import Tool would refuse. An empty list means the file fits."""
    by_name = {r["field_name"]: r for r in dictionary}
    problems = []
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        if not header or header[0] != dictionary[0]["field_name"]:
            problems.append(f"first column must be {dictionary[0]['field_name']}")
        problems += [f"unknown field {h}" for h in header if h not in by_name]
        for n, row in enumerate(reader, start=2):
            for name, value in row.items():
                spec = by_name.get(name)
                if not spec or not value:
                    continue
                if spec["field_type"] in ("radio", "dropdown") and value not in choices_from_row(spec):
                    problems.append(f"line {n}, {name}: {value} is not a code")
                if spec["text_validation_type_or_show_slider_number"] == "date_ymd" and not _is_ymd(value):
                    problems.append(f"line {n}, {name}: {value} is not YYYY-MM-DD")
    return problems


def _is_ymd(value: str) -> bool:
    import datetime as dt

    try:
        dt.datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False
