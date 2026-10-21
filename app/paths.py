"""Folders the app writes to: Documents/REDCap Uploader, or REDCAP_UPLOADER_HOME when it is set."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

HOME_ENV = "REDCAP_UPLOADER_HOME"
APP_FOLDER = "REDCap Uploader"


def home() -> Path:
    if os.environ.get(HOME_ENV):
        return Path(os.environ[HOME_ENV])
    documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or str(Path.home())
    return Path(documents) / APP_FOLDER


def profiles_folder() -> Path:
    """Forms the person created from their own spreadsheets."""
    return home() / "Profiles"


def keys_folder() -> Path:
    """The suggested place for a new key file (protected by a passphrase)."""
    return home() / "Keys"


def backups_folder() -> Path:
    """Copies of a project's data dictionary, saved before the app adds fields to it."""
    return home() / "Dictionary backups"
