"""The --smoke-test flag that CI runs against the built package."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.__main__ import main  # noqa: E402


def test_smoke_test_runs_the_demo_and_reports(qapp, tmp_path):
    report = tmp_path / "smoke.json"
    assert main(["--smoke-test", "--smoke-report", str(report)]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] is True and data["imported"] == 500
    assert [s["step"] for s in data["steps"]] == [
        "connect", "open file step", "sample file", "read and check", "preview", "plan upload", "upload", "explore"]
    assert "token" not in report.read_text(encoding="utf-8").lower()
