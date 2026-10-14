"""Phase 4 gate: the Explore window, offscreen."""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from app.explore_window import ExploreWindow  # noqa: E402
from app.i18n import Translator  # noqa: E402
from app.theme import load_brand  # noqa: E402
from core.pipeline import prepare  # noqa: E402
from synthetic.generate import write_set  # noqa: E402
from tests.conftest import TEST_KEY, TODAY  # noqa: E402

PSEUDONYMS = {"record_id", "patient_pid", "sitb_pid"}


@pytest.fixture(scope="module")
def prepared_so(tmp_path_factory, profiles):
    folder = tmp_path_factory.mktemp("explore")
    files = write_set(profiles["tbc03_so"], folder, 500, seed=42, formats=("xlsx",), today=TODAY)
    return prepare(files["clean_xlsx"], profiles["tbc03_so"], TEST_KEY, today=TODAY)


@pytest.fixture
def explore_window(qtbot, prepared_so):
    win = ExploreWindow(prepared_so, load_brand(), Translator("en"))
    qtbot.addWidget(win)
    win.show()
    return win


def _items(box):
    return [box.itemData(i) for i in range(box.count())]


def test_every_tab_renders_and_no_pseudonym_is_offered(explore_window):
    win = explore_window
    for i in range(win.tabs.count()):
        win.tabs.setCurrentIndex(i)
    distribution, compare, over_time = win.pages[2], win.pages[4], win.pages[5]
    offered = set(_items(distribution.field)) | set(_items(compare.field)) | set(_items(compare.by))
    assert offered and not offered & PSEUDONYMS
    assert set(_items(over_time.field)) == {f.name for f in win.fields if f.kind == "date"}
    assert win.pages[1].table.rowCount() == len(win.fields)


def test_every_explorable_field_gets_a_chart_and_a_table(explore_window):
    tab = explore_window.pages[2]
    explore_window.tabs.setCurrentIndex(2)
    for i in range(tab.field.count()):
        tab.field.setCurrentIndex(i)
        assert tab.chart.figure.axes or tab.chart.figure.texts, tab.field.itemData(i)
        assert tab.table.rowCount() > 0 or tab.chart.figure.texts, tab.field.itemData(i)


def test_charts_and_tables_save(explore_window, tmp_path):
    tab = explore_window.pages[2]
    explore_window.tabs.setCurrentIndex(2)
    png, csv = tmp_path / "age.png", tmp_path / "age.csv"
    tab.chart.save_png(str(png))
    tab.export.to_csv(csv, index=False)
    assert png.stat().st_size > 5_000 and png.read_bytes()[:4] == b"\x89PNG"
    assert csv.read_text(encoding="utf-8").splitlines()[0].startswith("From")


def test_language_switch_reaches_the_explore_window(explore_window):
    win = explore_window
    english = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    win.tr.set_language("id")
    indonesian = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert all(a != b for a, b in zip(english, indonesian))
    assert win.title.text() == "Jelajahi"


def test_small_groups_are_flagged(explore_window):
    from core import explore

    win = explore_window
    tab = win.pages[2]
    win.tabs.setCurrentIndex(2)
    small = next(f for f in win.fields
                 if f.kind == "categorical" and explore.distribution(win.frame, f, "en", win.settings)["small"].any())
    tab.field.setCurrentIndex(tab.field.findData(small.name))
    assert "fewer than 5" in tab.footnote.text()
    large = next(f for f in win.fields if f.name == "sex")
    tab.field.setCurrentIndex(tab.field.findData(large.name))
    assert "fewer than 5" not in tab.footnote.text()


def test_ten_thousand_rows_open_with_summary_and_first_chart_quickly(qtbot, tmp_path, profiles):
    files = write_set(profiles["tbc03_so"], tmp_path, 10_000, seed=5, formats=("xlsx",), today=TODAY)
    prepared = prepare(files["clean_xlsx"], profiles["tbc03_so"], TEST_KEY, today=TODAY)
    start = time.perf_counter()
    win = ExploreWindow(prepared, load_brand(), Translator("en"))
    qtbot.addWidget(win)
    win.show()
    win.tabs.setCurrentIndex(2)
    win.pages[2].chart.canvas.draw()
    elapsed = time.perf_counter() - start
    assert win.pages[1].table.rowCount() == len(win.fields)
    assert elapsed < 3.0, elapsed


def _ytick_text(chart):
    return [t.get_text().replace("\n", " ") for t in chart.figure.axes[0].get_yticklabels()]


def test_every_answer_is_drawn_in_comparisons_and_blank_stays_out_of_charts(explore_window):
    win = explore_window
    compare, distribution = win.pages[4], win.pages[2]
    win.tabs.setCurrentIndex(4)
    compare.field.setCurrentIndex(compare.field.findData("outcome"))
    compare.by.setCurrentIndex(compare.by.findData("sex"))
    answers = _ytick_text(compare.chart)
    assert "Lost to follow-up" in answers and "Other" not in answers  # nothing is folded away
    legend = [t.get_text() for t in compare.chart.figure.axes[0].get_legend().get_texts()]
    assert legend == ["Male", "Female"]
    win.tabs.setCurrentIndex(2)
    distribution.field.setCurrentIndex(distribution.field.findData("smear_dx"))
    assert "Blank" not in _ytick_text(distribution.chart)
    assert "blank for this field" in distribution.footnote.text()
