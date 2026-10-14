import logging

import pytest

from core import identifiers as ids
from core.grid import read_grid
from core.layout import detect_layout
from core.parse import parse_rows
from core.profile import PATIENT_ID_FIELD, RECORD_ID_FIELD
from tests.conftest import OTHER_TEST_KEY, TEST_KEY, fake_nik, raw_identifier_strings


@pytest.mark.parametrize("value, expected, status", [
    ("0000123456789012", "0000123456789012", "ok"),
    ("'0000123456789012", "0000123456789012", "ok"),  # Excel text prefix
    (" 0000 1234 5678 9012 ", "0000123456789012", "ok"),
    (3171012345678901.0, "3171012345678901", "ok"),  # exact as a float (below 2**53)
    (9471012345678901.0, None, "precision_lost"),  # above 2**53: digits may be gone
    ("3.17101E+15", None, "scientific"),
    ("317101234567890", None, "wrong_length"),
    ("31710123456789AB", None, "not_digits"),
    ("0000000000000000", None, "all_zero"),
    (None, None, "blank"),
    ("   ", None, "blank"),
])
def test_clean_nik(value, expected, status):
    assert ids.clean_nik(value) == (expected, status)


def test_pseudonym_is_stable_and_key_dependent():
    a = ids.pseudonym(TEST_KEY, "patient", "0000123456789012")
    assert a == ids.pseudonym(TEST_KEY, "patient", "0000123456789012")
    assert a != ids.pseudonym(OTHER_TEST_KEY, "patient", "0000123456789012")
    assert a != ids.pseudonym(TEST_KEY, "record", "0000123456789012")
    assert len(a) == ids.PSEUDONYM_HEX_CHARS


def test_record_id_differs_between_forms():
    assert ids.pseudonym(TEST_KEY, "record", "tbc03_so", "7001") != ids.pseudonym(TEST_KEY, "record", "tbc03_ro", "7001")


def _parsed(path, profile):
    grid = read_grid(path)
    layout = detect_layout(grid)
    return parse_rows(grid, layout, profile).frame


def test_identifiers_dropped_or_pseudonymised(so_file, so, so_rows):
    frame, report, issues = ids.apply_identifiers(_parsed(so_file, so), so, TEST_KEY)
    for key in ("c002", "c003", "c005", "c008", "c010", "c012", "c027", "c084", "c006", "c009"):
        assert key not in frame.columns
    for key in ("c023", "c024", "c025", "c026"):  # quasi-identifiers dropped by default
        assert key not in frame.columns
    assert frame[RECORD_ID_FIELD].notna().all()
    assert frame[PATIENT_ID_FIELD].notna().all()
    assert report.pseudonymised[RECORD_ID_FIELD] == len(so_rows)
    assert not [i for i in issues if i.is_error]
    raw = raw_identifier_strings(so_rows)
    flat = {str(v) for v in frame.to_numpy().ravel() if v is not None}
    assert not raw & flat


def test_same_patient_two_episodes_links_but_keeps_two_records(tmp_path, so):
    from synthetic.register_writer import RegisterSpec, write_register
    from tests.conftest import so_row

    rows = [so_row(1), so_row(2, c006=fake_nik(1))]  # same NIK, different register numbers
    path = write_register(tmp_path / "episodes.xls", so, RegisterSpec(rows=rows))
    frame, _, _ = ids.apply_identifiers(_parsed(path, so), so, TEST_KEY)
    assert frame[PATIENT_ID_FIELD].iloc[0] == frame[PATIENT_ID_FIELD].iloc[1]
    assert frame[RECORD_ID_FIELD].iloc[0] != frame[RECORD_ID_FIELD].iloc[1]


def test_bad_nik_gets_no_pseudonym_and_is_counted(tmp_path, so):
    from synthetic.register_writer import RegisterSpec, write_register
    from tests.conftest import so_row

    rows = [so_row(1, c006=None), so_row(2, c006="12345"), so_row(3)]
    path = write_register(tmp_path / "nik.xls", so, RegisterSpec(rows=rows))
    frame, report, issues = ids.apply_identifiers(_parsed(path, so), so, TEST_KEY)
    assert frame[PATIENT_ID_FIELD].isna().sum() == 2
    assert report.nik_status == {"blank": 1, "wrong_length": 1, "ok": 1}
    assert {i.code for i in issues} == {"nik_blank", "nik_wrong_length"}
    assert all(i.severity == "warning" for i in issues)


def test_blank_register_number_is_an_error(tmp_path, so):
    from synthetic.register_writer import RegisterSpec, write_register
    from tests.conftest import so_row

    path = write_register(tmp_path / "rid.xls", so, RegisterSpec(rows=[so_row(1, c009=None)]))
    _, report, issues = ids.apply_identifiers(_parsed(path, so), so, TEST_KEY)
    assert report.record_id_missing_rows == [18]
    assert [i.code for i in issues if i.is_error] == ["record_id_source_blank"]


def test_raw_identifiers_never_reach_the_log(so_file, so, so_rows, caplog):
    caplog.set_level(logging.DEBUG)
    ids.apply_identifiers(_parsed(so_file, so), so, TEST_KEY)
    for value in raw_identifier_strings(so_rows):
        assert value not in caplog.text


def test_load_key_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv(ids.KEY_ENV, raising=False)
    monkeypatch.delenv(ids.KEY_FILE_ENV, raising=False)
    with pytest.raises(ids.PseudonymKeyMissing):
        ids.load_key()


def test_load_key_refuses_short_key(monkeypatch):
    monkeypatch.setenv(ids.KEY_ENV, "ab" * 8)
    with pytest.raises(ids.PseudonymKeyInvalid):
        ids.load_key()


def test_load_key_refuses_key_file_inside_repo(monkeypatch):
    inside = ids.REPO_ROOT / "config" / "should-not-exist.key"
    monkeypatch.delenv(ids.KEY_ENV, raising=False)
    monkeypatch.setenv(ids.KEY_FILE_ENV, str(inside))
    with pytest.raises(ids.PseudonymKeyInvalid):
        ids.load_key()


def test_load_key_reads_file_outside_repo(monkeypatch, tmp_path):
    key_file = tmp_path / "project.key"
    key_file.write_text("ab" * 32, encoding="utf-8")
    monkeypatch.delenv(ids.KEY_ENV, raising=False)
    monkeypatch.setenv(ids.KEY_FILE_ENV, str(key_file))
    assert ids.load_key() == bytes.fromhex("ab" * 32)


def test_apply_refuses_short_key(so_file, so):
    with pytest.raises(ids.PseudonymKeyInvalid):
        ids.apply_identifiers(_parsed(so_file, so), so, b"short")
