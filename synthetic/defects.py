"""Check that every defect planted in a messy synthetic file was reported by the pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from core.pipeline import Prepared


def load_defects(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["defects"]


def is_detected(defect: dict, prepared: Prepared) -> bool:
    detect = defect["detected_as"]
    row = defect.get("row")
    kind = detect["kind"]
    if kind == "change":
        return any(c.field == detect["field"] and c.spelling == detect["spelling"] for c in prepared.changes)
    if kind == "blank_row":
        return row is not None and (row - 1) in prepared.layout.blank_rows
    if kind == "summary_row":
        return row is not None and (row - 1) in prepared.layout.summary_rows
    for issue in prepared.issues:
        if issue.code != detect["code"]:
            continue
        if "field" in detect and issue.field != detect["field"]:
            continue
        if "number" in detect and issue.params.get("number") != detect["number"]:
            continue
        if row is None or issue.row == row or str(row) in str(issue.params.get("others", "")).split(", "):
            return True
    return False


def undetected(defects: list[dict], prepared: Prepared) -> list[dict]:
    return [d for d in defects if not is_detected(d, prepared)]
