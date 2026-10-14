"""The Explore screen: descriptive summaries and charts of the cleaned data.

Opens from the Check step once there are no errors, and from Result. It reads the
cleaned table in memory and sends nothing anywhere. Every number comes from
core/explore; this module only lays it out. Each tab reads top to bottom: pickers,
a titled chart with its save button, then the table with its save button, then notes.
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
from app.teaching import TeachingPanel
from app.i18n import Translator
from app.theme import Brand
from app.widgets import Panel, fill_table, label, new_table
from core import explore
from core.pipeline import Prepared

MAX_CHART_GROUPS = 4  # answer comparisons: the four largest groups are drawn; the table has all
MISSING_CHART_FIELDS = 15
TABLE_ROWS = 12  # tables show this many rows before scrolling


def _num(x):
    """Whole numbers without '.0'; None stays blank."""
    if x is None or (isinstance(x, float) and x != x):
        return None
    return int(x) if float(x).is_integer() else x


class Tab(QWidget):
    """Pickers, chart and its save button, table and its save button, notes."""

    teach_keys: tuple[str, ...] = ()  # "What's happening?" paragraphs for this tab

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
        self.panel.body.setSpacing(10)
        inner_layout.addWidget(self.panel)
        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self.controls = QHBoxLayout()
        self.controls.setSpacing(10)
        self.panel.body.addLayout(self.controls)
        self.chart = Chart(win.brand) if with_chart else None
        self.save_png = QPushButton()
        self.save_png.clicked.connect(self._save_png)
        if self.chart:
            self.panel.body.addSpacing(6)
            self.panel.body.addWidget(self.chart.canvas)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(self.save_png)
            self.panel.body.addLayout(row)
            self.panel.body.addSpacing(18)
        table_head = QHBoxLayout()
        self.table_title = label("SectionTitle", wrap=False)
        self.save_csv = QPushButton()
        self.save_csv.clicked.connect(self._save_csv)
        table_head.addWidget(self.table_title)
        table_head.addStretch(1)
        table_head.addWidget(self.save_csv)
        self.panel.body.addLayout(table_head)
        self.table = new_table()
        self.panel.body.addWidget(self.table)
        self.footnote = label("Muted")
        self.panel.body.addWidget(self.footnote)
        self.teach = TeachingPanel(self.tr)
        self.panel.body.addSpacing(8)
        self.panel.body.addWidget(self.teach)
        self.export = pd.DataFrame()

    def picker(self, caption_key: str) -> QComboBox:
        box = QComboBox()
        box.setMinimumWidth(260)
        caption = label("Muted", wrap=False)
        caption.setProperty("key", caption_key)
        self.controls.addWidget(caption)
        self.controls.addWidget(box)
        box.currentIndexChanged.connect(lambda _: self.refresh())
        return box

    def show_table(self, display: pd.DataFrame, export: pd.DataFrame | None = None, stretch=()) -> None:
        """Show `display`; Save table writes `export` (the fuller table) when given."""
        self.export = display if export is None else export
        rows = [[None if (isinstance(v, float) and v != v) else v for v in row]
                for row in display.itertuples(index=False)]
        fill_table(self.table, [str(c) for c in display.columns], rows, stretch, fit_rows=TABLE_ROWS)

    def notes(self, *texts: str) -> None:
        self.footnote.setText("\n".join(t for t in texts if t))
        self.footnote.setVisible(any(texts))

    def retranslate(self) -> None:
        self.save_png.setText(self.tr("ui.explore.save_png"))
        self.save_csv.setText(self.tr("ui.explore.save_csv"))
        self.table_title.setText(self.tr("ui.explore.table_title"))
        for i in range(self.controls.count()):
            w = self.controls.itemAt(i).widget()
            if w is not None and w.property("key"):
                w.setText(self.tr(w.property("key")))
        self.teach.set_content([self.tr(k) for k in self.teach_keys])
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
            self.export.to_csv(path, index=False, encoding="utf-8-sig")


def fill_fields(box: QComboBox, fields: list[explore.FieldInfo], lang: str, preferred: list[str]) -> None:
    current = box.currentData()
    box.blockSignals(True)
    box.clear()
    for f in fields:
        box.addItem(f"{f.label(lang)} · {f.name}", f.name)
    target = current if box.findData(current) >= 0 else next((p for p in preferred if box.findData(p) >= 0), None)
    box.setCurrentIndex(max(box.findData(target), 0) if target else 0)
    box.blockSignals(False)


def small_note(tr, flags, settings: dict) -> str:
    return tr("ui.explore.small_note", n=settings["small_group"]) if any(flags) else ""


# ---- tabs -------------------------------------------------------------------------

class OverviewTab(Tab):
    teach_keys = ("ui.teach.ex_overview", "ui.teach.ex_private")

    def __init__(self, win):
        super().__init__(win, with_chart=False)
        for w in (self.table, self.table_title, self.save_csv):
            w.hide()
        grid = QGridLayout()
        grid.setHorizontalSpacing(56)
        grid.setVerticalSpacing(2)
        self.keys = ["rows", "explorable", "duplicate_rows", "numeric", "categorical", "dates"]
        self.numbers = {k: label("BigNumber", wrap=False) for k in self.keys}
        self.captions = {k: label("Muted", wrap=False) for k in self.keys}
        for i, k in enumerate(self.keys):
            r, c = (i // 3) * 3, i % 3
            grid.addWidget(self.numbers[k], r, c)
            grid.addWidget(self.captions[k], r + 1, c)
        grid.setRowMinimumHeight(2, 24)
        grid.setColumnStretch(3, 1)
        self.panel.body.insertLayout(0, grid)

    def refresh(self) -> None:
        o = explore.overview(self.win.frame, self.win.fields)
        for k in self.keys:
            self.numbers[k].setText(f"{o[k]:,}")
            self.captions[k].setText(self.tr(f"ui.explore.ov_{k}"))
        self.notes(self.tr("ui.explore.ov_note"))


class VariablesTab(Tab):
    teach_keys = ("ui.teach.ex_centre", "ui.teach.ex_spread")

    EXPORT = ["label", "field", "type", "count", "blank", "blank_pct", "unknown", "distinct",
              "mean", "sd", "min", "q1", "median", "q3", "max", "top"]

    def __init__(self, win):
        super().__init__(win, with_chart=False)

    def _summary(self, row) -> str:
        tr = self.tr
        median = row["median"]
        if row["type"] == "numeric" and median is not None and median == median:
            sd = row["sd"] if row["sd"] is not None and row["sd"] == row["sd"] else None
            return tr("ui.explore.sum_numeric", mean=_num(row["mean"]), sd=_num(sd) if sd is not None else "—",
                      median=_num(median), q1=_num(row["q1"]), q3=_num(row["q3"]),
                      min=_num(row["min"]), max=_num(row["max"]))
        if row["type"] == "date" and isinstance(row["min"], str):
            return tr("ui.explore.sum_date", min=row["min"], max=row["max"])
        return row["top"] or ""

    def refresh(self) -> None:
        tr = self.tr
        table = explore.variable_summary(self.win.frame, self.win.fields, tr.lang, self.win.settings)
        display = pd.DataFrame({
            tr("ui.explore.col_label"): table["label"],
            tr("ui.explore.col_type"): [tr(f"ui.explore.kind_{k}") for k in table["type"]],
            tr("ui.explore.col_count"): table["count"],
            tr("ui.explore.col_blank_pct"): table["blank_pct"],
            tr("ui.explore.col_unknown"): table["unknown"],
            tr("ui.explore.col_distinct"): table["distinct"],
            tr("ui.explore.col_summary"): [self._summary(r) for _, r in table.iterrows()],
        })
        export = table[self.EXPORT].copy()
        export["type"] = [tr(f"ui.explore.kind_{k}") for k in export["type"]]
        export = export.rename(columns={c: tr(f"ui.explore.col_{c}") for c in self.EXPORT})
        self.show_table(display, export, stretch=(6,))
        self.table.setMinimumHeight(520)
        self.table.setMaximumHeight(16777215)
        self.notes(tr("ui.explore.var_note"))


class DistributionTab(Tab):
    teach_keys = ("ui.teach.ex_distribution",)

    def __init__(self, win):
        super().__init__(win)
        self.field = self.picker("ui.explore.field")
        self.controls.addStretch(1)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        fill_fields(self.field, win.fields, tr.lang, win.profile.explore_defaults)
        f = win.field(self.field.currentData())
        if f is None:
            return
        name = f.label(tr.lang)
        data = explore.distribution(win.sample, f, tr.lang, win.settings)
        sampled = tr("ui.explore.sampled", n=len(win.sample)) if win.sampled else ""
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            self.notes(sampled)
            return
        if f.kind == "numeric":
            self.chart.histogram(tr("ui.explore.ct_hist", field=name), data["bin_start"], data["bin_end"], data["n"],
                                 name, tr("ui.explore.records"))
            table = pd.DataFrame({tr("ui.explore.col_from"): [_num(x) for x in data["bin_start"]],
                                  tr("ui.explore.col_to"): [_num(x) for x in data["bin_end"]],
                                  tr("ui.explore.col_n"): data["n"], tr("ui.explore.col_percent"): data["percent"]})
            self.show_table(table)
            self.notes(small_note(tr, data["small"], win.settings), sampled)
        elif f.kind == "date":
            self.chart.columns(tr("ui.explore.ct_month", field=name), list(data["month"]), list(data["n"]),
                               tr("ui.explore.records"))
            self.show_table(pd.DataFrame({tr("ui.explore.col_month"): data["month"], tr("ui.explore.col_n"): data["n"],
                                          tr("ui.explore.col_percent"): data["percent"]}))
            self.notes(small_note(tr, data["small"], win.settings), sampled)
        else:
            answered = data[~data["blank"]]
            blank_n = int(data.loc[data["blank"], "n"].sum())
            if answered.empty:
                self.chart.message(tr("ui.explore.no_values"))
            else:
                text = [f"{n:,}  ({p}%)" for n, p in zip(answered["n"], answered["percent_answered"])]
                self.chart.horizontal_bars(tr("ui.explore.ct_answers", field=name), list(answered["label"]),
                                           list(answered["n"]), text, list(answered["unknown"]), tr("ui.explore.records"))
            labels = [tr("ui.explore.blank") if b else lab for lab, b in zip(data["label"], data["blank"])]
            self.show_table(pd.DataFrame({
                tr("ui.explore.col_answer"): labels, tr("ui.explore.col_code"): data["code"],
                tr("ui.explore.col_n"): data["n"], tr("ui.explore.col_pct_answered"): data["percent_answered"],
                tr("ui.explore.col_pct_all"): data["percent"]}))
            blank_note = (tr("ui.explore.blank_note", n=blank_n, pct=round(100 * blank_n / data["n"].sum(), 1))
                          if blank_n else "")
            self.notes(blank_note, small_note(tr, data["small"], win.settings), sampled)


class MissingTab(Tab):
    teach_keys = ("ui.teach.ex_missing",)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        data = explore.missingness(win.frame, win.fields)
        shown = data[(data["blank"] + data["unknown"]) > 0].head(MISSING_CHART_FIELDS)
        labels = {f.name: f.label(tr.lang) for f in win.fields}
        if shown.empty:
            self.chart.message(tr("ui.explore.nothing_missing"))
        else:
            self.chart.stacked_two(tr("ui.explore.ct_missing", n=len(shown)), [labels[n] for n in shown["field"]],
                                   list(shown["blank_pct"]), list(shown["unknown_pct"]),
                                   (tr("ui.explore.blank"), tr("ui.explore.unknown")), tr("ui.explore.percent_of_records"))
        display = pd.DataFrame({
            tr("ui.explore.col_label"): [labels[n] for n in data["field"]], tr("ui.explore.col_field"): data["field"],
            tr("ui.explore.col_blank"): data["blank"], tr("ui.explore.col_blank_pct"): data["blank_pct"],
            tr("ui.explore.col_unknown"): data["unknown"], tr("ui.explore.col_unknown_pct"): data["unknown_pct"]})
        self.show_table(display)
        self.notes(tr("ui.explore.missing_note"))


class CompareTab(Tab):
    teach_keys = ("ui.teach.ex_compare", "ui.teach.ex_small")

    def __init__(self, win):
        super().__init__(win)
        self.field = self.picker("ui.explore.field")
        self.by = self.picker("ui.explore.by")
        self.controls.addStretch(1)

    def refresh(self) -> None:
        tr, win = self.tr, self.win
        fill_fields(self.field, [f for f in win.fields if f.kind in ("numeric", "categorical")], tr.lang,
                    ["age"] + win.profile.explore_defaults)
        fill_fields(self.by, [f for f in win.fields if f.kind == "categorical"], tr.lang, ["sex", "tb_site", "hiv"])
        f, by = win.field(self.field.currentData()), win.field(self.by.currentData())
        if f is None or by is None:
            return
        ungrouped = explore.ungrouped_count(win.sample, by)
        left_out = tr("ui.explore.ungrouped", n=ungrouped, by=by.label(tr.lang)) if ungrouped else ""
        if f.kind == "numeric":
            self._numeric(f, by, left_out)
        else:
            self._answers(f, by, left_out)

    def _numeric(self, f, by, left_out: str) -> None:
        tr, win = self.tr, self.win
        data = explore.group_comparison(win.sample, f, by, tr.lang, win.settings)
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            return
        self.chart.ranges(tr("ui.explore.ct_compare_num", field=f.label(tr.lang), by=by.label(tr.lang)),
                          list(data["group"]), list(data["q1"]), list(data["median"]), list(data["q3"]),
                          f.label(tr.lang), (tr("ui.explore.lg_median"), tr("ui.explore.lg_iqr")))
        cols = ["group", "n", "mean", "sd", "q1", "median", "q3"]
        self.show_table(data[cols].rename(columns={c: tr(f"ui.explore.col_{c}") for c in cols}))
        self.notes(small_note(tr, data["small"], win.settings), left_out)

    def _answers(self, f, by, left_out: str) -> None:
        tr, win = self.tr, self.win
        data = explore.answers_by_group(win.sample, f, by, tr.lang, win.settings)
        if data.empty:
            self.chart.message(tr("ui.explore.no_values"))
            self.show_table(pd.DataFrame())
            return
        groups = data[["group", "group_n"]].drop_duplicates().reset_index(drop=True)
        drawn = groups.nlargest(MAX_CHART_GROUPS, "group_n", keep="first").sort_index()
        answered = data[~data["blank"]]
        answers = list(dict.fromkeys(answered["answer"]))
        context = [bool(answered.loc[answered["answer"] == a, "context"].iloc[0]) for a in answers]
        percents = [[float(answered.loc[(answered["answer"] == a) & (answered["group"] == g), "percent"].sum())
                     for g in drawn["group"]] for a in answers]
        if answers:
            self.chart.grouped_bars(tr("ui.explore.ct_compare_cat", field=f.label(tr.lang), by=by.label(tr.lang)),
                                    answers, list(drawn["group"]), percents, context, tr("ui.explore.percent_of_answered"))
        else:
            self.chart.message(tr("ui.explore.no_values"))
        # Table: one row per answer, one column per group, "n (percent%)" in each cell.
        rows = []
        for a in dict.fromkeys(data["answer"]):
            part = data[data["answer"] == a]
            name = tr("ui.explore.blank") if part["blank"].iloc[0] else a
            row = {tr("ui.explore.col_answer"): name}
            for g, gn in zip(groups["group"], groups["group_n"]):
                cell = part[part["group"] == g]
                n = int(cell["n"].sum())
                pct = cell["percent"].iloc[0] if len(cell) and cell["percent"].notna().iloc[0] else None
                row[f"{g} (n={gn})"] = f"{n}" if pct is None else f"{n}  ({pct}%)"
            rows.append(row)
        export = data[["answer", "group", "group_n", "n", "percent"]].rename(columns={
            "answer": tr("ui.explore.col_answer"), "group": tr("ui.explore.col_group"),
            "group_n": tr("ui.explore.col_group_n"), "n": tr("ui.explore.col_n"),
            "percent": tr("ui.explore.col_pct_answered")})
        self.show_table(pd.DataFrame(rows), export)
        more = tr("ui.explore.top_groups", shown=len(drawn), n=len(groups)) if len(groups) > len(drawn) else ""
        self.notes(small_note(tr, data["small_group"], win.settings), left_out, more)


class OverTimeTab(Tab):
    teach_keys = ("ui.teach.ex_over_time",)

    def __init__(self, win):
        super().__init__(win)
        self.field = self.picker("ui.explore.date_field")
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
        self.chart.columns(tr("ui.explore.ct_month", field=f.label(tr.lang)), list(data["month"]), list(data["n"]),
                           tr("ui.explore.records"))
        self.show_table(pd.DataFrame({tr("ui.explore.col_month"): data["month"], tr("ui.explore.col_n"): data["n"],
                                      tr("ui.explore.col_percent"): data["percent"]}))
        self.notes(small_note(tr, data["small"], win.settings))


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
        self.resize(1180, 860)

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
