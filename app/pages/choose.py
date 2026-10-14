"""Step 2: pick a file (dialog, drag and drop, or a sample in Demo mode) and its form."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QPushButton, QWidget

from app import workers
from app.pages.base import StepPage
from app.widgets import DropZone, label
from core.dictionary import build_dictionary, missing_fields
from core.export_csv import write_dictionary_csv
from core.grid import SUPPORTED_SUFFIXES
from core.mapping import read_metadata
from core.pipeline import detect, prepare
from synthetic.generate import DEFAULT_ROWS, write_set

FORM_ORDER = ["tbc03_so", "tbc03_ro", "generic"]


class ChoosePage(StepPage):
    title_key = "ui.choose.title"
    lead_key = "ui.choose.lead"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.drop = DropZone(SUPPORTED_SUFFIXES)
        self.drop.dropped.connect(self.load)
        self.pick = QPushButton()
        self.pick.setObjectName("Primary")
        self.pick.clicked.connect(self._pick)
        row = QHBoxLayout()
        row.addWidget(self.pick)
        row.addStretch(1)
        self.sample_label = label("Muted", wrap=False)
        self.sample_clean, self.sample_messy = QPushButton(), QPushButton()
        self.sample_clean.clicked.connect(lambda: self._sample("clean"))
        self.sample_messy.clicked.connect(lambda: self._sample("messy"))
        for w in (self.sample_label, self.sample_clean, self.sample_messy):
            row.addWidget(w)
        self.body.addWidget(self.drop)
        self.body.addLayout(row)

        self.summary = QWidget()
        form = QFormLayout(self.summary)
        form.setContentsMargins(0, 12, 0, 0)
        form.setHorizontalSpacing(24)
        self.form_box = QComboBox()
        self.form_box.currentIndexChanged.connect(self._form_changed)
        self.values = {k: label() for k in ("file", "facility", "period", "rows", "columns")}
        self.names = {k: label("Muted") for k in ("file", "form", "facility", "period", "rows", "columns")}
        form.addRow(self.names["file"], self.values["file"])
        form.addRow(self.names["form"], self.form_box)
        for k in ("facility", "period", "rows", "columns"):
            form.addRow(self.names[k], self.values[k])
        self.summary.hide()
        self.body.addWidget(self.summary)

        self.save_dictionary = QPushButton()
        self.save_dictionary.clicked.connect(self._save_dictionary)
        self.save_dictionary.hide()
        self.body.addWidget(self.save_dictionary)
        self._samples_dir: Path | None = None

    def translate(self) -> None:
        tr = self.tr
        self.drop.hint.setText(tr("ui.choose.drop"))
        self.pick.setText(tr("ui.choose.pick"))
        self.sample_label.setText(tr("ui.choose.sample"))
        self.sample_clean.setText(tr("ui.choose.sample_clean"))
        self.sample_messy.setText(tr("ui.choose.sample_messy"))
        self.save_dictionary.setText(tr("ui.choose.save_dictionary"))
        for k, w in self.names.items():
            w.setText(tr(f"ui.choose.{k}"))
        self._fill_forms()
        self._show_summary()

    def on_enter(self) -> None:
        self._show_summary()
        demo = self.state.mode == "demo"
        for w in (self.sample_label, self.sample_clean, self.sample_messy):
            w.setVisible(demo)

    # ---- loading a file --------------------------------------------------------
    def _pick(self) -> None:
        pattern = " ".join(f"*{s}" for s in SUPPORTED_SUFFIXES)
        path, _ = QFileDialog.getOpenFileName(self, self.tr("ui.choose.pick"), "", f"{self.tr('ui.choose.file_types')} ({pattern})")
        if path:
            self.load(Path(path))

    def _sample(self, kind: str) -> None:
        state = self.state
        profile = state.profiles["tbc03_so"]

        def work():
            if self._samples_dir is None:
                self._samples_dir = Path(tempfile.mkdtemp(prefix="redcap-uploader-samples-"))
            written = write_set(profile, self._samples_dir, DEFAULT_ROWS["tbc03_so"], seed=42, formats=("xlsx",))
            return written[f"{kind}_xlsx"]

        self.ctx.set_busy(True)
        workers.run(work, lambda path: (self.ctx.set_busy(False), self.load(path)), self._failed)

    def load(self, path: Path) -> None:
        self.clear_error()
        self.save_dictionary.hide()
        self.state.forget_file()
        self.state.file = path
        profiles = self.state.profiles

        def done(detected):
            self.state.detected = detected
            self.state.form_code = detected.form_code
            self.ctx.set_busy(False)
            self._fill_forms()
            self._show_summary()
            self.ctx.refresh_nav()

        self.ctx.set_busy(True)
        workers.run(lambda: detect(path, profiles), done, self._failed)

    def _failed(self, key: str, params: dict) -> None:
        self.ctx.set_busy(False)
        self.show_error(key, params)
        self.ctx.refresh_nav()

    def _fill_forms(self) -> None:
        self.form_box.blockSignals(True)
        self.form_box.clear()
        for code in FORM_ORDER:
            if code in self.state.profiles:
                name = self.tr("ui.choose.generic") if code == "generic" else self.state.profiles[code].identity.name
                self.form_box.addItem(name, code)
        index = self.form_box.findData(self.state.form_code)
        self.form_box.setCurrentIndex(max(index, 0))
        self.form_box.blockSignals(False)

    def _form_changed(self) -> None:
        self.state.form_code = self.form_box.currentData()
        self.state.prepared = None
        self._show_summary()
        self.clear_error()
        self.save_dictionary.hide()

    def _show_summary(self) -> None:
        d = self.state.detected
        self.summary.setVisible(d is not None)
        if not d:
            return
        profile = self.state.profile
        meta = read_metadata(d.layout, profile) if profile else {}
        self.values["file"].setText(self.state.file.name if self.state.file else "")
        self.values["facility"].setText(meta.get("facility", "—"))
        self.values["period"].setText(meta.get("period", "—"))
        self.values["rows"].setText(str(len(d.layout.data_rows)))
        self.values["columns"].setText(str(len(d.layout.columns)))

    # ---- navigation ------------------------------------------------------------
    def ready(self) -> bool:
        return self.state.detected is not None and self.state.form_code is not None

    def advance(self, proceed) -> None:
        state = self.state
        profile = state.profile
        self.clear_error()
        self.save_dictionary.hide()
        if not profile.is_generic and state.mode == "real" and state.key is None:
            self.show_error("ui.error.key_missing")
            return

        def work():
            if state.mode == "demo" and not profile.is_generic:
                state.mock.project.dictionary = build_dictionary(profile)
                state.mock.project.records.clear()
            state.project = state.client.connect()
            missing = [] if profile.is_generic else missing_fields(profile, state.project.fields)
            if missing:
                return ("missing", missing)
            key = state.demo_key() if state.mode == "demo" else state.key
            return ("prepared", prepare(state.detected, profile, key, target_fields=state.project.fields,
                                        overrides=state.overrides))

        def done(result):
            self.ctx.set_busy(False)
            kind, value = result
            if kind == "missing":
                self.show_error("ui.choose.missing_fields", {"count": len(value), "fields": ", ".join(value[:6])})
                self.save_dictionary.show()
                return
            state.prepared = value
            if value.blocked:
                self.show_error("ui.choose.layout_differs",
                                {"problems": "\n".join(self.tr.describe(i) for i in value.errors[:8])})
                return
            proceed()

        self.ctx.set_busy(True)
        workers.run(work, done, self._failed)

    def _save_dictionary(self) -> None:
        profile = self.state.profile
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.choose.save_dictionary"),
                                              f"{profile.identity.form_code}_dictionary.csv", "CSV (*.csv)")
        if path:
            write_dictionary_csv(build_dictionary(profile), path)
