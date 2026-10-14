"""The Explore screen: descriptive summaries and charts of the cleaned data.

Opens from the Check step once there are no errors, and from Result. It reads the
cleaned table in memory and sends nothing anywhere. Every number comes from
core/explore; this module only lays it out. Each chart has its table beside it,
and both can be saved (PNG, CSV).
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.charts import Chart
from app.i18n import Translator
from app.theme import Brand
from app.widgets import Panel, fill_table, label, new_table
from core import explore
from core.pipeline import Prepared

FOLD_AFTER = 4  # categorical shares: four named answers, the rest folded into "other"
MISSING_CHART_FIELDS = 15


class Tab(QWidget):
    """Controls, chart, table, and the two save buttons."""

    def __init__(self, win: "ExploreWindow", with_chart: bool = True):
        super().__init__()
        self.win, self.tr = win, win.tr
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 12, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("Canvas")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)
        self.panel = Panel()
        inner_layout.addWidget(self.panel)
        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.controls = QHBoxLayout()
        self.panel.body.addLayout(self.controls)
        self.chart = Chart(win.brand) if with_chart else None
        if self.chart:
            self.panel.body.addWidget(self.chart.canvas)
        self.table = new_table()
        self.table.setMinimumHeight(200)
        self.panel.body.addWidget(self.table)
        self.footnote = label("Muted")
        self.panel.body.addWidget(self.footnote)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_png = QPushButton()
        self.save_csv = QPushButton()
        self.save_png.clicked.connect(self._save_png)
        self.save_csv.clicked.connect(self._save_csv)
        if self.chart:
            buttons.addWidget(self.save_png)
        buttons.addWidget(self.save_csv)
        self.panel.body.addLayout(buttons)
        self.table_frame = pd.DataFrame()

    def picker(self, caption_key: str) -> tuple[QComboBox, QWidget]:
        box = QComboBox()
        box.setMinimumWidth(240)
        caption = label("Muted", wrap=False)
        caption.setProperty("key", caption_key)
        self.controls.addWidget(caption)
        self.controls.addWidget(box)
        box.currentIndexChanged.connect(lambda _: self.refresh())
        return box, caption

    def show_table(self, frame: pd.DataFrame, stretch=()) -> None:
        self.table_frame = frame
        fill_table(self.table, [str(c) for c in frame.columns],
                   [["" if pd.isna(v) else v for v in row] for row in frame.itertuples(index=False)], stretch)

    def retranslate(self) -> None:
        self.save_png.setText(self.tr("ui.explore.save_png"))
        self.save_csv.setText(self.tr("ui.explore.save_csv"))
        for i in range(self.controls.count()):
            w = self.controls.itemAt(i).widget()
            if w is not None and w.property("key"):
                w.setText(self.tr(w.property("key")))
        self.refresh()

    def refresh(self) -> None:
        """Recompute and redraw for the current pickers and language."""

    def _save_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.explore.save_png"), "chart.png", "PNG (*.png)")
        if path:
            self.chart.save_png(path)

    def _save_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.explore.save_csv"), "table.csv", "CSV (*.csv)")
        if path:
            self.table_frame.to_csv(path, index=False, encoding="utf-8-sig")


def fill_fields(box: QComboBox, fields: list[explore.FieldInfo], lang: str, preferred: list[str]) -> None:
    current = box.currentData()
    box.blockSignals(True)
    box.clear()
    for f in fields:
        box.addItem(f"{f.label(lang)} · {f.name}", f.name)
    target = current or next((p for p in preferred if box.findData(p) >= 0), None)
    box.setCurrentIndex(max(box.findData(target), 0) if target else 0)
    box.blockSignals(False)


def small_note(tr, frame: pd.DataFrame, settings: dict) -> str:
    return tr("ui.explore.small_note", n=settings["small_group"]) if "small" in frame and frame["small"].any() else ""


# ---- tabs -------------------------------------------------------------------------

class OverviewTab(Tab):
    def __init__(self, win):
        super().__init__(win, with_chart=False)
        self.table.hide()
        self.save_csv.hide()
        grid = QGridLayout()
        grid.setHorizontalSpacing(48)
        grid.setVerticalSpacing(4)
        self.keys = ["rows", "explorable", "duplicate_rows", "numeric", "categorical", "dates"]
        self.numbers = {k: label("BigNumber", wrap=False) for k in self.keys}
        self.captions = {k: label("Muted") for k in self.keys}
        for i, k in enumerate(self.keys):
            grid.addWidget(self.numbers[k], (i // 3) * 2, i % 3)
            grid.addWidget(self.captions[k], (i // 3) * 2 + 1, i % 3)
        grid.setColumnStretch(3, 1)
        grid.setRowMinimumHeight(1, 40)
        self.panel.body.insertLayout(0, grid)

    def refresh(self) -> None:
        o = explore.overview(self.win.frame, self.win.fields)
        for k in self.keys:
            self.numbers[k].setText(f"{o[k]:,}")
            self.captions[k].setText(self.tr(f"ui.explore.ov_{k}"))
        self.footnote.setText(self.tr("ui.explore.ov_note"))


class VariablesTab(Tab):
    COLUMNS = ["label", "field", "type", "count", "blank", "blank_pct", "unknown", "distinct",
               "mean", "sd", "min", "q1", "median", "q3", "max", "top"]

    def __init__(self, win):
        super().__init__(win, with_chart=False)
        self.table.setMinimumHeight(460)

    def refresh(self) -> None:
        lang = self.tr.lang
        table = explore.variable_summary(self.win.frame, self.win.fields, lang, self.win.settings)
        table["type"] = [self.tr(f"ui.explore.kind_{k}") for k in table["type"]]
        table = table[self.COLUMNS].rename(columns={c: self.tr(f"ui.explore.col_{c}") for c in self.COLUMNS})
        self.show_table(table, stretch=(len(self.COLUMNS) - 1,))
        self.footnote.setText(self.tr("ui.explore.var_note"))


class DistributionTab(Tab):
    def __init__(self, win):
        super().__init__(win)
        self.field, _ = self.picker("ui.explore.field")
        self.controls.addStretch(1)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        fill_fields(self.field, win.fields, tr.lang, win.profile.explore_defaults)
        f = win.field(self.field.currentData())
        if f is None:
            return
        data = explore.distribution(win.sample, f, tr.lang, win.settings)
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            return
        if f.kind == "numeric":
            self.chart.histogram(data["bin_start"], data["bin_end"], data["n"], f.label(tr.lang), tr("ui.explore.records"))
            table = data[["bin_start", "bin_end", "n", "percent"]].rename(columns={
                "bin_start": tr("ui.explore.col_from"), "bin_end": tr("ui.explore.col_to"),
                "n": tr("ui.explore.col_n"), "percent": tr("ui.explore.col_percent")})
        elif f.kind == "date":
            self.chart.columns(list(data["month"]), list(data["n"]), tr("ui.explore.records"))
            table = data[["month", "n", "percent"]].rename(columns={
                "month": tr("ui.explore.col_month"), "n": tr("ui.explore.col_n"), "percent": tr("ui.explore.col_percent")})
        else:
            labels = [tr("ui.explore.blank") if b else lab for lab, b in zip(data["label"], data["blank"])]
            context = [bool(u or b) for u, b in zip(data["unknown"], data["blank"])]
            text = [f"{n:,} ({p}%)" for n, p in zip(data["n"], data["percent"])]
            self.chart.horizontal_bars(labels, list(data["n"]), text, context, tr("ui.explore.records"))
            table = pd.DataFrame({tr("ui.explore.col_answer"): labels, tr("ui.explore.col_code"): data["code"],
                                  tr("ui.explore.col_n"): data["n"], tr("ui.explore.col_percent"): data["percent"]})
        self.show_table(table)
        notes = [small_note(tr, data, win.settings)]
        if win.sampled:
            notes.append(tr("ui.explore.sampled", n=len(win.sample)))
        self.footnote.setText(" ".join(n for n in notes if n))


class MissingTab(Tab):
    def refresh(self) -> None:
        tr, win = self.tr, self.win
        data = explore.missingness(win.frame, win.fields)
        shown = data[(data["blank"] + data["unknown"]) > 0].head(MISSING_CHART_FIELDS)
        if shown.empty:
            self.chart.message(tr("ui.explore.nothing_missing"))
        else:
            labels = [win.field(n).label(tr.lang) for n in shown["field"]][::-1]
            self.chart.stacked_shares(labels, [(tr("ui.explore.blank"), list(shown["blank_pct"])[::-1], False),
                                               (tr("ui.explore.unknown"), list(shown["unknown_pct"])[::-1], False)],
                                      tr("ui.explore.percent_of_records"))
        table = data.rename(columns={c: tr(f"ui.explore.col_{c}") for c in data.columns})
        self.show_table(table)
        self.footnote.setText(tr("ui.explore.missing_note", shown=len(shown)))


class CompareTab(Tab):
    def __init__(self, win):
        super().__init__(win)
        self.field, _ = self.picker("ui.explore.field")
        self.by, _ = self.picker("ui.explore.by")
        self.controls.addStretch(1)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        fill_fields(self.field, [f for f in win.fields if f.kind in ("numeric", "categorical")], tr.lang,
                    ["age"] + win.profile.explore_defaults)
        fill_fields(self.by, [f for f in win.fields if f.kind == "categorical"], tr.lang, ["sex", "tb_site", "hiv"])
        f, by = win.field(self.field.currentData()), win.field(self.by.currentData())
        if f is None or by is None:
            return
        data = explore.group_comparison(win.sample, f, by, tr.lang, win.settings)
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            return
        groups = list(data["group"])
        if f.kind == "numeric":
            self.chart.ranges(groups, list(data["q1"]), list(data["median"]), list(data["q3"]), f.label(tr.lang))
            cols = ["group", "n", "mean", "sd", "q1", "median", "q3"]
            table = data[cols].rename(columns={c: tr(f"ui.explore.col_{c}") for c in cols})
        else:
            self.chart.stacked_shares(groups, self._shares(data, f), tr("ui.explore.percent_of_group"))
            table = data.drop(columns=["small"]).rename(columns={"group": tr("ui.explore.col_group"),
                                                                 "n": tr("ui.explore.col_n")})
        self.show_table(table)
        self.footnote.setText(small_note(tr, data, win.settings))

    def _shares(self, data: pd.DataFrame, f) -> list[tuple[str, list[float], bool]]:
        """Up to four named answers in the form's order; the rest folded into "other"; unknown/blank in grey."""
        tr = self.tr
        names = [c[:-2] for c in data.columns if c.endswith(" %")]
        unknown_labels = {f.choice_label(code, tr.lang) for code in f.unknown_codes} | {"—"}
        named = [n for n in names if n not in unknown_labels]
        series = [(n, list(data[f"{n} %"]), False) for n in named[:FOLD_AFTER]]
        rest = named[FOLD_AFTER:]
        if rest:
            series.append((tr("ui.explore.other"), list(data[[f"{n} %" for n in rest]].sum(axis=1)), True))
        for n in names:
            if n in unknown_labels:
                series.append((tr("ui.explore.blank") if n == "—" else n, list(data[f"{n} %"]), True))
        return series


