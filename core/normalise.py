"""Map each choice column's spellings to REDCap choice codes.

A spelling matches a choice when, ignoring case and extra spaces, it equals the
choice's label, its code, or one of its listed spellings. Every spelling that
was changed is listed, and every spelling that could not be mapped is reported
and left as it was (validation then flags it). Nothing is guessed: "Tidak
diketahui" keeps its own code and is never folded into "no" or blank.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field as dc_field

import pandas as pd

from core.parse import ROW
from core.profile import Choice, Profile

MAX_EXAMPLE_ROWS = 10


@dataclass
class SpellingChange:
    field: str
    spelling: str
    code: str
    label: str
    count: int


@dataclass
class UnmappedSpelling:
    field: str
    spelling: str
    count: int
    rows: list[int] = dc_field(default_factory=list)  # first few rows only


@dataclass
class NormaliseResult:
    frame: pd.DataFrame
    changes: list[SpellingChange] = dc_field(default_factory=list)
    unmapped: list[UnmappedSpelling] = dc_field(default_factory=list)


def spelling_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def lookup_table(choices: list[Choice]) -> dict[str, Choice]:
    """What a file may write, to the answer it means. Labels and spellings come first and codes last, so
    when codes were changed (1 and 2 swapped) the values the file wrote still find their own answer."""
    table: dict[str, Choice] = {}
    for choice in choices:
        for spelling in (choice.label_id, *choice.spellings):
            table.setdefault(spelling_key(spelling), choice)
    for choice in choices:
        table.setdefault(spelling_key(choice.code), choice)
    return table


def normalise(frame: pd.DataFrame, profile: Profile) -> NormaliseResult:
    """Frame columns are REDCap field names (after mapping)."""
    out = frame.copy()
    result = NormaliseResult(frame=out)
    for col in profile.columns:
        if col.type != "choice" or not col.field or col.field not in out.columns:
            continue
        table = lookup_table(profile.choices_for(col))
        changed: Counter = Counter()
        unmapped_rows: dict[str, list[int]] = defaultdict(list)
        new_values = []
        for row, value in zip(out[ROW], out[col.field]):
            if value is None:
                new_values.append(None)
                continue
            text = str(value).strip()
            choice = table.get(spelling_key(text))
            if choice is None:
                unmapped_rows[text].append(int(row))
                new_values.append(text)
                continue
            if text != choice.label_id and text != choice.code:
                changed[(text, choice.code, choice.label_id)] += 1
            new_values.append(choice.code)
        out[col.field] = pd.Series(new_values, index=out.index, dtype=object)
        result.changes += [SpellingChange(col.field, s, c, label, n) for (s, c, label), n in changed.most_common()]
        result.unmapped += [UnmappedSpelling(col.field, s, len(rows), rows[:MAX_EXAMPLE_ROWS])
                            for s, rows in sorted(unmapped_rows.items(), key=lambda kv: -len(kv[1]))]
    return result
