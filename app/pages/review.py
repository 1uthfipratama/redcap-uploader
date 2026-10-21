"""Step 3: the table that would be sent. Fix a value or skip a row; every change is logged.

Errors block the upload until each is fixed or its row is skipped. Nothing here is sent.
Edits and skipped rows live in core/review.py; this page only shows and drives them.
"""

from __future__ import annotations

import csv

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableView,
)

from app import workers
from app.pages.base import StepPage
from app.pages.review_columns import ColumnsSection
from app.review_table import MODES, EditCellDialog, ReviewModel
from app.widgets import Disclosure, fill_table, label, new_table
from core.pipeline import prepare


class ReviewPage(StepPage):
    title_key = "ui.review.title"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.model: ReviewModel | None = None  # built when the first table arrives
        self.headline = label("SectionTitle")
        self.status = label("Muted")
        self.notes = label("Warning")
        self.filter = QComboBox()
        for mode in MODES:
            self.filter.addItem("", mode)
        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.go_to = QLineEdit()
        self.go_to.setValidator(QIntValidator(1, 10**7))
        self.go_to.setMaximumWidth(150)
        self.go_to.returnPressed.connect(self._go_to_row)
        self.next_problem = QPushButton()
        self.next_problem.clicked.connect(self._next_problem)
        toolbar = QHBoxLayout()
        for w in (self.filter, self.go_to, self.next_problem):
            toolbar.addWidget(w)
        toolbar.addStretch(1)

        self.view = QTableView()
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(28)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setDefaultSectionSize(150)
        header.setStretchLastSection(False)
        self.view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.view.setMinimumHeight(380)
        self.view.doubleClicked.connect(self._edit)
        self.detail = label("Muted")
        self.detail.setContentsMargins(0, 6, 0, 0)

        self.edit_button = QPushButton()
        self.skip_button = QPushButton()
        self.restore_button = QPushButton()
        self.skip_errors = QPushButton()
        self.edit_button.clicked.connect(self._edit)
        self.skip_button.clicked.connect(self._skip)
        self.restore_button.clicked.connect(self._restore)
        self.skip_errors.clicked.connect(self._skip_errors)
        actions = QHBoxLayout()
        for w in (self.edit_button, self.skip_button, self.restore_button):
            actions.addWidget(w)
        actions.addStretch(1)
        actions.addWidget(self.skip_errors)

        self.columns = ColumnsSection(self.tr, self.state)
        self.columns_box = Disclosure(self.columns)
        self.changes = new_table()
        self.changes.setMinimumHeight(180)
        self.changes_box = Disclosure(self.changes)
        self.save = QPushButton()
        self.save.clicked.connect(self._save)
        self.explore = QPushButton()
        self.explore.clicked.connect(self.ctx.open_explore)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.save)
        bottom.addWidget(self.explore)

        for w in (self.headline, self.status, self.notes):
            self.body.addWidget(w)
        self.body.addLayout(toolbar)
        self.body.addWidget(self.view)
        self.body.addWidget(self.detail)
        self.body.addLayout(actions)
        self.body.addWidget(self.columns_box)
        self.body.addWidget(self.changes_box)
        self.body.addLayout(bottom)

    # ---- text ---------------------------------------------------------------------
    def translate(self) -> None:
        tr = self.tr
        for i, mode in enumerate(MODES):
            self.filter.setItemText(i, tr(f"ui.review.filter_{mode}"))
        self.go_to.setPlaceholderText(tr("ui.review.go_to"))
        self.next_problem.setText(tr("ui.review.next_problem"))
        self.edit_button.setText(tr("ui.review.edit"))
        self.skip_button.setText(tr("ui.review.skip"))
        self.restore_button.setText(tr("ui.review.restore"))
        self.skip_errors.setText(tr("ui.review.skip_errors"))
        self.columns_box.set_text(tr("ui.preview.columns"))
        self.save.setText(tr("ui.validate.save"))
        self.explore.setText(tr("ui.explore.open"))
        if self.model is not None:
            self.model.retranslate()
        self.on_enter()

    # ---- content --------------------------------------------------------------------
    def on_enter(self) -> None:
        state = self.state
        if state.prepared is None or state.prepared.frame is None or state.review is None:
            return
        if self.model is None:
            self.model = ReviewModel(state.review, self.tr, self.ctx.brand)
            self.view.setModel(self.model)
            self.view.setColumnWidth(0, 70)
            self.view.selectionModel().currentChanged.connect(lambda *_: self._update_buttons())
        elif self.model.review is not state.review:
            self.filter.blockSignals(True)
            self.filter.setCurrentIndex(0)
            self.filter.blockSignals(False)
            self.model.mode = "all"
            self.model.set_review(state.review)
            self.view.setColumnWidth(0, 70)
        self.columns.refresh()
        self.columns_box.button.setChecked(state.prepared.profile.is_generic)
        self._refresh()

    def _refresh(self) -> None:
        self.model.refresh()
        self._summary()
        self._update_buttons()
        self.ctx.refresh_nav()

    def _summary(self) -> None:
        state, tr = self.state, self.tr
        final, review = state.final, state.review
        colors = self.ctx.brand.colors
        if final.errors:
            text, color = tr("ui.validate.has_errors", count=len(final.errors)), colors["error"]
        elif not len(final.frame):
            text, color = tr("ui.review.nothing"), colors["error"]
        else:
            text, color = tr("ui.validate.ready", count=len(final.frame)), colors["success"]
        self.headline.setText(text)
        self.headline.setStyleSheet(f"color: {color};")
        left_out = state.prepared.skipped_rows
        self.status.setText(tr("ui.review.status", edited=len(review.edits), skipped=len(review.skipped),
                               blank=left_out["blank"], summary=left_out["summary"]))
        general = [i for i in final.issues if i.row is None]
        self.notes.setText("\n".join(tr.problem(i) for i in general))
        self.notes.setObjectName("Error" if any(i.is_error for i in general) else "Warning")
        self.notes.style().unpolish(self.notes)
        self.notes.style().polish(self.notes)
        self.notes.setVisible(bool(general))
        prepared = state.prepared
        change_headers = [tr("ui.validate.h_field"), tr("ui.validate.h_in_file"), tr("ui.validate.h_becomes"),
                          tr("ui.validate.h_rows")]
        fill_table(self.changes, change_headers,
                   [[c.field, c.spelling, f"{c.code} · {c.label}", c.count] for c in prepared.changes], stretch=(2,))
        self.changes_box.setVisible(bool(prepared.changes))
        self.changes_box.set_text(tr("ui.validate.changes", count=len(prepared.changes)))
        self.save.setVisible(bool(final.issues))
        self.explore.setVisible(final.ready and len(final.frame) > 0)

    def _update_buttons(self) -> None:
        if self.model is None:
            return
        review, index = self.state.review, self.view.currentIndex()
        row, field = self.model.row_at(index), self.model.field_at(index)
        skipped = row is not None and row in review.skipped
        self.edit_button.setEnabled(row is not None and not skipped and field is not None
                                    and review.spec(field) is not None)
        self.skip_button.setVisible(not skipped)
        self.skip_button.setEnabled(row is not None)
        self.restore_button.setVisible(skipped)
        self.skip_errors.setEnabled(bool(self.model.error_rows))
        self.next_problem.setEnabled(bool(self.model.error_rows))
        self._show_detail(row, skipped)

    def _show_detail(self, row: int | None, skipped: bool) -> None:
        tr = self.tr
        if row is None:
            self.detail.setText(tr("ui.review.select_row"))
            return
        lines = [tr("ui.review.row_heading", row=row)]
        if skipped:
            lines.append(tr("ui.review.skipped_tip"))
        else:
            issues = self.model.row_issues.get(row, [])
            lines += [f"{i.field or '—'}: {tr.problem(i)} {tr.fix(i)}" for i in issues] or [tr("ui.review.no_problems")]
        self.detail.setText("\n".join(lines))

    # ---- actions --------------------------------------------------------------------
    def open_dialog(self, dialog: QDialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _changed(self, row: int | None = None, field: str | None = None) -> None:
        """Re-check, then put the selection back where it was."""
        scroll = self.view.verticalScrollBar().value()
        self.state.plan = None  # the upload plan counts the records that will be sent
        self._refresh()
        self.view.verticalScrollBar().setValue(scroll)
        if row is not None:
            index = self.model.index_of(row, field)
            if index.isValid():
                self.view.setCurrentIndex(index)
        self._update_buttons()

    def _current(self) -> tuple[int | None, str | None]:
        index = self.view.currentIndex()
        return self.model.row_at(index), self.model.field_at(index)

    def _edit(self, index: QModelIndex | bool = False) -> None:
        if isinstance(index, QModelIndex) and index.isValid():
            self.view.setCurrentIndex(index)
        row, field = self._current()
        review = self.state.review
        if row is None or field is None or review.spec(field) is None or row in review.skipped:
            return
        dialog = EditCellDialog(self.tr, self.model, row, field, self)
        if not self.open_dialog(dialog):
            return
        if dialog.reset_requested:
            review.reset(row, field)
        else:
            review.set_value(row, field, dialog.text())
        self._changed(row, field)

    def _skip(self) -> None:
        row, field = self._current()
        if row is not None:
            self.state.review.skip([row])
            self._changed(row, field)

    def _restore(self) -> None:
        row, field = self._current()
        if row is not None:
            self.state.review.restore([row])
            self._changed(row, field)

    def _skip_errors(self) -> None:
        self.state.review.skip_rows_with_errors()
        self._changed()

    def _filter_changed(self) -> None:
        if self.model is not None:
            self.model.set_mode(self.filter.currentData())
            self._update_buttons()

    def _select(self, row: int, field: str | None = None) -> bool:
        index = self.model.index_of(row, field)
        if not index.isValid() and self.filter.currentData() != "all":
            self.filter.setCurrentIndex(0)  # the filter hides this row
            index = self.model.index_of(row, field)
        if not index.isValid():
            return False
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index)
        return True

    def _go_to_row(self) -> None:
        self.clear_error()
        if self.model is None or not self.go_to.text():
            return
        row = int(self.go_to.text())
        if not self.state.review.has_row(row) or not self._select(row):
            self.show_error("ui.review.no_such_row", {"row": row})

    def _next_problem(self) -> None:
        rows = self.model.error_rows
        if not rows:
            return
        current = self._current()[0] or 0
        target = next((r for r in rows if r > current), rows[0])
        issue = next(i for i in self.model.row_issues[target] if i.is_error)
        self._select(target, issue.field)

    # ---- files and navigation ------------------------------------------------------------
    def ready(self) -> bool:
        final = self.state.final
        return bool(final and final.ready and len(final.frame))

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.validate.save"), "problems.csv", "CSV (*.csv)")
        if not path:
            return
        tr = self.tr
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([tr("ui.validate.h_row"), tr("ui.validate.h_field"), tr("ui.validate.h_severity"),
                             tr("ui.validate.h_problem"), tr("ui.validate.h_fix")])
            for i in self.state.final.issues:
                writer.writerow([i.row or "", i.field or "", tr(f"ui.severity.{i.severity}"), tr.problem(i), tr.fix(i)])

    def advance(self, proceed) -> None:
        state = self.state
        if not state.prepared_stale:
            proceed()
            return

        def done(prepared):
            self.ctx.set_busy(False)
            state.set_prepared(prepared)
            state.prepared_stale = False
            proceed()

        def failed(key, params):
            self.ctx.set_busy(False)
            self.show_error(key, params)

        self.ctx.set_busy(True)
        workers.run(lambda: prepare(state.detected, state.profile, None, target_fields=state.project.fields,
                                    overrides=state.overrides), done, failed)
