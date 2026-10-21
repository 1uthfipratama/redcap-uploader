"""The "Columns" section of the Review step: how each file column is handled.

Register forms are matched by official column number, so the mapping is fixed.
In Generic mode each column has a field picker; changes are applied on Next.
"""

from __future__ import annotations

from collections import Counter

from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from app.i18n import Translator
from app.state import AppState
from app.widgets import fill_table, label, new_table
from core.profile import PATIENT_ID_FIELD, RECORD_ID_FIELD, Role

ROLE_KEYS = {
    Role.data: "upload",
    Role.identifier_pseudonymise: "pseudonymise",
    Role.record_id_source: "record_id",
    Role.patient_id_source: "patient_link",
    Role.identifier_drop: "drop_identifier",
    Role.quasi_identifier: "drop_location",
    Role.ignore: "ignore",
    Role.constant: "ignore",
}


class ColumnsSection(QWidget):
    def __init__(self, tr: Translator, state: AppState):
        super().__init__()
        self.tr, self.state = tr, state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.counts = label("Muted")
        self.table = new_table()
        self.table.setMinimumHeight(320)
        layout.addWidget(self.counts)
        layout.addWidget(self.table)
        self._pickers: dict[str, QComboBox] = {}

    def refresh(self) -> None:
        p = self.state.prepared
        if not p or p.frame is None:
            return
        if p.profile.is_generic:
            self._generic_rows()
        else:
            self._profile_rows()

    def _role_text(self, role: Role, keep: bool = False) -> str:
        if role == Role.quasi_identifier and keep:
            return self.tr("ui.role.upload")
        return self.tr(f"ui.role.{ROLE_KEYS[role]}")

    def _profile_rows(self) -> None:
        p, profile = self.state.prepared, self.state.prepared.profile
        rows, roles = [], Counter()
        for col in p.layout.columns:
            spec = profile.column(col.key)
            if spec is None:
                continue
            field = {Role.record_id_source: RECORD_ID_FIELD, Role.patient_id_source: PATIENT_ID_FIELD}.get(spec.role, spec.field)
            if spec.role == Role.quasi_identifier and not spec.keep:
                field = None
            key = "upload" if spec.role == Role.quasi_identifier and spec.keep else ROLE_KEYS[spec.role]
            roles[key] += 1
            number = f"({col.number})" + (f" {col.sub_label}" if col.sub_label else "") if col.number else "—"
            rows.append([number, col.label, field or "—", self._role_text(spec.role, spec.keep)])
        headers = [self.tr(f"ui.preview.h_{k}") for k in ("number", "column", "field", "handling")]
        fill_table(self.table, headers, rows, stretch=(1, 3))
        uploaded = sum(1 for r in rows if r[2] != "—")
        pseudonymised = roles["pseudonymise"] + roles["record_id"] + roles["patient_link"]
        self.counts.setText(self.tr("ui.preview.counts", total=len(rows), uploaded=uploaded,
                                    pseudonymised=pseudonymised, dropped=len(rows) - uploaded))

    def _generic_rows(self) -> None:
        p = self.state.prepared
        fields = [""] + (self.state.project.fields if self.state.project else [])
        headers = [self.tr(f"ui.preview.h_{k}") for k in ("column", "field", "match", "handling")]
        rows = []
        for m in p.mapping.matches:
            match = self.tr(f"ui.match.{m.method}", score=round(m.confidence * 100))
            handling = (self.tr("ui.role.drop_identifier") if m.role == Role.identifier_drop.value
                        else self.tr("ui.role.upload") if m.field else self.tr("ui.role.ignore"))
            rows.append([m.source_label, m.field or "", match, handling])
        fill_table(self.table, headers, rows, stretch=(0, 3))
        self._pickers = {}
        for r, m in enumerate(p.mapping.matches):
            if m.role == Role.identifier_drop.value:
                continue
            picker = QComboBox()
            for f in fields:
                picker.addItem(f or "—", f or None)
            picker.setCurrentIndex(max(picker.findData(m.field), 0))
            picker.currentIndexChanged.connect(lambda _=0, key=m.source_key, box=picker: self._override(key, box))
            self.table.setCellWidget(r, 1, picker)
            self._pickers[m.source_key] = picker
        uploaded = sum(1 for m in p.mapping.matches if m.field)
        self.counts.setText(self.tr("ui.preview.counts_generic", total=len(p.mapping.matches), uploaded=uploaded))

    def _override(self, key: str, box: QComboBox) -> None:
        self.state.overrides[key] = box.currentData()
        self.state.prepared_stale = True
