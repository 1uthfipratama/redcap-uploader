"""Step 1: Demo (built-in mock) or Real (URL and token), then connect."""

from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QRadioButton, QWidget

from pathlib import Path

from app import workers
from app.key_dialog import BACKUP_NAME, CreateKeyDialog, PassphraseDialog
from app.pages.base import StepPage
from app.widgets import label
from core import identifiers, keyfile
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
        self.create_key_button = QPushButton()
        self.backup_key_button = QPushButton()
        key_row.addWidget(self.key_status, 1)
        for button in (self.backup_key_button, self.create_key_button, self.key_button):
            key_row.addWidget(button)
        self.url_label, self.token_label, self.key_label = label(), label(), label()
        form.addRow(self.url_label, self.url)
        form.addRow(self.token_label, self.token)
        form.addRow(self.key_label, key_row)
        self.body.addWidget(self.real_box)

        self.key_note = label("Success")
        self.key_note.hide()
        self.body.addWidget(self.key_note)
        self.status = label("Success")
        self.body.addWidget(self.status)
        self._real_key: bytes | None = None  # kept while switching between Demo and Real

        self.demo.toggled.connect(self._mode_changed)
        self.url.textChanged.connect(self._reset)
        self.token.textChanged.connect(self._reset)
        self.key_button.clicked.connect(self._choose_key)
        self.create_key_button.clicked.connect(self._create_key)
        self.backup_key_button.clicked.connect(self._backup_key)
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
        self.create_key_button.setText(tr("ui.connect.create_key"))
        self.backup_key_button.setText(tr("ui.connect.backup_key"))
        self._show_key_status()
        self._show_status()

    def teaching(self):
        tr = self.tr
        mode = tr("ui.teach.connect_demo") if self.state.mode == "demo" else tr("ui.teach.connect_real")
        return [mode, tr("ui.teach.connect_token"), tr("ui.teach.connect_calls")], self.requests_here()

    # ---- mode, key and connection --------------------------------------------
    def _mode_changed(self) -> None:
        self.state.mode = "demo" if self.demo.isChecked() else "real"
        self.real_box.setVisible(self.state.mode == "real")
        self.state.key = None
        if self.state.mode == "real":
            self.state.key = self._real_key
            if self.state.key is None:
                try:
                    self.state.key = identifiers.load_key()
                except (identifiers.PseudonymKeyMissing, identifiers.PseudonymKeyInvalid):
                    self.state.key = None
        self._reset()
        self._show_key_status()

    def _set_key(self, key: bytes | None) -> None:
        self.state.key = self._real_key = key
        self._show_key_status()
        self.ctx.refresh_nav()

    def _choose_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("ui.connect.choose_key"), str(Path.home()),
                                              f"{self.tr('ui.key.files')} (*{keyfile.KEY_SUFFIX} *.txt)")
        if path:
            self.load_key(path)

    def load_key(self, path: str, passphrase: str | None = None) -> None:
        """Load a key file, asking for its passphrase when it is protected."""
        self.key_note.hide()
        try:
            key = keyfile.read_key(path, passphrase)
        except keyfile.PassphraseNeeded:
            passphrase = self.ask_passphrase()
            if passphrase is not None:
                self.load_key(path, passphrase)
            return
        except keyfile.WrongPassphrase:
            self._set_key(None)
            self.show_error("ui.error.key_passphrase")
            return
        except identifiers.PseudonymKeyInvalid:
            self._set_key(None)
            self.show_error("ui.error.key_invalid")
            return
        self.clear_error()
        self._set_key(key)

    def _create_key(self) -> None:
        self.key_note.hide()
        dialog = CreateKeyDialog(self.tr, replacing=self.state.key is not None, parent=self)
        if self.open_dialog(dialog) and dialog.key:
            self.clear_error()
            self._set_key(dialog.key)

    def _backup_key(self) -> None:
        passphrase = self.ask_passphrase(new=True)
        if passphrase is None:
            return
        path = self.ask_save_path(Path.home() / BACKUP_NAME)
        if not path:
            return
        try:
            written = keyfile.write_key(path, self.state.key, passphrase)
        except keyfile.KeyFileExists:
            self.show_error("ui.key.problem_exists")
            return
        except identifiers.PseudonymKeyInvalid:
            self.show_error("ui.key.problem_location")
            return
        self.clear_error()
        self.key_note.setText(self.tr("ui.key.backup_saved", path=str(written)))
        self.key_note.show()

    # ---- seams for tests ---------------------------------------------------------------
    def ask_passphrase(self, new: bool = False) -> str | None:
        keys = ("ui.key.backup_title", "ui.key.backup_passphrase_lead") if new else (
            "ui.key.unlock_title", "ui.key.unlock_lead")
        dialog = PassphraseDialog(self.tr, new=new, title_key=keys[0], lead_key=keys[1], parent=self)
        return dialog.passphrase if dialog.exec() == QDialog.DialogCode.Accepted else None

    def ask_save_path(self, default: Path) -> str:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.key.backup_title"), str(default),
                                              f"{self.tr('ui.key.files')} (*{keyfile.KEY_SUFFIX})")
        return path

    def open_dialog(self, dialog) -> bool:
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _show_key_status(self) -> None:
        key = self.state.key if self.state.mode == "real" else None
        self.key_status.setText(self.tr("ui.connect.key_set", fingerprint=keyfile.fingerprint(key)) if key
                                else self.tr("ui.connect.key_missing"))
        self.backup_key_button.setVisible(key is not None)

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
