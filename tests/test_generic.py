from core.pipeline import detect, prepare
from tests.conftest import TODAY


def _csv(tmp_path, text):
    path = tmp_path / "generic.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_generic_matches_names_and_synonyms_and_drops_lookalike_identifiers(tmp_path, profiles):
    path = _csv(tmp_path, "ID Pasien,Nama,NIK,Umur,Jenis Kelamin,Status HIV\n"
                          "P-001,NAMA-SINTETIS-0001,0000000000000001,34,1,0\n")
    detected = detect(path, profiles)
    assert detected.form_code == "generic"
    p = prepare(detected, profiles["generic"], target_fields=["record_id", "age", "sex", "hiv"],
                overrides={"id_pasien": "record_id"}, today=TODAY)
    by_label = {m.source_label: (m.field, m.method) for m in p.mapping.matches}
    assert by_label["Umur"] == ("age", "synonym")
    assert by_label["Jenis Kelamin"] == ("sex", "synonym")
    assert by_label["Status HIV"] == ("hiv", "synonym")
    assert by_label["ID Pasien"] == ("record_id", "override")
    assert by_label["Nama"][0] is None and by_label["NIK"][0] is None
    assert list(p.frame.columns) == ["_row", "record_id", "age", "sex", "hiv"]
    assert "NAMA-SINTETIS-0001" not in p.frame.to_string()
    assert p.ready


def test_generic_without_record_id_is_an_error(tmp_path, profiles):
    p = prepare(_csv(tmp_path, "Umur\n34\n"), profiles["generic"], target_fields=["record_id", "age"], today=TODAY)
    assert [i.code for i in p.errors] == ["record_id_not_mapped"]


def test_generic_similar_names_carry_a_confidence(tmp_path, profiles):
    p = prepare(_csv(tmp_path, "record_id,tx_start_dt\n1,01/02/2025\n"), profiles["generic"],
                target_fields=["record_id", "tx_start_date"], today=TODAY)
    match = next(m for m in p.mapping.matches if m.source_label == "tx_start_dt")
    assert match.field == "tx_start_date" and 0.75 <= match.confidence < 1
