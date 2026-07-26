from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from access import user_can
from components import TableSkeletonOverlay, make_icon, show_notice
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


EMPLOYEE_STATUSES = [
    "PRE_CADASTRO",
    "AGUARDANDO_FOTO",
    "AGUARDANDO_DOCUMENTOS",
    "EM_VALIDACAO",
    "ATIVO",
    "INATIVO",
]


class EmployeeDialog(QDialog):
    def __init__(self, api_client, employee: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.employee = employee or {}
        self.result_payload: dict | None = None
        self.selected_photo_path: str | None = None
        self.setWindowTitle("Cadastro de colaborador")
        configure_dialog_window(self, width=820, height=680, min_width=680, min_height=600)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=820)
        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("users", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        title_wrap = QVBoxLayout()
        title = QLabel("Cadastro de colaborador")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Cadastre o vínculo funcional sem obrigar a criação de um login de sistema.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_layout.addWidget(icon_label, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self.registration_input = QLineEdit(self.employee.get("registration", ""))
        self.full_name_input = QLineEdit(self.employee.get("full_name", ""))
        self.function_input = QLineEdit(self.employee.get("function_name", ""))
        self.team_input = QLineEdit(self.employee.get("team_name", ""))
        self.shift_input = QLineEdit(self.employee.get("shift_name", ""))
        self.hired_on_input = QLineEdit(self.employee.get("hired_on", ""))
        self.hired_on_input.setPlaceholderText("AAAA-MM-DD")
        self.notes_input = QLineEdit(self.employee.get("notes", ""))

        self.status_combo = QComboBox()
        self.status_combo.addItems(EMPLOYEE_STATUSES)
        self.status_combo.setCurrentText(self.employee.get("status") or "PRE_CADASTRO")

        self.user_combo = QComboBox()
        self.user_combo.addItem("Sem login vinculado", None)
        try:
            users = self.api_client.get_linkable_employee_users()
        except Exception:
            users = []
        for user in users:
            self.user_combo.addItem(f"{user.get('nome')} ({user.get('login')})", user.get("id"))
        linked_user_id = self.employee.get("user_id")
        for index in range(self.user_combo.count()):
            if self.user_combo.itemData(index) == linked_user_id:
                self.user_combo.setCurrentIndex(index)
                break

        self.photo_label = QLabel(self.employee.get("photo_path") or "Nenhuma foto selecionada")
        self.photo_label.setObjectName("SectionCaption")
        self.photo_label.setWordWrap(True)
        photo_button = QPushButton("Selecionar foto")
        photo_button.clicked.connect(self._choose_photo)
        photo_box = QHBoxLayout()
        photo_box.addWidget(photo_button)
        photo_box.addWidget(self.photo_label, 1)

        def add_field(row: int, column: int, label_text: str, widget):
            box = QFrame()
            field_layout = QVBoxLayout(box)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(5)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            if isinstance(widget, QHBoxLayout):
                field_layout.addLayout(widget)
            else:
                field_layout.addWidget(widget)
            form.addWidget(box, row, column)

        add_field(0, 0, "Matrícula *", self.registration_input)
        add_field(0, 1, "Nome completo *", self.full_name_input)
        add_field(1, 0, "Função *", self.function_input)
        add_field(1, 1, "Atividade *", self.team_input)
        add_field(2, 0, "Turno *", self.shift_input)
        add_field(2, 1, "Situação", self.status_combo)
        add_field(3, 0, "Data de admissão", self.hired_on_input)
        add_field(3, 1, "Login vinculado", self.user_combo)
        add_field(4, 0, "Foto", photo_box)
        add_field(4, 1, "Observação", self.notes_input)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        save = QPushButton("Salvar colaborador")
        save.setProperty("variant", "primary")
        cancel.setMinimumHeight(46)
        save.setMinimumHeight(46)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(save)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar foto", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.selected_photo_path = path
            self.photo_label.setText(path)

    def _submit(self):
        payload = {
            "registration": self.registration_input.text().strip(),
            "full_name": self.full_name_input.text().strip(),
            "function_name": self.function_input.text().strip(),
            "team_name": self.team_input.text().strip(),
            "shift_name": self.shift_input.text().strip(),
            "status": self.status_combo.currentText(),
            "hired_on": self.hired_on_input.text().strip() or None,
            "user_id": self.user_combo.currentData(),
            "notes": self.notes_input.text().strip() or None,
            "photo_path": self.employee.get("photo_path") or None,
        }
        if not all((payload["registration"], payload["full_name"], payload["function_name"], payload["team_name"], payload["shift_name"])):
            show_notice(self, "Campos obrigatórios", "Informe matrícula, nome, função, atividade e turno.", icon_name="warning")
            return
        self.result_payload = payload
        self.accept()


class EmployeesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_user = current_user or {}
        self.can_manage = user_can(self.current_user, "manage_employees")
        self.employees: list[dict] = []
        self.selected_employee: dict | None = None
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        header = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel("Recursos Humanos")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Cadastre colaboradores, função, atividade, turno, situação, foto e vínculo opcional com login.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(subtitle)
        self.add_button = QPushButton("Novo colaborador")
        self.add_button.setProperty("variant", "primary")
        self.add_button.clicked.connect(self.add_employee)
        self.edit_button = QPushButton("Editar selecionado")
        self.edit_button.clicked.connect(self.edit_employee)
        self.add_button.setVisible(self.can_manage)
        self.edit_button.setVisible(self.can_manage)
        header.addLayout(text)
        header.addStretch()
        header.addWidget(self.add_button)
        header.addWidget(self.edit_button)

        filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por matrícula ou nome")
        self.search_input.returnPressed.connect(self.refresh)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todas as situações", "")
        for status in EMPLOYEE_STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.status_filter)
        filters.addWidget(refresh_button)

        self.table_card = QFrame()
        style_table_card(self.table_card)
        self.table_skeleton = TableSkeletonOverlay(self.table_card, rows=6)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(8)
        table_title = QLabel("Colaboradores cadastrados")
        table_title.setObjectName("SectionTitle")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Matrícula", "Nome", "Função", "Atividade", "Turno", "Situação", "Login"])
        configure_table(self.table)
        self.table.setMinimumHeight(500)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table)

        self.info_label = QLabel("Selecione um colaborador para editar.")
        self.info_label.setObjectName("MutedText")
        layout.addLayout(header)
        layout.addLayout(filters)
        layout.addWidget(self.table_card)
        layout.addWidget(self.info_label)
        self.edit_button.setEnabled(False)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando colaboradores")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self, preferred_employee_id: int | None = None):
        self.employees = self.api_client.get_employees(
            search=self.search_input.text().strip() or None,
            status=self.status_filter.currentData() or None,
        )
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.employees))
            for row, employee in enumerate(self.employees):
                linked_user = employee.get("linked_user") or {}
                self.table.setItem(row, 0, make_table_item(employee.get("registration", ""), payload=employee))
                self.table.setItem(row, 1, make_table_item(employee.get("full_name", "")))
                self.table.setItem(row, 2, make_table_item(employee.get("function_name", "")))
                self.table.setItem(row, 3, make_table_item(employee.get("team_name", "")))
                self.table.setItem(row, 4, make_table_item(employee.get("shift_name", "")))
                self.table.setItem(row, 5, make_table_item(employee.get("status", "")))
                self.table.setItem(row, 6, make_table_item(linked_user.get("login", "Sem login")))
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(True)
        if self.employees:
            selected_row = next(
                (index for index, employee in enumerate(self.employees) if employee.get("id") == preferred_employee_id),
                0,
            )
            self.table.selectRow(selected_row)
        else:
            self.selected_employee = None
            self.edit_button.setEnabled(False)
            self.info_label.setText("Nenhum colaborador encontrado.")

    def _selection_changed(self):
        rows = self.table.selectedRanges()
        if not rows:
            self.selected_employee = None
            self.edit_button.setEnabled(False)
            return
        item = self.table.item(rows[0].topRow(), 0)
        self.selected_employee = item.data(Qt.UserRole) if item else None
        self.edit_button.setEnabled(self.can_manage and bool(self.selected_employee))
        if self.selected_employee:
            self.info_label.setText(
                f"{self.selected_employee.get('full_name')} • {self.selected_employee.get('function_name')} • {self.selected_employee.get('status')}"
            )

    def _prepare_photo(self, dialog: EmployeeDialog, payload: dict):
        if dialog.selected_photo_path:
            upload = self.api_client.upload_file(
                dialog.selected_photo_path,
                "rh",
                payload["registration"],
                self.current_user.get("login") or "rh",
            )
            payload["photo_path"] = upload.get("path")
        return payload

    def add_employee(self):
        dialog = EmployeeDialog(self.api_client, parent=self)
        if not dialog.exec() or not dialog.result_payload:
            return
        try:
            created = self.api_client.create_employee(self._prepare_photo(dialog, dialog.result_payload))
            show_notice(self, "Colaborador criado", "Cadastro funcional criado com sucesso.", icon_name="users")
            self.refresh((created or {}).get("id"))
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao criar", str(exc), icon_name="warning")

    def edit_employee(self):
        if not self.selected_employee:
            return
        dialog = EmployeeDialog(self.api_client, self.selected_employee, self)
        if not dialog.exec() or not dialog.result_payload:
            return
        try:
            updated = self.api_client.update_employee(
                self.selected_employee["id"], self._prepare_photo(dialog, dialog.result_payload)
            )
            show_notice(self, "Colaborador atualizado", "Dados funcionais atualizados com sucesso.", icon_name="users")
            self.refresh((updated or {}).get("id"))
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")
