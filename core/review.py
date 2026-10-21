"""Corrections a person makes between the check and the upload: edited cells and skipped rows.

The prepared table is never changed. Edits and skips are layered on top of it and
the whole table is checked again after each one, so the problems shown always
describe what would be sent. Nothing is dropped silently: every edit and every
skipped row is kept, with its row number, and goes into the upload log.

Only uploaded data fields can be edited. Fields made from an identifier (record
ID and the pseudonym fields) cannot, so an identifier can neither be typed in
nor changed here. Rows are named by their spreadsheet row number, never by an
identifier.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from core.issues import Issue
from core.parse import ROW, convert_text
from core.pipeline import Prepared, redcap_value as show
from core.profile import ColumnSpec, Role
from core.validate import validate

SKIPPED_BY_CHOICE = "chosen"
SKIPPED_FOR_ERRORS = "errors"


@dataclass(frozen=True)
class Edit:
    row: int
    field: str
    original: object  # the value in the table before any edit; None means blank
    new: object


class EditRejected(ValueError):
    """The text could not be read as a value of that field. `issue` says why, in the usual way."""

    def __init__(self, issue: Issue):
        super().__init__(issue.code)
        self.issue = issue


class Review:
    def __init__(self, base: Prepared, today: dt.date | None = None):
        self.base = base
        self.today = today
        self.edits: dict[tuple[int, str], Edit] = {}
        self.skipped: dict[int, str] = {}  # spreadsheet row -> why
        self.effective: Prepared = base  # the table as it would be sent, with its problems
        frame = base.frame
        self._position = {} if frame is None else {int(r): i for i, r in enumerate(frame[ROW])}
        self._specs: dict[str, ColumnSpec] = {}
        if frame is not None:
            for col in base.profile.columns:
                if col.field in frame.columns and (col.role == Role.data or (col.role == Role.quasi_identifier and col.keep)):
                    self._specs[col.field] = col

    # ---- what can be changed -------------------------------------------------------
    def spec(self, field: str) -> ColumnSpec | None:
        """The column's rules if its value may be edited, else None."""
        return self._specs.get(field)

    def has_row(self, row: int) -> bool:
        return row in self._position

    @property
    def changed(self) -> bool:
        return bool(self.edits or self.skipped)

    def original(self, row: int, field: str) -> object:
        return self.base.frame[field].iat[self._position[row]]

    def value(self, row: int, field: str) -> object:
        """The value now: the edit if there is one, else what the file held."""
        edit = self.edits.get((row, field))
        return edit.new if edit else self.original(row, field)

    # ---- edits -----------------------------------------------------------------------
    def parse(self, field: str, text: str) -> object:
        """The typed value for text entered in `field`. Blank text means an empty cell.

        A choice takes its code. Raises EditRejected, with the same problem a file would have
        had, when the text is not a value of that type. A value that is readable but breaks a
        rule (an age of 212) is accepted; the check that follows reports it.
        """
        spec = self._specs[field]
        text = text.strip()
        if not text:
            return None
        row = 0  # the message is shown next to the cell; the row number is not part of it
        if spec.type == "choice":
            codes = {c.code for c in self.base.profile.choices_for(spec)}
            if text not in codes:
                raise EditRejected(Issue("choice_unknown", row=row, field=field, params={"value": text}))
            return text
        value, issues = convert_text(text, spec, self.base.profile.layout.date_format, row)
        if issues:
            raise EditRejected(issues[0])
        return value

    def set_value(self, row: int, field: str, text: str) -> Edit | None:
        """Edit one cell. Returns the edit, or None when the text is the original value (the edit is undone)."""
        if field not in self._specs or row not in self._position:
            raise KeyError((row, field))
        new = self.parse(field, text)
        original = self.original(row, field)
        if _same(new, original):
            self.edits.pop((row, field), None)
            edit = None
        else:
            edit = self.edits[(row, field)] = Edit(row, field, original, new)
        self._refresh()
        return edit

    def reset(self, row: int, field: str) -> None:
        if self.edits.pop((row, field), None) is not None:
            self._refresh()

    # ---- skipped rows ------------------------------------------------------------------
    def skip(self, rows: Iterable[int], reason: str = SKIPPED_BY_CHOICE) -> None:
        for row in rows:
            if row in self._position:
                self.skipped.setdefault(row, reason)
        self._refresh()

    def restore(self, rows: Iterable[int]) -> None:
        for row in rows:
            self.skipped.pop(row, None)
        self._refresh()

    def skip_rows_with_errors(self) -> int:
        """Skip every row that has an error. Returns how many rows were skipped."""
        rows = {i.row for i in self.effective.errors if i.row in self._position and i.row not in self.skipped}
        self.skip(rows, SKIPPED_FOR_ERRORS)
        return len(rows)

    # ---- the table as it would be sent ------------------------------------------------
    def _refresh(self) -> None:
        base = self.base
        if base.frame is None:
            return
        frame = base.frame.copy()
        for (row, field), edit in self.edits.items():
            frame.at[frame.index[self._position[row]], field] = edit.new
        if self.skipped:
            frame = frame[~frame[ROW].isin(list(self.skipped))].reset_index(drop=True)
        read = [i for i in base.read_issues if not self._settled(i)]
        issues = read + validate(frame, base.profile, base.unmapped, today=self.today, already=read)
        self.effective = dataclasses.replace(base, frame=frame, issues=issues, read_issues=read)

    def _settled(self, issue: Issue) -> bool:
        """A problem found while reading is gone once its row is skipped or its cell is edited."""
        return issue.row in self.skipped or (issue.row, issue.field) in self.edits

    # ---- the record of what was done ----------------------------------------------------
    def log(self) -> dict:
        """Row numbers, fields and values for the upload log. Free-text values are left out of it."""
        edited = []
        for edit in sorted(self.edits.values(), key=lambda e: (e.row, e.field)):
            entry = {"row": edit.row, "field": edit.field}
            if self._specs[edit.field].type != "text":
                entry |= {"from": show(edit.original), "to": show(edit.new)}
            edited.append(entry)
        skipped = [{"row": row, "reason": why} for row, why in sorted(self.skipped.items())]
        return {"edited": edited, "skipped": skipped}


def _same(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return show(a) == show(b)
