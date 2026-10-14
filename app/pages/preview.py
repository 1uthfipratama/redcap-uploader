"""Step 3: how each file column is handled, and the first rows after cleaning.

Register forms are matched by official column number, so the mapping is fixed.
In Generic mode each column has a field picker; changes are applied on Next.
"""

from __future__ import annotations

from collections import Counter

from PySide6.QtWidgets import QComboBox

from app import workers
from app.pages.base import StepPage
from app.widgets import Disclosure, FrameModel, fill_table, label, new_table, table_view
from core.parse import ROW
from core.pipeline import prepare
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


class PreviewPage(StepPage):
    title_key = "ui.preview.title"
    lead_key = "ui.preview.lead"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.counts = label("Muted")
        self.columns_title = label("SectionTitle")
        self.columns = new_table()
        self.columns.setMinimumHeight(320)
        self.model = FrameModel(max_rows=50)
        self.rows_view = table_view(self.model)
        self.rows_view.setMinimumHeight(260)
        self.rows_box = Disclosure(self.rows_view)
        self.body.addWidget(self.counts)
        self.body.addWidget(self.columns_title)
        self.body.addWidget(self.columns)
        self.body.addWidget(self.rows_box)
        self._pickers: dict[str, QComboBox] = {}

    def translate(self) -> None:
        self.columns_title.setText(self.tr("ui.preview.columns"))
        self.rows_box.set_text(self.tr("ui.preview.first_rows"))
        self.on_enter()

    # ---- content -------------------------------------------------------------
    def on_enter(self) -> None:
        p = self.state.prepared
        if not p or p.frame is None:
            return
        if p.profile.is_generic:
            self._generic_rows()
        else:
            self._profile_rows()
        self.model.set_frame(p.frame.rename(columns={ROW: self.tr("ui.preview.row")}))

    def _role_text(self, role: Role, keep: bool = False) -> str:
        if role == Role.quasi_identifier and keep:
            return self.tr("ui.role.upload")
        return self.tr(f"ui.role.{ROLE_KEYS[role]}")

    def _profile_rows(self) -> list:
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
            number = f"({col.number})" + (f" {col.sub_label}" if col.sub_label else "")
            rows.append([number, col.label, field or "—", self._role_text(spec.role, spec.keep)])
        headers = [self.tr(f"ui.preview.h_{k}") for k in ("number", "column", "field", "handling")]
        fill_table(self.columns, headers, rows)
        self.counts.setText(self.tr("ui.preview.counts", total=sum(roles.values()),
                                    uploaded=roles["upload"] + roles["record_id"] + roles["patient_link"],
                                    pseudonymised=roles["pseudonymise"] + roles["record_id"] + roles["patient_link"],
                                    dropped=roles["drop_identifier"] + roles["drop_location"] + roles["ignore"]))
        return rows

    def _generic_rows(self) -> list:
        p = self.state.prepared
        fields = [""] + (self.state.project.fields if self.state.project else [])
        headers = [self.tr(f"ui.preview.h_{k}") for k in ("column", "field", "match", "handling")]
        rows = []
        for m in p.mapping.matches:
            match = self.tr(f"ui.match.{m.method}", score=round(m.confidence * 100))
            handling = (self.tr("ui.role.drop_identifier") if m.role == Role.identifier_drop.value
                        else self.tr("ui.role.upload") if m.field else self.tr("ui.role.ignore"))
            rows.append([m.source_label, m.field or "", match, handling])
        fill_table(self.columns, headers, rows)
        self._pickers = {}
        for r, m in enumerate(p.mapping.matches):
            if m.role == Role.identifier_drop.value:
                continue
            picker = QComboBox()
            for f in fields:
                picker.addItem(f or "—", f or None)
            picker.setCurrentIndex(max(picker.findData(m.field), 0))
            picker.currentIndexChanged.connect(lambda _=0, key=m.source_key, box=picker: self._override(key, box))
            self.columns.setCellWidget(r, 1, picker)
            self._pickers[m.source_key] = picker
        uploaded = sum(1 for m in p.mapping.matches if m.field)
        self.counts.setText(self.tr("ui.preview.counts_generic", total=len(p.mapping.matches), uploaded=uploaded))
        return rows

    def _override(self, key: str, box: QComboBox) -> None:
        self.state.overrides[key] = box.currentData()
        self.state.prepared_stale = True

    # ---- navigation ------------------------------------------------------------
    def advance(self, proceed) -> None:
        state = self.state
        if not state.prepared_stale:
            proceed()
            return

        def done(prepared):
            self.ctx.set_busy(False)
            state.prepared, state.prepared_stale = prepared, False
            proceed()

        def failed(key, params):
            self.ctx.set_busy(False)
            self.show_error(key, params)

        self.ctx.set_busy(True)
        workers.run(lambda: prepare(state.detected, state.profile, None, target_fields=state.project.fields,
                                    overrides=state.overrides), done, failed)
