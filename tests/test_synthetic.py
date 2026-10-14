"""Phase 2 gate: synthetic files read like real ones, clean uploads cleanly, messy is caught."""

import json
import re

import pytest

from core.client import RedcapClient
from core.dictionary import build_dictionary
from core.grid import read_grid
from core.layout import detect_layout
from core.messages import describe
from core.pipeline import prepare, to_redcap_records
from core.profile import RECORD_ID_FIELD
from core.upload import upload
from mock_redcap.runner import MockRedcap
from synthetic.defects import is_detected, load_defects, undetected
from synthetic.generate import DEFAULT_ROWS, write_set
from tests.conftest import TEST_KEY, TODAY

FORMS = ("tbc03_so", "tbc03_ro")


@pytest.fixture(scope="session")
def sets(tmp_path_factory, profiles):
    out = {}
    for code in FORMS:
        folder = tmp_path_factory.mktemp(code)
        out[code] = write_set(profiles[code], folder, DEFAULT_ROWS[code], seed=42, today=TODAY)
    return out


@pytest.fixture(scope="session")
def prepared(sets, profiles):
    return {(code, kind, fmt): prepare(sets[code][f"{kind}_{fmt}"], profiles[code], TEST_KEY, today=TODAY)
            for code in FORMS for kind in ("clean", "messy") for fmt in ("xls", "xlsx")}


def _cells(path):
    grid = read_grid(path)
    return [[grid.text(r, c) for c in range(grid.ncols)] for r in range(grid.nrows)]


@pytest.mark.parametrize("code", FORMS)
def test_same_seed_gives_identical_files(tmp_path, profiles, sets, code):
    again = write_set(profiles[code], tmp_path, DEFAULT_ROWS[code], seed=42, today=TODAY)
    for name in ("clean_xls", "clean_xlsx", "messy_xls", "messy_xlsx"):
        assert _cells(again[name]) == _cells(sets[code][name]), name
    assert again["defects"].read_text(encoding="utf-8") == sets[code]["defects"].read_text(encoding="utf-8")


def test_different_seed_gives_different_data(tmp_path, profiles, sets):
    other = write_set(profiles["tbc03_so"], tmp_path, 50, seed=7, today=TODAY)
    assert _cells(other["clean_xls"])[17:20] != _cells(sets["tbc03_so"]["clean_xls"])[17:20]


@pytest.mark.parametrize("code", FORMS)
@pytest.mark.parametrize("kind", ["clean", "messy"])
def test_xls_and_xlsx_read_identically(prepared, code, kind):
    a, b = prepared[(code, kind, "xls")], prepared[(code, kind, "xlsx")]
    assert a.frame.equals(b.frame)
    assert [(i.code, i.row, i.field) for i in a.issues] == [(i.code, i.row, i.field) for i in b.issues]


@pytest.mark.parametrize("code", FORMS)
def test_layout_matches_the_real_exports(sets, profiles, code):
    layout = detect_layout(read_grid(sets[code]["clean_xls"]))
    assert layout.number_row == 16 and layout.first_data_row == 17  # Excel rows 17 and 18, as in the inventory
    assert [c.key for c in layout.columns] == [c.key for c in profiles[code].columns]
    assert len(layout.data_rows) == DEFAULT_ROWS[code]


@pytest.mark.parametrize("code", FORMS)
def test_identifiers_are_obviously_fake(sets, profiles, code):
    profile = profiles[code]
    grid = read_grid(sets[code]["clean_xls"])
    layout = detect_layout(grid)
    nik = next(c for c in profile.columns if c.role.value == "patient_id_source")
    name = next(c for c in profile.columns if "nama lengkap" in c.label.casefold())
    col = {c.key: c.sheet_col for c in layout.columns}
    niks = [grid.text(r, col[nik.key]) for r in layout.data_rows]
    names = [grid.text(r, col[name.key]) for r in layout.data_rows]
    assert all(re.fullmatch(r"0000\d{12}", n) for n in niks)
    assert all(n.startswith("NAMA-SINTETIS-") for n in names)


