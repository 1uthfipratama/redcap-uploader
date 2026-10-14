import datetime as dt

import pytest

from core.pipeline import prepare
from synthetic.register_writer import RegisterSpec, write_register
from tests.conftest import TEST_KEY, TODAY, so_row


def _prepare(tmp_path, so, rows, name="t.xls"):
    path = write_register(tmp_path / name, so, RegisterSpec(rows=rows))
    return prepare(path, so, TEST_KEY, today=TODAY)


def _codes(prepared):
    return [(i.code, i.row, i.field) for i in prepared.issues]


# ---- normalisation -----------------------------------------------------------

def test_spelling_variants_map_to_one_code(tmp_path, so):
    rows = [so_row(1, c044="Neg"), so_row(2, c044="NEG"), so_row(3, c044="negatif"), so_row(4, c044="1+")]
    p = _prepare(tmp_path, so, rows)
    assert list(p.frame["smear_dx"]) == ["0", "0", "0", "11"]
    changed = {(c.field, c.spelling) for c in p.changes}
    assert ("smear_dx", "NEG") in changed and ("smear_dx", "negatif") in changed
    assert ("smear_dx", "Neg") not in changed  # the canonical label is not a change


def test_unknown_keeps_its_own_code(tmp_path, so):
    rows = [so_row(1, c033="Tidak Diketahui"), so_row(2, c033="Tidak Tahu"), so_row(3, c033="Tidak")]
    p = _prepare(tmp_path, so, rows)
    assert list(p.frame["dm"]) == ["99", "99", "0"]


def test_sex_letters_become_codes(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c014="L"), so_row(2, c014="P")])
    assert list(p.frame["sex"]) == ["1", "2"]


def test_unknown_spelling_is_reported_not_guessed(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c034="Positif HIV"), so_row(2, c034="Positif HIV"), so_row(3)])
    assert [(u.field, u.spelling, u.count, u.rows) for u in p.unmapped] == [("hiv", "Positif HIV", 2, [18, 19])]
    assert ("spelling_unmapped", 18, "hiv") in _codes(p)
    assert p.frame["hiv"].iloc[0] == "Positif HIV"  # left as it was, not recoded
    assert not p.ready


# ---- validation rules ----------------------------------------------------------

def test_clean_file_has_no_errors(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(i) for i in range(1, 4)])
    assert p.errors == []
    assert p.ready


def test_required_field_missing(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c014=None)])
    assert ("required_missing", 18, "sex") in _codes(p)


def test_required_when_condition(tmp_path, so):
    # An outcome without its date is an error; no outcome and no date is fine.
    p = _prepare(tmp_path, so, [so_row(1, c074=None), so_row(2, c074=None, c075=None)])
    assert ("required_when_missing", 18, "outcome_date") in _codes(p)
    assert ("required_when_missing", 19, "outcome_date") not in _codes(p)


def test_value_not_in_choices(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c014="X")])
    assert ("spelling_unmapped", 18, "sex") in _codes(p)


@pytest.mark.parametrize("age, code", [(-1, "below_min"), (212, "above_max")])
def test_age_out_of_range(tmp_path, so, age, code):
    p = _prepare(tmp_path, so, [so_row(1, c013=age)])
    issue = next(i for i in p.issues if i.code == code)
    assert (issue.row, issue.field) == (18, "age")


def test_age_not_a_number(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c013="dua puluh")])
    assert ("not_a_number", 18, "age") in _codes(p)


def test_unreadable_and_mixed_dates(tmp_path, so):
    rows = [so_row(1, c039="2025-03-14"), so_row(2, c039="31/02/2025"), so_row(3, c039="14/03/2025")]
    p = _prepare(tmp_path, so, rows)
    assert ("date_unreadable", 18, "tx_start_date") in _codes(p)
    assert ("date_unreadable", 19, "tx_start_date") in _codes(p)
    assert p.frame["tx_start_date"].iloc[2] == dt.date(2025, 3, 14)


def test_future_date(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c039=dt.date(2027, 1, 1))])
    assert ("date_in_future", 18, "tx_start_date") in _codes(p)


def test_duplicate_record_ids_name_rows_not_values(tmp_path, so):
    rows = [so_row(1), so_row(2, c009=so_row(1)["c009"]), so_row(3)]
    p = _prepare(tmp_path, so, rows)
    dup = [i for i in p.issues if i.code == "duplicate_record_id"]
    assert len(dup) == 1 and dup[0].row == 18 and dup[0].params == {"others": "19"}


def test_same_nik_in_two_episodes_is_not_a_duplicate(tmp_path, so):
    rows = [so_row(1), so_row(2, c006=so_row(1)["c006"])]
    p = _prepare(tmp_path, so, rows)
    assert not [i for i in p.issues if i.code == "duplicate_record_id"]


def test_choice_code_not_allowed_when_validated_directly(so):
    # Normalise reports unknown spellings first; validate still catches any code it is handed
    # that the choice set does not allow (for example from a Generic mapping).
    import pandas as pd

    from core.parse import ROW
    from core.validate import validate

    frame = pd.DataFrame([{ROW: 18, "record_id": "a" * 16, "sex": "7"}], dtype=object)
    issues = validate(frame, so, unmapped=None, today=TODAY)
    assert ("choice_unknown", 18, "sex") in [(i.code, i.row, i.field) for i in issues]


def test_unreadable_required_date_is_reported_once(tmp_path, so):
    p = _prepare(tmp_path, so, [so_row(1, c039="2025-03-14")])
    assert [(i.code, i.field) for i in p.issues if i.row == 18] == [("date_unreadable", "tx_start_date")]
