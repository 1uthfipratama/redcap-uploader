"""Step 5: how many records are new or updates, then the batched upload.

The alternative path writes the files for REDCap's Data Import Tool instead.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QProgressBar, QPushButton

from app import workers
from app.pages.base import StepPage
from app.widgets import label
from core.dictionary import build_dictionary
from core.export_csv import write_dictionary_csv, write_import_csv
from core.parse import ROW
from core.pipeline import to_redcap_records
from core.profile import RECORD_ID_FIELD
from core.upload import plan_upload, upload


class UploadPage(StepPage):
    title_key = "ui.upload.title"
    lead_key = "ui.upload.lead"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.plan = label("SectionTitle")
        self.detail = label("Muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.batch = label("Muted")
        self.alt_note = label("Muted")
        self.alt = QPushButton()
        self.alt.clicked.connect(self._save_files)
        self.saved = label("Success")
        self.saved.hide()
        row = QHBoxLayout()
        row.addWidget(self.alt_note, 1)
        row.addWidget(self.alt)
        for w in (self.plan, self.detail, self.progress, self.batch):
            self.body.addWidget(w)
        self.body.addSpacing(12)
        self.body.addLayout(row)
        self.body.addWidget(self.saved)
        self._saved_to: Path | None = None

    def translate(self) -> None:
        self.alt_note.setText(self.tr("ui.upload.alt_note"))
        self.alt.setText(self.tr("ui.upload.alt"))
        if self._saved_to:
            self.saved.setText(self.tr("ui.upload.saved", folder=str(self._saved_to)))
        self._show_plan()

    def next_key(self) -> str:
        return "ui.nav.upload"

    # ---- plan ----------------------------------------------------------------
    def _records(self):
        return to_redcap_records(self.state.prepared.frame)

    def on_enter(self) -> None:
        state = self.state
        if state.plan is not None:
            self._show_plan()
            return
        self.plan.setText(self.tr("ui.upload.checking"))
        self.detail.setText("")

        def done(plan):
            state.plan = plan  # before set_busy(False), which re-reads ready()
            self.ctx.set_busy(False)
            self._show_plan()

        def failed(key, params):
            self.ctx.set_busy(False)
            self.show_error(key, params)

        self.ctx.set_busy(True)
        workers.run(lambda: plan_upload(state.client, self._records(), RECORD_ID_FIELD), done, failed)

    def _show_plan(self) -> None:
        plan = self.state.plan
        if plan is None:
            return
        project = self.state.project.title if self.state.project else ""
        self.plan.setText(self.tr("ui.upload.plan", total=plan.total, project=project))
        self.detail.setText(self.tr("ui.upload.plan_detail", new=plan.new, existing=plan.existing))

    # ---- upload --------------------------------------------------------------
    def ready(self) -> bool:
        return self.state.plan is not None

    def advance(self, proceed) -> None:
        state = self.state
        frame = state.prepared.frame
        rows = dict(zip(frame[RECORD_ID_FIELD], frame[ROW].astype(int)))
        records = self._records()
        self.progress.setValue(0)
        self.progress.show()

        def report(i, n):
            self.progress.setMaximum(n)
            self.progress.setValue(i)
            self.batch.setText(self.tr("ui.upload.batch", i=i, n=n))

        def work(progress):
            return upload(state.client, records, record_id_field=RECORD_ID_FIELD,
                          batch_size=state.target.batch_size, overwrite=state.target.overwrite_behavior,
                          rows_by_record=rows, plan=state.plan, on_progress=progress)

        def done(result):
            state.result = result
            state.plan = None  # counts change after an upload
            self.ctx.set_busy(False)
            proceed()

        def failed(key, params):
            self.ctx.set_busy(False)
            self.show_error(key, params)

        self.ctx.set_busy(True)
        workers.run(work, done, failed, on_progress=report)

    # ---- files for the Data Import Tool --------------------------------------
    def _save_files(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.tr("ui.upload.alt"))
        if not folder:
            return
        state, folder = self.state, Path(folder)
        profile = state.profile
        dictionary = state.project.dictionary if profile.is_generic else build_dictionary(profile)
        code = profile.identity.form_code
        write_import_csv(state.prepared.frame, dictionary, folder / f"{code}_import.csv")
        write_dictionary_csv(dictionary, folder / f"{code}_dictionary.csv")
        self._saved_to = folder
        self.saved.setText(self.tr("ui.upload.saved", folder=str(folder)))
        self.saved.show()