def test_generator_never_reads_a_spreadsheet(tmp_path, profiles, monkeypatch):
    import core.grid

    def refuse(*args, **kwargs):
        raise AssertionError("the generator must not read any spreadsheet")

    monkeypatch.setattr(core.grid, "read_grid", refuse)
    write_set(profiles["tbc03_ro"], tmp_path, 20, seed=1, today=TODAY)


@pytest.mark.parametrize("code", FORMS)
def test_clean_file_has_no_issues_and_uploads_with_nothing_rejected(prepared, profiles, code):
    p = prepared[(code, "clean", "xls")]
    assert p.issues == [], [describe(i, "en") for i in p.issues[:5]]
    records = to_redcap_records(p.frame)
    with MockRedcap(build_dictionary(profiles[code])) as mock:
        client = RedcapClient(mock.url, mock.token)
        result = upload(client, records, record_id_field=RECORD_ID_FIELD, batch_size=100)
        assert result.complete and result.imported == DEFAULT_ROWS[code]
        assert len(client.export_records(fields=[RECORD_ID_FIELD])) == DEFAULT_ROWS[code]


@pytest.mark.parametrize("code", FORMS)
def test_messy_file_fails_and_every_planted_defect_is_reported(sets, prepared, code):
    p = prepared[(code, "messy", "xls")]
    assert not p.ready
    defects = load_defects(sets[code]["defects"])
    assert len(defects) >= 15
    assert undetected(defects, p) == []


EXPECTED_MESSAGES = {
    "missing_record_id": "the Nomor Register Pasien column is empty, so no record ID can be made for this row.",
    "age_out_of_range": "212 is above the allowed maximum of 120.",
    "mixed_date_format": "is not a date in the dd/mm/yyyy format.",
    "unknown_spelling": "\"Laki\" is not a spelling the form profile knows.",
    "required_missing": "this field is required but is empty.",
    "future_date": "01/01/2099 is in the future.",
    "nik_scientific": "the NIK was saved in scientific notation",
    "nik_wrong_length": "the NIK does not have 16 digits.",
    "duplicate_record_id": "has the same patient register number as row(s)",
    "changed_header_label": "is labelled \"Usia (Tahun)\" instead of \"Umur (Tahun)\"",
    "case_count_mismatch": "but 500 data rows were read.",
}


@pytest.mark.parametrize("defect_type", sorted(EXPECTED_MESSAGES))
def test_each_defect_type_has_a_readable_message(sets, prepared, defect_type):
    p = prepared[("tbc03_so", "messy", "xls")]
    defect = next(d for d in load_defects(sets["tbc03_so"]["defects"]) if d["type"] == defect_type)
    assert is_detected(defect, p)
    code = defect["detected_as"]["code"]
    messages = [describe(i, "en") for i in p.issues if i.code == code]
    assert any(EXPECTED_MESSAGES[defect_type] in m for m in messages), messages
    if defect["row"] is not None and defect_type != "duplicate_record_id":
        assert any(m.startswith(f"Row {defect['row']}") for m in messages)


@pytest.mark.parametrize("spelling", ["Tidak Tahu", "Tidak Diketahui", "TDL", "NEG"])
def test_spelling_variants_are_listed_as_changes(sets, prepared, spelling):
    p = prepared[("tbc03_so", "messy", "xls")]
    defect = next(d for d in load_defects(sets["tbc03_so"]["defects"])
                  if d["type"] == "spelling_variant" and d["detected_as"]["spelling"] == spelling)
    assert is_detected(defect, p)


def test_blank_and_summary_rows_are_skipped_and_counted(sets, prepared):
    p = prepared[("tbc03_so", "messy", "xls")]
    assert p.skipped_rows["summary"] == 1
    assert p.skipped_rows["blank"] >= 2  # the planted one and the trailing one
    assert len(p.frame) == DEFAULT_ROWS["tbc03_so"]


def test_defects_json_is_self_describing(sets):
    data = json.loads(sets["tbc03_so"]["defects"].read_text(encoding="utf-8"))
    assert data["form"] == "tbc03_so" and data["seed"] == 42 and data["rows"] == 500
    for d in data["defects"]:
        assert {"id", "type", "row", "column", "detected_as"} <= set(d)
