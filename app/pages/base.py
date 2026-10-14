"""What every wizard step has: a title, a short lead, a panel, and the navigation hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from app.i18n import Translator
from app.state import AppState
from app.theme import Brand
from app.teaching import TeachingPanel
from app.widgets import Panel, label


@dataclass
class Context:
    tr: Translator
    state: AppState
    brand: Brand
    set_busy: Callable[[bool], None]  # disables navigation while work runs
    refresh_nav: Callable[[], None]  # re-reads ready() and the Next label
    go_to: Callable[[int], None]
    open_explore: Callable[[], None]


class StepPage(QWidget):
    title_key = ""
    lead_key = ""

    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx, self.tr, self.state = ctx, ctx.tr, ctx.state
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("Canvas")
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(10)
        self.title = label("PageTitle")
        self.lead = label("PageLead")
        self.panel = Panel()
        self.body = self.panel.body
        self.message = label("Error")
        self.message.hide()
        layout.addWidget(self.title)
        layout.addWidget(self.lead)
        layout.addSpacing(8)
        layout.addWidget(self.panel)
        layout.addWidget(self.message)
        self.teach = TeachingPanel(self.tr)
        layout.addSpacing(6)
        layout.addWidget(self.teach)
        layout.addStretch(1)
        self._error: tuple[str, dict] | None = None
        self.log_start = 0  # client.log position when this step was entered

    # ---- language --------------------------------------------------------------
    def retranslate(self) -> None:
        self.title.setText(self.tr(self.title_key))
        self.lead.setText(self.tr(self.lead_key))
        if self._error:
            self.message.setText(self.tr(*self._error[:1], **self._error[1]))
        self.translate()

    def translate(self) -> None:
        """Pages set their own text here; called on start and on every language switch."""

    # ---- "What's happening?" ---------------------------------------------------
    def teaching(self) -> tuple[list[str], list | None]:
        """Paragraphs for this step, and the REDCap requests to show (None: this step sends none)."""
        return [], None

    def requests_here(self) -> list:
        client = self.state.client
        return list(client.log[self.log_start:]) if client else []

    def update_teaching(self) -> None:
        paragraphs, requests = self.teaching()
        self.teach.set_content(paragraphs, requests)

    # ---- navigation ------------------------------------------------------------
    def on_enter(self) -> None:
        """Called each time the step is shown."""

    def ready(self) -> bool:
        return True

    def next_key(self) -> str:
        return "ui.nav.next"

    def advance(self, proceed: Callable[[], None]) -> None:
        """Called by Next. Pages that must do work first call proceed() when it succeeds."""
        proceed()

    # ---- inline errors ---------------------------------------------------------
    def show_error(self, key: str, params: dict | None = None) -> None:
        self._error = (key, params or {})
        self.message.setText(self.tr(key, **(params or {})))
        self.message.show()

    def clear_error(self) -> None:
        self._error = None
        self.message.hide()