class OverTimeTab(Tab):
    def __init__(self, win):
        super().__init__(win)
        self.field, _ = self.picker("ui.explore.date_field")
        self.controls.addStretch(1)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        dates = [f for f in win.fields if f.kind == "date"]
        fill_fields(self.field, dates, tr.lang, ["tx_start_date"])
        f = win.field(self.field.currentData())
        if f is None:
            self.chart.message(tr("ui.explore.no_dates"))
            return
        data = explore.over_time(win.frame, f, win.settings)
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            return
        self.chart.columns(list(data["month"]), list(data["n"]), tr("ui.explore.records"))
        self.show_table(data[["month", "n", "percent"]].rename(columns={
            "month": tr("ui.explore.col_month"), "n": tr("ui.explore.col_n"), "percent": tr("ui.explore.col_percent")}))
        self.footnote.setText(small_note(tr, data, win.settings))


TABS = [("overview", OverviewTab), ("variables", VariablesTab), ("distribution", DistributionTab),
        ("missing", MissingTab), ("compare", CompareTab), ("over_time", OverTimeTab)]


class ExploreWindow(QMainWindow):
    def __init__(self, prepared: Prepared, brand: Brand, tr: Translator):
        super().__init__()
        self.brand, self.tr = brand, tr
        self.profile = prepared.profile
        self.frame = prepared.frame
        self.settings = explore.load_settings()
        self.fields = explore.explorable_fields(self.frame, self.profile, self.settings)
        self._by_name = {f.name: f for f in self.fields}
        self.sample, self.sampled = explore.maybe_sample(self.frame, self.settings)
        self.resize(1180, 820)

        root = QWidget()
        root.setObjectName("Canvas")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 24, 32, 24)
        self.title = label("PageTitle")
        self.note = label("PageLead")
        self.tabs = QTabWidget()
        self.pages = [cls(self) for _, cls in TABS]
        for page in self.pages:
            self.tabs.addTab(page, "")
        self.tabs.currentChanged.connect(lambda i: self.pages[i].refresh())
        layout.addWidget(self.title)
        layout.addWidget(self.note)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        tr.changed.connect(lambda _: self.retranslate())
        self.retranslate()

    def field(self, name: str | None) -> explore.FieldInfo | None:
        return self._by_name.get(name) if name else None

    def retranslate(self) -> None:
        self.setWindowTitle(f"{self.tr('ui.explore.title')} · {self.brand.product_name}")
        self.title.setText(self.tr("ui.explore.title"))
        self.note.setText(self.tr("ui.explore.note"))
        for i, (key, _) in enumerate(TABS):
            self.tabs.setTabText(i, self.tr(f"ui.explore.tab_{key}"))
        for page in self.pages:
            page.retranslate()
