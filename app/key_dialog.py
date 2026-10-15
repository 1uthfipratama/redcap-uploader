"""Windows for the pseudonym key: create one (and back it up), unlock one, back one up."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import paths
from app.widgets import label
from core.identifiers import PseudonymKeyInvalid
from core.keyfile import KEY_SUFFIX, MIN_PASSPHRASE, KeyFileExists, fingerprint, new_key, write_key

DEFAULT_NAME = "study-pseudonym" + KEY_SUFFIX
BACKUP_NAME = "study-pseudonym-backup" + KEY_SUFFIX


def _box(parent: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)
    return layout


def _password() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    return field


class PassphraseDialog(QDialog):
    """Ask for a passphrase: once to unlock a key file, or twice to protect a new copy."""

    def __init__(self, tr, *, new: bool, title_key: str, lead_key: str, parent=None):
        super().__init__(parent)
        self.tr, self.new = tr, new
        self.passphrase = ""
        self.setWindowTitle(tr(title_key))
        self.setMinimumWidth(460)
        layout = _box(self)
        layout.addWidget(label("Muted", tr(lead_key)))
        form = QFormLayout()
        self.first, self.second = _password(), _password()
        form.addRow(label("", tr("ui.key.passphrase"), wrap=False), self.first)
        if new:
            form.addRow(label("", tr("ui.key.passphrase_again"), wrap=False), self.second)
        layout.addLayout(form)
        if new:
            layout.addWidget(label("Muted", tr("ui.key.passphrase_hint")))
        self.problem = label("Error")
        self.problem.hide()
        layout.addWidget(self.problem)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel, ok = QPushButton(tr("ui.key.cancel")), QPushButton(tr("ui.key.ok"))
        ok.setObjectName("Primary")
        ok.setDefault(True)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._ok)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _ok(self) -> None:
        problem = passphrase_problem(self.first.text(), self.second.text()) if self.new else None
        if problem:
            self.problem.setText(self.tr(problem))
            self.problem.show()
            return
        self.passphrase = self.first.text()
        self.accept()


def passphrase_problem(first: str, second: str) -> str | None:
    if len(first) < MIN_PASSPHRASE:
        return "ui.key.problem_short"
    if first != second:
        return "ui.key.problem_mismatch"
    return None


class CreateKeyDialog(QDialog):
    """Create a key, save it protected by a passphrase, then save a backup copy."""

    def __init__(self, tr, *, replacing: bool, parent=None):
        super().__init__(parent)
        self.tr = tr
        self.key: bytes | None = None
        self.saved_to: Path | None = None
        self.backed_up = False
        self.setWindowTitle(tr("ui.key.create_title"))
        self.setMinimumWidth(560)
        self.pages = QStackedWidget()
        _box(self).addWidget(self.pages)
        self.pages.addWidget(self._first_page(replacing))
        self.pages.addWidget(self._second_page())

    # ---- step 1: passphrase and save -------------------------------------------------
    def _first_page(self, replacing: bool) -> QWidget:
        tr, page = self.tr, QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(label("", tr("ui.key.create_lead")))
        if replacing:
            layout.addWidget(label("Error", tr("ui.key.replace_warning")))
        form = QFormLayout()
        self.first, self.second = _password(), _password()
        form.addRow(label("", tr("ui.key.passphrase"), wrap=False), self.first)
        form.addRow(label("", tr("ui.key.passphrase_again"), wrap=False), self.second)
        layout.addLayout(form)
        layout.addWidget(label("Muted", tr("ui.key.passphrase_hint")))
        self.problem = label("Error")
        self.problem.hide()
        layout.addWidget(self.problem)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel, create = QPushButton(tr("ui.key.cancel")), QPushButton(tr("ui.key.create"))
        create.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        create.clicked.connect(self.create)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        layout.addLayout(buttons)
        return page

    def create(self) -> None:
        problem = passphrase_problem(self.first.text(), self.second.text())
        if problem:
            return self._show_problem(problem)
        path = self.ask_save_path(paths.keys_folder() / DEFAULT_NAME)
        if not path:
            return
        key = new_key()
        try:
            self.saved_to = write_key(path, key, self.first.text())
        except KeyFileExists:
            return self._show_problem("ui.key.problem_exists")
        except PseudonymKeyInvalid:
            return self._show_problem("ui.key.problem_location")
        self.key = key
        self.saved.setText(self.tr("ui.key.saved", path=str(self.saved_to), fingerprint=fingerprint(key)))
        self.pages.setCurrentIndex(1)

    def _show_problem(self, key: str) -> None:
        self.problem.setText(self.tr(key))
        self.problem.show()

    # ---- step 2: backup ------------------------------------------------------------------
    def _second_page(self) -> QWidget:
        tr, page = self.tr, QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.saved = label("Success")
        layout.addWidget(self.saved)
        layout.addWidget(label("", tr("ui.key.backup_lead")))
        self.backup_status = label("Success")
        self.backup_status.hide()
        layout.addWidget(self.backup_status)
        self.backup_problem = label("Error")
        self.backup_problem.hide()
        layout.addWidget(self.backup_problem)
        buttons = QHBoxLayout()
        self.backup_button = QPushButton(tr("ui.key.backup"))
        self.backup_button.setObjectName("Primary")
        self.backup_button.clicked.connect(self.backup)
        done = QPushButton(tr("ui.key.done"))
        done.clicked.connect(self.finish)
        buttons.addStretch(1)
        buttons.addWidget(self.backup_button)
        buttons.addWidget(done)
        layout.addLayout(buttons)
        return page

    def backup(self) -> None:
        path = self.ask_save_path(Path.home() / BACKUP_NAME)
        if not path:
            return
        try:
            written = write_key(path, self.key, self.first.text())
        except KeyFileExists:
            return self._backup_problem("ui.key.problem_exists")
        except PseudonymKeyInvalid:
            return self._backup_problem("ui.key.problem_location")
        if self.saved_to and Path(written).resolve() == self.saved_to.resolve():
            return self._backup_problem("ui.key.problem_exists")
        self.backed_up = True
        self.backup_problem.hide()
        self.backup_status.setText(self.tr("ui.key.backup_saved", path=str(written)))
        self.backup_status.show()

    def _backup_problem(self, key: str) -> None:
        self.backup_problem.setText(self.tr(key))
        self.backup_problem.show()

    def finish(self) -> None:
        if self.backed_up or self.confirm_no_backup():
            self.accept()

    # ---- seams for tests -----------------------------------------------------------------
    def ask_save_path(self, default: Path) -> str:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.key.create_title"), str(default),
                                              f"{self.tr('ui.key.files')} (*{KEY_SUFFIX})")
        return path

    def confirm_no_backup(self) -> bool:
        answer = QMessageBox.question(self, self.tr("ui.key.no_backup_title"), self.tr("ui.key.no_backup"),
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes
