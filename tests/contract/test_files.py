"""A15 and A16: the files a person hands to REDCap's own tools. These need no server."""

from core.dictionary import CSV_HEADERS, build_dictionary
from core.export_csv import check_import_csv, read_dictionary_csv, write_dictionary_csv, write_import_csv
from core.pipeline import prepare
from tests.conftest import TEST_KEY, TODAY


def test_dictionary_csv_columns(tmp_path, so, ro):
    """A15"""
    for profile in (so, ro):
        dictionary = build_dictionary(profile)
        path = write_dictionary_csv(dictionary, tmp_path / f"{profile.identity.form_code}_dictionary.csv")
        assert path.read_text(encoding="utf-8").splitlines()[0].split(",")[0] == "Variable / Field Name"
        rows = read_dictionary_csv(path)
        assert len(CSV_HEADERS) == 18
        assert rows == dictionary
        assert rows[0]["field_name"] == "record_id"
        assert {r["field_name"] for r in rows if r["identifier"] == "y"} == {"patient_pid", "sitb_pid"}


def test_import_csv_matches_dictionary(tmp_path, so, so_file):
    """A16"""
    prepared = prepare(so_file, so, TEST_KEY, today=TODAY)
    dictionary = build_dictionary(so)
    path = write_import_csv(prepared.frame, dictionary, tmp_path / "import.csv")
    assert check_import_csv(path, dictionary) == []
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:2] == ["record_id", "patient_pid"]


def test_import_csv_check_catches_labels_and_dates(tmp_path, so):
    dictionary = build_dictionary(so)
    path = tmp_path / "bad.csv"
    path.write_text("record_id,sex,tx_start_date\nabc,Laki-laki,14/03/2025\n", encoding="utf-8")
    problems = check_import_csv(path, dictionary)
    assert any("sex" in p for p in problems) and any("tx_start_date" in p for p in problems)
