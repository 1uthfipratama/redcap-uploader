"""The wizard window: header with the brand and language, step rail, pages, Back and Next."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.pages.base import Context, StepPage
from app.pages.choose import ChoosePage
from app.pages.connect import ConnectPage
from app.pages.preview import PreviewPage
from app.pages.result import ResultPage
from app.pages.upload import UploadPage
from app.pages.validate import ValidatePage
from app.state import AppState
from app.theme import Brand
from app.widgets import StepRail, label
from core.messages import LANGUAGES

PAGES = [ConnectPage, ChoosePage, PreviewPage, ValidatePage, UploadPage, ResultPage]


class MainWindow(QMainWindow):
    def __init__(self, state: AppState, brand: Brand, tr: Translator):
        super().__init__()
        self.state, self.brand, self.tr = state, brand, tr
        self.busy = False
        self._built = False  # pages call refresh_nav() while they are being created
        self.setWindowTitle(brand.product_name)
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)

        root = QWidget()
        root.setObjectName("Canvas")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        self.rail = StepRail(tr)
        self.stack = QStackedWidget()
        ctx = Context(tr=tr, state=state, brand=brand, set_busy=self.set_busy,
                      refresh_nav=self.refresh_nav, go_to=self.go_to, open_explore=self.open_explore)
        self.explore_window = None
        self.pages: list[StepPage] = [cls(ctx) for cls in PAGES]
        for page in self.pages:
            self.stack.addWidget(page)
        middle.addWidget(self.rail)
        middle.addWidget(self.stack, 1)
        outer.addLayout(middle, 1)
        outer.addWidget(self._footer())
        self.setCentralWidget(root)

        self._built = True
        tr.changed.connect(lambda _: self.retranslate())
        self.retranslate()
        self.go_to(0)

    # ---- chrome ----------------------------------------------------------------
    def _header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 12, 24, 12)
        if self.brand.logo:
            logo = QLabel()
            logo.setPixmap(QPixmap(str(self.brand.logo)).scaledToHeight(36, Qt.SmoothTransformation))
            h.addWidget(logo)
        else:
            h.addWidget(label("Wordmark", self.brand.name, wrap=False))
        h.addSpacing(10)
        h.addWidget(label("ProductName", self.brand.product_name, wrap=False))
        h.addStretch(1)
        self.mode_note = label("Muted", wrap=False)
        h.addWidget(self.mode_note)
        h.addSpacing(16)
        self.language = QComboBox()
        for lang in LANGUAGES:
            self.language.addItem("", lang)
        self.language.setCurrentIndex(self.language.findData(self.tr.lang))
        self.language.currentIndexChanged.connect(lambda _: self.tr.set_language(self.language.currentData()))
        h.addWidget(self.language)
        return header

    def _footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("Footer")
        h = QHBoxLayout(footer)
        h.setContentsMargins(24, 12, 24, 12)
        self.back = QPushButton()
        self.back.clicked.connect(lambda: self.go_to(self.stack.currentIndex() - 1))
        self.status = label("Muted", wrap=False)
        self.next = QPushButton()
        self.next.setObjectName("Primary")
        self.next.clicked.connect(self._next)
        h.addWidget(self.back)
        h.addStretch(1)
        h.addWidget(self.status)
        h.addSpacing(12)
        h.addWidget(self.next)
        return footer

    def retranslate(self) -> None:
        for i, lang in enumerate(LANGUAGES):
            self.language.setItemText(i, self.tr(f"ui.lang.{lang}"))
        self.back.setText(self.tr("ui.nav.back"))
        self.rail.retranslate()
        for page in self.pages:
            page.retranslate()
        self.refresh_nav()

    # ---- navigation ------------------------------------------------------------
    @property
    def page(self) -> StepPage:
        return self.pages[self.stack.currentIndex()]

    def go_to(self, index: int) -> None:
        index = max(0, min(index, len(self.pages) - 1))
        self.stack.setCurrentIndex(index)
        self.rail.set_current(index)
        self.page.clear_error()
        self.page.log_start = len(self.state.client.log) if self.state.client else 0
        self.page.on_enter()
        self.refresh_nav()

    def _next(self) -> None:
        index = self.stack.currentIndex()
        self.page.advance(lambda: self.go_to(index + 1))

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.status.setText(self.tr("ui.nav.working") if busy else "")
        self.refresh_nav()

    def refresh_nav(self) -> None:
        if not self._built:
            return
        index = self.stack.currentIndex()
        last = index == len(self.pages) - 1
        self.back.setVisible(0 < index and not last)
        self.next.setVisible(not last)
        self.next.setText(self.tr(self.page.next_key()))
        self.back.setEnabled(not self.busy)
        self.next.setEnabled(not self.busy and self.page.ready())
        self.language.setEnabled(not self.busy)
        self.mode_note.setText(self.tr(f"ui.mode.{self.state.mode}") if self.state.project else "")
        self.page.update_teaching()

    def open_explore(self) -> None:
        """Summaries of the cleaned table in its own window; matplotlib loads only now."""
        from app.explore_window import ExploreWindow

        if self.state.prepared is None or self.state.prepared.frame is None:
            return
        if self.explore_window is not None:
            self.explore_window.close()
        self.explore_window = ExploreWindow(self.state.prepared, self.brand, self.tr)
        self.explore_window.show()
        self.explore_window.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.explore_window is not None:
            self.explore_window.close()
        self.state.stop_mock()
        super().closeEvent(event)
