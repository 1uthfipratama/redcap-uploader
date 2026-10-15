"""Add the fields a form needs to a REDCap project, through the API (A18).

Only projects in Development status can take a new data dictionary through the API;
in production a REDCap administrator has to approve changes, so the app hands over the
dictionary file instead. Fields the project already has are never changed or removed,
and a copy of the project's dictionary is saved before anything is sent.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from core.client import RedcapClient
from core.dictionary import FieldConflict, build_dictionary, field_conflicts, merge_dictionary
from core.export_csv import write_dictionary_csv
from core.profile import Profile


class ProjectInProduction(Exception):
    """Fields can only be added to a project in Development status."""


class FieldsConflict(Exception):
    """The project has fields of the same name set up differently; adding the rest would mix meanings."""

    def __init__(self, conflicts: list[FieldConflict]):
        super().__init__(", ".join(c.field for c in conflicts))
        self.conflicts = conflicts


@dataclass
class FieldsAdded:
    added: list[str]  # field names, in upload order; empty when nothing was missing
    backup: Path | None  # the project's dictionary as it was, or None when nothing was sent


def add_missing_fields(client: RedcapClient, profile: Profile, backup_dir: Path,
                       now: dt.datetime | None = None) -> FieldsAdded:
    """Add the fields this form uploads that the project lacks. Raises ProjectInProduction,
    FieldsConflict or core.dictionary.RecordIdDiffers when the project cannot take them."""
    info = client.connect()
    if info.in_production:
        raise ProjectInProduction(info.title)
    wanted = build_dictionary(profile)
    conflicts = field_conflicts(info.dictionary, wanted)
    if conflicts:
        raise FieldsConflict(conflicts)
    merged, added = merge_dictionary(info.dictionary, wanted)
    if not added:
        return FieldsAdded([], None)
    stamp = (now or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    name = re.sub(r"[^A-Za-z0-9]+", "-", info.title).strip("-").lower() or "project"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = write_dictionary_csv(info.dictionary, backup_dir / f"{name}-dictionary-before-{stamp}.csv")
    client.import_dictionary(merged)
    return FieldsAdded(added, backup)
