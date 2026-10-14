"""Phase 1b gate: fixture file -> mock REDCap -> export, with batches, rejections and no leaks."""

import logging

import pytest

from core.client import MASK, ConnectionFailed, InvalidSettings, RedcapClient
from core.dictionary import build_dictionary
from core.pipeline import prepare, to_redcap_records
from core.profile import RECORD_ID_FIELD
from core.upload import plan_upload, upload
from mock_redcap.runner import MockRedcap
from tests.conftest import TEST_KEY, TODAY, raw_identifier_strings


@pytest.fixture
def mock(so):
    with MockRedcap(build_dictionary(so)) as m:
        yield m


def _prepared(so_file, so):
    p = prepare(so_file, so, TEST_KEY, today=TODAY)
    assert p.ready
    records = to_redcap_records(p.frame)
    rows = dict(zip(p.frame[RECORD_ID_FIELD], p.frame["_row"].astype(int)))
    return records, rows


def test_gate_fixture_uploads_and_exports_back(so_file, so, so_rows, mock, caplog):
    caplog.set_level(logging.DEBUG)
    records, rows = _prepared(so_file, so)
    client = RedcapClient(mock.url, mock.token)
    client.connect()

    first = upload(client, records, record_id_field="record_id", batch_size=2, rows_by_record=rows)
    assert first.plan.new == 5 and first.plan.existing == 0
    assert [b.status for b in first.batches] == ["imported", "imported", "imported"]
    assert first.imported == 5 and first.complete

    exported = client.export_records()
    assert len(exported) == 5
    by_id = {r["record_id"]: r for r in exported}
    for rec in records:
        got = by_id[rec["record_id"]]
        assert all(got[k] == v for k, v in rec.items())

    raw = raw_identifier_strings(so_rows)
    assert not raw & {v for r in exported for v in r.values()}

    again = plan_upload(client, records, "record_id")
    assert (again.new, again.existing) == (0, 5)

    log_text = repr(client.log) + caplog.text + repr(client)
    assert mock.token not in log_text
    assert MASK in repr(client.log[0])
    for value in raw:
        assert value not in log_text


def test_rejected_batch_stops_upload_and_keeps_earlier_batches(so_file, so, mock):
    records, rows = _prepared(so_file, so)
    records[2]["age"] = "212"  # bypasses validation on purpose, to exercise REDCap's own check
    client = RedcapClient(mock.url, mock.token)
    result = upload(client, records, record_id_field="record_id", batch_size=2, rows_by_record=rows)
    assert [b.status for b in result.batches] == ["imported", "rejected", "not_sent"]
    assert result.imported == 2 and result.not_sent == 1 and not result.complete
    rejected = result.rejected_batch
    problem = rejected.problems[0]
    assert (problem.record, problem.field, problem.value) == (records[2]["record_id"], "age", "212")
    assert rejected.rows[problem.record] == 20  # spreadsheet row of the third data row
    # A06: the good record in the rejected batch was not saved either.
    assert client.export_records(fields=["record_id"], records=[records[3]["record_id"]]) == []


def test_unreachable_server_is_a_plain_error():
    client = RedcapClient("http://127.0.0.1:9/api/", "A" * 32, timeout=2)
    with pytest.raises(ConnectionFailed) as caught:
        client.connect()
    assert "A" * 32 not in str(caught.value)


@pytest.mark.parametrize("url, token, what", [
    ("http://127.0.0.1/api/", "A" * 31, "token"),
    ("http://127.0.0.1/api/", "A" * 31 + "!", "token"),
    ("http://127.0.0.1/", "A" * 32, "url"),
    ("ftp://127.0.0.1/api/", "A" * 32, "url"),
])
def test_bad_settings_never_echo_the_token(url, token, what):
    with pytest.raises(InvalidSettings) as caught:
        RedcapClient(url, token)
    assert caught.value.what == what
    assert token not in str(caught.value) and token not in repr(caught.value)
