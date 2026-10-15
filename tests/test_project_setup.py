"""Adding a form's missing fields to a REDCap project (A18)."""

import datetime as dt

import pytest

from core.client import RedcapClient
from core.dictionary import RecordIdDiffers, build_dictionary, merge_dictionary
from core.export_csv import read_dictionary_csv
from core.project_setup import ProjectInProduction, add_missing_fields
from mock_redcap.runner import MockRedcap

NOW = dt.datetime(2026, 10, 15, 9, 30)


def _field(name, form="form_1", **extra):
    return {"field_name": name, "form_name": form, "field_type": "text", "field_label": name, **extra}


def test_fresh_project_takes_the_form_dictionary_as_it_is(so):
    wanted = build_dictionary(so)
    merged, added = merge_dictionary([_field("record_id")], wanted)
    assert merged == wanted  # record_id moves onto the form's own instrument
    assert added == [r["field_name"] for r in wanted[1:]]


def test_existing_fields_are_kept_unchanged_and_first(so):
    wanted = build_dictionary(so)
    existing = [_field("record_id"), _field("visit_note", "followup"), dict(wanted[3], field_label="Changed")]
    merged, added = merge_dictionary(existing, wanted)
    assert merged[:3] == existing
    assert [r["field_name"] for r in merged[3:]] == added
    assert wanted[3]["field_name"] not in added and "visit_note" not in added
    assert len(merged) == len(wanted) + 1


def test_nothing_missing_adds_nothing(so):
    wanted = build_dictionary(so)
    merged, added = merge_dictionary(wanted, wanted)
    assert merged == wanted and added == []


def test_a_different_record_id_field_is_refused(so):
    with pytest.raises(RecordIdDiffers) as caught:
        merge_dictionary([_field("study_id")], build_dictionary(so))
    assert caught.value.field_name == "study_id"


def test_missing_fields_are_added_with_a_backup_first(so, tmp_path):
    with MockRedcap([_field("record_id")]) as mock:
        client = RedcapClient(mock.url, mock.token)
        result = add_missing_fields(client, so, tmp_path, now=NOW)
        assert result.added == so.redcap_fields()[1:]
        assert client.connect().fields == so.redcap_fields()
        assert [r["field_name"] for r in read_dictionary_csv(result.backup)] == ["record_id"]
        assert result.backup.name == "demo-project-mock-redcap-dictionary-before-20261015-093000.csv"
        sent = [e for e in client.log if e.content == "metadata" and "data" in e.params]
        assert len(sent) == 1 and sent[0].params["data"] == f"<{len(so.redcap_fields())} fields>"

        again = add_missing_fields(client, so, tmp_path, now=NOW)
        assert again.added == [] and again.backup is None
        assert len([e for e in client.log if e.content == "metadata" and "data" in e.params]) == 1


def test_other_instruments_survive(so, tmp_path):
    existing = [_field("record_id"), _field("visit_note", "followup")]
    with MockRedcap(existing) as mock:
        client = RedcapClient(mock.url, mock.token)
        add_missing_fields(client, so, tmp_path, now=NOW)
        fields = client.connect().fields
        assert fields[:2] == ["record_id", "visit_note"]
        assert set(so.redcap_fields()) <= set(fields)


def test_production_projects_are_not_changed(so, tmp_path):
    with MockRedcap([_field("record_id")]) as mock:
        mock.project.in_production = True
        client = RedcapClient(mock.url, mock.token)
        with pytest.raises(ProjectInProduction):
            add_missing_fields(client, so, tmp_path, now=NOW)
        assert client.connect().fields == ["record_id"]
        assert not any(tmp_path.iterdir())


def test_same_name_different_setup_is_a_conflict(so, ro):
    from core.dictionary import field_conflicts

    assert field_conflicts(build_dictionary(so), build_dictionary(so)) == []
    found = {(c.field, c.aspect) for c in field_conflicts(build_dictionary(so), build_dictionary(ro))}
    assert found == {("regimen_cat", "choices"), ("dm_screen", "choices")}
    text_instead = [dict(r, field_type="text") if r["field_name"] == "sex" else r for r in build_dictionary(so)]
    assert [(c.field, c.aspect) for c in field_conflicts(text_instead, build_dictionary(so))] == [("sex", "type")]


def test_conflicting_fields_stop_the_adding(so, ro, tmp_path):
    from core.project_setup import FieldsConflict

    with MockRedcap(build_dictionary(so)) as mock:
        client = RedcapClient(mock.url, mock.token)
        with pytest.raises(FieldsConflict) as caught:
            add_missing_fields(client, ro, tmp_path, now=NOW)
        assert {c.field for c in caught.value.conflicts} == {"regimen_cat", "dm_screen"}
        assert client.connect().fields == so.redcap_fields()
