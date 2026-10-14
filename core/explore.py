"""Descriptive summaries of the cleaned table, for the Explore screen.

Descriptive only: counts, percentages, means, medians, spreads. No tests,
p-values or models. Every number the screen shows is computed here, so each can
be tested; the UI only draws. Identifier and pseudonym fields are never offered.
"Tidak diketahui" (unknown) is counted apart from blank.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from core.parse import ROW
from core.profile import GENERATED_FIELDS, Profile, Role

CONFIG = Path(__file__).resolve().parent.parent / "config" / "explore.yaml"
UNKNOWN_LABEL = "tidak diketahui"


def load_settings(path: Path = CONFIG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass
class FieldInfo:
    name: str
    kind: str  # "numeric", "categorical", "date" or "text"
    label_id: str = ""
    label_en: str = ""
    choices: dict[str, tuple[str, str]] = field(default_factory=dict)  # code -> (Indonesian, English)
    unknown_codes: set[str] = field(default_factory=set)

    def label(self, lang: str) -> str:
        return (self.label_en if lang == "en" else self.label_id) or self.name

    def choice_label(self, code: str, lang: str) -> str:
        if code in self.choices:
            label_id, label_en = self.choices[code]
            return label_en if lang == "en" else label_id
        return str(code)


# ---- which fields may be explored ---------------------------------------------------

def explorable_fields(frame: pd.DataFrame, profile: Profile, settings: dict | None = None) -> list[FieldInfo]:
    """Fields in the cleaned table that can be summarised. Never identifiers or pseudonyms."""
    settings = settings or load_settings()
    blocked = set(GENERATED_FIELDS) | {ROW}
    blocked |= {c.field for c in profile.columns if c.role == Role.identifier_pseudonymise and c.field}
    out = []
    if profile.is_generic:
        for name in frame.columns:
            if name not in blocked:
                out.append(_infer(frame[name], name, settings["max_categories"]))
        return out
    for col in profile.columns:
        if not col.field or col.field in blocked or col.field not in frame.columns:
            continue
        if col.role not in (Role.data, Role.quasi_identifier):
            continue
        kind = {"integer": "numeric", "number": "numeric", "date": "date", "choice": "categorical"}.get(col.type, "text")
        choices, unknown = {}, set()
        for c in profile.choices_for(col) if col.type == "choice" else []:
            choices[c.code] = (c.label_id, c.label_en)
            if c.label_id.casefold() == UNKNOWN_LABEL:
                unknown.add(c.code)
        out.append(FieldInfo(col.field, kind, col.label or col.field, col.label_en or col.field, choices, unknown))
    return out


def _infer(series: pd.Series, name: str, max_categories: int) -> FieldInfo:
    values = series.dropna()
    if len(values) and all(isinstance(v, (dt.date, dt.datetime)) for v in values):
        kind = "date"
    elif len(values) and pd.to_numeric(values, errors="coerce").notna().all():
        kind = "numeric"
    elif values.nunique() <= max_categories:
        kind = "categorical"
    else:
        kind = "text"
    unknown = {v for v in values.unique() if str(v).casefold() == UNKNOWN_LABEL}
    return FieldInfo(name, kind, name, name, {}, {str(v) for v in unknown})


# ---- helpers ----------------------------------------------------------------------

def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def _numbers(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series[~_blank(series)], errors="coerce").dropna().astype(float)


def _fmt(x: float | None, digits: int = 1) -> float | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), digits)


def maybe_sample(frame: pd.DataFrame, settings: dict | None = None) -> tuple[pd.DataFrame, bool]:
    """Above the row cap, a seeded sample is used for distributions; the caller tells the user."""
    settings = settings or load_settings()
    cap = settings["row_cap"]
    if len(frame) <= cap:
        return frame, False
    return frame.sample(n=cap, random_state=settings["sample_seed"]), True


# ---- panels -------------------------------------------------------------------------

def overview(frame: pd.DataFrame, fields: list[FieldInfo]) -> dict:
    data = frame.drop(columns=[ROW], errors="ignore")
    return {
        "rows": len(data),
        "columns": len(data.columns),
        "explorable": len(fields),
        "duplicate_rows": int(data.duplicated().sum()),
        "numeric": sum(f.kind == "numeric" for f in fields),
        "categorical": sum(f.kind == "categorical" for f in fields),
        "dates": sum(f.kind == "date" for f in fields),
    }


def variable_summary(frame: pd.DataFrame, fields: list[FieldInfo], lang: str = "en",
                     settings: dict | None = None) -> pd.DataFrame:
    """One row per field: counts and, by type, centre and spread or the most common values."""
    settings = settings or load_settings()
    rows = []
    n = len(frame)
    for f in fields:
        series = frame[f.name]
        blank = _blank(series)
        unknown = series.astype(str).isin(f.unknown_codes) & ~blank
        filled = series[~blank & ~unknown]
        row = {
            "field": f.name, "label": f.label(lang), "type": f.kind,
            "count": int((~blank).sum()), "blank": int(blank.sum()),
            "blank_pct": _fmt(100 * blank.sum() / n if n else 0), "unknown": int(unknown.sum()),
            "distinct": int(filled.astype(str).nunique()),
            "mean": None, "sd": None, "min": None, "q1": None, "median": None, "q3": None, "max": None, "top": "",
        }
        if f.kind == "numeric":
            x = _numbers(filled)
            if len(x):
                row.update(mean=_fmt(x.mean()), sd=_fmt(x.std(ddof=1)) if len(x) > 1 else None,
                           min=_fmt(x.min()), q1=_fmt(x.quantile(0.25)), median=_fmt(x.median()),
                           q3=_fmt(x.quantile(0.75)), max=_fmt(x.max()))
        elif f.kind == "date":
            dates = pd.to_datetime(filled, errors="coerce").dropna()
            if len(dates):
                row.update(min=dates.min().strftime("%Y-%m-%d"), max=dates.max().strftime("%Y-%m-%d"))
        if f.kind in ("categorical", "text"):
            counts = series[~blank].astype(str).value_counts().head(settings["top_values"])
            row["top"] = "; ".join(f"{f.choice_label(code, lang)} ({k})" for code, k in counts.items())
        rows.append(row)
    return pd.DataFrame(rows)


def distribution(frame: pd.DataFrame, f: FieldInfo, lang: str = "en", settings: dict | None = None) -> pd.DataFrame:
    """Numeric: histogram bins. Categorical: one row per answer, in the form's order, then blank.
    Date: records per month. Every row has n, percent and a small-group flag."""
    settings = settings or load_settings()
    series = frame[f.name]
    small = settings["small_group"]
    if f.kind == "numeric":
        x = _numbers(series[~series.astype(str).isin(f.unknown_codes)])
        if not len(x):
            return pd.DataFrame(columns=["bin_start", "bin_end", "n", "percent", "small"])
        counts, edges = np.histogram(x, bins=nice_edges(x.min(), x.max(), settings["histogram_bins"]))
        out = pd.DataFrame({"bin_start": edges[:-1].round(2), "bin_end": edges[1:].round(2), "n": counts})
    elif f.kind == "date":
        return over_time(frame, f, settings=settings)
    else:
        out = category_counts(series, f, lang)
    total = out["n"].sum()
    out["percent"] = (100 * out["n"] / total).round(1) if total else 0.0
    out["small"] = (out["n"] > 0) & (out["n"] < small)
    return out


def nice_edges(low: float, high: float, target_bins: int) -> np.ndarray:
    """Bin edges on round numbers (widths of 1, 2, 2.5 or 5 times a power of ten), so bins read as 0-5, 5-10."""
    if high <= low:
        return np.array([low - 0.5, low + 0.5])
    raw = (high - low) / target_bins
    power = 10 ** np.floor(np.log10(raw))
    width = next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)
    start = np.floor(low / width) * width
    stop = np.floor(high / width) * width + width  # the last bin includes the maximum
    return np.arange(start, stop + width / 2, width)


def category_counts(series: pd.Series, f: FieldInfo, lang: str) -> pd.DataFrame:
    blank = _blank(series)
    if blank.all():
        return pd.DataFrame({"code": [""] if len(series) else [], "label": [""] if len(series) else [],
                             "n": [len(series)] if len(series) else [], "unknown": [False] if len(series) else [],
                             "blank": [True] if len(series) else []})
    counts = series[~blank].astype(str).value_counts()
    order = [c for c in f.choices if c in counts.index] + [c for c in counts.index if c not in f.choices]
    rows = [{"code": c, "label": f.choice_label(c, lang), "n": int(counts[c]), "unknown": c in f.unknown_codes}
            for c in order]
    if blank.any():
        rows.append({"code": "", "label": "", "n": int(blank.sum()), "unknown": False, "blank": True})
    out = pd.DataFrame(rows)
    out["blank"] = out.get("blank", False)
    out["blank"] = out["blank"].fillna(False).astype(bool)
    return out


def missingness(frame: pd.DataFrame, fields: list[FieldInfo]) -> pd.DataFrame:
    """Per field: blank and "unknown" counted apart, as numbers and percentages."""
    n = len(frame)
    rows = []
    for f in fields:
        series = frame[f.name]
        blank = _blank(series)
        unknown = series.astype(str).isin(f.unknown_codes) & ~blank
        rows.append({"field": f.name, "blank": int(blank.sum()), "unknown": int(unknown.sum()),
                     "filled": int(n - blank.sum() - unknown.sum()),
                     "blank_pct": _fmt(100 * blank.sum() / n if n else 0),
                     "unknown_pct": _fmt(100 * unknown.sum() / n if n else 0)})
    return pd.DataFrame(rows).sort_values(["blank_pct", "unknown_pct"], ascending=False, ignore_index=True)


def group_comparison(frame: pd.DataFrame, f: FieldInfo, by: FieldInfo, lang: str = "en",
                     settings: dict | None = None) -> pd.DataFrame:
    """A field across the groups of a categorical field. Numeric: n, mean, SD, median, quartiles per group.
    Categorical: counts and row percentages. Groups under the small-group size are flagged."""
    settings = settings or load_settings()
    small = settings["small_group"]
    groups = frame[by.name].where(~_blank(frame[by.name]), None)
    order = [c for c in by.choices if c in set(groups.dropna().astype(str))]
    order += sorted({str(g) for g in groups.dropna()} - set(order))
    rows = []
    for code in order:
        part = frame[groups.astype(str) == code]
        row = {"group": by.choice_label(code, lang), "n": len(part), "small": 0 < len(part) < small}
        if f.kind == "numeric":
            x = _numbers(part[f.name][~part[f.name].astype(str).isin(f.unknown_codes)])
            row.update(mean=_fmt(x.mean()) if len(x) else None,
                       sd=_fmt(x.std(ddof=1)) if len(x) > 1 else None,
                       q1=_fmt(x.quantile(0.25)) if len(x) else None,
                       median=_fmt(x.median()) if len(x) else None,
                       q3=_fmt(x.quantile(0.75)) if len(x) else None)
        else:
            counts = category_counts(part[f.name], f, lang)
            for _, c in counts.iterrows():
                label = c["label"] if not c["blank"] else "—"
                row[label] = int(c["n"])
                row[f"{label} %"] = round(100 * c["n"] / len(part), 1) if len(part) else 0.0
        rows.append(row)
    return pd.DataFrame(rows).fillna(0) if f.kind != "numeric" else pd.DataFrame(rows)


def over_time(frame: pd.DataFrame, f: FieldInfo, settings: dict | None = None) -> pd.DataFrame:
    """Records per calendar month of a date field (months with no records are shown as 0)."""
    settings = settings or load_settings()
    dates = pd.to_datetime(frame[f.name][~_blank(frame[f.name])], errors="coerce").dropna()
    if not len(dates):
        return pd.DataFrame(columns=["month", "n", "percent", "small"])
    months = dates.dt.to_period("M")
    counts = months.value_counts().sort_index()
    full = pd.period_range(counts.index.min(), counts.index.max(), freq="M")
    counts = counts.reindex(full, fill_value=0)
    out = pd.DataFrame({"month": [str(p) for p in counts.index], "n": counts.values.astype(int)})
    total = out["n"].sum()
    out["percent"] = (100 * out["n"] / total).round(1) if total else 0.0
    out["small"] = (out["n"] > 0) & (out["n"] < settings["small_group"])
    return out
