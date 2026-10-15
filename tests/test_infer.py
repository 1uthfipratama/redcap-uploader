"""Drafting a data dictionary (a profile) from a spreadsheet with one header row."""

import datetime as dt

import pytest
from openpyxl import Workbook

from core.client import RedcapClient
from core.dictionary import build_dictionary
from core.infer import draft_columns, draft_problems, form_code_for, profile_from_draft, unique_name
from core.mapping import check_layout, recognise
from core.pipeline import detect, prepare, to_redcap_records
from core.profile import Role, load_all_profiles, load_profile, save_profile
from core.project_setup import add_missing_fields
from core.upload import upload
from mock_redcap.runner import MockRedcap
from tests.conftest import TEST_KEY

ROWS = 30
TODAY = dt.date(2026, 10, 15)
HEADERS = ["No", "No. Register", "NIK", "Nama Pasien", "No HP", "Umur", "Berat Badan (kg)", "Jenis Kelamin",
           "Tanggal Mulai", "Tanggal Lahir", "Status HIV", "Kecamatan Tujuan", "Catatan", "Kosong"]
SEXES = ["Laki-laki", "perempuan", "L", "Perempuan"]
HIV = ["Positif", "Negatif", "Negatif", "Tidak diketahui"]
PLACES = ["Satu", "Dua", "Dua", "Tiga", "Dua"]


def _row(i: int) -> list:
    return [i, f"REG-{i:04d}", f"9571{i:012d}", f"Pasien Sintetis {chr(64 + i % 26 + 1)}", f"0812{i:08d}",
            20 + i, 50.5 + i, SEXES[i % 4], f"{i % 28 + 1:02d}/03/2025", f"{i % 28 + 1:02d}/01/1980",
            HIV[i % 4], PLACES[i % 5], f"Catatan panjang nomor {i} tentang jalannya pengobatan", None]


def write_sheet(path, rows=ROWS, extra_header=None):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS + ([extra_header] if extra_header else []))
    for i in range(1, rows + 1):
        ws.append(_row(i) + (["x"] if extra_header else []))
    wb.save(path)
    return path


@pytest.fixture
def sheet(tmp_path):
    return write_sheet(tmp_path / "cohort.xlsx")


@pytest.fixture
def draft(sheet):
    detected = detect(sheet, {})
    return draft_columns(detected.grid, detected.layout)


def by_header(draft):
    return {c.header: c for c in draft.columns}


def test_each_column_gets_a_type_and_a_handling(draft):
    c = by_header(draft)
    assert (c["No. Register"].role, c["No. Register"].reason) == (Role.record_id_source, "unique_id")
    assert c["NIK"].role == Role.patient_id_source
    assert (c["Nama Pasien"].role, c["Nama Pasien"].reason) == (Role.identifier_drop, "identifier_header")
    assert (c["No HP"].role, c["No HP"].reason) == (Role.identifier_drop, "phone")
    assert (c["Tanggal Lahir"].role, c["Tanggal Lahir"].reason) == (Role.identifier_drop, "identifier_header")
    assert (c["Catatan"].role, c["Catatan"].reason) == (Role.identifier_drop, "free_text")
    assert (c["No"].role, c["No"].reason) == (Role.ignore, "row_number")
    assert (c["Kosong"].role, c["Kosong"].type) == (Role.ignore, "empty")
    assert [c[h].type for h in ("Umur", "Berat Badan (kg)", "Tanggal Mulai")] == ["integer", "number", "date"]
    assert all(c[h].role == Role.data for h in ("Umur", "Berat Badan (kg)", "Jenis Kelamin", "Status HIV"))
    assert draft.date_format == "%d/%m/%Y"


def test_known_answer_sets_get_their_usual_codes(draft):
    c = by_header(draft)
    sex = {ch.code: ch.label_id for ch in c["Jenis Kelamin"].choices}
    assert sex == {"1": "Laki-laki", "2": "Perempuan"}  # "perempuan" and "L" are spellings of these
    hiv = {ch.code: ch.label_id for ch in c["Status HIV"].choices}
    assert hiv == {"1": "Positif", "0": "Negatif", "99": "Tidak diketahui"}


