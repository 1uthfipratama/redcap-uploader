"""Problems found while reading, cleaning or validating a file.

An Issue carries a message key and parameters, never finished text, so the UI
can show it in either language (see core/messages.py and i18n/). Parameters
must never hold a raw identifier value.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str = ERROR
    row: int | None = None  # 1-based row number as the user sees it in the spreadsheet
    field: str | None = None
    params: dict = dc_field(default_factory=dict, hash=False, compare=False)

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.is_error]


def warnings(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if not i.is_error]
