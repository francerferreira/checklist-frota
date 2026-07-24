from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QTableWidget, QTextEdit, QVBoxLayout

from components import TableSkeletonOverlay, show_notice
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


class EmployeeRecordDialog(QDialog):
    def __init__(self, api_client, record_kind: str, current_user: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.record_kind = record_kind
        self.current_user = current_user or {}
        self.result_payload = None
        self.selected_file = None
        titles = {"document": "Novo documento", "training": "Novo treinamento", "history": "Novo evento funcional"}
        self.setWindowTitle(titles[record_kind])
        configure_dialog_window(self, width=700, height=520, min_width=620, min_height=440)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=700)
        title = QLabel(titles[record_kind]); title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("O arquivo fica protegido no sistema. Documentos sensiveis sao exclusivos do administrador.")
        subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        card = QFrame(); card.setObjectName("HeaderCard"); card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(card); form.setContentsMargins(18, 18, 18, 18); form.setHorizontalSpacing(16); form.setVerticalSpacing(12)
        self.employee_combo = QComboBox()
        for employee in self.api_client.get_employees():
            self.employee_combo.addItem(f"{employee.get('registration')} - {employee.get('full_name')}", employee.get("id"))
        self.type_input = QLineEdit(); self.secondary_input = QLineEdit(); self.provider_input = QLineEdit()
        self.date_one = QLineEdit(date.today().isoformat()); self.date_two = QLineEdit(); self.expires_on = QLineEdit()
        self.hours_input = QLineEdit(); self.notes_input = QTextEdit(); self.notes_input.setMaximumHeight(90)
        self.sensitive = QCheckBox("Documento sensivel (somente administrador)")
        self.sensitive.setEnabled(str(self.current_user.get("tipo") or "").lower() == "admin")
        self.file_label = QLabel("Nenhum arquivo selecionado")
        file_button = QPushButton("Anexar arquivo"); file_button.clicked.connect(self._choose_file)
        file_box = QHBoxLayout(); file_box.addWidget(file_button); file_box.addWidget(self.file_label, 1)

        def field(row, column, label_text, widget):
            box = QFrame(); box_layout = QVBoxLayout(box); box_layout.setContentsMargins(0, 0, 0, 0); box_layout.setSpacing(5)
            label = QLabel(label_text); label.setObjectName("SectionCaption"); box_layout.addWidget(label)
            box_layout.addLayout(widget) if isinstance(widget, QHBoxLayout) else box_layout.addWidget(widget)
            form.addWidget(box, row, column)

        field(0, 0, "Colaborador", self.employee_combo)
        if record_kind == "document":
            self.type_input.setPlaceholderText("Ex.: CNH, ASO, certificado")
            self.date_two.setPlaceholderText("AAAA-MM-DD (opcional)")
            field(0, 1, "Tipo de documento", self.type_input); field(1, 0, "Data de emissao", self.date_one)
            field(1, 1, "Validade", self.date_two); field(2, 0, "Arquivo", file_box); field(2, 1, "Protecao", self.sensitive)
        elif record_kind == "training":
            self.type_input.setPlaceholderText("Ex.: NR-35"); self.secondary_input.setPlaceholderText("Ex.: seguranca")
            self.provider_input.setPlaceholderText("Empresa ou instrutor"); self.date_two.setPlaceholderText("AAAA-MM-DD (opcional)")
            self.expires_on.setPlaceholderText("AAAA-MM-DD (opcional)"); self.hours_input.setPlaceholderText("Ex.: 8")
            field(0, 1, "Nome do curso", self.type_input); field(1, 0, "Tipo", self.secondary_input); field(1, 1, "Instituicao", self.provider_input)
            field(2, 0, "Data inicial", self.date_one); field(2, 1, "Data final", self.date_two); field(3, 0, "Carga horaria", self.hours_input); field(3, 1, "Validade", self.expires_on); field(4, 0, "Certificado", file_box)
        else:
            self.type_input.setPlaceholderText("Ex.: mudanca de funcao, advertencia")
            field(0, 1, "Tipo de evento", self.type_input); field(1, 0, "Data do evento", self.date_one)
        field(5, 0, "Observacao ou descricao", self.notes_input)
        layout.addWidget(card)
        actions = QHBoxLayout(); actions.addStretch(); cancel = QPushButton("Cancelar"); save = QPushButton("Salvar")
        save.setProperty("variant", "primary"); cancel.clicked.connect(self.reject); save.clicked.connect(self._submit)
        actions.addWidget(cancel); actions.addWidget(save); layout.addLayout(actions)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", "Documentos (*.pdf *.png *.jpg *.jpeg)")
        if path: self.selected_file = path; self.file_label.setText(path)

    def _submit(self):
        if self.employee_combo.currentData() is None:
            show_notice(self, "Colaborador obrigatorio", "Selecione um colaborador antes de salvar.", icon_name="warning"); return
        notes = self.notes_input.toPlainText().strip() or None
        if self.record_kind == "document":
            if not self.type_input.text().strip() or not self.selected_file:
                show_notice(self, "Dados obrigatorios", "Informe o tipo e anexe o documento.", icon_name="warning"); return
            self.result_payload = {"employee_id": self.employee_combo.currentData(), "document_type": self.type_input.text().strip(), "issued_on": self.date_one.text().strip() or None, "expires_on": self.date_two.text().strip() or None, "is_sensitive": self.sensitive.isChecked(), "notes": notes}
        elif self.record_kind == "training":
            if not self.type_input.text().strip() or not self.secondary_input.text().strip():
                show_notice(self, "Dados obrigatorios", "Informe o curso e o tipo do treinamento.", icon_name="warning"); return
            self.result_payload = {"employee_id": self.employee_combo.currentData(), "course_name": self.type_input.text().strip(), "training_type": self.secondary_input.text().strip(), "provider_name": self.provider_input.text().strip() or None, "starts_on": self.date_one.text().strip() or None, "ends_on": self.date_two.text().strip() or None, "workload_hours": self.hours_input.text().strip() or None, "expires_on": self.expires_on.text().strip() or None, "notes": notes}
        else:
            if not self.type_input.text().strip() or not notes:
                show_notice(self, "Dados obrigatorios", "Informe o tipo e a descricao do evento.", icon_name="warning"); return
            self.result_payload = {"employee_id": self.employee_combo.currentData(), "event_type": self.type_input.text().strip(), "occurred_on": self.date_one.text().strip(), "description": notes}
        self.accept()


class EmployeeRecordsPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client; self.current_user = current_user or {}; self.employees = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self); layout.setContentsMargins(28, 28, 28, 28); layout.setSpacing(16)
        header = QHBoxLayout(); text = QVBoxLayout()
        title = QLabel("Documentos e treinamentos"); title.setObjectName("PageTitle")
        subtitle = QLabel("Acompanhe documentos, certificados e eventos funcionais sem apagar o historico."); subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        text.addWidget(title); text.addWidget(subtitle); header.addLayout(text); header.addStretch()
        for caption, kind in [("Novo documento", "document"), ("Novo treinamento", "training"), ("Novo evento", "history")]:
            button = QPushButton(caption); button.setProperty("variant", "primary" if kind == "document" else "default"); button.clicked.connect(lambda _, item=kind: self.add_record(item)); header.addWidget(button)
        layout.addLayout(header)
        filters = QHBoxLayout(); self.employee_filter = QComboBox(); self.employee_filter.addItem("Todos os colaboradores", None); self.employee_filter.currentIndexChanged.connect(self.refresh)
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh); filters.addWidget(QLabel("Colaborador:")); filters.addWidget(self.employee_filter, 1); filters.addWidget(refresh); layout.addLayout(filters)
        self.tabs = QTabWidget(); self.document_table = self._table(["Colaborador", "Documento", "Validade", "Situacao", "Protegido"]); self.training_table = self._table(["Colaborador", "Curso", "Tipo", "Validade", "Situacao"]); self.history_table = self._table(["Data", "Colaborador", "Evento", "Descricao"])
        self.tabs.addTab(self.document_table, "Documentos"); self.tabs.addTab(self.training_table, "Treinamentos"); self.tabs.addTab(self.history_table, "Historico funcional"); layout.addWidget(self.tabs, 1)
        self.skeleton = TableSkeletonOverlay(self, rows=6)

    def _table(self, headers):
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); configure_table(table); table.setMinimumHeight(460); return table

    def set_loading_state(self, loading: bool):
        self.skeleton.show_skeleton("Carregando registros de RH") if loading else self.skeleton.hide_skeleton()

    def refresh(self, *_):
        self.employees = self.api_client.get_employees()
        selected = self.employee_filter.currentData()
        self.employee_filter.blockSignals(True); self.employee_filter.clear(); self.employee_filter.addItem("Todos os colaboradores", None)
        for employee in self.employees: self.employee_filter.addItem(f"{employee.get('registration')} - {employee.get('full_name')}", employee.get("id"))
        for index in range(self.employee_filter.count()):
            if self.employee_filter.itemData(index) == selected: self.employee_filter.setCurrentIndex(index); break
        self.employee_filter.blockSignals(False); employee_id = self.employee_filter.currentData()
        self._fill(self.document_table, self.api_client.get_employee_documents(employee_id=employee_id), lambda row: [row.get("employee", {}).get("full_name", ""), row.get("document_type", ""), row.get("expires_on") or "Sem validade", row.get("status", ""), "Sim" if row.get("is_sensitive") else "Nao"])
        self._fill(self.training_table, self.api_client.get_employee_trainings(employee_id=employee_id), lambda row: [row.get("employee", {}).get("full_name", ""), row.get("course_name", ""), row.get("training_type", ""), row.get("expires_on") or "Sem validade", row.get("status", "")])
        history = self.api_client.get_employee_history(employee_id) if employee_id else []
        self._fill(self.history_table, history, lambda row: [row.get("occurred_on", ""), row.get("employee", {}).get("full_name", ""), row.get("event_type", ""), row.get("description", "")])

    @staticmethod
    def _fill(table, rows, columns):
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate(columns(row)): table.setItem(index, column, make_table_item(str(value or ""), payload=row if column == 0 else None))
        table.resizeColumnsToContents()

    def add_record(self, record_kind: str):
        dialog = EmployeeRecordDialog(self.api_client, record_kind, self.current_user, self)
        if not dialog.exec() or not dialog.result_payload: return
        try:
            payload = dialog.result_payload
            if dialog.selected_file:
                upload = self.api_client.upload_file(dialog.selected_file, "rh", record_kind, self.current_user.get("login") or "rh")
                payload["file_path" if record_kind == "document" else "certificate_path"] = upload.get("path")
            if record_kind == "document": self.api_client.create_employee_document(payload)
            elif record_kind == "training": self.api_client.create_employee_training(payload)
            else: self.api_client.create_employee_history(payload)
            show_notice(self, "Registro salvo", "O registro foi incluido no historico do colaborador.", icon_name="dashboard")
            self.refresh(); self.data_changed.emit()
        except Exception as exc: show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")
