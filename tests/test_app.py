"""Phase 3: the wizard, driven offscreen with pytest-qt, in both languages."""

import ast
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QLabel  # noqa: E402

from app.__main__ import build  # noqa: E402

APP_DIR = Path(__file__).resolve().parent.parent / "app"
TEXT_METHODS = {"setText", "setWindowTitle", "setPlaceholderText", "setToolTip", "addItem", "setItemText",
                "setHorizontalHeaderLabels", "QLabel", "QPushButton", "QRadioButton", "QCheckBox", "setTitle"}


@pytest.fixture
def window(qtbot, request):
    lang = getattr(request, "param", "en")
    _, w = build(lang)
    qtbot.addWidget(w)
    w.show()
    yield w
    w.close()


def idle(qtbot, w, timeout=60000):
    qtbot.waitUntil(lambda: not w.busy and QThreadPool.globalInstance().activeThreadCount() == 0, timeout=timeout)


def next_step(qtbot, w):
    assert w.next.isEnabled(), w.page.message.text()
    w._next()
    idle(qtbot, w)


def to_check_step(qtbot, w, kind):
    next_step(qtbot, w)  # connect to the demo REDCap
    assert w.state.project is not None
    next_step(qtbot, w)  # to Choose file
    w.pages[1]._sample(kind)
    idle(qtbot, w)
    assert w.state.form_code == "tbc03_so"
    next_step(qtbot, w)  # read, de-identify and check
    next_step(qtbot, w)  # past Preview
    assert w.stack.currentIndex() == 3


@pytest.mark.parametrize("window", ["en", "id"], indirect=True)
def test_demo_clean_upload_end_to_end(qtbot, window):
    w = window
    to_check_step(qtbot, w, "clean")
    assert w.state.prepared.ready
    next_step(qtbot, w)  # Upload step plans new vs existing
    assert w.state.plan.new == 500
    next_step(qtbot, w)  # upload
    assert w.stack.currentIndex() == 5
    assert w.state.result.complete and w.state.result.imported == 500
    assert w.pages[5].numbers["imported"].text() == "500"
    assert not w.next.isVisible()


def test_messy_file_is_stopped_at_the_check_step(qtbot, window):
    w = window
    to_check_step(qtbot, w, "messy")
    page = w.pages[3]
    assert not w.next.isEnabled()
    assert page.errors.rowCount() == len(w.state.prepared.errors) > 0
    problems = [page.errors.item(r, 2).text() for r in range(page.errors.rowCount())]
    assert any("212 is above the allowed maximum of 120" in p for p in problems)


def _visible_texts(widget) -> list[str]:
    texts = [w.text() for w in widget.findChildren(QLabel) + widget.findChildren(QAbstractButton)]
    return [t for t in texts if t]


def test_language_switch_changes_every_screen(qtbot, window):
    w = window
    english = [p.title.text() for p in w.pages] + [w.next.text(), w.back.text()]
    w.language.setCurrentIndex(w.language.findData("id"))
    assert w.tr.lang == "id"
    indonesian = [p.title.text() for p in w.pages] + [w.next.text(), w.back.text()]
    assert all(a != b for a, b in zip(english, indonesian)), list(zip(english, indonesian))
    for text in _visible_texts(w):
        assert not text.startswith("ui."), f"missing translation: {text}"


def test_every_screen_has_text_for_every_key(qtbot, window):
    for lang in ("en", "id"):
        window.tr.set_language(lang)
        for text in _visible_texts(window):
            assert not text.startswith(("ui.", "issue.", "fix.")), text


def test_bad_token_shows_a_plain_message_without_the_token(qtbot, window):
    w = window
    page = w.pages[0]
    page.real.setChecked(True)
    page.url.setText("https://redcap.example.org/api/")
    wrong_length_token = "ABCDEF0123456789ABCDEF012345678"  # 31 characters: invalid on purpose
    page.token.setText(wrong_length_token)
    next_step(qtbot, w)
    assert page.message.isVisible()
    assert page.message.text() == w.tr("ui.error.token")
    assert wrong_length_token not in page.message.text()


def test_unreachable_server_shows_a_plain_message(qtbot, window):
    w = window
    page = w.pages[0]
    page.real.setChecked(True)
    page.url.setText("http://127.0.0.1:9/api/")
    page.token.setText("A" * 32)
    next_step(qtbot, w)
    assert page.message.text() == w.tr("ui.error.connection")
    assert w.stack.currentIndex() == 0


def test_no_hard_coded_text_in_app():
    """Visible text must come from i18n/: no string literal with letters goes to a text setter."""
    problems = []
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name not in TEXT_METHODS:
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and any(ch.isalpha() for ch in arg.value):
                    problems.append(f"{path.name}:{node.lineno} {arg.value!r}")
    assert problems == []


def test_generic_sheet_maps_by_name_and_reaches_the_check_step(qtbot, window, tmp_path):
    w = window
    sheet = tmp_path / "other_study.csv"
    sheet.write_text("Record ID,Nama,Umur,Jenis Kelamin\nG-001,NAMA-SINTETIS-0001,34,1\nG-002,NAMA-SINTETIS-0002,51,2\n",
                     encoding="utf-8")
    next_step(qtbot, w)
    next_step(qtbot, w)
    w.pages[1].load(sheet)
    idle(qtbot, w)
    assert w.state.form_code == "generic"
    next_step(qtbot, w)
    matches = {m.source_label: m.field for m in w.state.prepared.mapping.matches}
    assert matches["Umur"] == "age" and matches["Jenis Kelamin"] == "sex" and matches["Nama"] is None
    assert matches["Record ID"] == "record_id"
    assert "NAMA-SINTETIS-0001" not in w.state.prepared.frame.to_string()
    next_step(qtbot, w)
    assert w.stack.currentIndex() == 3 and w.state.prepared.ready


def test_explore_opens_from_the_check_step_only_when_ready(qtbot, window):
    w = window
    to_check_step(qtbot, w, "clean")
    page = w.pages[3]
    assert page.explore.isVisible()
    page.explore.click()
    assert w.explore_window is not None and w.explore_window.isVisible()
    assert w.explore_window.pages[0].numbers["rows"].text() == "500"
