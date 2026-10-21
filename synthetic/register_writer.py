"""Write a spreadsheet in the layout of a SITB register export, from a profile.

The layout matches the real files: two empty leading columns, a title block,
a four-row merged header, a row of official column numbers, the data rows and
a trailing blank row. Values come from the caller; this module never reads a
real export. Used by the tests now and by the synthetic data generator later.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from core.profile import Profile

FIRST_COL = 2
HEADER_START = 12  # 0-based, as in the real files (row 13 in Excel)
HEADER_ROWS = 4
NUMBER_ROW = HEADER_START + HEADER_ROWS  # row 17 in Excel
FIRST_DATA_ROW = NUMBER_ROW + 1


@dataclass
class TitleBlock:
    facility: str = "FASYANKES SINTETIS"
    facility_code: str = "0000000"
    facility_type: str = "Rumah Sakit"
    district: str = "Kota Sintetis"
    province: str = "Provinsi Sintetis"
    period: str = "Januari - Desember 2025"
    form_line: str = ""  # e.g. "TBC.03 SO FASYANKES"; defaults from the profile
    edition: str = ""
    include_case_count: bool = True
    stated_case_count: int | None = None  # None = the real number of data rows


@dataclass
class RegisterSpec:
    rows: list[dict[str, object]]  # column key -> value; missing keys are blank
    title: TitleBlock = field(default_factory=TitleBlock)
    label_overrides: dict[str, str] = field(default_factory=dict)  # key -> header text to show instead
    drop_keys: set[str] = field(default_factory=set)  # columns to leave out of the file
    summary_row: bool = False  # add a "Jumlah" row after the data
    blank_rows_after: list[int] = field(default_factory=list)  # insert a blank row after these data indexes
    extra_top_rows: int = 0  # shift everything down, to test header detection
    date_as_text: bool = True


def _header_parts(profile: Profile, key: str, overrides: dict[str, str]) -> list[str]:
    col = profile.column(key)
    parts = col.label_id.split(" > ") if col.label_id else [col.label]
    if key in overrides:
        parts = parts[:-1] + [overrides[key]]
    return parts[:HEADER_ROWS]


def _cell_value(value: object, date_as_text: bool) -> object:
    if isinstance(value, dt.date) and date_as_text:
        return value.strftime("%d/%m/%Y")
    return value


def build_cells(profile: Profile, spec: RegisterSpec):
    """Returns (cells dict {(r, c): value}, merges [(r1, r2, c1, c2) inclusive], ncols)."""
    keys = [c.key for c in profile.columns if c.key not in spec.drop_keys]
    col_of = {k: FIRST_COL + i for i, k in enumerate(keys)}
    off = spec.extra_top_rows
    cells: dict[tuple[int, int], object] = {}
    merges: list[tuple[int, int, int, int]] = []
    paths = {k: _header_parts(profile, k, spec.label_overrides) for k in keys}

    # Header: group labels merged across the columns that share them, last part merged down.
    for level in range(HEADER_ROWS):
        i = 0
        while i < len(keys):
            path = paths[keys[i]]
            if level >= len(path):
                i += 1
                continue
            j = i
            if level < len(path) - 1:
                while j + 1 < len(keys) and paths[keys[j + 1]][: level + 1] == path[: level + 1] and len(paths[keys[j + 1]]) > level + 1:
                    j += 1
            r = off + HEADER_START + level
            cells[(r, col_of[keys[i]])] = path[level]
            last_row = r if level < len(path) - 1 else off + HEADER_START + HEADER_ROWS - 1
            if j > i or last_row > r:
                merges.append((r, last_row, col_of[keys[i]], col_of[keys[j]]))
            i = j + 1

    # Official numbers, once per number (sub-columns share it).
    seen_numbers: set[int] = set()
    for k in keys:
        number = profile.column(k).number
        if number is not None and number not in seen_numbers:
            cells[(off + NUMBER_ROW, col_of[k])] = f"({number})"
            seen_numbers.add(number)

    ncols = FIRST_COL + len(keys) + 1
    _title(profile, spec, cells, off, ncols)

    r = off + FIRST_DATA_ROW
    for i, row in enumerate(spec.rows):
        for k, v in row.items():
            if k in col_of and v is not None:
                cells[(r, col_of[k])] = _cell_value(v, spec.date_as_text)
        r += 1
        if i in spec.blank_rows_after:
            r += 1
    if spec.summary_row:
        cells[(r, FIRST_COL)] = "Jumlah"
        cells[(r, FIRST_COL + 1)] = len(spec.rows)
        r += 1
    cells[(r, FIRST_COL)] = ""  # one trailing blank row, as in the real files
    return cells, merges, ncols, r + 1


def _title(profile: Profile, spec: RegisterSpec, cells, off: int, ncols: int) -> None:
    t = spec.title
    right = ncols - 3
    form_line = t.form_line or f"{profile.identity.recognition[0] if profile.identity.recognition else 'FORM'} FASYANKES"
    cells[(off + 2, FIRST_COL)] = "PENANGGULANGAN TBC NASIONAL"
    cells[(off + 2, right)] = form_line
    cells[(off + 3, FIRST_COL)] = "REGISTER PASIEN TBC (SINTETIS)"
    cells[(off + 3, right)] = t.edition or profile.identity.edition
    pairs = [("Nama Fasyankes", t.facility), ("Kode Fasyankes", t.facility_code), ("Jenis Fasyankes", t.facility_type),
             ("Kabupaten/ Kota", t.district), ("Provinsi", t.province), ("Periode", t.period)]
    for i, (label, value) in enumerate(pairs):
        cells[(off + 5 + i, FIRST_COL)] = label
        cells[(off + 5 + i, FIRST_COL + 2)] = value
    if t.include_case_count and profile.layout.case_count_label:
        cells[(off + 6, right - 5)] = profile.layout.case_count_label
        cells[(off + 6, right)] = t.stated_case_count if t.stated_case_count is not None else len(spec.rows)


def data_row_numbers(spec: RegisterSpec) -> list[int]:
    """The 1-based spreadsheet row of each data row, after any inserted blank rows."""
    rows, r = [], spec.extra_top_rows + FIRST_DATA_ROW
    for i in range(len(spec.rows)):
        rows.append(r + 1)
        r += 1
        if i in spec.blank_rows_after:
            r += 1
    return rows


def summary_row_number(spec: RegisterSpec) -> int | None:
    if not spec.summary_row:
        return None
    rows = data_row_numbers(spec)
    last = rows[-1] if rows else spec.extra_top_rows + FIRST_DATA_ROW
    return last + 1 + (1 if spec.rows and len(spec.rows) - 1 in spec.blank_rows_after else 0)


def write_register(path: str | Path, profile: Profile, spec: RegisterSpec) -> Path:
    path = Path(path)
    cells, merges, ncols, nrows = build_cells(profile, spec)
    if path.suffix.lower() == ".xls":
        _write_xls(path, cells, merges)
    elif path.suffix.lower() == ".xlsx":
        _write_xlsx(path, cells, merges)
    else:
        raise ValueError(path.suffix)
    return path


def _write_xls(path: Path, cells, merges) -> None:
    import xlwt  # dev-only dependency

    book = xlwt.Workbook()
    sheet = book.add_sheet("Sheet1")
    merged_origins = set()
    for r1, r2, c1, c2 in merges:
        sheet.write_merge(r1, r2, c1, c2, cells.get((r1, c1)))
        merged_origins.add((r1, c1))
    for (r, c), v in cells.items():
        if (r, c) not in merged_origins:
            sheet.write(r, c, v)
    book.save(str(path))


def _write_xlsx(path: Path, cells, merges) -> None:
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    for (r, c), v in cells.items():
        sheet.cell(row=r + 1, column=c + 1, value=v)
    for r1, r2, c1, c2 in merges:
        sheet.merge_cells(start_row=r1 + 1, start_column=c1 + 1, end_row=r2 + 1, end_column=c2 + 1)
    book.save(str(path))
