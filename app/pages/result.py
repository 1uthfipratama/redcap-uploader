"""Step 5: what was imported, what was rejected and why, and a log to keep."""

from __future__ import annotations

import datetime as dt
import json

from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QPushButton

from app.pages.base import StepPage
from app.widgets import fill_table, label, new_table
from core import receipt
from core.client import classify_problem


class ResultPage(StepPage):
    title_key = "ui.result.title"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.headline = label("SectionTitle")
        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        self.numbers = {k: label("BigNumber") for k in ("imported", "rejected", "not_sent")}
        self.captions = {k: label("Muted") for k in self.numbers}
        for col, k in enumerate(self.numbers):
            grid.addWidget(self.numbers[k], 0, col)
            grid.addWidget(self.captions[k], 1, col)
        grid.setColumnStretch(3, 1)
        self.problems_title = label("SectionTitle")
        self.problems = new_table()
        self.problems.setMinimumHeight(220)
        self.changes_title = label("SectionTitle")
        self.changes = new_table()
        self.changes.setMinimumHeight(160)
        self.save = QPushButton()
        self.again = QPushButton()
        self.again.setObjectName("Primary")
        self.save.clicked.connect(self._save_log)
        self.receipt = QPushButton()
        self.receipt.clicked.connect(self._save_receipt)
        self.again.clicked.connect(self._again)
        self.explore = QPushButton()
        self.explore.clicked.connect(self.ctx.open_explore)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save)
        buttons.addWidget(self.receipt)
        buttons.addWidget(self.explore)
        buttons.addWidget(self.again)
        self.body.addWidget(self.headline)
        self.body.addLayout(grid)
        self.body.addWidget(self.problems_title)
        self.body.addWidget(self.problems)
        self.body.addWidget(self.changes_title)
        self.body.addWidget(self.changes)
        self.body.addLayout(buttons)

    def translate(self) -> None:
        tr = self.tr
        for k, w in self.captions.items():
            w.setText(tr(f"ui.result.{k}"))
        self.problems_title.setText(tr("ui.result.problems"))
        self.save.setText(tr("ui.result.save_log"))
        self.receipt.setText(tr("ui.result.save_receipt"))
        self.again.setText(tr("ui.result.again"))
        self.explore.setText(tr("ui.explore.open"))
        self.on_enter()

    def on_enter(self) -> None:
        result = self.state.result
        if result is None:
            return
        tr = self.tr
        rejected = result.rejected_batch
        self.numbers["imported"].setText(str(result.imported))
        self.numbers["rejected"].setText(str(rejected.size if rejected else 0))
        self.numbers["not_sent"].setText(str(result.not_sent))
        if result.complete:
            self.headline.setText(tr("ui.result.all_in", count=result.imported))
            self.headline.setStyleSheet(f"color: {self.ctx.brand.colors['success']};")
        else:
            first = rejected is None or rejected.index == 1
            self.headline.setText(tr("ui.result.stopped_first") if first else tr("ui.result.stopped", batch=rejected.index))
            self.headline.setStyleSheet(f"color: {self.ctx.brand.colors['error']};")
        rows = []
        if rejected:
            for p in rejected.problems:
                fix = tr(f"ui.fix.redcap_{classify_problem(p.message)}", field=p.field or "—")
                rows.append([rejected.rows.get(p.record, ""), p.field, p.value, p.message, fix])
        headers = [tr(f"ui.result.h_{k}") for k in ("row", "field", "value", "message", "fix")]
        fill_table(self.problems, headers, rows, stretch=(3, 4))
        self.problems.setVisible(bool(rows))
        self.problems_title.setVisible(bool(rows))
        self._show_changes()

    def _show_changes(self) -> None:
        """What the person edited or skipped on the Review step, listed again here."""
        tr, review = self.tr, self.state.review
        made = review.log() if review else {"edited": [], "skipped": []}
        rows = [[e["row"], e["field"], e.get("from", "—"), e.get("to", "—")] for e in made["edited"]]
        rows += [[s["row"], "—", "", tr(f"ui.result.skipped_{s['reason']}")] for s in made["skipped"]]
        headers = [tr("ui.result.h_row"), tr("ui.result.h_field"), tr("ui.result.was"), tr("ui.result.now")]
        fill_table(self.changes, headers, rows, stretch=(3,))
        self.changes.setVisible(bool(rows))
        self.changes_title.setVisible(bool(rows))
        self.changes_title.setText(tr("ui.result.changes", edited=len(made["edited"]), skipped=len(made["skipped"])))

    def ready(self) -> bool:
        return False  # the last step; "Upload another file" starts again

    def _save_log(self) -> None:
        result = self.state.result
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.result.save_log"), f"upload-log-{stamp}.json", "JSON (*.json)")
        if not path:
            return
        log = {
            "time": dt.datetime.now().isoformat(timespec="seconds"),
            "mode": self.state.mode,
            "project": self.state.project.title if self.state.project else "",
            "form": self.state.profile.identity.form_code if self.state.profile else "",
            "records": result.plan.total,
            "new": result.plan.new,
            "existing": result.plan.existing,
            "imported": result.imported,
            "not_sent": result.not_sent,
            **(self.state.review.log() if self.state.review else {"edited": [], "skipped": []}),
            "batches": [{"batch": b.index, "size": b.size, "status": b.status,
                         "problems": [{"row": b.rows.get(p.record), "record": p.record, "field": p.field,
                                       "value": p.value, "message": p.message} for p in b.problems]}
                        for b in result.batches],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=2, ensure_ascii=False)

    def _save_receipt(self) -> None:
        state, tr = self.state, self.tr
        if state.result is None or state.review is None:
            return
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        path, _ = QFileDialog.getSaveFileName(self, tr("ui.result.save_receipt"), f"receipt-{stamp}.csv", "CSV (*.csv)")
        if not path:
            return
        labels = {receipt.CREATED: "ui.receipt.created", receipt.UPDATED: "ui.receipt.updated",
                  receipt.IMPORTED: "ui.result.imported", receipt.REJECTED: "ui.result.rejected",
                  receipt.NOT_SENT: "ui.result.not_sent", f"{receipt.SKIPPED_PREFIX}chosen": "ui.result.skipped_chosen",
                  f"{receipt.SKIPPED_PREFIX}errors": "ui.result.skipped_errors"}
        header = [tr(f"ui.receipt.h_{k}") for k in ("row", "record", "status", "batch", "edited")]
        receipt.write_receipt_csv(receipt.build_receipt(state.review, state.result), path, header,
                                  lambda status: tr(labels[status]))

    def _again(self) -> None:
        self.state.forget_file()
        self.state.file = None
        self.ctx.go_to(1)
