"""Small building blocks shared by the wizard steps."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

STEP_KEYS = ["connect", "choose", "preview", "validate", "upload", "result"]


def label(name: str = "", text: str = "", wrap: bool = True) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Panel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(12)


class StepRail(QFrame):
    """Numbered list of the six steps, the current one highlighted."""

    def __init__(self, tr):
        super().__init__()
        self.setObjectName("StepRail")
        self.setFixedWidth(230)
        self.tr_ = tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(4)
        self.rows: list[tuple[QFrame, QLabel, QLabel]] = []
        for i, _ in enumerate(STEP_KEYS, start=1):
            row = QFrame()
            row.setObjectName("Step")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            h.setSpacing(10)
            number = QLabel(str(i))
            number.setObjectName("StepNumber")
            text = QLabel()
            text.setWordWrap(True)
            h.addWidget(number)
            h.addWidget(text, 1)
            layout.addWidget(row)
            self.rows.append((row, number, text))
        layout.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        for (_, _, text), key in zip(self.rows, STEP_KEYS):
            text.setText(self.tr_(f"ui.step.{key}"))

    def set_current(self, index: int) -> None:
        for i, (row, number, _) in enumerate(self.rows):
            state = "current" if i == index else ("done" if i < index else "todo")
            number.setText("✓" if state == "done" else str(i + 1))
            for widget in (row, number):
                widget.setProperty("state", state)
                repolish(widget)


class Disclosure(QWidget):
    """A heading that shows or hides the detail under it."""

    def __init__(self, content: QWidget, expanded: bool = False):
        super().__init__()
        self.button = QToolButton()
        self.button.setObjectName("Disclosure")
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button, 0, Qt.AlignLeft)
        layout.addWidget(content)
        self.button.toggled.connect(self._toggle)
        self._toggle(expanded)

    def _toggle(self, on: bool) -> None:
        self.button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.content.setVisible(on)

    def set_text(self, text: str) -> None:
        self.button.setText(text)


class FrameModel(QAbstractTableModel):
    """Read-only view of a DataFrame's first rows."""

    def __init__(self, frame: pd.DataFrame | None = None, max_rows: int = 50):
        super().__init__()
        self.max_rows = max_rows
        self.frame = pd.DataFrame()
        if frame is not None:
            self.set_frame(frame)

    def set_frame(self, frame: pd.DataFrame) -> None:
        self.beginResetModel()
        self.frame = frame.head(self.max_rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return len(self.frame)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return len(self.frame.columns)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            value = self.frame.iat[index.row(), index.column()]
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return ""
            if hasattr(value, "strftime"):
                return value.strftime("%Y-%m-%d")
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return str(self.frame.columns[section])
        return None


def table_view(model: QAbstractTableModel) -> QTableView:
    view = QTableView()
    view.setModel(model)
    view.verticalHeader().setVisible(False)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    view.horizontalHeader().setStretchLastSection(True)
    view.setAlternatingRowColors(False)
    view.setSelectionBehavior(QTableView.SelectRows)
    return view


def fill_table(table: QTableWidget, headers: list[str], rows: list[list[object]],
               stretch: tuple[int, ...] = (), fit_rows: int | None = None) -> None:
    """Fill a read-only table. Numbers are right-aligned; columns fit their content, and
    columns in `stretch` share any spare width and wrap. With fit_rows, the table is only
    as tall as its rows (up to fit_rows, then it scrolls)."""
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, item)
    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.setStretchLastSection(False)
    table.resizeColumnsToContents()
    for c in range(len(headers)):
        if c in stretch:
            header.setSectionResizeMode(c, QHeaderView.Stretch)
        else:
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
    table.resizeRowsToContents()
    if fit_rows is not None:
        shown = min(len(rows), fit_rows)
        height = header.height() + sum(table.rowHeight(r) for r in range(shown)) + 2 * table.frameWidth() + 2
        if len(rows) > fit_rows:
            height += table.horizontalScrollBar().sizeHint().height()
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)


def new_table() -> QTableWidget:
    table = QTableWidget()
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setWordWrap(True)
    return table


class DropZone(QFrame):
    """Accepts a dropped file; shows a short hint."""

    dropped = Signal(Path)

    def __init__(self, suffixes: tuple[str, ...]):
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.suffixes = suffixes
        self.hint = label("Muted")
        self.hint.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)

    def _file(self, event) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in self.suffixes:
                return path
        return None

    def dragEnterEvent(self, event):  # noqa: N802 (Qt API)
        if self._file(event):
            self.setProperty("hover", True)
            repolish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setProperty("hover", False)
        repolish(self)

    def dropEvent(self, event):  # noqa: N802
        self.setProperty("hover", False)
        repolish(self)
        path = self._file(event)
        if path:
            self.dropped.emit(path)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


Callback = Callable[[], None]
