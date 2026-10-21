"""The Tutorial tab: annotated screenshots of each step, and short notes on how the app works.

The screenshots are made by tools/make_tutorial.py from the running app, with synthetic data only.
What to press is highlighted and numbered; the numbers match the captions under each picture.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.diagrams import svg
from app.i18n import Translator
from app.widgets import clear_layout, label

ASSETS = Path(__file__).resolve().parent / "assets" / "tutorial"
# step -> how many things are highlighted (and captioned) in its screenshot
STEPS = {"connect": 2, "connect_real": 4, "connected": 3, "choose": 3, "review": 5, "edit": 2, "ready": 2, "upload": 2, "result": 3}
# topic -> the diagram drawn under its text, if any
TOPICS = {"overview": "pipeline", "identifiers": "identifiers", "pseudonyms": None, "checks": None,
          "records": None, "edits": None, "setup": "lifecycle"}
MAX_WIDTH, MIN_WIDTH, LIST_WIDTH, MARGIN = 900, 480, 250, 72


def screenshot_path(lang: str, step: str) -> Path:
    return ASSETS / lang / f"{step}.png"


def diagram_pixmap(name: str, tr: Translator, width: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg(name, tr).encode("utf-8")))
    size = renderer.defaultSize()
    image = QImage(width, round(size.height() * width / size.width()), QImage.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


class TutorialView(QWidget):
    def __init__(self, tr: Translator):
        super().__init__()
        self.tr = tr
        self._entries: list[tuple[str, str]] = []  # (kind, key) for each row of the list
        self._source: QPixmap | None = None  # the picture before it is fitted to the window
        self._diagram: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.list = QListWidget()
        self.list.setObjectName("TutorialList")
        self.list.setFixedWidth(LIST_WIDTH)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.currentRowChanged.connect(self._show)
        root.addWidget(self.list)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("Canvas")
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        page = QVBoxLayout(inner)
        page.setContentsMargins(36, 28, 36, 28)
        page.setSpacing(12)
        self.title = label("PageTitle")
        self.body = label("PageLead")
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.captions = QVBoxLayout()
        self.captions.setSpacing(6)
        self.prev = QPushButton()
        self.next = QPushButton()
        self.prev.clicked.connect(lambda: self._step(-1))
        self.next.clicked.connect(lambda: self._step(1))
        nav = QHBoxLayout()
        nav.addWidget(self.prev)
        nav.addStretch(1)
        nav.addWidget(self.next)
        for w in (self.title, self.body, self.picture):
            page.addWidget(w)
        page.addLayout(self.captions)
        page.addLayout(nav)
        page.addStretch(1)
        self.retranslate()

    # ---- list ---------------------------------------------------------------------
    def retranslate(self) -> None:
        tr = self.tr
        current = self._entries[self.list.currentRow()] if self._entries and self.list.currentRow() >= 0 else ("step", "connect")
        self.list.blockSignals(True)
        self.list.clear()
        self._entries = []
        for heading, kind, keys in (("ui.tut.steps", "step", STEPS), ("ui.tut.how", "topic", TOPICS)):
            item = QListWidgetItem(tr(heading))
            item.setFlags(Qt.NoItemFlags)
            font = QFont(item.font())
            font.setBold(True)
            item.setFont(font)
            self.list.addItem(item)
            self._entries.append(("heading", heading))
            for key in keys:
                title = tr(f"ui.tut.{key}.title" if kind == "step" else f"ui.tut.topic.{key}.title")
                self.list.addItem(QListWidgetItem("    " + title))
                self._entries.append((kind, key))
        self.list.blockSignals(False)
        self.list.setCurrentRow(self._entries.index(current) if current in self._entries else 1)
        self._show(self.list.currentRow())

    def select(self, kind: str, key: str) -> None:
        self.list.setCurrentRow(self._entries.index((kind, key)))

    def _step(self, direction: int) -> None:
        rows = [i for i, (kind, _) in enumerate(self._entries) if kind != "heading"]
        at = rows.index(self.list.currentRow())
        self.list.setCurrentRow(rows[max(0, min(len(rows) - 1, at + direction))])

    # ---- content --------------------------------------------------------------------
    def _show(self, row: int) -> None:
        if not 0 <= row < len(self._entries) or self._entries[row][0] == "heading":
            return
        kind, key = self._entries[row]
        tr = self.tr
        clear_layout(self.captions)
        self._source, self._diagram = None, None
        if kind == "step":
            self.title.setText(tr(f"ui.tut.{key}.title"))
            self.body.setText(tr(f"ui.tut.{key}.body"))
            path = screenshot_path(tr.lang, key)
            if path.exists():
                self._source = QPixmap(str(path))
            for n in range(1, STEPS[key] + 1):
                self.captions.addWidget(self._caption(n, tr(f"ui.tut.{key}.m{n}")))
            if self._source is None:
                self.captions.addWidget(label("Muted", tr("ui.tut.missing")))
        else:
            self.title.setText(tr(f"ui.tut.topic.{key}.title"))
            self.body.setText(tr(f"ui.tut.topic.{key}.body"))
            self._diagram = TOPICS[key]
        self.prev.setText(tr("ui.tut.prev"))
        self.next.setText(tr("ui.tut.next"))
        rows = [i for i, (k, _) in enumerate(self._entries) if k != "heading"]
        self.prev.setVisible(row != rows[0])
        self.next.setVisible(row != rows[-1])
        self._fit()

    def _caption(self, number: int, text: str) -> QLabel:
        caption = label("", f'<span style="color:#1E6BBD; font-weight:600">{number}</span>&nbsp;&nbsp;{escape(text)}')
        caption.setTextFormat(Qt.RichText)
        return caption

    def _width(self) -> int:
        return max(MIN_WIDTH, min(MAX_WIDTH, self.width() - LIST_WIDTH - MARGIN))

    def _fit(self) -> None:
        width = self._width()
        if self._source is not None:
            self.picture.setPixmap(self._source.scaledToWidth(width, Qt.SmoothTransformation))
        elif self._diagram is not None:
            self.picture.setPixmap(diagram_pixmap(self._diagram, self.tr, width))
        else:
            self.picture.clear()
        self.picture.setVisible(self.picture.pixmap() is not None and not self.picture.pixmap().isNull())

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._fit()
