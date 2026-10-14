"""Step 1: Demo (built-in mock) or Real (URL and token), then connect."""

from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QRadioButton, QWidget

from app import workers
from app.pages.base import StepPage
from app.widgets import label
from core import identifiers
from core.client import RedcapClient
from core.dictionary import build_dictionary
from mock_redcap.runner import MockRedcap


class ConnectPage(StepPage):
    title_key = "ui.connect.title"
    lead_key = "ui.connect.lead"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.demo = QRadioButton()
        self.real = QRadioButton()
        self.demo.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.demo)
        group.addButton(self.real)
        self.demo_note = label("Muted")
        self.real_note = label("Muted")
        self.body.addWidget(self.demo)
        self.body.addWidget(self.demo_note)
        self.body.addWidget(self.real)
        self.body.addWidget(self.real_note)

        self.real_box = QWidget()
        form = QFormLayout(self.real_box)
        form.setContentsMargins(26, 4, 0, 0)
        self.url = QLineEdit()
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        key_row = QHBoxLayout()
        self.key_status = label("Muted")
        self.key_button = QPushButton()
        key_row.addWidget(self.key_status, 1)
        key_row.addWidget(self.key_button)
        self.url_label, self.token_label, self.key_label = label(), label(), label()
        form.addRow(self.url_label, self.url)
        form.addRow(self.token_label, self.token)
        form.addRow(self.key_label, key_row)
        self.body.addWidget(self.real_box)

        self.status = label("Success")
        self.body.addWidget(self.status)

        self.demo.toggled.connect(self._mode_changed)
        self.url.textChanged.connect(self._reset)
        self.token.textChanged.connect(self._reset)
        self.key_button.clicked.connect(self._choose_key)
        self._mode_changed()

    def translate(self) -> None:
        tr = self.tr
        self.demo.setText(tr("ui.connect.demo"))
        self.demo_note.setText(tr("ui.connect.demo_note"))
        self.real.setText(tr("ui.connect.real"))
        self.real_note.setText(tr("ui.connect.real_note"))
        self.url_label.setText(tr("ui.connect.url"))
        self.token_label.setText(tr("ui.connect.token"))
        self.key_label.setText(tr("ui.connect.key"))
        self.url.setPlaceholderText(tr("ui.connect.url_hint"))
        self.key_button.setText(tr("ui.connect.choose_key"))
        self._show_key_status()
        self._show_status()

    # ---- mode, key and connection --------------------------------------------
    def _mode_changed(self) -> None:
        self.state.mode = "demo" if self.demo.isChecked() else "real"
        self.real_box.setVisible(self.state.mode == "real")
        self.state.key = None
        if self.state.mode == "real":
            try:
                self.state.key = identifiers.load_key()
            except (identifiers.PseudonymKeyMissing, identifiers.PseudonymKeyInvalid):
                self.state.key = None
        self._reset()
        self._show_key_status()

    def _choose_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("ui.connect.choose_key"))
        if not path:
            return
        try:
            self.state.key = identifiers.read_key_file(path)
            self.clear_error()
        except identifiers.PseudonymKeyInvalid:
            self.state.key = None
            self.show_error("ui.error.key_invalid")
        self._show_key_status()
        self.ctx.refresh_nav()

    def _show_key_status(self) -> None:
        self.key_status.setText(self.tr("ui.connect.key_set" if self.state.key else "ui.connect.key_missing"))

    def _reset(self) -> None:
        self.state.client = self.state.project = None
        self.state.stop_mock()
        self.state.forget_file()
        self.clear_error()
        self._show_status()
        self.ctx.refresh_nav()

    def _show_status(self) -> None:
        p = self.state.project
        self.status.setVisible(p is not None)
        if p:
            self.status.setText(self.tr("ui.connect.connected", project=p.title, version=p.version))

    # ---- navigation ------------------------------------------------------------
    def ready(self) -> bool:
        if self.state.project:
            return True
        if self.state.mode == "real":
            return bool(self.url.text().strip() and self.token.text().strip())
        return True

    def next_key(self) -> str:
        return "ui.nav.next" if self.state.project else "ui.nav.connect"

    def advance(self, proceed) -> None:
        if self.state.project:
            proceed()
            return
        self.clear_error()
        state, url, token = self.state, self.url.text().strip(), self.token.text().strip()
        default_profile = state.profiles.get("tbc03_so") or next(iter(state.profiles.values()))

        def work():
            if state.mode == "demo":
                state.stop_mock()
                state.mock = MockRedcap(build_dictionary(default_profile)).start()
                state.demo_key()
                client = RedcapClient(state.mock.url, state.mock.token)
            else:
                client = RedcapClient(url, token, timeout=state.target.timeout_seconds)
            return client, client.connect()

        def done(result):
            self.state.client, self.state.project = result
            self.ctx.set_busy(False)
            self._show_status()
            self.ctx.refresh_nav()

        def failed(key, params):
            self.ctx.set_busy(False)
            self.show_error(key, params)

        self.ctx.set_busy(True)
        workers.run(work, done, failed)
