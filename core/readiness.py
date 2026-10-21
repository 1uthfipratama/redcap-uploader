"""Is this project ready for the app? A short checklist, made when the app connects.

Each check says what was found and, when something is wrong, where the message tells the person
to look. Nothing here blocks anything: the steps that follow check what they need (the form's
fields at Choose file, the rows at Review, REDCap's own rules at Upload). The checklist only
tells the person early.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.client import ApiError, ProjectInfo, RedcapClient
from core.settings import RedcapTarget

OK, INFO, WARN, ERROR = "ok", "info", "warn", "error"


@dataclass(frozen=True)
class Check:
    key: str  # status, record_id, design, repeating, records or import
    variant: str  # which message: ui.ready.<key>.<variant>
    level: str
    params: dict = field(default_factory=dict, hash=False, compare=False)


def count_records(client: RedcapClient, info: ProjectInfo) -> int | None:
    """How many records the project holds, or None when REDCap refuses to export them."""
    try:
        return len(client.existing_record_ids(info.record_id_field))
    except ApiError:
        return None


def check_project(info: ProjectInfo, target: RedcapTarget, records: int | None) -> list[Check]:
    checks = [
        Check("status", "production", INFO) if info.in_production else Check("status", "development", OK),
        Check("record_id", "ok", OK, {"field": info.record_id_field}) if info.record_id_field == target.record_id_field
        else Check("record_id", "different", ERROR, {"field": info.record_id_field, "expected": target.record_id_field}),
        Check("design", "longitudinal", ERROR) if info.is_longitudinal and target.project_type == "classic"
        else Check("design", "classic", OK),
        Check("repeating", "present", WARN) if info.has_repeating and not target.repeating_instruments
        else Check("repeating", "none", OK),
        Check("records", "refused", ERROR) if records is None else Check("records", "count", INFO, {"count": records}),
        Check("import", "later", INFO),
    ]
    return checks
