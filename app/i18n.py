"""The current interface language and a tr() for every visible string.

All text comes from i18n/<lang>.json (keys starting with "ui."); nothing visible
is written in app/ code. Switching language emits `changed`, and every screen
re-reads its text.
"""

from __future__ import annotations

from PySide6.QtCore import QLocale, QObject, Signal

from core import messages
from core.issues import Issue


class Translator(QObject):
    changed = Signal(str)

    def __init__(self, lang: str | None = None):
        super().__init__()
        self.lang = lang or default_language()

    def set_language(self, lang: str) -> None:
        if lang in messages.LANGUAGES and lang != self.lang:
            self.lang = lang
            self.changed.emit(lang)

    def __call__(self, key: str, **params) -> str:
        return messages.text(key, self.lang, **params)

    def describe(self, issue: Issue) -> str:
        return messages.describe(issue, self.lang)

    def fix(self, issue: Issue) -> str:
        return messages.suggest_fix(issue, self.lang)

    def problem(self, issue: Issue) -> str:
        """The message alone, without the "Row 14, age:" prefix (for tables with their own columns)."""
        params = {"row": issue.row, "field": issue.field, **issue.params}
        text = messages.text(f"issue.{issue.code}", self.lang, **params)
        return text[:1].upper() + text[1:]


def default_language() -> str:
    """Follows the operating system: Indonesian on an Indonesian system, English otherwise."""
    return "id" if QLocale.system().name().lower().startswith("id") else "en"
