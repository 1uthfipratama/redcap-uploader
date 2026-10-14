"""Start the app: python -m app"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from app.i18n import Translator
from app.main_window import MainWindow
from app.state import AppState
from app.theme import load_brand, style_sheet
from core.profile import load_all_profiles
from core.settings import load_target


def setup_logging() -> Path:
    """Log to the user's app-data folder. The log never holds the token or raw identifiers."""
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "app.log"
    logging.basicConfig(filename=path, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return path


def build(lang: str | None = None) -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    brand = load_brand()
    app.setApplicationName(brand.product_name)
    app.setOrganizationName(brand.name)
    app.setStyleSheet(style_sheet(brand))
    state = AppState(profiles=load_all_profiles(), target=load_target())
    window = MainWindow(state, brand, Translator(lang))
    return app, window


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--smoke-test" in argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no window needed; works on CI machines
        from app.smoke import run

        report = argv[argv.index("--smoke-report") + 1] if "--smoke-report" in argv else None
        return run(report)
    if "--quit-after-start" in argv:
        from app.smoke import start_and_quit

        return start_and_quit()
    app, window = build()
    setup_logging()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
