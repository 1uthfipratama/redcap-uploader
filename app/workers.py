"""Run slow work (reading files, talking to REDCap) off the UI thread.

Errors never reach the user as a stack trace: the worker turns them into an
i18n message key, and the detail goes to the log (which never holds the token).
"""

from __future__ import annotations

import logging
import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.client import ApiError, ConnectionFailed, InvalidSettings
from core.dictionary import RecordIdDiffers
from core.grid import UnsupportedFile
from core.identifiers import PseudonymKeyInvalid, PseudonymKeyMissing
from core.project_setup import FieldsConflict, ProjectInProduction

log = logging.getLogger("redcap_uploader.app")


def error_key(exc: BaseException) -> tuple[str, dict]:
    """The message key (and parameters) for an error the user should see."""
    if isinstance(exc, ConnectionFailed):
        return "ui.error.connection", {}
    if isinstance(exc, InvalidSettings):
        return f"ui.error.{exc.what}", {}
    if isinstance(exc, ApiError):
        return "ui.error.api", {"message": exc.message[:300]}
    if isinstance(exc, PseudonymKeyMissing):
        return "ui.error.key_missing", {}
    if isinstance(exc, PseudonymKeyInvalid):
        return "ui.error.key_invalid", {}
    if isinstance(exc, UnsupportedFile):
        return "ui.error.file_type", {}
    if isinstance(exc, ProjectInProduction):
        return "ui.error.project_in_production", {}
    if isinstance(exc, FieldsConflict):
        return "ui.error.fields_conflict", {"fields": ", ".join(c.field for c in exc.conflicts[:6])}
    if isinstance(exc, RecordIdDiffers):
        return "ui.error.record_id_differs", {"field": exc.field_name}
    if isinstance(exc, (OSError, ValueError)):
        return "ui.error.file_read", {}
    return "ui.error.unexpected", {}


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str, dict)
    progress = Signal(int, int)


class _Job(QRunnable):
    def __init__(self, fn: Callable, signals: _Signals, with_progress: bool):
        super().__init__()
        self.fn, self.signals, self.with_progress = fn, signals, with_progress

    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit) if self.with_progress else self.fn()
        except BaseException as exc:  # noqa: BLE001 - every error becomes a plain message
            key, params = error_key(exc)
            log.error("background task failed: %s\n%s", type(exc).__name__, traceback.format_exc(limit=8))
            self.signals.failed.emit(key, params)
            return
        self.signals.done.emit(result)


_live: set[_Signals] = set()  # keep signal objects alive until their job reports back


def run(fn: Callable, on_done: Callable[[object], None], on_failed: Callable[[str, dict], None],
        on_progress: Callable[[int, int], None] | None = None) -> None:
    """Run fn on the thread pool. With on_progress, fn receives a report(i, n) callable."""
    signals = _Signals()
    _live.add(signals)

    def finish(callback):
        def handler(*args):
            _live.discard(signals)
            callback(*args)
        return handler

    signals.done.connect(finish(on_done))
    signals.failed.connect(finish(on_failed))
    if on_progress:
        signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(_Job(fn, signals, on_progress is not None))
