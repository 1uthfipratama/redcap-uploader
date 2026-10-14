"""Step 4: the dry run's findings. Nothing has been sent; errors block the upload."""

from __future__ import annotations

import csv

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton

from app.pages.base import StepPage
from app.widgets import Disclosure, fill_table, label, new_table


class ValidatePage(StepPage):
    title_key = "ui.validate.title"
    lead_key = "ui.validate.lead"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.headline = label("Success")
        self.headline.setObjectName("SectionTitle")
        self.skipped = label("Muted")
        self.errors = new_table()
        self.errors.setMinimumHeight(260)
        self.warnings = new_table()
        self.warnings.setMinimumHeight(180)
        self.changes = new_table()
        self.changes.setMinimumHeight(180)
        self.warnings_box = Disclosure(self.warnings)
        self.changes_box = Disclosure(self.changes)
        self.save = QPushButton()
        self.save.clicked.connect(self._save)
        self.explore = QPushButton()
        self.explore.clicked.connect(self.ctx.open_explore)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.save)
        row.addWidget(self.explore)
        for w in (self.headline, self.skipped, self.errors, self.warnings_box, self.changes_box):
            self.body.addWidget(w)
        self.body.addLayout(row)

    def translate(self) -> None:
        self.save.setText(self.tr("ui.validate.save"))
        self.explore.setText(self.tr("ui.explore.open"))
        self.on_enter()

    def _issue_rows(self, issues) -> list[list]:
        return [[i.row or "", i.field or "", self.tr.problem(i), self.tr.fix(i)] for i in issues]

    def on_enter(self) -> None:
        p = self.state.prepared
        if not p or p.frame is None:
            return
        tr = self.tr
        headers = [tr("ui.validate.h_row"), tr("ui.validate.h_field"), tr("ui.validate.h_problem"), tr("ui.validate.h_fix")]
        if p.errors:
            self.headline.setText(tr("ui.validate.has_errors", count=len(p.errors)))
            self.headline.setStyleSheet(f"color: {self.ctx.brand.colors['error']};")
        else:
            self.headline.setText(tr("ui.validate.ready", count=len(p.frame)))
            self.headline.setStyleSheet(f"color: {self.ctx.brand.colors['success']};")
        self.skipped.setText(tr("ui.validate.skipped", blank=p.skipped_rows["blank"], summary=p.skipped_rows["summary"]))
        self.errors.setVisible(bool(p.errors))
        fill_table(self.errors, headers, self._issue_rows(p.errors), stretch=(2, 3))
        fill_table(self.warnings, headers, self._issue_rows(p.warnings), stretch=(2, 3))
        self.warnings_box.setVisible(bool(p.warnings))
        self.warnings_box.set_text(tr("ui.validate.warnings", count=len(p.warnings)))
        change_headers = [tr("ui.validate.h_field"), tr("ui.validate.h_in_file"), tr("ui.validate.h_becomes"),
                          tr("ui.validate.h_rows")]
        fill_table(self.changes, change_headers,
                   [[c.field, c.spelling, f"{c.code} · {c.label}", c.count] for c in p.changes], stretch=(2,))
        self.changes_box.setVisible(bool(p.changes))
        self.changes_box.set_text(tr("ui.validate.changes", count=len(p.changes)))
        self.save.setVisible(bool(p.issues))
        self.explore.setVisible(p.ready)

    def ready(self) -> bool:
        p = self.state.prepared
        return bool(p and p.ready)

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.validate.save"), "problems.csv", "CSV (*.csv)")
        if not path:
            return
        tr = self.tr
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([tr("ui.validate.h_row"), tr("ui.validate.h_field"), tr("ui.validate.h_severity"),
                             tr("ui.validate.h_problem"), tr("ui.validate.h_fix")])
            for i in self.state.prepared.issues:
                writer.writerow([i.row or "", i.field or "", tr(f"ui.severity.{i.severity}"), tr.problem(i), tr.fix(i)])
