"""Edit one drafted answer list: codes, labels and their order."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.widgets import label
from core.infer import AnswerProblem, revise_answers
from core.profile import Choice

CODE, LABEL, MATCHES = range(3)


class AnswersDialog(QDialog):
    def __init__(self, tr, column: str, choices: list[Choice], parent=None):
        super().__init__(parent)
        self.tr, self.original = tr, choices
        self.choices: list[Choice] | None = None  # the edited list, once saved
        self.setWindowTitle(tr("ui.answers.title", column=column))
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(label("Muted", tr("ui.answers.lead")))

        self.table = QTableWidget(len(choices), 3)
        self.table.setHorizontalHeaderLabels([tr(f"ui.answers.h_{k}") for k in ("code", "label", "matches")])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(LABEL, QHeaderView.Stretch)
        header.setSectionResizeMode(MATCHES, QHeaderView.Stretch)
        for row, choice in enumerate(choices):
            self._set_row(row, row, choice.code, choice.label_id)
        layout.addWidget(self.table, 1)

        moves = QHBoxLayout()
        self.up = QPushButton(tr("ui.answers.up"))
        self.down = QPushButton(tr("ui.answers.down"))
        self.number = QPushButton(tr("ui.answers.number"))
        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(1))
        self.number.clicked.connect(self._number_in_order)
        for button in (self.up, self.down):
            moves.addWidget(button)
        moves.addStretch(1)
        moves.addWidget(self.number)
        layout.addLayout(moves)
        self.problem = label("Error")
        self.problem.hide()
        layout.addWidget(self.problem)

        buttons = QHBoxLayout()
        cancel = QPushButton(tr("ui.answers.cancel"))
        cancel.clicked.connect(self.reject)
        self.save = QPushButton(tr("ui.answers.save"))
        self.save.setObjectName("Primary")
        self.save.clicked.connect(self._save)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save)
        layout.addLayout(buttons)

    def _set_row(self, row: int, index: int, code: str, text: str) -> None:
        """One answer; `index` points into the original list, which the matches and spellings come from."""
        original = self.original[index]
        code_item = QTableWidgetItem(code)
        code_item.setData(Qt.UserRole, index)
        matches = QTableWidgetItem(", ".join(dict.fromkeys([original.label_id, *original.spellings])))
        matches.setFlags(matches.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, CODE, code_item)
        self.table.setItem(row, LABEL, QTableWidgetItem(text))
        self.table.setItem(row, MATCHES, matches)

    def rows(self) -> list[tuple[int, str, str]]:
        """(index into the original list, code, label) in the order shown."""
        items = [(self.table.item(r, CODE), self.table.item(r, LABEL)) for r in range(self.table.rowCount())]
        return [(code.data(Qt.UserRole), code.text(), text.text()) for code, text in items]

    def _move(self, step: int) -> None:
        row = self.table.currentRow()
        other = row + step
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        rows = self.rows()
        for r, (index, code, text) in ((row, rows[other]), (other, rows[row])):
            self._set_row(r, index, code, text)
        self.table.setCurrentCell(other, LABEL)

    def _number_in_order(self) -> None:
        for r in range(self.table.rowCount()):
            self.table.item(r, CODE).setText(str(r + 1))

    def _save(self) -> None:
        try:
            self.choices = revise_answers(self.original, self.rows())
        except AnswerProblem as problem:
            self.problem.setText(self.tr(f"ui.answers.problem_{problem.code}", **problem.params))
            self.problem.show()
            return
        self.accept()
