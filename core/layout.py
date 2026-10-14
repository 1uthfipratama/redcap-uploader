"""Find the structure of a register export: title block, header rows, official
column numbers, data rows, and blank or summary rows to skip.

Two kinds of sheet are recognised:
- "numbered": a SITB-style register with a multi-row merged header and a row of
  official column numbers such as (1) (2) ... (84). Numbers are the stable keys.
- "single_header": any sheet whose first non-blank row is the header (Generic).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.grid import Grid

NUMBER_RE = re.compile(r"^\((\d+)\)$")
DEFAULT_SUMMARY_PATTERN = r"^(jumlah|total)\b"
HEADER_SCAN_ROWS = 80


@dataclass
class SheetColumn:
    """One sheet column as the file presents it."""

    sheet_col: int
    key: str
    header_path: tuple[str, ...]
    number: int | None = None
    sub_label: str = ""

    @property
    def label(self) -> str:
        return self.header_path[-1] if self.header_path else ""

    @property
    def header_text(self) -> str:
        return " > ".join(self.header_path)


@dataclass
class Layout:
    kind: str  # "numbered" or "single_header"
    title_text: list[str]
    metadata: dict[str, str]
    header_start: int
    number_row: int | None
    first_data_row: int
    columns: list[SheetColumn]
    data_rows: list[int] = field(default_factory=list)
    blank_rows: list[int] = field(default_factory=list)
    summary_rows: list[int] = field(default_factory=list)

    def column(self, key: str) -> SheetColumn | None:
        return next((c for c in self.columns if c.key == key), None)


def normalise_label(text: str) -> str:
    """Case-folded label with single spaces and no trailing colon, for comparisons."""
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip().casefold()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def detect_layout(grid: Grid, summary_pattern: str = DEFAULT_SUMMARY_PATTERN) -> Layout:
    number_row = _find_number_row(grid)
    if number_row is None:
        return _single_header_layout(grid, summary_pattern)
    header_start = _find_header_start(grid, number_row)
    columns = _numbered_columns(grid, header_start, number_row)
    title_text, metadata = _read_title_block(grid, header_start)
    layout = Layout(
        kind="numbered",
        title_text=title_text,
        metadata=metadata,
        header_start=header_start,
        number_row=number_row,
        first_data_row=number_row + 1,
        columns=columns,
    )
    _classify_rows(grid, layout, summary_pattern)
    return layout


def _find_number_row(grid: Grid) -> int | None:
    """The row holding (1), (2), ... The first number must be 1."""
    for r in range(min(grid.nrows, HEADER_SCAN_ROWS)):
        numbers = [int(m.group(1)) for c in range(grid.ncols) if (m := NUMBER_RE.match(grid.text(r, c)))]
        if len(numbers) >= 3 and min(numbers) == 1:
            return r
    return None


def _row_continues_merge(grid: Grid, r: int) -> bool:
    return any(r0 < r < r1 for r0, r1, _, _ in grid.merged)


def _find_header_start(grid: Grid, number_row: int) -> int:
    """Walk up from the number row while rows hold header text or continue a merge."""
    r = number_row - 1
    while r >= 0 and (not grid.row_is_blank(r) or _row_continues_merge(grid, r)):
        r -= 1
    return r + 1


def _header_path(grid: Grid, c: int, header_start: int, number_row: int) -> tuple[str, ...]:
    parts: list[str] = []
    for r in range(header_start, number_row):
        r0, c0 = grid.merged_origin(r, c)
        text = re.sub(r"\s+", " ", grid.text(r0, c0)).strip()
        if text and (not parts or parts[-1] != text):
            parts.append(text)
    return tuple(parts)


def _own_header_text(grid: Grid, c: int, header_start: int, number_row: int) -> bool:
    """True if some header cell in this column has text of its own, not inherited from a merge to the left."""
    for r in range(header_start, number_row):
        r0, c0 = grid.merged_origin(r, c)
        if c0 == c and grid.text(r0, c0):
            return True
    return False


def _numbered_columns(grid: Grid, header_start: int, number_row: int) -> list[SheetColumn]:
    groups: list[list[SheetColumn]] = []
    for c in range(grid.ncols):
        match = NUMBER_RE.match(grid.text(number_row, c))
        path = _header_path(grid, c, header_start, number_row)
        if match:
            groups.append([SheetColumn(sheet_col=c, key="", header_path=path, number=int(match.group(1)))])
        elif groups and _own_header_text(grid, c, header_start, number_row):
            # A sub-column of the previous number, such as the culture half of a smear/culture pair.
            groups[-1].append(SheetColumn(sheet_col=c, key="", header_path=path, number=groups[-1][0].number))
    columns: list[SheetColumn] = []
    for group in groups:
        number = group[0].number
        if len(group) == 1:
            group[0].key = f"c{number:03d}"
            columns.append(group[0])
            continue
        seen: set[str] = set()
        for i, col in enumerate(group, start=1):
            col.sub_label = col.label
            suffix = slug(col.sub_label) or str(i)
            if suffix in seen:
                suffix = f"{suffix}_{i}"
            seen.add(suffix)
            col.key = f"c{number:03d}_{suffix}"
            columns.append(col)
    return columns


def _read_title_block(grid: Grid, header_start: int) -> tuple[list[str], dict[str, str]]:
    """All text above the header, plus label/value pairs read left to right in each row."""
    title_text: list[str] = []
    metadata: dict[str, str] = {}
    for r in range(header_start):
        cells = [grid.text(r, c) for c in range(grid.ncols) if grid.text(r, c)]
        title_text.extend(cells)
        for label, value in zip(cells[0::2], cells[1::2]):
            metadata[normalise_label(label)] = value
    return title_text, metadata


def _classify_rows(grid: Grid, layout: Layout, summary_pattern: str) -> None:
    summary_re = re.compile(summary_pattern, re.IGNORECASE)
    cols = [col.sheet_col for col in layout.columns]
    for r in range(layout.first_data_row, grid.nrows):
        texts = [grid.text(r, c) for c in cols]
        filled = [t for t in texts if t]
        if not filled:
            layout.blank_rows.append(r)
        elif summary_re.search(filled[0]):
            layout.summary_rows.append(r)
        else:
            layout.data_rows.append(r)


def _single_header_layout(grid: Grid, summary_pattern: str) -> Layout:
    header_row = next((r for r in range(grid.nrows) if not grid.row_is_blank(r)), 0)
    columns: list[SheetColumn] = []
    seen: set[str] = set()
    for c in range(grid.ncols):
        text = grid.text(header_row, c)
        if not text:
            continue
        key = slug(text) or f"col{c + 1}"
        if key in seen:
            key = f"{key}_{c + 1}"
        seen.add(key)
        columns.append(SheetColumn(sheet_col=c, key=key, header_path=(text,)))
    layout = Layout(
        kind="single_header",
        title_text=[],
        metadata={},
        header_start=header_row,
        number_row=None,
        first_data_row=header_row + 1,
        columns=columns,
    )
    _classify_rows(grid, layout, summary_pattern)
    return layout
