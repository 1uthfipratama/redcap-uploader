"""Dry-run a real export through the pipeline and print an aggregate-only report.

Use it on the approved machine to see how well a profile copes with real files
before any upload. Nothing is sent anywhere, and no patient value is printed:
- issues are counted per kind and field, never listed per row;
- unreadable dates and numbers are shown as shapes ("9999-99-99"), not values;
- unknown spellings are shown only when seen at least MIN_COUNT times;
- pseudonyms are made with a throwaway key and never shown.

    python -m tools.dry_run_report FILE.xls [FILE.xls ...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import secrets
from collections import Counter, defaultdict
from pathlib import Path

from core.issues import ERROR
from core.pipeline import detect, prepare
from core.profile import load_all_profiles

MIN_COUNT = 5
SHAPE_CODES = {"date_unreadable", "not_a_number", "not_whole_number"}


def shape(value: str) -> str:
    """A value's form without its content: digits become 9, letters become a."""
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", str(value)))[:20]


def report(path: Path, profiles, today: dt.date) -> list[str]:
    lines = [f"== {path.name}"]
    detected = detect(path, profiles)
    profile = profiles[detected.form_code]
    lines.append(f"form recognised: {detected.form_code}")
    prepared = prepare(detected, profile, secrets.token_bytes(32), target_fields=None, today=today)
    layout = prepared.layout
    lines.append(f"data rows: {len(layout.data_rows)}; blank rows skipped: {len(layout.blank_rows)}; "
                 f"summary rows skipped: {len(layout.summary_rows)}")
    if prepared.blocked:
        lines.append("LAYOUT DOES NOT MATCH THE PROFILE:")
        for i in prepared.errors:
            lines.append(f"  {i.code}: column ({i.params.get('number')}) {i.params.get('label', '')}")
        return lines

    by_kind: Counter = Counter()
    shapes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for i in prepared.issues:
        by_kind[(i.severity, i.code, i.field or "")] += 1
        if i.code in SHAPE_CODES and "value" in i.params:
            shapes[(i.code, i.field or "")][shape(i.params["value"])] += 1
    errors = sum(n for (sev, _, _), n in by_kind.items() if sev == ERROR)
    lines.append(f"rows ready: {len(prepared.frame)}; errors: {errors}; "
                 f"warnings: {sum(by_kind.values()) - errors}")
    report_ = prepared.identifier_report
    if report_:
        lines.append(f"NIK: {dict(report_.nik_status)}; record IDs missing: {len(report_.record_id_missing_rows)}")
    lines.append("issues by kind and field:")
    for (sev, code, field), n in sorted(by_kind.items(), key=lambda kv: (-kv[1], kv[0])):
        line = f"  {n:6d}  {sev:7s}  {code:24s} {field}"
        if (code, field) in shapes:
            line += "   shapes: " + ", ".join(f"{s} x{k}" for s, k in shapes[(code, field)].most_common(4))
        lines.append(line)
    lines.append(f"unknown spellings seen {MIN_COUNT}+ times (rarer ones counted only):")
    rare = 0
    for u in sorted(prepared.unmapped, key=lambda u: -u.count):
        if u.count >= MIN_COUNT:
            lines.append(f"  {u.count:6d}  {u.field:22s} \"{u.spelling}\"")
        else:
            rare += 1
    lines.append(f"  ({rare} rarer spelling(s) not shown)")
    lines.append(f"spellings standardised: {len(prepared.changes)} kinds")
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    profiles = load_all_profiles()
    for path in args.files:
        print("\n".join(report(path, profiles, dt.date.today())))
        print()


if __name__ == "__main__":
    main()
