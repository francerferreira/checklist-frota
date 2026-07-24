from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout

from components import TableSkeletonOverlay, show_notice
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


OCCURRENCE_TYPES = ["PRESENTE", "FALTA", "ATRASO", "ATESTADO", "FERIAS", "DSR", "FOLGA", "CURSO", "AFASTADO", "SERVICO_EXTERNO"]


class AttendanceDialog(QDialog):
    def __init__(self, api_client, record: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.record = record or {}
        self.result_payload = None
        self.selected_document = None
        self.setWindowTitle("Lançamento de frequência")
        configure_dialog_window(self, width=780, height=620, min_width=640, min_height=560)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=780)

        header = QLabel("Frequência e ocorrências")
        header.setObjectName("PageTitle")
        subtitle = QLabel("Registre presença, falta, atraso, atestado, férias, DSR ou folga. Não há exclusão física.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("HeaderCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.employee_combo = QComboBox()
        for employee in self.api_client.get_employees():
            self.employee_combo.addItem(f"{employee.get('registration')} - {employee.get('full_name')}", employee.get("id"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(OCCURRENCE_TYPES)
        self.type_combo.setCurrentText(self.record.get("occurrence_type") or "PRESENTE")
        self.date_input = QLineEdit(self.record.get("occurrence_date") or date.today().isoformat())
        self.end_date_input = QLineEdit("")
        self.end_date_input.setPlaceholderText("Opcional para atestado, férias ou afastamento")
        self.scheduled_input = QLineEdit(self.record.get("scheduled_time") or "")
        self.scheduled_input.setPlaceholderText("HH:MM")
        self.arrival_input = QLineEdit(self.record.get("arrival_time") or "")
        self.arrival_input.setPlaceholderText("HH:MM")
        self.justified = QCheckBox("Ocorrência justificada")
        self.justified.setChecked(bool(self.record.get("is_justified")))
        self.reason_input = QLineEdit(self.record.get("reason") or "")
        self.notes_input = QLineEdit(self.record.get("notes") or "")
        self.change_reason_input = QLineEdit()
        self.change_reason_input.setPlaceholderText("Obrigatório ao corrigir")
        self.document_label = QLabel(self.record.get("document_path") or "Nenhum documento selecionado")
        document_button = QPushButton("Anexar documento")
        document_button.clicked.connect(self._choose_document)
        document_box = QHBoxLayout()
        document_box.addWidget(document_button)
        document_box.addWidget(self.document_label, 1)

        selected_employee_id = self.record.get("employee_id")
        for index in range(self.employee_combo.count()):
            if self.employee_combo.itemData(index) == selected_employee_id:
                self.employee_combo.setCurrentIndex(index)
                break
        if self.record:
            self.employee_combo.setEnabled(False)
            self.date_input.setEnabled(False)

        def field(row, column, label_text, widget):
            box = QFrame()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(5)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            box_layout.addWidget(label)
            if isinstance(widget, QHBoxLayout): box_layout.addLayout(widget)
            else: box_layout.addWidget(widget)
            form.addWidget(box, row, column)

        field(0, 0, "Colaborador", self.employee_combo)
        field(0, 1, "Tipo", self.type_combo)
        field(1, 0, "Data", self.date_input)
        field(1, 1, "Data final", self.end_date_input)
        field(2, 0, "Horário previsto", self.scheduled_input)
        field(2, 1, "Horário de chegada", self.arrival_input)
        field(3, 0, "Justificativa", self.justified)
        field(3, 1, "Motivo", self.reason_input)
        field(4, 0, "Documento", document_box)
        field(4, 1, "Observação", self.notes_input)
        if self.record: field(5, 0, "Motivo da correção", self.change_reason_input)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        save = QPushButton("Salvar lançamento")
        save.setProperty("variant", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _choose_document(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar documento", "", "Documentos (*.pdf *.png *.jpg *.jpeg)")
        if path:
            self.selected_document = path
            self.document_label.setText(path)

    def _submit(self):
        if self.employee_combo.currentData() is None:
            show_notice(self, "Colaborador obrigatório", "Cadastre ou selecione um colaborador antes do lançamento.", icon_name="warning")
            return
        self.result_payload = {
            "employee_id": self.employee_combo.currentData(),
            "occurrence_date": self.date_input.text().strip(),
            "end_date": self.end_date_input.text().strip() or None,
            "occurrence_type": self.type_combo.currentText(),
            "scheduled_time": self.scheduled_input.text().strip() or None,
            "arrival_time": self.arrival_input.text().strip() or None,
            "is_justified": self.justified.isChecked(),
            "reason": self.reason_input.text().strip() or None,
            "notes": self.notes_input.text().strip() or None,
            "document_path": self.record.get("document_path") or None,
        }
        if self.record:
            self.result_payload["change_reason"] = self.change_reason_input.text().strip()
        self.accept()


class AttendancePage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_user = current_user or {}
        self.records = []
        self.selected_record = None
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        header = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel("Frequência e ocorrências")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Controle diário de presença, falta, atraso, atestado, férias, DSR e folgas com histórico auditável.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title); text.addWidget(subtitle)
        self.add_button = QPushButton("Novo lançamento")
        self.add_button.setProperty("variant", "primary")
        self.add_button.clicked.connect(self.add_record)
        self.edit_button = QPushButton("Corrigir selecionado")
        self.edit_button.clicked.connect(self.edit_record)
        self.cancel_button = QPushButton("Cancelar lançamento")
        self.cancel_button.setProperty("variant", "danger")
        self.cancel_button.clicked.connect(self.cancel_record)
        header.addLayout(text); header.addStretch(); header.addWidget(self.add_button); header.addWidget(self.edit_button); header.addWidget(self.cancel_button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.date_filter = QLineEdit(date.today().isoformat())
        self.type_filter = QComboBox(); self.type_filter.addItem("Todos os tipos", "")
        for occurrence_type in OCCURRENCE_TYPES: self.type_filter.addItem(occurrence_type, occurrence_type)
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        filters.addWidget(QLabel("Data:")); filters.addWidget(self.date_filter); filters.addWidget(self.type_filter); filters.addWidget(refresh); filters.addStretch()
        layout.addLayout(filters)

        card = QFrame(); style_table_card(card); self.table_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card); card_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Data", "Colaborador", "Tipo", "Atraso", "Justificado", "Situação", "Motivo"])
        configure_table(self.table); self.table.setMinimumHeight(500); self.table.itemSelectionChanged.connect(self._selection_changed)
        card_layout.addWidget(self.table); layout.addWidget(card)
        self.info = QLabel("Selecione um lançamento para corrigir ou cancelar."); self.info.setObjectName("MutedText"); layout.addWidget(self.info)
        self.edit_button.setEnabled(False); self.cancel_button.setEnabled(False)

    def set_loading_state(self, loading: bool):
        self.table_skeleton.show_skeleton("Carregando frequência") if loading else self.table_skeleton.hide_skeleton()

    def refresh(self, preferred_id: int | None = None):
        self.records = self.api_client.get_employee_attendance(occurrence_date=self.date_filter.text().strip() or None, occurrence_type=self.type_filter.currentData() or None)
        self.table.setSortingEnabled(False); self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.records))
            for row, record in enumerate(self.records):
                employee = record.get("employee") or {}
                self.table.setItem(row, 0, make_table_item(record.get("occurrence_date", ""), payload=record))
                self.table.setItem(row, 1, make_table_item(employee.get("full_name", "")))
                self.table.setItem(row, 2, make_table_item(record.get("occurrence_type", "")))
                self.table.setItem(row, 3, make_table_item(str(record.get("delay_minutes", 0))))
                self.table.setItem(row, 4, make_table_item("Sim" if record.get("is_justified") else "Não"))
                self.table.setItem(row, 5, make_table_item(record.get("record_status", "")))
                self.table.setItem(row, 6, make_table_item(record.get("reason", "")))
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False); self.table.setSortingEnabled(True)
        if self.records:
            self.table.selectRow(next((index for index, record in enumerate(self.records) if record.get("id") == preferred_id), 0))
        else:
            self.selected_record = None; self.edit_button.setEnabled(False); self.cancel_button.setEnabled(False)

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        self.selected_record = self.table.item(selected[0].topRow(), 0).data(Qt.UserRole) if selected else None
        active = bool(self.selected_record and self.selected_record.get("record_status") == "ATIVO")
        self.edit_button.setEnabled(active); self.cancel_button.setEnabled(active)

    def _upload_document(self, dialog: AttendanceDialog, payload: dict):
        if dialog.selected_document:
            upload = self.api_client.upload_file(dialog.selected_document, "rh", "frequencia", self.current_user.get("login") or "rh")
            payload["document_path"] = upload.get("path")
        return payload

    def add_record(self):
        dialog = AttendanceDialog(self.api_client, parent=self)
        if not dialog.exec() or not dialog.result_payload: return
        try:
            records = self.api_client.create_employee_attendance(self._upload_document(dialog, dialog.result_payload))
            show_notice(self, "Lançamento registrado", f"{len(records)} dia(s) registrado(s) com sucesso.", icon_name="dashboard")
            self.refresh((records or [{}])[0].get("id")); self.data_changed.emit()
        except Exception as exc: show_notice(self, "Falha no lançamento", str(exc), icon_name="warning")

    def edit_record(self):
        if not self.selected_record: return
        dialog = AttendanceDialog(self.api_client, self.selected_record, self)
        if not dialog.exec() or not dialog.result_payload: return
        try:
            updated = self.api_client.update_employee_attendance(self.selected_record["id"], self._upload_document(dialog, dialog.result_payload))
            show_notice(self, "Lançamento corrigido", "A correção foi auditada.", icon_name="dashboard")
            self.refresh((updated or {}).get("id")); self.data_changed.emit()
        except Exception as exc: show_notice(self, "Falha na correção", str(exc), icon_name="warning")

    def cancel_record(self):
        if not self.selected_record: return
        reason, accepted = QInputDialog.getText(self, "Cancelar lançamento", "Motivo do cancelamento:")
        if not accepted or not reason.strip(): return
        try:
            self.api_client.cancel_employee_attendance(self.selected_record["id"], reason.strip())
            show_notice(self, "Lançamento cancelado", "O histórico foi preservado.", icon_name="warning")
            self.refresh(); self.data_changed.emit()
        except Exception as exc: show_notice(self, "Falha no cancelamento", str(exc), icon_name="warning")
