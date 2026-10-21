"""Seeded generator of synthetic SITB register files, clean and messy.

Inputs are only the form profile and its structure-only inventory in synthetic/forms/
(fill rates and the spellings seen there). It never opens a real export.
Identifiers are present but obviously fake: names like NAMA-SINTETIS-0001, NIKs
that start with 0000 (not a valid province code), placeholder addresses.

    python -m synthetic.generate tbc03_so --rows 500 --seed 42 --out out/synthetic

writes <form>_clean.xls/.xlsx, <form>_messy.xls/.xlsx and <form>_defects.json.
The same seed gives the same files.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import importlib.util
import json
import random
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.normalise import spelling_key
from core.profile import Choice, ColumnSpec, Profile, Role, load_all_profiles
from synthetic.register_writer import (
    RegisterSpec,
    TitleBlock,
    data_row_numbers,
    summary_row_number,
    write_register,
)

REPO = Path(__file__).resolve().parent.parent
FORMS_DIR = Path(__file__).resolve().parent / "forms"
DISTRIBUTIONS = Path(__file__).resolve().parent / "distributions.yaml"
DEFAULT_ROWS = {"tbc03_so": 500, "tbc03_ro": 100}
MONTHS = "Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember".split()


@dataclass
class Generated:
    spec: RegisterSpec
    defects: list[dict] = field(default_factory=list)


# ---- inputs ----------------------------------------------------------------------

def load_inventory(form_code: str) -> dict[str, dict]:
    """Per column key: fill rate (0-1) and spellings in inventory order (most common first)."""
    path = FORMS_DIR / f"{form_code}_columns.csv"
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            spellings = [s.strip() for s in row["spellings"].split(" | ") if s.strip()]
            out[row["key"]] = {"fill": float(row["fill_pct"] or 0) / 100, "spellings": spellings}
    return out


def load_distributions() -> dict:
    with open(DISTRIBUTIONS, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---- clean rows ----------------------------------------------------------------------

class RowMaker:
    def __init__(self, profile: Profile, rng: random.Random, inventory: dict, dist: dict,
                 period_year: int, facilities: int, today: dt.date):
        self.p, self.rng, self.inv, self.dist = profile, rng, inventory, dist
        self.year, self.today = period_year, today
        self.is_ro = "ro" in profile.identity.form_code.split("_")[-1]
        self.facilities = [{
            "fasyankes_name": f"FASYANKES SINTETIS {k}", "fasyankes_code": f"000000{k}",
            "fasyankes_province": "Provinsi Sintetis", "fasyankes_district": "Kota Sintetis",
            "fasyankes_type": "Rumah Sakit", "fasyankes_ownership": "Kemenkes",
        } for k in range(1, facilities + 1)]
        self.patients: list[tuple[str, str]] = []  # (NIK, SITB number)

    def fill(self, col: ColumnSpec) -> float:
        if col.required:
            return 1.0
        return self.inv.get(col.key, {}).get("fill", 0.5)

    def present(self, col: ColumnSpec) -> bool:
        return self.rng.random() < self.fill(col)

    def spelling_for(self, col: ColumnSpec, choice: Choice) -> str:
        """The spelling real exports use for this choice, if the inventory shows one."""
        wanted = {spelling_key(s) for s in (choice.label_id, *choice.spellings)}
        for s in self.inv.get(col.key, {}).get("spellings", []):
            if spelling_key(s) in wanted:
                return s
        return choice.label_id

    def pick_choice(self, col: ColumnSpec) -> Choice:
        choices = self.p.choices_for(col)
        weights = self.dist["choice_weights"].get(col.field, {})
        if weights:
            w = [weights.get(c.code, 0.0) for c in choices]
        else:
            seen = [spelling_key(s) for s in self.inv.get(col.key, {}).get("spellings", [])]
            w = []
            for c in choices:
                keys = {spelling_key(s) for s in (c.label_id, *c.spellings)}
                rank = next((i for i, s in enumerate(seen) if s in keys), None)
                w.append(1.0 / (rank + 1) if rank is not None else 0.02)
        if not any(w):
            w = [1.0] * len(choices)
        return self.rng.choices(choices, weights=w)[0]

    def age(self) -> int:
        bands = self.dist["age_bands"]
        low, high, _ = self.rng.choices(bands, weights=[b[2] for b in bands])[0]
        return self.rng.randint(low, high)

    def date_from(self, start: dt.date, offsets: list[int]) -> dt.date:
        return start + dt.timedelta(days=self.rng.randint(*offsets))

    def text_for(self, col: ColumnSpec) -> str:
        options = self.inv.get(col.key, {}).get("spellings") or self.dist["text_values"].get(col.field)
        return self.rng.choice(options) if options else f"Teks sintetis {col.field}"

    def identifier(self, col: ColumnSpec, i: int) -> str | None:
        label = col.label_id.casefold()
        if not self.present(col):
            return None
        if "nama" in label:
            return f"NAMA-SINTETIS-{i:04d}"
        if "bpjs" in label:
            return f"0000{i:09d}"
        if "rekam medis" in label:
            return f"RM-SINTETIS-{i:05d}"
        if "alamat" in label:
            return f"ALAMAT-SINTETIS-{i:04d}"
        if "keterangan" in label:
            return f"CATATAN-SINTETIS-{i:04d}"
        if "lab" in label:
            return f"LAB-SINTETIS-{i:05d}"
        return f"REG-SINTETIS-{i:05d}"

    def quasi(self, col: ColumnSpec) -> str:
        label = col.label.casefold()
        if "provinsi" in label:
            return "Provinsi Sintetis"
        if "kabupaten" in label:
            return f"Kabupaten Sintetis {self.rng.randint(1, 5)}"
        if "kecamatan" in label:
            return f"Kecamatan Sintetis {self.rng.randint(1, 20)}"
        return f"Kelurahan Sintetis {self.rng.randint(1, 40)}"

    def row(self, i: int) -> dict[str, object]:
        """One clean row, by column key. i is 1-based."""
        rng = self.rng
        if self.patients and rng.random() < self.dist["repeat_patient_share"]:
            nik, sitb = rng.choice(self.patients)
        else:
            n = len(self.patients) + 1
            nik, sitb = f"0000{n:012d}", f"0001{n:08d}"
            self.patients.append((nik, sitb))
        facility = rng.choice(self.facilities)
        start = dt.date(self.year, 1, 1) + dt.timedelta(days=rng.randint(0, 364))
        codes: dict[str, str] = {}
        out: dict[str, object] = {}
        outcome_present = None
        for col in self.p.columns:
            f = col.field or ""
            if col.role == Role.record_id_source:
                out[col.key] = f"0000{i:08d}"
            elif col.role == Role.patient_id_source:
                out[col.key] = nik
            elif col.role == Role.identifier_pseudonymise:
                out[col.key] = sitb
            elif col.role == Role.identifier_drop:
                out[col.key] = self.identifier(col, i)
            elif col.role == Role.quasi_identifier:
                out[col.key] = self.quasi(col)
            elif col.role == Role.ignore:
                out[col.key] = i if "urut" in col.label.casefold() else None
            elif col.role == Role.constant:
                out[col.key] = None
            elif f in facility:
                out[col.key] = facility[f]
            elif f == "tx_start_date":
                out[col.key] = start
            elif f == "reg_month":
                out[col.key] = MONTHS[start.month - 1]
            elif f == "age":
                out[col.key] = self.age()
                codes["age"] = str(out[col.key])
            elif f == "child_tb_score":
                out[col.key] = rng.randint(0, 13) if int(codes.get("age", "99")) < 15 else None
            elif f == "pregnant":
                out[col.key] = (self.spelling_for(col, self.pick_choice(col))
                                if codes.get("sex") == "2" and rng.random() < 0.9 else None)
            elif f == "outcome_date":
                out[col.key] = None  # set after the outcome is drawn
            elif col.type == "choice":
                if self.present(col):
                    choice = self.pick_choice(col)
                    codes[f] = choice.code
                    out[col.key] = self.spelling_for(col, choice)
                else:
                    out[col.key] = None
                if f == "outcome":
                    outcome_present = out[col.key] is not None
            elif col.type == "date":
                out[col.key] = self.date_from(start, self.dist["date_offsets"]["before_start"]) if self.present(col) else None
            elif col.type in ("integer", "number"):
                low = int(col.min) if col.min is not None else 0
                high = int(col.max) if col.max is not None else 100
                out[col.key] = rng.randint(low, high) if self.present(col) else None
            else:
                out[col.key] = self.text_for(col) if self.present(col) else None
        self._outcome_date(out, start, outcome_present)
        return out

    def _outcome_date(self, out: dict, start: dt.date, outcome_present: bool | None) -> None:
        date_col = self.p.column_for_field("outcome_date")
        outcome_col = self.p.column_for_field("outcome")
        if not date_col or not outcome_col or not outcome_present:
            return
        offsets = self.dist["date_offsets"]["outcome_ro" if self.is_ro else "outcome_so"]
        when = self.date_from(start, offsets)
        if when > self.today:  # still on treatment: no outcome yet
            out[outcome_col.key] = None
        else:
            out[date_col.key] = when


def clean_rows(profile: Profile, n: int, seed: int, period_year: int = 2024, facilities: int = 1,
               today: dt.date | None = None) -> list[dict[str, object]]:
    maker = RowMaker(profile, random.Random(seed), load_inventory(profile.identity.form_code),
                     load_distributions(), period_year, facilities, today or dt.date.today())
    return [maker.row(i) for i in range(1, n + 1)]


def title_for(profile: Profile, period_year: int) -> TitleBlock:
    return TitleBlock(facility="FASYANKES SINTETIS 1", facility_code="0000001",
                      period=f"Januari - Desember {period_year}")


# ---- messy: planted defects ---------------------------------------------------------

def _key(profile: Profile, field_name: str) -> str | None:
    col = profile.column_for_field(field_name)
    return col.key if col else None


def _column_with_spelling(profile: Profile, spelling: str, prefer: list[str]) -> ColumnSpec | None:
    wanted = spelling_key(spelling)
    cols = [profile.column_for_field(f) for f in prefer] + profile.uploaded_columns()
    for col in cols:
        if col and col.type == "choice":
            for choice in profile.choices_for(col):
                if wanted in {spelling_key(s) for s in (choice.label_id, *choice.spellings)} and spelling != choice.label_id:
                    return col
    return None


def plant_defects(profile: Profile, rows: list[dict], spec: RegisterSpec, rng: random.Random) -> list[dict]:
    """Change rows and spec in place; return the defects with what should detect each."""
    rid = next(c.key for c in profile.columns if c.role == Role.record_id_source)
    nik = next((c.key for c in profile.columns if c.role == Role.patient_id_source), None)
    picks = iter(rng.sample(range(len(rows)), 16))
    planned: list[dict] = []

    def add(kind_of_defect, index, column, detect):
        planned.append({"type": kind_of_defect, "index": index, "column": column, "detected_as": detect})

    for spelling, prefer in (("Tidak Tahu", ["dm"]), ("Tidak Diketahui", ["hiv"]), ("TDL", ["cxr", "dst_h"]),
                             ("NEG", ["smear_dx", "smear_m1"])):
        col = _column_with_spelling(profile, spelling, prefer)
        if col:
            i = next(picks)
            rows[i][col.key] = spelling
            add("spelling_variant", i, col.key, {"kind": "change", "field": col.field, "spelling": spelling})

    i = next(picks)
    rows[i][rid] = None
    add("missing_record_id", i, rid, {"kind": "issue", "code": "record_id_source_blank"})

    i, j = sorted((next(picks), next(picks)))
    rows[j][rid] = rows[i][rid]
    for f in ("fasyankes_code",):
        if (k := _key(profile, f)):
            rows[j][k] = rows[i][k]
    add("duplicate_record_id", j, rid, {"kind": "issue", "code": "duplicate_record_id", "field": "record_id"})

    if (k := _key(profile, "age")):
        i = next(picks)
        rows[i][k] = 212
        add("age_out_of_range", i, k, {"kind": "issue", "code": "above_max", "field": "age"})

    if (k := _key(profile, "tx_start_date")):
        i = next(picks)
        start = rows[i][k]
        rows[i][k] = start.strftime("%Y-%m-%d") if isinstance(start, dt.date) else "2024-03-14"
        add("mixed_date_format", i, k, {"kind": "issue", "code": "date_unreadable", "field": "tx_start_date"})

    if (k := _key(profile, "sex")):
        i = next(picks)
        rows[i][k] = "Laki"
        add("unknown_spelling", i, k, {"kind": "issue", "code": "spelling_unmapped", "field": "sex"})

    if (k := _key(profile, "tb_site")):
        i = next(picks)
        rows[i][k] = None
        add("required_missing", i, k, {"kind": "issue", "code": "required_missing", "field": "tb_site"})

    ko, kd = _key(profile, "outcome"), _key(profile, "outcome_date")
    if ko and kd:
        i = next(picks)
        rows[i][ko] = "Sembuh"
        rows[i][kd] = dt.date(2099, 1, 1)
        add("future_date", i, kd, {"kind": "issue", "code": "date_in_future", "field": "outcome_date"})

    if nik:
        i = next(picks)
        rows[i][nik] = "1.0E+15"
        add("nik_scientific", i, nik, {"kind": "issue", "code": "nik_scientific"})
        i = next(picks)
        rows[i][nik] = "000012345"
        add("nik_wrong_length", i, nik, {"kind": "issue", "code": "nik_wrong_length"})

    i = next(picks)
    spec.blank_rows_after.append(i)
    add("extra_blank_row", i, None, {"kind": "blank_row"})

    if (k := _key(profile, "age")):
        col = profile.column(k)
        spec.label_overrides[k] = "Usia (Tahun)"
        add("changed_header_label", None, k, {"kind": "issue", "code": "label_changed", "number": col.number})

    spec.summary_row = True
    add("summary_row", None, None, {"kind": "summary_row"})

    if profile.layout.case_count_label:
        spec.title.stated_case_count = len(rows) + 3
        add("case_count_mismatch", None, None, {"kind": "issue", "code": "case_count_mismatch"})

    numbers = data_row_numbers(spec)
    defects = []
    for n, d in enumerate(planned, start=1):
        row = None
        if d["type"] == "extra_blank_row":
            row = numbers[d["index"]] + 1
        elif d["type"] == "summary_row":
            row = summary_row_number(spec)
        elif d["index"] is not None:
            row = numbers[d["index"]]
        defects.append({"id": n, "type": d["type"], "row": row, "column": d["column"], "detected_as": d["detected_as"]})
    return defects


# ---- whole files -------------------------------------------------------------------

def generate(profile: Profile, n: int, seed: int, *, messy: bool = False, period_year: int = 2024,
             facilities: int = 1, today: dt.date | None = None) -> Generated:
    rows = clean_rows(profile, n, seed, period_year, facilities, today)
    spec = RegisterSpec(rows=rows, title=title_for(profile, period_year))
    if not messy:
        return Generated(spec)
    spec = copy.deepcopy(spec)
    defects = plant_defects(profile, spec.rows, spec, random.Random(seed + 1))
    return Generated(spec, defects)


def write_set(profile: Profile, out_dir: str | Path, n: int, seed: int, *, formats=("xls", "xlsx"),
              period_year: int = 2024, facilities: int = 1, today: dt.date | None = None) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if "xls" in formats and importlib.util.find_spec("xlwt") is None:
        warnings.warn("xlwt is not installed, so .xls files are not written (pip install xlwt)")
        formats = tuple(f for f in formats if f != "xls")
    code = profile.identity.form_code
    written: dict[str, Path] = {}
    for kind, messy in (("clean", False), ("messy", True)):
        result = generate(profile, n, seed, messy=messy, period_year=period_year, facilities=facilities, today=today)
        for fmt in formats:
            written[f"{kind}_{fmt}"] = write_register(out_dir / f"{code}_{kind}.{fmt}", profile, result.spec)
        if messy:
            path = out_dir / f"{code}_defects.json"
            path.write_text(json.dumps({"form": code, "seed": seed, "rows": n, "defects": result.defects},
                                       indent=2, ensure_ascii=False), encoding="utf-8")
            written["defects"] = path
    return written


def main(argv: list[str] | None = None) -> None:
    profiles = load_all_profiles()
    parser = argparse.ArgumentParser(description="Write synthetic clean and messy register files.")
    parser.add_argument("form", choices=sorted(k for k, p in profiles.items() if not p.is_generic))
    parser.add_argument("--rows", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--facilities", type=int, default=1)
    parser.add_argument("--out", type=Path, default=REPO / "out" / "synthetic")
    args = parser.parse_args(argv)
    n = args.rows or DEFAULT_ROWS.get(args.form, 200)
    written = write_set(profiles[args.form], args.out, n, args.seed, period_year=args.year, facilities=args.facilities)
    for name, path in written.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
