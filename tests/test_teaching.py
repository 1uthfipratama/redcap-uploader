"""Phase 5 gate: every screen explains itself, in both languages, and leaks nothing."""

import logging
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QLabel  # noqa: E402

from app.__main__ import build  # noqa: E402
from app.teaching import request_line  # noqa: E402
from core.client import PROBLEM_PATTERNS, RequestLog  # noqa: E402
from core.messages import strings  # noqa: E402
from tests.test_app import idle, next_step  # noqa: E402

# Synthetic identifiers look like these; a real NIK never starts with 0000.
IDENTIFIER_RE = re.compile(r"NAMA-SINTETIS|ALAMAT-SINTETIS|RM-SINTETIS|CATATAN-SINTETIS|LAB-SINTETIS|"
                           r"REG-SINTETIS|(?<!\d)0000\d{12}(?!\d)")


def _all_text(widget) -> list[str]:
    """Every label, button and table cell under a widget, including tables backed by models."""
    texts = [w.text() for w in widget.findChildren(QLabel) + widget.findChildren(QAbstractButton) if w.text()]
    for view in widget.findChildren(QAbstractItemView):
        model = view.model()
        if model is None:
            continue
        for r in range(model.rowCount()):
            for c in range(model.columnCount()):
                value = model.data(model.index(r, c))
                if value:
                    texts.append(str(value))
    return texts


@pytest.fixture
def run(qtbot, request):
    lang = getattr(request, "param", "en")
    _, w = build(lang)
    qtbot.addWidget(w)
    w.show()
    yield w
    w.close()


def _through_upload(qtbot, w):
    next_step(qtbot, w)  # connect
    next_step(qtbot, w)
    w.pages[1]._sample("clean")
    idle(qtbot, w)
    for _ in range(4):  # read, preview, check, upload
        next_step(qtbot, w)
    assert w.stack.currentIndex() == 5


@pytest.mark.parametrize("run", ["en", "id"], indirect=True)
def test_every_step_has_an_explanation(qtbot, run):
    w = run
    _through_upload(qtbot, w)
    for page in w.pages:
        page.update_teaching()
        paragraphs, _ = page.teaching()
        assert paragraphs and all(paragraphs), type(page).__name__
        assert page.teach.toggle.text() == w.tr("ui.teach.toggle")


def test_steps_that_talk_to_redcap_show_the_actual_requests(qtbot, run):
    w = run
    _through_upload(qtbot, w)
    connect_requests = w.pages[0].teaching()[1]
    assert [e.content for e in connect_requests][:3] == ["version", "project", "metadata"]
    result_requests = w.pages[5].teaching()[1]
    assert result_requests and all(e.content == "record" and "data" in e.params for e in result_requests)
    lines = [request_line(e) for e in result_requests]
    assert all("content=record" in line and "overwriteBehavior=normal" in line for line in lines)
    assert all("data=<100 records>" in line and "token=********" in line for line in lines)
    w.pages[5].teach.toggle.setChecked(True)
    shown = " ".join(w.pages[5].teach.texts())
    assert "Sent 100 records to be saved (overwrite: normal)" in shown


def test_no_token_or_identifier_on_any_screen_or_in_the_log(qtbot, run, caplog):
    caplog.set_level(logging.DEBUG)
    w = run
    _through_upload(qtbot, w)
    token = w.state.mock.token
    w.pages[2].rows_box.button.setChecked(True)  # the cleaned rows preview
    w.pages[2].on_enter()
    w.open_explore()
    texts = []
    for page in w.pages:
        page.teach.toggle.setChecked(True)
        page.update_teaching()
        texts += page.teach.texts()
    texts += _all_text(w)
    explore = w.explore_window
    for i in range(explore.tabs.count()):
        explore.tabs.setCurrentIndex(i)
        explore.pages[i].teach.toggle.setChecked(True)
    texts += _all_text(explore)
    everything = "\n".join(texts) + "\n" + caplog.text + "\n" + repr(w.state.client.log)
    assert token not in everything
    assert not IDENTIFIER_RE.search(everything), IDENTIFIER_RE.search(everything).group(0)


@pytest.mark.parametrize("run", ["en", "id"], indirect=True)
def test_every_explore_tab_has_an_explanation(qtbot, run):
    w = run
    _through_upload(qtbot, w)
    w.open_explore()
    for tab in w.explore_window.pages:
        assert tab.teach_keys
        assert all(w.tr(k) != k for k in tab.teach_keys)
        assert len(tab.teach.texts()) >= 1


def test_request_lines_never_show_record_data_or_the_token():
    entry = RequestLog("record", {"content": "record", "data": "<3 records>", "token": "********",
                                  "fields[0]": "record_id", "overwriteBehavior": "normal"})
    line = request_line(entry)
    assert "data=<3 records>" in line and "token=********" in line and "fields=record_id" in line


def test_every_kind_of_redcap_problem_has_a_plain_fix_in_both_languages():
    kinds = [k for k, _ in PROBLEM_PATTERNS] + ["other"]
    for lang in ("en", "id"):
        for kind in kinds:
            assert f"ui.fix.redcap_{kind}" in strings(lang), (lang, kind)
