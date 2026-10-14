"""The "What's happening?" panel: a short plain-language explanation under each step,
and, where the app talked to REDCap, the actual requests it sent (token masked).

Collapsed by default so it never crowds the work; one click opens it. Request lines
come from RedcapClient.log, which already masks the token and reduces record data to
a count, so nothing secret or identifying can reach this panel.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget

from app.i18n import Translator
from app.widgets import label
from core.client import RequestLog

ELLIPSIS = "…"
# Parameters shown in the technical line, in this order; the rest are left out as noise.
SHOWN_PARAMS = ["content", "action", "format", "type", "overwriteBehavior", "returnContent", "dateFormat",
                "data", "fields", "records", "token"]


def request_kind(entry: RequestLog) -> str:
    if entry.content == "record":
        return "record_import" if "data" in entry.params else "record_export"
    return entry.content if entry.content in ("version", "project", "metadata", "formEventMapping") else "other"


def request_line(entry: RequestLog) -> str:
    """content=record · format=json · data=<100 records> · token=********"""
    parts = []
    fields = [v for k, v in entry.params.items() if k.startswith("fields[")]
    records = [v for k, v in entry.params.items() if k.startswith("records[")]
    for key in SHOWN_PARAMS:
        if key == "fields" and fields:
            more = ELLIPSIS if len(fields) > 3 else ""
            parts.append(f"fields={','.join(fields[:3])}{more}")
        elif key == "records" and records:
            parts.append(f"records=<{len(records)}>")
        elif key in entry.params:
            parts.append(f"{key}={entry.params[key]}")
    return "  ·  ".join(parts)


def describe_request(tr: Translator, entry: RequestLog) -> str:
    kind = request_kind(entry)
    count = entry.params.get("data", "").strip("<>").split(" ")[0] if kind == "record_import" else ""
    text = tr(f"ui.req.{kind}", count=count, overwrite=entry.params.get("overwriteBehavior", ""))
    if entry.ok:
        return tr("ui.req.ok", what=text, seconds=entry.seconds)
    return tr("ui.req.failed", what=text, seconds=entry.seconds)


class TeachingPanel(QFrame):
    def __init__(self, tr: Translator):
        super().__init__()
        self.setObjectName("Teach")
        self.tr = tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(8)
        self.toggle = QToolButton()
        self.toggle.setObjectName("Disclosure")
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.toggled.connect(self._show)
        layout.addWidget(self.toggle, 0, Qt.AlignLeft)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(4, 0, 0, 0)
        self.body_layout.setSpacing(8)
        layout.addWidget(self.body)
        self._signature = None
        self._show(False)

    def _show(self, on: bool) -> None:
        self.toggle.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)

    def set_content(self, paragraphs: list[str], requests: list[RequestLog] | None = None) -> None:
        """Replace the text. `requests` None means this step does not talk to REDCap."""
        self.toggle.setText(self.tr("ui.teach.toggle"))
        signature = (self.tr.lang, tuple(paragraphs),
                     None if requests is None else tuple((e.content, e.ok, e.seconds, len(e.params)) for e in requests))
        if signature == self._signature:
            return
        self._signature = signature
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()  # gone at once; deleteLater alone leaves it painted until the next event loop
                widget.setParent(None)
                widget.deleteLater()
        for text in paragraphs:
            if text:
                self.body_layout.addWidget(label("TeachText", text))
        if requests is None:
            return
        self.body_layout.addWidget(label("TeachHeading", self.tr("ui.teach.requests", count=len(requests))))
        if not requests:
            self.body_layout.addWidget(label("TeachText", self.tr("ui.teach.no_requests")))
        for i, entry in enumerate(requests, start=1):
            self.body_layout.addWidget(label("TeachText", f"{i}. {describe_request(self.tr, entry)}"))
            code = QLabel(request_line(entry))
            code.setObjectName("TeachCode")
            code.setWordWrap(True)
            code.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.body_layout.addWidget(code)
            if not entry.ok and entry.message:
                self.body_layout.addWidget(label("TeachText", self.tr("ui.req.answer", message=entry.message[:300])))

    def texts(self) -> list[str]:
        """Everything the panel shows (used by tests that look for leaks)."""
        out = [self.toggle.text()]
        for i in range(self.body_layout.count()):
            w = self.body_layout.itemAt(i).widget()
            if isinstance(w, QLabel):
                out.append(w.text())
        return out
