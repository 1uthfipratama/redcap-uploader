"""Turn Issues into plain-language text in Indonesian or English.

All wording lives in i18n/<lang>.json; this module only fills in the blanks.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.issues import Issue

I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
LANGUAGES = ("id", "en")


@lru_cache(maxsize=None)
def strings(lang: str) -> dict[str, str]:
    with open(I18N_DIR / f"{lang}.json", encoding="utf-8") as fh:
        return json.load(fh)


def text(key: str, lang: str = "id", **params) -> str:
    template = strings(lang).get(key, key)
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def describe(issue: Issue, lang: str = "id") -> str:
    """One sentence: where, what is wrong."""
    params = {"row": issue.row, "field": issue.field, **issue.params}
    message = text(f"issue.{issue.code}", lang, **params)
    if issue.row is not None and issue.field:
        prefix = text("where.row_field", lang, row=issue.row, field=issue.field)
    elif issue.row is not None:
        prefix = text("where.row", lang, row=issue.row)
    elif issue.field:
        prefix = text("where.field", lang, field=issue.field)
    else:
        return message
    return f"{prefix}: {message}"


def suggest_fix(issue: Issue, lang: str = "id") -> str:
    params = {"row": issue.row, "field": issue.field, **issue.params}
    key = f"fix.{issue.code}"
    return text(key, lang, **params) if key in strings(lang) else ""
