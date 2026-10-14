"""Send prepared records to REDCap in batches.

Before sending, the record IDs already in the project are exported, so the user
sees how many records are new and how many will update existing ones. Batches
are all-or-nothing (A06): when one is rejected, upload stops, the batches
already imported stay, and that batch's problems are returned per record and
field, with the spreadsheet row where it is known.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from core.client import ApiError, ImportProblem, RedcapClient

log = logging.getLogger("redcap_uploader.upload")


@dataclass
class UploadPlan:
    total: int
    new: int
    existing: int


@dataclass
class BatchResult:
    index: int  # 1-based
    size: int
    status: str  # "imported", "rejected" or "not_sent"
    saved_ids: list[str] = field(default_factory=list)
    problems: list[ImportProblem] = field(default_factory=list)
    rows: dict[str, int] = field(default_factory=dict)  # record ID -> spreadsheet row, for messages


@dataclass
class UploadResult:
    plan: UploadPlan
    batches: list[BatchResult]

    @property
    def imported(self) -> int:
        return sum(len(b.saved_ids) for b in self.batches if b.status == "imported")

    @property
    def rejected_batch(self) -> BatchResult | None:
        return next((b for b in self.batches if b.status == "rejected"), None)

    @property
    def not_sent(self) -> int:
        return sum(b.size for b in self.batches if b.status == "not_sent")

    @property
    def complete(self) -> bool:
        return all(b.status == "imported" for b in self.batches)


def plan_upload(client: RedcapClient, records: list[dict[str, str]], record_id_field: str) -> UploadPlan:
    existing = client.existing_record_ids(record_id_field)
    ids = {r[record_id_field] for r in records}
    return UploadPlan(total=len(records), new=len(ids - existing), existing=len(ids & existing))


def batches_of(records: list, size: int) -> list[list]:
    return [records[i:i + size] for i in range(0, len(records), size)]


def upload(client: RedcapClient, records: list[dict[str, str]], *, record_id_field: str, batch_size: int,
           overwrite: str = "normal", rows_by_record: dict[str, int] | None = None, plan: UploadPlan | None = None,
           on_progress: Callable[[int, int], None] | None = None) -> UploadResult:
    """Import every batch in order; stop at the first rejected batch."""
    plan = plan or plan_upload(client, records, record_id_field)
    rows_by_record = rows_by_record or {}
    chunks = batches_of(records, batch_size)
    results: list[BatchResult] = []
    stopped = False
    for i, chunk in enumerate(chunks, start=1):
        ids = [r[record_id_field] for r in chunk]
        rows = {rid: rows_by_record[rid] for rid in ids if rid in rows_by_record}
        if stopped:
            results.append(BatchResult(i, len(chunk), "not_sent", rows=rows))
            continue
        try:
            saved = client.import_records(chunk, overwrite=overwrite)
            results.append(BatchResult(i, len(chunk), "imported", saved_ids=[str(s) for s in saved], rows=rows))
        except ApiError as exc:
            results.append(BatchResult(i, len(chunk), "rejected", problems=exc.problems, rows=rows))
            stopped = True
            log.info("batch %d of %d rejected with %d problem(s); upload stopped", i, len(chunks), len(exc.problems))
        if on_progress:
            on_progress(i, len(chunks))
    result = UploadResult(plan=plan, batches=results)
    log.info("upload finished: %d imported, %d not sent", result.imported, result.not_sent)
    return result
