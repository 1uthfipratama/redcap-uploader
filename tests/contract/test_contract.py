"""One test per assumption in docs/REDCAP_ASSUMPTIONS.md (IDs in each docstring)."""

import pytest

from core.client import ApiError, RedcapClient


def test_connect(client):
    """A02"""
    info = client.connect()
    assert info.title
    assert info.version
    assert info.record_id_field == "record_id"
    assert {"age", "sex", "tx_start_date"} <= set(info.fields)
    assert [e.content for e in client.log] == ["version", "project", "metadata"]


def test_classic_project_is_not_longitudinal(client):
    """A03"""
    assert client.connect().is_longitudinal is False
    assert client._project.is_longitudinal is False


def test_import_counts(client, new_id):
    """A04, A12"""
    ids = [new_id(), new_id()]
    saved = client.import_records([{"record_id": ids[0], "age": "30"}, {"record_id": ids[1], "age": "41"}])
    assert sorted(saved) == sorted(ids)
    sent = client.log[-1].params
    assert sent["content"] == "record" and sent["overwriteBehavior"] == "normal" and sent["dateFormat"] == "YMD"
    assert sent["data"] == "<2 records>"


def test_export_round_trip(client, new_id):
    """A05"""
    rid = new_id()
    client.import_records([{"record_id": rid, "age": "30", "sex": "2", "tx_start_date": "2025-03-14"}])
    rows = client.export_records(fields=["record_id", "age", "sex", "tx_start_date"], records=[rid])
    assert rows == [{"record_id": rid, "age": "30", "sex": "2", "tx_start_date": "2025-03-14"}]


def test_bad_batch_imports_nothing(client, new_id):
    """A06"""
    good, bad = new_id(), new_id()
    with pytest.raises(ApiError):
        client.import_records([{"record_id": good, "age": "30"}, {"record_id": bad, "age": "212"}])
    assert client.export_records(fields=["record_id"], records=[good, bad]) == []


def test_error_names_record_field_value(client, new_id):
    """A07"""
    rid = new_id()
    with pytest.raises(ApiError) as caught:
        client.import_records([{"record_id": rid, "age": "212"}])
    problem = caught.value.problems[0]
    assert (problem.record, problem.field, problem.value) == (rid, "age", "212")
    assert problem.message


def test_date_must_be_ymd(client, new_id):
    """A08"""
    with pytest.raises(ApiError):
        client.import_records([{"record_id": new_id(), "tx_start_date": "14/03/2025"}])


def test_label_instead_of_code_is_rejected(client, new_id):
    """A09"""
    with pytest.raises(ApiError):
        client.import_records([{"record_id": new_id(), "sex": "Laki-laki"}])


def test_blank_does_not_erase(client, new_id):
    """A10"""
    rid = new_id()
    client.import_records([{"record_id": rid, "age": "30"}])
    client.import_records([{"record_id": rid, "age": ""}])
    assert client.export_records(fields=["record_id", "age"], records=[rid])[0]["age"] == "30"


def test_reimport_updates(client, new_id):
    """A11"""
    rid = new_id()
    client.import_records([{"record_id": rid, "age": "30"}])
    client.import_records([{"record_id": rid, "age": "31"}])
    rows = client.export_records(fields=["record_id", "age"], records=[rid])
    assert rows == [{"record_id": rid, "age": "31"}]


def test_unknown_field_is_rejected(client, new_id):
    """A13"""
    with pytest.raises(ApiError):
        client.import_records([{"record_id": new_id(), "no_such_field": "1"}])


def test_out_of_range_is_rejected(client, new_id):
    """A14"""
    with pytest.raises(ApiError):
        client.import_records([{"record_id": new_id(), "age": "-1"}])


def test_bad_token_is_refused(target):
    """A17"""
    wrong = RedcapClient(target["url"], "0" * 32)
    with pytest.raises(ApiError):
        wrong.connect()
