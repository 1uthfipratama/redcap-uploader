"""Smoke test: run the whole demo headlessly and exit 0 if it works.

    REDCap-Uploader --smoke-test [--smoke-report report.json]

Used by CI against the built package (not the source) on Windows and macOS:
connect to the built-in practice REDCap, load the clean synthetic sample, read,
de-identify and check it, upload it, and open Explore. The report holds step
names, timings and counts only.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QThreadPool

STEP_TIMEOUT = 120  # seconds


def _settle(app, window, timeout: float = STEP_TIMEOUT) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if not window.busy and QThreadPool.globalInstance().activeThreadCount() == 0:
            app.processEvents()
            return
        time.sleep(0.02)
    raise TimeoutError("step did not finish in time")


def run(report_path: str | None = None) -> int:
    from app.__main__ import build

    started = time.perf_counter()
    report: dict = {"ok": False, "steps": []}
    app, window = build("en")
    window.show()

    def step(name: str, action, check) -> None:
        t = time.perf_counter()
        action()
        _settle(app, window)
        if not check():
            raise AssertionError(f"{name} failed: {window.page.message.text()[:200]}")
        report["steps"].append({"step": name, "seconds": round(time.perf_counter() - t, 2)})

    try:
        report["startup_seconds"] = round(time.perf_counter() - started, 2)
        step("connect", window._next, lambda: window.state.project is not None)
        step("open file step", window._next, lambda: window.stack.currentIndex() == 1)
        step("sample file", lambda: window.pages[1]._sample("clean"), lambda: window.state.form_code == "tbc03_so")
        step("read and check", window._next, lambda: window.state.prepared is not None and window.state.prepared.ready)
        step("preview", window._next, lambda: window.stack.currentIndex() == 3)
        step("plan upload", window._next, lambda: window.state.plan is not None)
        step("upload", window._next, lambda: window.state.result is not None and window.state.result.complete)

        def explore():
            window.open_explore()
            window.explore_window.tabs.setCurrentIndex(2)
            window.explore_window.pages[2].chart.canvas.draw()

        step("explore", explore, lambda: window.explore_window is not None)
        report.update(ok=True, imported=window.state.result.imported)
    except Exception as exc:  # noqa: BLE001 - the report says what failed, the exit code says that it failed
        report["error"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        report["total_seconds"] = round(time.perf_counter() - started, 2)
        window.close()
    text = json.dumps(report, indent=2)
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if report["ok"] else 1


def start_and_quit() -> int:
    """--quit-after-start: open the window, let it draw once, exit (for measuring start-up time)."""
    from PySide6.QtCore import QTimer

    from app.__main__ import build

    app, window = build()
    window.show()
    QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
