"""The table on the Review step, and the window for editing one value.

The table lists every row that would be sent, one column per field. Problems, edited
cells and skipped rows are marked; the colours come from the brand file. Rows are named
by their spreadsheet row number. Fields made from an identifier cannot be edited.
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from app.i18n import Translator
from app.theme import Brand
from app.widgets import label
from core.issues import Issue
from core.parse import ROW, human_format
from core.pipeline import redcap_value
from core.review import EditRejected, Review

MODES = ("all", "errors", "warnings", "edited", "skipped")
TINT_ALPHA = 46


def _tint(color: str) -> QBrush:
    c = QColor(color)
    c.setAlpha(TINT_ALPHA)
    return QBrush(c)


class ReviewModel(QAbstractTableModel):
    """Read-only view of a Review: the file's values with the edits laid over them."""

    def __init__(self, review: Review, tr: Translator, brand: Brand):
        super().__init__()
        self.tr = tr
        colors = brand.colors
        self._tints = {"error": _tint(colors["error"]), "warning": _tint(colors["warning"]),
                       "edited": QBrush(QColor(colors["primary_soft"]))}
        self._skipped_brush = QBrush(QColor(colors["canvas"]))
        self._muted = QBrush(QColor(colors["muted"]))
        self._struck = QFont(QApplication.font())
        self._struck.setStrikeOut(True)
        self.mode = "all"
        self._labels: dict[str, dict[str, str]] = {}
        self.set_review(review)

    # ---- content ------------------------------------------------------------------
    def set_review(self, review: Review) -> None:
        self.beginResetModel()
        self.review = review
        frame = review.base.frame
        self.fields = [c for c in frame.columns if c != ROW]
        self._values = {f: frame[f].tolist() for f in self.fields}
        self._rows = [int(r) for r in frame[ROW]]
        self._position = {row: i for i, row in enumerate(self._rows)}
        profile = review.base.profile
        self._specs = {f: profile.column_for_field(f) for f in self.fields}
        self._date_format = profile.layout.date_format
        self._labels = {}
        self._load()
        self.endResetModel()

    def refresh(self) -> None:
        """Call after the review changed or the filter was set."""
        self.beginResetModel()
        self._load()
        self.endResetModel()

    def retranslate(self) -> None:
        self._labels = {}
        if self.rowCount():
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount() - 1)

    def _load(self) -> None:
        review = self.review
        self.cell_issues: dict[tuple[int, str], list[Issue]] = {}
        self.row_issues: dict[int, list[Issue]] = {}
        for issue in review.effective.issues:
            if issue.row is None:
                continue
            self.row_issues.setdefault(issue.row, []).append(issue)
            if issue.field:
                self.cell_issues.setdefault((issue.row, issue.field), []).append(issue)
        self.error_rows = sorted(row for row, issues in self.row_issues.items()
                                 if row in self._position and any(i.is_error for i in issues))
        warning_rows = {row for row, issues in self.row_issues.items()
                        if row in self._position and any(not i.is_error for i in issues)}
        edited_rows = {row for row, _ in review.edits}
        keep = {"all": lambda row: True,
                "errors": set(self.error_rows).__contains__,
                "warnings": warning_rows.__contains__,
                "edited": edited_rows.__contains__,
                "skipped": review.skipped.__contains__}[self.mode]
        self._visible = [i for i, row in enumerate(self._rows) if keep(row)]
        self._shown_at = {pos: i for i, pos in enumerate(self._visible)}

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.refresh()

    # ---- lookups the page needs -----------------------------------------------------
    def row_at(self, index: QModelIndex) -> int | None:
        return self._rows[self._visible[index.row()]] if index.isValid() else None

    def field_at(self, index: QModelIndex) -> str | None:
        return self.fields[index.column() - 1] if index.isValid() and index.column() > 0 else None

    def index_of(self, row: int, field: str | None = None) -> QModelIndex:
        """The cell for a row (and field), or an invalid index when the filter hides the row."""
        shown = self._shown_at.get(self._position.get(row))
        if shown is None:
            return QModelIndex()
        return self.index(shown, self.fields.index(field) + 1 if field in self.fields else 0)

    # ---- Qt model API -----------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 (Qt API)
        return 0 if parent.isValid() else len(self._visible)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.fields) + 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return self.tr("ui.preview.row") if section == 0 else self.fields[section - 1]
        if role == Qt.ToolTipRole and section > 0:
            spec = self._specs[self.fields[section - 1]]
            if spec is not None:
                return (spec.label_id if self.tr.lang == "id" else spec.label_en) or spec.label
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, field = self.row_at(index), self.field_at(index)
        skipped = row in self.review.skipped
        if role == Qt.DisplayRole:
            return str(row) if field is None else self._text(row, field)
        if role == Qt.BackgroundRole:
            return self._skipped_brush if skipped else self._tints.get(self._state(row, field))
        if role == Qt.ForegroundRole and skipped:
            return self._muted
        if role == Qt.FontRole and skipped:
            return self._struck
        if role == Qt.ToolTipRole:
            return self._tip(row, field, skipped)
        return None

    # ---- how a cell looks ------------------------------------------------------------
    def _state(self, row: int, field: str | None) -> str | None:
        issues = self.row_issues.get(row, []) if field is None else self.cell_issues.get((row, field), [])
        if issues:
            return "error" if any(i.is_error for i in issues) else "warning"
        edited = any(r == row for r, _ in self.review.edits) if field is None else (row, field) in self.review.edits
        return "edited" if edited else None

    def _value(self, row: int, field: str) -> object:
        edit = self.review.edits.get((row, field))
        return edit.new if edit else self._values[field][self._position[row]]

    def _text(self, row: int, field: str) -> str:
        return self.format(field, self._value(row, field))

    def format(self, field: str, value: object) -> str:
        """A value as the person reads and types it: dates as in the file, answers with their code."""
        if value is None:
            return ""
        if isinstance(value, (dt.date, dt.datetime)):
            return value.strftime(self._date_format)
        spec = self._specs.get(field)
        if spec is not None and spec.type == "choice":
            name = self._choice_labels(field).get(str(value))
            return f"{value} · {name}" if name else str(value)
        return redcap_value(value)

    def _choice_labels(self, field: str) -> dict[str, str]:
        if field not in self._labels:
            profile, spec = self.review.base.profile, self._specs[field]
            self._labels[field] = {c.code: (c.label_id if self.tr.lang == "id" else c.label_en)
                                   for c in profile.choices_for(spec)}
        return self._labels[field]

    def _tip(self, row: int, field: str | None, skipped: bool) -> str | None:
        tr = self.tr
        if skipped:
            return tr("ui.review.skipped_tip")
        issues = self.row_issues.get(row, []) if field is None else self.cell_issues.get((row, field), [])
        lines = [f"{tr.problem(i)} {tr.fix(i)}" for i in issues]
        if field is not None:
            edit = self.review.edits.get((row, field))
            if edit:
                lines.append(tr("ui.review.edited_was", value=self.format(field, edit.original) or tr("ui.edit.blank")))
            if self.review.spec(field) is None:
                lines.append(tr("ui.review.locked"))
        return "\n".join(lines) or None


