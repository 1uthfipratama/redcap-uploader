import pytest

from core.grid import guess_delimiter, read_grid
from core.layout import detect_layout
from core.mapping import check_layout, read_metadata, recognise
from synthetic.register_writer import RegisterSpec, write_register
from tests.conftest import so_row


def _layout(path):
    return detect_layout(read_grid(path))


def test_numbered_layout_found_by_official_numbers(so_file, so):
    layout = _layout(so_file)
    assert layout.kind == "numbered"
    assert layout.number_row == 16 and layout.first_data_row == 17
    assert [c.number for c in layout.columns] == list(range(1, 85))
    assert [c.key for c in layout.columns] == [c.key for c in so.columns]
    assert len(layout.data_rows) == 5
    assert len(layout.blank_rows) == 1  # the trailing blank row


def test_xls_and_xlsx_read_identically(so_file, so_file_xlsx):
    a, b = _layout(so_file), _layout(so_file_xlsx)
    assert [(c.key, c.header_path) for c in a.columns] == [(c.key, c.header_path) for c in b.columns]
    assert a.data_rows == b.data_rows
    assert a.metadata == b.metadata


def test_merged_header_is_flattened(so_file):
    layout = _layout(so_file)
    col = layout.column("c018")
    assert col.header_path == ("Alamat Lengkap Faskes", "Kabupaten/Kota")
    assert layout.column("c044").header_text == "Pemeriksaan Contoh Uji > Sebelum Pengobatan > Hasil Mikroskopis"


def test_ro_smear_culture_pairs_become_sub_columns(tmp_path, ro):
    path = write_register(tmp_path / "ro.xls", ro, RegisterSpec(rows=[]))
    layout = _layout(path)
    keys = [c.key for c in layout.columns]
    assert keys == [c.key for c in ro.columns]
    assert len(layout.columns) == 144
    assert len({c.number for c in layout.columns}) == 114
    month4 = [c for c in layout.columns if c.number == 86]
    assert [c.sub_label for c in month4] == ["BTA", "B", "BTA 2", "B 2"]


def test_title_block_metadata_and_recognition(so_file, so, profiles):
    layout = _layout(so_file)
    assert read_metadata(layout, so)["facility"] == "FASYANKES SINTETIS"
    assert recognise(layout, profiles) == "tbc03_so"


def test_unknown_title_falls_back_to_generic(tmp_path, profiles):
    path = tmp_path / "plain.csv"
    path.write_text("id,umur\n1,30\n", encoding="utf-8")
    assert recognise(_layout(path), profiles) == "generic"


def test_shifted_header_is_still_found(tmp_path, so):
    path = write_register(tmp_path / "shift.xls", so, RegisterSpec(rows=[so_row(1)], extra_top_rows=3))
    layout = _layout(path)
    assert layout.number_row == 19
    assert len(layout.data_rows) == 1


def test_summary_and_blank_rows_are_skipped_and_counted(tmp_path, so):
    spec = RegisterSpec(rows=[so_row(i) for i in range(1, 4)], summary_row=True, blank_rows_after=[0])
    layout = _layout(write_register(tmp_path / "s.xls", so, spec))
    assert len(layout.data_rows) == 3
    assert len(layout.summary_rows) == 1
    assert len(layout.blank_rows) == 2


def test_missing_column_blocks_and_changed_label_warns(tmp_path, so):
    spec = RegisterSpec(rows=[so_row(1)], drop_keys={"c084"}, label_overrides={"c013": "Usia"})
    issues = check_layout(_layout(write_register(tmp_path / "d.xls", so, spec)), so)
    codes = {(i.code, i.severity) for i in issues}
    assert ("column_missing", "error") in codes
    assert ("label_changed", "warning") in codes


def test_csv_single_header(tmp_path):
    path = tmp_path / "g.csv"
    path.write_text("Record ID;Umur\n1;30\n\n2;41\n", encoding="utf-8")
    layout = _layout(path)
    assert layout.kind == "single_header"
    assert [c.key for c in layout.columns] == ["record_id", "umur"]
    assert len(layout.data_rows) == 2 and len(layout.blank_rows) == 1


@pytest.mark.parametrize("text, delim", [
    ("Record ID;Umur\n1;30\n\n2;41\n", ";"),
    ("Record ID,Umur,Nama Kota\n1,30,\"Jakarta, Timur\"\n2,41,Bogor\n", ","),
    ("a\tb\tc\n1\t2\t3\n", "\t"),
    ("a|b\n1|2\n", "|"),
    ("berat;tinggi\n55,5;160\n61,2;158\n", ";"),  # decimal commas inside semicolon CSV
    ("only one column\n1\n2\n", ","),
    ("", ","),
])
def test_csv_delimiter_is_guessed_the_same_on_every_python(text, delim):
    assert guess_delimiter(text) == delim
