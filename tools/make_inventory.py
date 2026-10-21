"""Write a structure-only column inventory from one or more real register exports.

This is the only code in the repo that opens a real export. It prints nothing
from the data rows and writes only:
- per column: official number, header, inferred type, fill rate, distinct count,
  uniqueness share and a suggested role;
- for low-cardinality, non-identifier columns: the spellings seen at least
  MIN_COUNT times (rarer spellings are counted, never listed).

Nothing that says where an export came from is written: columns and title-block
labels that name a facility or a place (SITE_RE) never list their values, and
those title values show as <value>.

Run it on the approved machine, read the output, then commit it:

    python -m tools.make_inventory synthetic/forms/tbc03_so FILE.xls [FILE.xls ...]

It writes <out>_columns.csv and <out>_layout.yaml.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from core.grid import read_grid
from core.layout import Layout, SheetColumn, detect_layout, normalise_label

MIN_COUNT = 5  # spellings seen fewer times are suppressed
MAX_CATEGORIES = 30  # above this a column is treated as free text and no spellings are listed
DATE_TEXT_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")

# Header patterns (matched on the case-folded header path) that decide the suggested role.
ROLE_RULES: list[tuple[str, str]] = [
    (r"\(nik\)|identitas kependudukan", "patient_id_source"),
    (r"nama lengkap pasien", "identifier_drop"),
    (r"nomor bpjs", "identifier_drop"),
    (r"rekam medis", "identifier_drop"),
    (r"alamat lengkap pasien > alamat lengkap", "identifier_drop"),
    (r"alamat lengkap pasien > (provinsi|kabupaten|kecamatan|kelurahan)", "quasi_identifier"),
    (r"no\.? ?reg(istrasi)?\b|nomor register|no reg lab", "identifier_pseudonymise"),
    (r"keterangan", "identifier_drop"),
    (r"^no\. urut", "ignore"),
    (r"alamat lengkap faskes", "facility"),
]
# Headers and title-block labels that name a facility or a place. Their values say where an
# export came from, so the inventory never lists them.
SITE_RE = re.compile(r"fasyankes|faskes|puskesmas|rumah sakit|provinsi|kabupaten|kota|kecamatan|kelurahan|desa",
                     re.IGNORECASE)
IDENTIFIER_ROLES = {"patient_id_source", "identifier_drop", "identifier_pseudonymise", "quasi_identifier"}

FIELDS = [
    "official_number", "sub_label", "key", "sheet_col", "header", "type", "fill_pct",
    "distinct", "unique_share", "suggested_role", "spellings", "rare_spellings_suppressed", "notes",
]


def suggest_role(col: SheetColumn, filled: int, distinct: int) -> str:
    header = normalise_label(col.header_text)
    for pattern, role in ROLE_RULES:
        if re.search(pattern, header):
            if role == "facility":
                return "constant" if distinct <= 1 else "data"
            return role
    return "ignore" if filled == 0 else "data"


def infer_type(values: list[object]) -> tuple[str, str]:
    """Returns (type, note). Only counts and shares go into the note, never values."""
    if not values:
        return "empty", ""
    n = len(values)
    excel_dates = sum(isinstance(v, dt.datetime) for v in values)
    text_dates = sum(isinstance(v, str) and bool(DATE_TEXT_RE.match(v.strip())) for v in values)
    numbers = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    numbers += [float(v) for v in values if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip())]
    if (excel_dates + text_dates) / n >= 0.9:
        return "date", f"dd/mm/yyyy text {text_dates / n:.0%}, Excel date cells {excel_dates / n:.0%}"
    if len(numbers) / n >= 0.95:
        integral = all(float(x).is_integer() for x in numbers)
        return ("integer" if integral else "number"), ""
    return "text", ""


def column_stats(grid, layout: Layout, col: SheetColumn) -> dict:
    values = [grid.value(r, col.sheet_col) for r in layout.data_rows]
    filled_values = [v for v in values if v is not None and str(v).strip()]
    texts = [str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip() for v in filled_values]
    counts = Counter(texts)
    filled, distinct = len(filled_values), len(counts)
    col_type, note = infer_type(filled_values)
    if col_type == "text" and distinct <= MAX_CATEGORIES:
        col_type = "choice"
    role = suggest_role(col, filled, distinct)
    spellings, rare = "", 0
    if col_type == "choice" and role not in IDENTIFIER_ROLES and not SITE_RE.search(col.header_text):
        common = [s for s, k in counts.most_common() if k >= MIN_COUNT]
        rare = sum(1 for k in counts.values() if k < MIN_COUNT)
        spellings = " | ".join(common)
    return {
        "official_number": col.number if col.number is not None else "",
        "sub_label": col.sub_label,
        "key": col.key,
        "sheet_col": col.sheet_col,
        "header": col.header_text,
        "type": col_type,
        "fill_pct": round(100 * filled / max(len(values), 1), 1),
        "distinct": distinct,
        "unique_share": round(distinct / filled, 3) if filled else "",
        "suggested_role": role,
        "spellings": spellings,
        "rare_spellings_suppressed": rare,
        "notes": note,
    }


def merge_layouts(paths: list[Path]):
    """Read every file, check they share one header, and pool their data rows."""
    loaded = []
    for path in paths:
        grid = read_grid(path)
        layout = detect_layout(grid)
        loaded.append((path, grid, layout))
    first = [(c.key, c.header_text) for c in loaded[0][2].columns]
    for path, _, layout in loaded[1:]:
        if [(c.key, c.header_text) for c in layout.columns] != first:
            sys.exit(f"Header differs from the first file: {path.name}")
    return loaded


def write_inventory(out_prefix: Path, paths: list[Path]) -> None:
    loaded = merge_layouts(paths)
    _, _, layout0 = loaded[0]
    rows_by_key: dict[str, dict] = {}
    # Pool the data by treating each file's rows in turn; stats are recomputed on the pooled values.
    pooled: dict[str, list[object]] = {c.key: [] for c in layout0.columns}
    for _, grid, layout in loaded:
        for col in layout.columns:
            pooled[col.key].extend(grid.value(r, col.sheet_col) for r in layout.data_rows)

    class _Pooled:
        def __init__(self, values):
            self._values = values

        def value(self, r, _c):
            return self._values[r]

    for col in layout0.columns:
        values = pooled[col.key]
        fake_layout = Layout(kind=layout0.kind, title_text=[], metadata={}, header_start=0,
                             number_row=None, first_data_row=0, columns=[], data_rows=list(range(len(values))))
        rows_by_key[col.key] = column_stats(_Pooled(values), fake_layout, col)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    with open(f"{out_prefix}_columns.csv", "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows_by_key[c.key] for c in layout0.columns)

    site_values = {v for _, _, l in loaded for label, v in l.metadata.items() if SITE_RE.search(label)}
    summary = {
        "files": len(loaded),
        "data_rows_total": sum(len(l.data_rows) for _, _, l in loaded),
        "kind": layout0.kind,
        "header_rows_1based": [layout0.header_start + 1, layout0.number_row],
        "number_row_1based": layout0.number_row + 1,
        "first_data_row_1based": layout0.first_data_row + 1,
        "sheet_columns_used": len(layout0.columns),
        "official_numbers": len({c.number for c in layout0.columns}),
        "title_lines": ["<value>" if t in site_values else t
                        for t in layout0.title_text if re.search(r"[A-Za-z]{4}", t) and not re.search(r"\d{3,}", t)],
        "title_labels": sorted(layout0.metadata),
        "trailing_blank_rows": [len(l.blank_rows) for _, _, l in loaded],
        "summary_rows_at_end": [len(l.summary_rows) for _, _, l in loaded],
        "metadata_case_count_matches_rows": [
            l.metadata.get("jumlah kasus") in (None, str(len(l.data_rows))) for _, _, l in loaded
        ],
    }
    with open(f"{out_prefix}_layout.yaml", "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(summary, fh, sort_keys=False, allow_unicode=True)
    print(f"Wrote {out_prefix}_columns.csv ({len(layout0.columns)} columns) and {out_prefix}_layout.yaml")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_prefix", type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    write_inventory(args.out_prefix, args.files)


if __name__ == "__main__":
    main()