def test_other_answers_are_coded_by_how_often_they_appear(draft):
    places = by_header(draft)["Kecamatan Tujuan"].choices
    assert [(ch.code, ch.label_id) for ch in places] == [("1", "Dua"), ("2", "Satu"), ("3", "Tiga")]


def test_field_names_are_valid_and_unique(draft):
    names = [c.field for c in draft.columns]
    assert len(names) == len(set(names))
    assert by_header(draft)["Berat Badan (kg)"].field == "berat_badan_kg"
    assert unique_name("1st_visit", set()) == "f_1st_visit"
    assert unique_name("a" * 40, {"a" * 26}) == "a" * 24 + "_2"
    assert form_code_for("Cohort baseline 2025", {"cohort_baseline_2025"}) == "cohort_baseline_2025"[:18] + "_2"


def test_identifier_values_never_reach_the_draft_or_profile(draft, tmp_path):
    profile = profile_from_draft("Cohort", draft.columns, draft.date_format, "cohort")
    saved = save_profile(profile, tmp_path / "cohort.yaml").read_text(encoding="utf-8")
    text = repr(draft) + saved
    for i in range(1, ROWS + 1):
        row = _row(i)
        for value in (row[1], row[2], row[3], row[4], row[12]):  # register, NIK, name, phone, notes
            assert value not in text


def test_the_draft_becomes_a_profile_that_reads_the_file_strictly(draft, sheet):
    assert draft_problems(draft.columns) == []
    profile = profile_from_draft("Cohort", draft.columns, draft.date_format, "cohort")
    assert not profile.is_generic
    prepared = prepare(sheet, profile, TEST_KEY, today=TODAY)
    assert prepared.ready, prepared.errors
    frame = prepared.frame
    assert {"record_id", "patient_pid", "umur", "jenis_kelamin", "tanggal_mulai", "status_hiv"} <= set(frame.columns)
    assert not {"nama_pasien", "no_hp", "catatan", "tanggal_lahir"} & set(frame.columns)
    assert set(frame["jenis_kelamin"]) == {"1", "2"}
    fields = [r["field_name"] for r in build_dictionary(profile)]
    assert fields == profile.redcap_fields()
    assert build_dictionary(profile)[0]["field_label"] == "Record ID (pseudonym of No. Register)"


def test_saved_profiles_load_back_and_recognise_the_next_file(draft, tmp_path):
    profile = profile_from_draft("Cohort", draft.columns, draft.date_format, "cohort")
    path = save_profile(profile, tmp_path / "mine" / "cohort.yaml")
    assert load_profile(path) == profile
    profiles = load_all_profiles(load_all_profiles.__defaults__[0], tmp_path / "mine")
    assert "cohort" in profiles and "tbc03_so" in profiles
    next_month = detect(write_sheet(tmp_path / "next.xlsx", rows=12, extra_header="Kolom Baru"), profiles)
    assert next_month.form_code == "cohort"
    issues = check_layout(next_month.layout, profile)
    assert [(i.code, i.severity) for i in issues] == [("header_extra", "warning")]
    assert recognise(next_month.layout, {"so": profiles["tbc03_so"]}) == "generic"


def test_problems_stop_a_draft_from_becoming_a_profile(draft):
    columns = draft.columns
    by_header(draft)["No. Register"].role = Role.data
    by_header(draft)["Umur"].field = "Umur!"
    by_header(draft)["Berat Badan (kg)"].field = "jenis_kelamin"
    codes = {code for code, _ in draft_problems(columns)}
    assert codes == {"no_record_id", "field_name", "field_twice"}


def test_fields_are_added_to_a_fresh_project_and_the_file_uploads(draft, sheet, tmp_path):
    profile = profile_from_draft("Cohort", draft.columns, draft.date_format, "cohort")
    first = {"field_name": "record_id", "form_name": "form_1", "field_type": "text", "field_label": "Record ID"}
    with MockRedcap([first]) as mock:
        client = RedcapClient(mock.url, mock.token)
        added = add_missing_fields(client, profile, tmp_path)
        assert added.added == profile.redcap_fields()[1:]
        prepared = prepare(sheet, profile, TEST_KEY, target_fields=client.connect().fields, today=TODAY)
        result = upload(client, to_redcap_records(prepared.frame), record_id_field="record_id", batch_size=100)
        assert result.complete and result.imported == ROWS
