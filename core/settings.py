"""Settings from config/ files. Code reads these instead of hard-coding them."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class RedcapTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id_field: str = "record_id"
    date_format: Literal["YMD", "DMY", "MDY"] = "YMD"
    overwrite_behavior: Literal["normal", "overwrite"] = "normal"
    batch_size: int = Field(default=100, ge=1, le=10000)
    timeout_seconds: float = Field(default=60, gt=0)
    project_type: Literal["classic", "longitudinal"] = "classic"
    repeating_instruments: bool = False
    data_access_groups: bool = False


def load_target(path: str | Path = CONFIG_DIR / "redcap_target.yaml") -> RedcapTarget:
    with open(path, encoding="utf-8") as fh:
        return RedcapTarget.model_validate(yaml.safe_load(fh) or {})
