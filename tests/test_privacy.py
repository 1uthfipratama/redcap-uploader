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



def test_inventories_do_not_name_the_source_site(so_file, tmp_path):
    """A facility's name, district and province never reach an inventory, committed or newly written."""
    import csv

    from tools.make_inventory import SITE_RE, write_inventory

    for path in (REPO / "docs" / "forms").glob("*_columns.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8")):
            if SITE_RE.search(row["header"]):
                assert row["spellings"] == "", (path.name, row["key"])
    write_inventory(tmp_path / "inv", [so_file])
    written = (tmp_path / "inv_columns.csv").read_text(encoding="utf-8")
    written += (tmp_path / "inv_layout.yaml").read_text(encoding="utf-8")
    for site in ("FASYANKES SINTETIS", "Kota Sintetis", "Provinsi Sintetis"):
        assert site not in written, site
    assert "<value>" in written and "TBC.03 SO" in written


def test_no_secrets_are_tracked():
    """No REDCap-token-shaped strings, private keys, certificates or hard-coded passwords."""
    token = re.compile(r"(?<![0-9A-Fa-f])[0-9A-F]{32}(?![0-9A-Fa-f])")  # REDCap API tokens: 32 hex characters
    private_key = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
    password = re.compile(r"(password|passwd|secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE)
    hits = []
    for path in _tracked_files():
        if path.suffix.lower() in (".pem", ".p12", ".pfx", ".cer", ".key", ".keychain"):
            hits.append(path.name)
            continue
        if path.suffix.lower() in (".py", ".yaml", ".yml", ".csv", ".md", ".json", ".txt", ".toml", ".iss", ".sh", ".spec"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in (token, private_key, password):
                if pattern.search(text):
                    hits.append(f"{path.name}: {pattern.pattern[:30]}")
    assert hits == [], hits


def test_licence_and_notices_are_present():
    licence = (REPO / "LICENSE").read_text(encoding="utf-8")
    assert licence.startswith("MIT License") and "Luthfi Izza Pratama" in licence
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "PySide6" in notices and "LGPL" in notices
    for text in ("GPL-3.0.txt", "LGPL-3.0.txt"):
        assert (REPO / "licenses" / text).exists(), text
