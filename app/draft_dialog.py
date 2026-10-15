"""Review a data dictionary drafted from a spreadsheet, then keep it as a form (a profile)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.widgets import label
from core.dictionary import build_dictionary
from core.export_csv import write_dictionary_csv
from core.infer import Draft, draft_problems, form_code_for, profile_from_draft
from core.profile import PATIENT_ID_FIELD, RECORD_ID_FIELD, Profile, Role

# Handling choices on the review screen, and the role each one gives a column.
HANDLING = {
    "upload": Role.data,
    "record_id": Role.record_id_source,
    "patient_link": Role.patient_id_source,
    "pseudonymise": Role.identifier_pseudonymise,
    "leave_out": Role.identifier_drop,
}
COLUMNS = ("column", "field", "type", "handling", "answers")


def handling_of(role: Role) -> str:
    return next((k for k, r in HANDLING.items() if r == role), "leave_out")


class DraftDialog(QDialog):
    def __init__(self, tr, draft: Draft, default_name: str, taken_codes: set[str], parent=None):
        super().__init__(parent)
        self.tr, self.draft, self.taken = tr, draft, taken_codes
        self.profile: Profile | None = None
        self.setWindowTitle(tr("ui.draft.title"))
        self.resize(1040, 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(label("Muted", tr("ui.draft.lead", rows=draft.rows)))

        form = QFormLayout()
        self.name = QLineEdit(default_name)
        form.addRow(label("Muted", tr("ui.draft.name"), wrap=False), self.name)
        layout.addLayout(form)
        self.summary = label()
        layout.addWidget(self.summary)

        self.table = QTableWidget(len(draft.columns), len(COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(f"ui.draft.h_{k}") for k in COLUMNS])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COLUMNS.index("answers"), QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        layout.addWidget(label("Muted", tr("ui.draft.answers_note")))
        self.problems = label("Error")
        self.problems.hide()
        layout.addWidget(self.problems)

        buttons = QHBoxLayout()
        self.save_file = QPushButton(tr("ui.draft.save_file"))
        self.save_file.clicked.connect(self._save_file)
        self.cancel = QPushButton(tr("ui.draft.cancel"))
        self.cancel.clicked.connect(self.reject)
        self.use_button = QPushButton(tr("ui.draft.use"))
        self.use_button.setObjectName("Primary")
        self.use_button.clicked.connect(lambda: self.use() and self.accept())
        buttons.addWidget(self.save_file)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.use_button)
        layout.addLayout(buttons)

        self.type_boxes: list[QComboBox] = []
        self.handling_boxes: list[QComboBox] = []
        for row, col in enumerate(draft.columns):
            self._fill_row(row, col)
        self.table.itemChanged.connect(self._field_edited)
        self._refresh()

    # ---- table ---------------------------------------------------------------------
    def _fill_row(self, row: int, col) -> None:
        tr = self.tr
        name = QTableWidgetItem(col.header)
        name.setFlags(name.flags() & ~Qt.ItemIsEditable)
        if col.reason:
            name.setToolTip(tr(f"ui.draft.reason_{col.reason}"))
        self.table.setItem(row, 0, name)
        self.table.setItem(row, 1, QTableWidgetItem(col.field))

        types = QComboBox()
        types.setObjectName("Cell")
        for kind in col.allowed_types() if col.type != "empty" else ["empty"]:
            types.addItem(tr(f"ui.draft.type_{kind}"), kind)
        types.setCurrentIndex(max(types.findData(col.type), 0))
        types.currentIndexChanged.connect(lambda _=0, c=col, box=types: self._type_changed(c, box))
        self.table.setCellWidget(row, 2, types)
        self.type_boxes.append(types)

        handling = QComboBox()
        handling.setObjectName("Cell")
        for key in HANDLING:
            if key == "record_id" and not col.unique:
                continue  # a record ID needs a different value on every row
            if key == "patient_link" and col.reason != "nik":
                continue  # a patient link is made from a NIK
            handling.addItem(tr(f"ui.draft.handling_{key}"), key)
        handling.setCurrentIndex(max(handling.findData(handling_of(col.role)), 0))
        handling.currentIndexChanged.connect(lambda _=0, c=col, box=handling: self._handling_changed(c, box))
        if col.reason:
            handling.setToolTip(tr(f"ui.draft.reason_{col.reason}"))
        self.table.setCellWidget(row, 3, handling)
        self.handling_boxes.append(handling)

        answers = " · ".join(f"{c.code} = {c.label_id}" for c in col.choices) or "—"
        item = QTableWidgetItem(answers)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setToolTip(answers)
        self.table.setItem(row, 4, item)

    def _type_changed(self, col, box: QComboBox) -> None:
        col.type = box.currentData()
        self._refresh()

    def _handling_changed(self, col, box: QComboBox) -> None:
        key = box.currentData()
        col.role = HANDLING[key]
        if key == "leave_out" and not col.reason:
            col.role = Role.ignore  # plain data the person chose not to upload
        self._refresh()

    def _field_edited(self, item: QTableWidgetItem) -> None:
        col = self.draft.columns[item.row()]
        if item.column() == 1 and col.role in (Role.data, Role.identifier_pseudonymise):
            col.field = item.text().strip()

    def _refresh(self) -> None:
        cols = self.draft.columns
        uploaded = sum(c.role == Role.data for c in cols)
        pseudonyms = sum(c.role in (Role.record_id_source, Role.patient_id_source, Role.identifier_pseudonymise)
                         for c in cols)
        self.summary.setText(self.tr("ui.draft.summary", total=len(cols), uploaded=uploaded, pseudonyms=pseudonyms,
                                     left_out=len(cols) - uploaded - pseudonyms))
        for col, box in zip(cols, self.type_boxes):
            box.setEnabled(col.role == Role.data and box.count() > 1)
        self._show_fields()

    def _show_fields(self) -> None:
        """The REDCap field each column becomes: editable when uploaded; record_id or patient_pid for
        the pseudonyms the app makes; a dash when the column is left out."""
        muted = self.palette().color(QPalette.PlaceholderText)
        self.table.blockSignals(True)
        for row, col in enumerate(self.draft.columns):
            item = self.table.item(row, 1)
            uploaded = col.role in (Role.data, Role.identifier_pseudonymise)
            text = {Role.record_id_source: RECORD_ID_FIELD, Role.patient_id_source: PATIENT_ID_FIELD}.get(col.role, "—")
            item.setText(col.field if uploaded else text)
            item.setFlags(item.flags() | Qt.ItemIsEditable if uploaded else item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QBrush() if uploaded else QBrush(muted))
        self.table.blockSignals(False)

    # ---- result ----------------------------------------------------------------------
    def _build(self) -> Profile | None:
        name = self.name.text().strip()
        problems = [("name", {})] if not name else []
        problems += draft_problems(self.draft.columns)
        if not problems:
            try:
                code = form_code_for(name, self.taken)
                return profile_from_draft(name, self.draft.columns, self.draft.date_format, code)
            except ValueError:
                problems = [("invalid", {})]
        self.problems.setText("\n".join(self.tr(f"ui.draft.problem_{code}", **params) for code, params in problems))
        self.problems.show()
        return None

    def use(self) -> bool:
        """Check the draft and keep it as self.profile. False (with the problems shown) if it cannot be used."""
        self.profile = self._build()
        return self.profile is not None

    def _save_file(self) -> None:
        profile = self._build()
        if profile is None:
            return
        self.problems.hide()
        path, _ = QFileDialog.getSaveFileName(self, self.tr("ui.draft.save_file"),
                                              f"{profile.identity.form_code}_dictionary.csv", "CSV (*.csv)")
        if path:
            write_dictionary_csv(build_dictionary(profile), path)
