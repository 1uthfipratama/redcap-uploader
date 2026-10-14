"""Repo-level guards: no real exports, no keys, and no identifier-looking values in fixtures."""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [REPO / line for line in out.splitlines() if line]


def test_no_spreadsheets_or_keys_are_tracked():
    bad = [p for p in _tracked_files() if p.suffix.lower() in (".xls", ".xlsx", ".key", ".env")]
    assert bad == []


def test_no_plausible_nik_in_tracked_text():
    """A real NIK starts with a province code 11-94. Synthetic ones start with 0000."""
    nik = re.compile(r"(?<!\d)(1[1-9]|[2-8]\d|9[0-4])\d{14}(?!\d)")
    hits = []
    for path in _tracked_files():
        if path.suffix.lower() in (".py", ".yaml", ".yml", ".csv", ".md", ".json", ".txt"):
            if nik.search(path.read_text(encoding="utf-8", errors="ignore")):
                hits.append(path.name)
    assert hits == [], hits


def test_inventories_list_no_values_for_identifier_columns():
    import csv

    for path in (REPO / "docs" / "forms").glob("*_columns.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8")):
            if row["suggested_role"] in ("patient_id_source", "identifier_drop", "identifier_pseudonymise", "quasi_identifier"):
                assert row["spellings"] == "", (path.name, row["key"])
