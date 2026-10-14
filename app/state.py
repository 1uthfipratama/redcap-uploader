"""What the wizard knows so far, shared by all steps."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path

from core.client import ProjectInfo, RedcapClient
from core.pipeline import Detected, Prepared
from core.profile import Profile
from core.settings import RedcapTarget
from core.upload import UploadPlan, UploadResult
from mock_redcap.runner import MockRedcap


@dataclass
class AppState:
    profiles: dict[str, Profile]
    target: RedcapTarget
    mode: str = "demo"  # "demo" or "real"
    mock: MockRedcap | None = None
    client: RedcapClient | None = None
    project: ProjectInfo | None = None
    key: bytes | None = None  # pseudonym key; a throwaway one in Demo mode
    file: Path | None = None
    detected: Detected | None = None
    form_code: str | None = None
    overrides: dict[str, str | None] = field(default_factory=dict)  # Generic mapping corrections
    prepared: Prepared | None = None
    plan: UploadPlan | None = None
    result: UploadResult | None = None

    @property
    def profile(self) -> Profile | None:
        return self.profiles.get(self.form_code) if self.form_code else None

    def demo_key(self) -> bytes:
        """Demo mode only handles synthetic files, so a fresh random key per session is enough."""
        if self.key is None:
            self.key = secrets.token_bytes(32)
        return self.key

    def forget_file(self) -> None:
        self.detected = self.prepared = self.plan = self.result = None
        self.overrides = {}

    def stop_mock(self) -> None:
        if self.mock is not None:
            self.mock.stop()
            self.mock = None
