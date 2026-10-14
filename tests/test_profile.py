import pytest
from pydantic import ValidationError

from core.profile import Profile, field_name_problem


def _minimal(columns, **extra):
    return {
        "identity": {"form_code": "t", "name": "T"},
        "instrument": "t",
        "columns": columns,
        **extra,
    }


ID_COL = {"key": "c001", "number": 1, "label": "No", "role": "record_id_source"}


def test_shipped_profiles_load(profiles):
    assert set(profiles) == {"tbc03_so", "tbc03_ro", "generic"}
    assert len(profiles["tbc03_so"].columns) == 84
    assert len(profiles["tbc03_ro"].columns) == 144


def test_record_id_and_patient_pid_come_first(so):
    assert so.redcap_fields()[:2] == ["record_id", "patient_pid"]


def test_identifier_columns_are_never_uploaded(so):
    uploaded = {c.key for c in so.uploaded_columns()}
    for key in ("c006", "c009", "c012", "c027", "c084", "c023"):
        assert key not in uploaded


@pytest.mark.parametrize("name, ok", [
    ("age", True), ("tx_start_date", True), ("Age", False), ("1age", False),
    ("age-years", False), ("a" * 27, False), ("a" * 26, True),
])
def test_field_name_rules(name, ok):
    assert (field_name_problem(name) is None) == ok


def test_bad_field_name_rejected():
    with pytest.raises(ValidationError, match="lowercase"):
        Profile.model_validate(_minimal([ID_COL, {"key": "c002", "label": "Umur", "role": "data", "field": "Umur"}]))


def test_duplicate_field_rejected():
    cols = [ID_COL, {"key": "c002", "label": "a", "role": "data", "field": "age"},
            {"key": "c003", "label": "b", "role": "data", "field": "age"}]
    with pytest.raises(ValidationError, match="used twice"):
        Profile.model_validate(_minimal(cols))


def test_reserved_field_rejected():
    with pytest.raises(ValidationError, match="reserved"):
        Profile.model_validate(_minimal([ID_COL, {"key": "c002", "label": "a", "role": "data", "field": "record_id"}]))


def test_unknown_choice_set_rejected():
    col = {"key": "c002", "label": "a", "role": "data", "field": "sex", "type": "choice", "choice_set": "nope"}
    with pytest.raises(ValidationError, match="unknown choice set"):
        Profile.model_validate(_minimal([ID_COL, col]))


def test_register_profile_needs_one_record_id_source():
    with pytest.raises(ValidationError, match="record_id_source"):
        Profile.model_validate(_minimal([{"key": "c002", "label": "a", "role": "data", "field": "age"}]))
