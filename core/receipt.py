"""A receipt for one upload: what became of every row of the file.

Rows are named by their spreadsheet row number and records by their REDCap record ID, which is a
keyed code, so the receipt holds no identifier. Next to the source file it can trace a record back
to its row, which is its use for spot checks, so keep it with the same care as the source.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.parse import ROW
from core.profile import RECORD_ID_FIELD
from core.review import Review
from core.upload import UploadResult

CREATED, UPDATED, IMPORTED = "created", "updated", "imported"
REJECTED, NOT_SENT = "rejected", "not_sent"
SKIPPED_PREFIX = "skipped_"  # followed by the reason a row was skipped: chosen or errors


@dataclass(frozen=True)
class ReceiptRow:
    row: int
    record_id: str  # empty when the row has none
    status: str
    batch: int | None = None
    edited: tuple[str, ...] = ()  # names of the fields edited in this row, never their values


def build_receipt(review: Review, result: UploadResult) -> list[ReceiptRow]:
    """One entry for every data row read from the file, in file order."""
    frame = review.base.frame
    batch_of = {rid: batch for batch in result.batches for rid in batch.rows}
    edited: dict[int, list[str]] = defaultdict(list)
    for row, field in sorted(review.edits):
        edited[row].append(field)
    rows = []
    for row, record in zip(frame[ROW], frame[RECORD_ID_FIELD]):
        row, record = int(row), "" if record is None else str(record)
        batch = batch_of.get(record) if record else None
        if row in review.skipped:
            status, batch = SKIPPED_PREFIX + review.skipped[row], None
        elif batch is None:
            status = NOT_SENT
        elif batch.status == "imported":
            plan = result.plan
            listed = plan.existing_ids or not plan.existing  # a plan from before the receipt lists no records
            status = (UPDATED if record in plan.existing_ids else CREATED) if listed else IMPORTED
        else:
            status = REJECTED if batch.status == "rejected" else NOT_SENT
        rows.append(ReceiptRow(row, record, status, batch.index if batch else None, tuple(edited.get(row, ()))))
    return rows


def write_receipt_csv(rows: list[ReceiptRow], path: str | Path, header: list[str], label: Callable[[str], str]) -> None:
    """A spreadsheet-friendly file: `header` names the five columns, `label` turns a status into text."""
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r in rows:
            writer.writerow([r.row, r.record_id, label(r.status), r.batch or "", ", ".join(r.edited)])
