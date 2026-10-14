"""Phase 1a gate: a TBC.03-shaped file goes from layout to a clean, validated table."""

import datetime as dt
import logging

import pytest

from core import identifiers as ids
from core.messages import describe, suggest_fix
from core.pipeline import detect, prepare, to_redcap_records
from core.profile import PATIENT_ID_FIELD, RECORD_ID_FIELD
from synthetic.register_writer import RegisterSpec, write_register
from tests.conftest import TEST_KEY, TODAY, raw_identifier_strings, so_row


@pytest.mark.parametrize("fixture", ["so_file", "so_file_xlsx"])
def test_gate_clean_file_end_to_end(request, so, so_rows, fixture, caplog):
    caplog.set_level(logging.DEBUG)
    path = request.getfixturevalue(fixture)
    detected = detect(path)
    assert detected.form_code == "tbc03_so"

    p = prepare(detected, so, TEST_KEY, today=TODAY)
    assert p.ready, [describe(i, "en") for i in p.errors]
    assert len(p.frame) == len(so_rows)
    assert p.metadata["facility"] == "FASYANKES SINTETIS"
    assert p.skipped_rows == {"blank": 1, "summary": 0}

    # Generated IDs lead; only profile fields follow; no identifier column survives.
    assert list(p.frame.columns[:3]) == ["_row", RECORD_ID_FIELD, PATIENT_ID_FIELD]
    assert set(p.frame.columns) - {"_row"} <= set(so.redcap_fields())
    for field in ("pt_province", "pt_village"):
        assert field not in p.frame.columns

    # Codes, not labels; dates as dates; ints as ints.
    first = p.frame.iloc[0]
    assert first["sex"] == "1" and first["tb_site"] == "1" and first["outcome"] == "1"
    assert first["tx_start_date"] == dt.date(2025, 3, 2)
    assert first["age"] == 21

    records = to_redcap_records(p.frame)
    assert records[0]["tx_start_date"] == "2025-03-02"
    assert records[0]["age"] == "21"
    assert "_row" not in records[0]

    raw = raw_identifier_strings(so_rows)
    flat = {v for r in records for v in r.values()}
    assert not raw & flat
    for value in raw:
        assert value not in caplog.text


def test_messy_file_is_stopped_with_readable_messages(tmp_path, so):
    rows = [
        so_row(1, c013=212),
        so_row(2, c014=None),
        so_row(3, c009=None),
        so_row(4, c034="Positif HIV"),
        so_row(5, c039="2025-03-14"),
    ]
    path = write_register(tmp_path / "messy.xls", so, RegisterSpec(rows=rows))
    p = prepare(path, so, TEST_KEY, today=TODAY)
    assert not p.ready
    codes = {i.code for i in p.errors}
    assert {"above_max", "required_missing", "record_id_source_blank", "spelling_unmapped", "date_unreadable"} <= codes
    age = next(i for i in p.errors if i.code == "above_max")
    assert describe(age, "en") == "Row 18, age: 212 is above the allowed maximum of 120."
    assert describe(age, "id") == "Baris 18, age: 212 melebihi batas maksimum 120."
    assert suggest_fix(age, "en")


def test_layout_mismatch_blocks_reading(tmp_path, so):
    path = write_register(tmp_path / "old.xls", so, RegisterSpec(rows=[so_row(1)], drop_keys={"c050"}))
    p = prepare(path, so, TEST_KEY, today=TODAY)
    assert p.blocked and p.frame is None
    assert [i.code for i in p.errors] == ["column_missing"]


def test_case_count_mismatch_is_a_warning(tmp_path, so):
    from core.layout import detect_layout
    from core.grid import read_grid
    from core.mapping import check_case_count

    path = write_register(tmp_path / "count.xls", so, RegisterSpec(rows=[so_row(1), so_row(2)]))
    layout = detect_layout(read_grid(path))
    layout.metadata["jumlah kasus"] = "3"
    assert [i.code for i in check_case_count(layout, so)] == ["case_count_mismatch"]


def test_register_profile_needs_a_key(so_file, so):
    with pytest.raises(ids.PseudonymKeyMissing):
        prepare(so_file, so, None)


def test_ro_file_end_to_end(tmp_path, ro):
    row = {
        "c001": 1, "c006": dt.date(2025, 2, 3), "c008": "0000000000000099", "c009": "900000000099",
        "c011": "700000000099", "c013": "NAMA-SINTETIS-0099", "c014": 45, "c015": "P", "c032": "TBC Paru",
        "c041": "Paduan Jangka Pendek", "c083_bta": "NEG", "c083_b": "Neg", "c086_bta_2": "Neg",
        "c108": "Sembuh", "c107": dt.date(2025, 11, 1), "c112": "Tidak",
    }
    path = write_register(tmp_path / "ro.xlsx", ro, RegisterSpec(rows=[row]))
    detected = detect(path)
    assert detected.form_code == "tbc03_ro"
    p = prepare(detected, ro, TEST_KEY, today=TODAY)
    assert p.ready, [describe(i, "en") for i in p.errors]
    first = p.frame.iloc[0]
    assert (first["smear_m1"], first["culture_m1"], first["smear2_m4"]) == ("0", "0", "0")
    assert first["regimen_cat"] == "1" and first["dm_screen"] == "0"