class EditCellDialog(QDialog):
    """One value: a list of answers for a choice field, a box for anything else."""

    def __init__(self, tr: Translator, model: ReviewModel, row: int, field: str, parent=None):
        super().__init__(parent)
        self.tr, self.model, self.row, self.field = tr, model, row, field
        review = model.review
        spec = review.spec(field)
        self.reset_requested = False
        self.setWindowTitle(tr("ui.edit.title"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(label("SectionTitle", tr("ui.edit.lead", row=row, field=field)))
        original = model.format(field, review.original(row, field)) or tr("ui.edit.blank")
        layout.addWidget(label("Muted", tr("ui.edit.original", value=original)))
        for issue in model.cell_issues.get((row, field), []):
            layout.addWidget(label("Error" if issue.is_error else "Warning", f"{tr.problem(issue)} {tr.fix(issue)}"))
        current = review.value(row, field)
        if spec.type == "choice":
            self.box = QComboBox()
            self.box.addItem("—", "")
            for choice in review.base.profile.choices_for(spec):
                name = choice.label_id if tr.lang == "id" else choice.label_en
                self.box.addItem(f"{choice.code} · {name}", choice.code)
            self.box.setCurrentIndex(max(self.box.findData(current if current is not None else ""), 0))
            self.input = self.box
        else:
            self.line = QLineEdit(model.format(field, current))
            if spec.type == "date":
                self.line.setPlaceholderText(human_format(review.base.profile.layout.date_format))
            self.input = self.line
        layout.addWidget(self.input)
        self.error = label("Error")
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        self.reset = QPushButton(tr("ui.edit.reset"))
        self.reset.clicked.connect(self._reset)
        self.reset.setVisible((row, field) in review.edits)
        cancel = QPushButton(tr("ui.edit.cancel"))
        cancel.clicked.connect(self.reject)
        self.save = QPushButton(tr("ui.edit.save"))
        self.save.setObjectName("Primary")
        self.save.setDefault(True)
        self.save.clicked.connect(self._save)
        buttons.addWidget(self.reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save)
        layout.addLayout(buttons)

    def text(self) -> str:
        return self.box.currentData() if hasattr(self, "box") else self.line.text()

    def _reset(self) -> None:
        self.reset_requested = True
        self.accept()

    def _save(self) -> None:
        try:
            self.model.review.parse(self.field, self.text())
        except EditRejected as refused:
            self.error.setText(self.tr.problem(refused.issue))
            self.error.show()
            return
        self.accept()
