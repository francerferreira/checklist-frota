from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from access import PAGE_ACCESS_BY_ROLE, allowed_pages_for_role, normalize_user_role, user_can
from components import TableSkeletonOverlay, ask_confirmation, make_icon, show_notice
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


class UserDialog(QDialog):
    def __init__(self, api_client, user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = user
        self.result_payload = None
        self.setWindowTitle("Cadastro de Login")
        configure_dialog_window(self, width=760, height=620, min_width=620, min_height=520)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=760)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)
        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("users", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        header_title = QLabel("Cadastro de login")
        header_title.setObjectName("DialogHeaderTitle")
        header_subtitle = QLabel("Gerencie credenciais e perfil de acesso em uma estrutura mais clara e corporativa.")
        header_subtitle.setObjectName("DialogHeaderSubtitle")
        header_subtitle.setWordWrap(True)
        title_wrap.addWidget(header_title)
        title_wrap.addWidget(header_subtitle)
        header_row.addWidget(icon_badge, 0, Qt.AlignTop)
        header_row.addLayout(title_wrap, 1)
        header_layout.addLayout(header_row)

        self.nome_input = QLineEdit((user or {}).get("nome", ""))
        self.login_input = QLineEdit((user or {}).get("login", ""))
        self.senha_input = QLineEdit("")
        self.senha_input.setPlaceholderText("Preencha para definir ou alterar a senha")

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(["admin", "gestor", "operacional"])
        if user:
            current_type = str(user.get("tipo", "operacional"))
            if current_type not in {"admin", "gestor", "operacional"}:
                self.tipo_combo.addItem(current_type)
            self.tipo_combo.setCurrentText(current_type)

        self.ativo_checkbox = QCheckBox("Login ativo")
        self.ativo_checkbox.setChecked((user or {}).get("ativo", True))

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(14)

        def add_field(row: int, column: int, label_text: str, widget, highlight: bool = False):
            field = QFrame()
            if highlight:
                field.setObjectName("DialogInfoBlock")
                field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(12 if highlight else 0, 12 if highlight else 0, 12 if highlight else 0, 12 if highlight else 0)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form_layout.addWidget(field, row, column)

        add_field(0, 0, "Nome", self.nome_input)
        add_field(0, 1, "Login", self.login_input, highlight=True)
        add_field(1, 0, "Senha", self.senha_input)
        add_field(1, 1, "Tipo", self.tipo_combo, highlight=True)
        form_layout.addWidget(self.ativo_checkbox, 2, 0, 1, 2, Qt.AlignLeft)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar login")
        save_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        save_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        save_button.setMinimumWidth(180)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)

        actions.addWidget(cancel_button)
        actions.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def submit(self):
        payload = {
            "nome": self.nome_input.text().strip(),
            "login": self.login_input.text().strip(),
            "tipo": self.tipo_combo.currentText(),
            "ativo": self.ativo_checkbox.isChecked(),
        }
        if self.senha_input.text():
            payload["senha"] = self.senha_input.text()
        if not self.user and "senha" not in payload:
            show_notice(self, "Senha obrigatória", "Informe a senha para o novo login.", icon_name="warning")
            return
        self.result_payload = payload
        self.accept()


PROFILE_PAGE_LABELS = {
    "dashboard": "Dashboard",
    "operations_center": "Central Operacional",
    "nc": "Central de Resolucao",
    "productivity": "Produtividade",
    "reports": "Relatorios",
    "checklist_history": "Historico de Checklist",
    "spreader_history": "Historico de Spreaders",
    "equipment": "Equipamentos",
    "checklist_items": "Itens de Checklist",
    "inspection_templates": "Inspecao Tecnica",
    "materials": "Materiais",
    "washes": "Lavagens",
    "activities": "Inspecoes",
    "maintenance": "Manutencao",
    "availability": "Disponibilidade e Horimetro",
    "emergencies": "Emergenciais e OS",
    "pcm": "PCM",
    "resources": "Recursos e Ferramentas",
    "purchases": "Compras e Fornecedores",
    "supply_library": "Suprimentos e Biblioteca",
    "employees": "Colaboradores",
    "attendance": "Frequencia e Ocorrencias",
    "employee_records": "Documentos e Treinamentos",
    "hr_management": "Painel de RH",
    "vacations": "Ferias",
    "special_schedule": "Escala de Domingo e Feriado",
    "rtg_module": "Gestao RTG",
    "lbs_module": "Gestao LBS",
    "rtg_maintenance": "Corretivas RTG",
    "lbs_maintenance": "Corretivas LBS",
    "rtg_downtime": "Controle de Paradas RTG",
    "lbs_downtime": "Controle de Paradas LBS",
    "users": "Usuarios",
    "cloud_backup": "Backup",
    "audit_logs": "Logs de Auditoria",
    "admin_rules": "Configuracoes",
}


class UserProfileDialog(QDialog):
    """Central administrativa para identidade digital e telas do usuario."""

    def __init__(self, api_client, user: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = dict(user or {})
        self.updated = False
        self.page_checkboxes = {}
        self.setWindowTitle("Gerenciar perfil de acesso")
        configure_dialog_window(self, width=1080, height=760, min_width=860, min_height=620)
        style_card(self)

        try:
            loaded = self.api_client.get_user_profile(int(self.user.get("id")))
            if isinstance(loaded, dict):
                self.user = loaded
        except Exception as exc:
            show_notice(self, "Perfil parcial", f"Nao foi possivel carregar todos os dados: {exc}", icon_name="warning")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Gerenciamento de perfil")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"{self.user.get('nome', '-') }  •  login {self.user.get('login', '-')}  •  perfil {str(self.user.get('tipo', '-')).upper()}"
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 10, 2)
        content_layout.setSpacing(14)

        identity = self.user.get("identity") or {}
        summary = QFrame()
        summary.setObjectName("HeaderCard")
        summary.setAttribute(Qt.WA_StyledBackground, True)
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setHorizontalSpacing(24)
        summary_layout.setVerticalSpacing(8)
        summary_items = [
            ("Colaborador", identity.get("full_name") or "Sem vinculo"),
            ("Matricula", identity.get("registration") or "-"),
            ("Funcao", identity.get("function_name") or "-"),
            ("Equipe / turno", " / ".join(value for value in [identity.get("team_name"), identity.get("shift_name")] if value) or "-"),
        ]
        for index, (label_text, value_text) in enumerate(summary_items):
            label = QLabel(label_text.upper())
            label.setObjectName("SectionCaption")
            value = QLabel(str(value_text))
            value.setObjectName("DialogInfoValue")
            value.setWordWrap(True)
            summary_layout.addWidget(label, index // 2 * 2, index % 2)
            summary_layout.addWidget(value, index // 2 * 2 + 1, index % 2)
        content_layout.addWidget(summary)

        media_row = QHBoxLayout()
        media_row.setSpacing(14)
        self.photo_label = self._image_card("FOTO DE PERFIL", identity.get("photo_path"), 250, 210, "Foto ainda nao cadastrada")
        self.signature_label = self._image_card("ASSINATURA ELETRONICA", identity.get("signature_path"), 350, 160, "Assinatura ainda nao cadastrada")
        media_row.addWidget(self.photo_label[0], 1)
        media_row.addWidget(self.signature_label[0], 1)
        content_layout.addLayout(media_row)

        status_card = QFrame()
        status_card.setObjectName("DialogInfoBlock")
        status_card.setAttribute(Qt.WA_StyledBackground, True)
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        self.identity_status = QLabel()
        self.identity_status.setObjectName("SectionTitle")
        completed_at = identity.get("first_access_completed_at")
        self.identity_status.setText(
            f"Identidade verificada em {completed_at.replace('T', ' ') if completed_at else 'aguardando primeiro acesso'}"
        )
        status_layout.addWidget(self.identity_status)
        status_layout.addStretch()
        content_layout.addWidget(status_card)

        screens_card = QFrame()
        screens_card.setObjectName("HeaderCard")
        screens_card.setAttribute(Qt.WA_StyledBackground, True)
        screens_layout = QVBoxLayout(screens_card)
        screens_layout.setContentsMargins(18, 16, 18, 16)
        screens_layout.setSpacing(10)
        screens_title = QLabel("Telas personalizadas")
        screens_title.setObjectName("SectionTitle")
        screens_caption = QLabel("Escolha quais telas este usuario vera. O Dashboard permanece sempre disponivel.")
        screens_caption.setObjectName("SectionCaption")
        screens_caption.setWordWrap(True)
        screens_layout.addWidget(screens_title)
        screens_layout.addWidget(screens_caption)
        screens_grid = QGridLayout()
        screens_grid.setHorizontalSpacing(24)
        screens_grid.setVerticalSpacing(8)
        role_pages = allowed_pages_for_role(normalize_user_role(self.user))
        current_pages = set(self.user.get("custom_page_keys") or role_pages)
        for index, page_key in enumerate(sorted(role_pages, key=lambda key: PROFILE_PAGE_LABELS.get(key, key))):
            checkbox = QCheckBox(PROFILE_PAGE_LABELS.get(page_key, page_key.replace("_", " ").title()))
            checkbox.setChecked(page_key in current_pages or page_key == "dashboard")
            if page_key == "dashboard":
                checkbox.setChecked(True)
                checkbox.setEnabled(False)
            self.page_checkboxes[page_key] = checkbox
            screens_grid.addWidget(checkbox, index // 3, index % 3)
        screens_layout.addLayout(screens_grid)
        content_layout.addWidget(screens_card)
        content_layout.addStretch()
        scroll.setWidget(content)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        reset_button = QPushButton("Resetar primeiro acesso")
        reset_button.setProperty("variant", "danger")
        reset_button.clicked.connect(self.reset_first_access)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.reject)
        save_button = QPushButton("Salvar perfil e telas")
        save_button.setProperty("variant", "primary")
        save_button.clicked.connect(self.save_profile)
        footer_layout.addWidget(reset_button)
        footer_layout.addStretch()
        footer_layout.addWidget(close_button)
        footer_layout.addWidget(save_button)

        root.addWidget(header)
        root.addWidget(scroll, 1)
        root.addWidget(footer)

    def _image_card(self, title_text: str, path: str | None, width: int, height: int, placeholder: str):
        card = QFrame()
        card.setObjectName("HeaderCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("SectionCaption")
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setMinimumSize(width, height)
        image.setMaximumHeight(height)
        image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        image.setStyleSheet("border: 1px solid #D8E1EC; border-radius: 12px; background: #F5F8FC; color: #607086; padding: 8px;")
        image_data = self.api_client.fetch_image(path) if path else None
        pixmap = QPixmap()
        if image_data:
            pixmap.loadFromData(image_data)
        if not pixmap.isNull():
            image.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            image.setText(placeholder)
        layout.addWidget(title)
        layout.addWidget(image)
        return card, image

    def _selected_pages(self) -> list[str]:
        return sorted(page_key for page_key, checkbox in self.page_checkboxes.items() if checkbox.isChecked())

    def save_profile(self):
        try:
            updated = self.api_client.update_user_pages(int(self.user["id"]), self._selected_pages())
            if isinstance(updated, dict):
                self.user = updated
            self.updated = True
            show_notice(self, "Perfil atualizado", "As telas personalizadas foram salvas.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao salvar perfil", str(exc), icon_name="warning")

    def reset_first_access(self):
        if not ask_confirmation(
            self,
            "Resetar primeiro acesso",
            "A foto e a assinatura serao solicitadas novamente no proximo login deste colaborador. Continuar?",
            confirm_text="Resetar",
            cancel_text="Cancelar",
            icon_name="warning",
        ):
            return
        try:
            updated = self.api_client.reset_user_first_access(int(self.user["id"]))
            if isinstance(updated, dict):
                self.user = updated
            self.updated = True
            self.identity_status.setText("Identidade resetada: aguardando novo primeiro acesso")
            self.photo_label[1].clear()
            self.photo_label[1].setText("Foto ainda nao cadastrada")
            self.signature_label[1].clear()
            self.signature_label[1].setText("Assinatura ainda nao cadastrada")
            show_notice(self, "Primeiro acesso resetado", "O colaborador devera cadastrar foto e assinatura novamente.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao resetar", str(exc), icon_name="warning")


class UsersPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_user = current_user or {}
        self.can_manage_users = user_can(self.current_user, "manage_users")
        self.users = []
        self.current_user_item = None
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()

        text_wrap = QVBoxLayout()
        title = QLabel("Logins")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Gerencie perfis ADMIN, GESTOR e OPERACIONAL, identidades digitais e telas personalizadas."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        add_button = QPushButton("Novo login")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.add_user)
        add_button.setVisible(self.can_manage_users)

        edit_button = QPushButton("Editar selecionado")
        edit_button.clicked.connect(self.edit_selected)
        edit_button.setVisible(self.can_manage_users)

        delete_button = QPushButton("Excluir selecionado")
        delete_button.setProperty("variant", "danger")
        delete_button.clicked.connect(self.delete_selected)
        delete_button.setVisible(self.can_manage_users)

        profile_button = QPushButton("Perfil e telas")
        profile_button.clicked.connect(self.open_profile_selected)
        profile_button.setVisible(self.can_manage_users)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addWidget(add_button)
        header.addWidget(edit_button)
        header.addWidget(profile_button)
        header.addWidget(delete_button)
        self.add_button = add_button
        self.edit_button = edit_button
        self.profile_button = profile_button
        self.delete_button = delete_button

        self.table_card = QFrame()
        style_table_card(self.table_card)
        self.table_skeleton = TableSkeletonOverlay(self.table_card, rows=5)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        table_title = QLabel("Usu\u00e1rios cadastrados")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel("Selecione um registro para editar perfil, senha ou status.")
        table_caption.setObjectName("SectionCaption")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Nome", "Login", "Tipo", "Ativo", "Primeiro acesso", "Identidade"])
        configure_table(self.table)
        self.table.setMinimumHeight(500)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())

        self.info_label = QLabel(
            "Somente o administrador pode criar ou alterar logins." if not self.can_manage_users else "Selecione um login para editar."
        )
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)

        table_layout.addWidget(table_title)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addWidget(self.table_card)
        layout.addWidget(self.info_label)

        self.edit_button.setEnabled(False)
        self.profile_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando acessos cadastrados")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self, preferred_user_id: int | None = None):
        self.users = self.api_client.get_users()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.users))
            for row, user in enumerate(self.users):
                self.table.setItem(row, 0, make_table_item(user["nome"], payload=user))
                self.table.setItem(row, 1, make_table_item(user["login"]))
                self.table.setItem(row, 2, make_table_item(user["tipo"]))
                self.table.setItem(row, 3, make_table_item("Sim" if user["ativo"] else "N\u00e3o"))
                identity = user.get("identity") or {}
                first_access = "Conclu\u00eddo" if identity.get("first_access_completed_at") else ("Pendente" if identity else "Sem v\u00ednculo")
                identity_status = "Foto + assinatura" if identity.get("photo_path") and identity.get("signature_path") else ("Incompleta" if identity else "Sem v\u00ednculo")
                self.table.setItem(row, 4, make_table_item(first_access))
                self.table.setItem(row, 5, make_table_item(identity_status))
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        enable_actions = self.can_manage_users and bool(self.users)
        self.edit_button.setEnabled(enable_actions)
        self.profile_button.setEnabled(enable_actions)
        self.delete_button.setEnabled(enable_actions)
        if self.users:
            selected_row = 0
            if preferred_user_id is not None:
                for row_index, user_item in enumerate(self.users):
                    if int(user_item.get("id") or 0) == int(preferred_user_id):
                        selected_row = row_index
                        break
            self.table.selectRow(selected_row)
            self.current_user_item = self._selected_user()
        else:
            self.current_user_item = None

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_user_item = None
            self.info_label.setText(
                "Somente o administrador pode criar ou alterar logins."
                if not self.can_manage_users
                else "Selecione um login para editar."
            )
            self.edit_button.setEnabled(False)
            self.profile_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return

        row = selected[0].topRow()
        first_cell = self.table.item(row, 0)
        self.current_user_item = first_cell.data(Qt.UserRole) if first_cell else None
        if not self.current_user_item and 0 <= row < len(self.users):
            self.current_user_item = self.users[row]
        if not self.current_user_item:
            self.info_label.setText("Selecione um login para editar.")
            self.edit_button.setEnabled(False)
            self.profile_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return
        self.info_label.setText(
            f"{self.current_user_item['nome']} ({self.current_user_item['login']}) \u2022 "
            f"perfil {self.current_user_item['tipo']} \u2022 "
            f"{'ativo' if self.current_user_item['ativo'] else 'inativo'}"
        )
        allow_actions = self.can_manage_users
        self.edit_button.setEnabled(allow_actions)
        self.profile_button.setEnabled(allow_actions)
        self.delete_button.setEnabled(allow_actions and self.current_user_item["id"] != self.current_user.get("id"))

    def _selected_user(self):
        selected = self.table.selectedRanges()
        if selected:
            row = selected[0].topRow()
            first_cell = self.table.item(row, 0)
            user_item = first_cell.data(Qt.UserRole) if first_cell else None
            if not user_item and 0 <= row < len(self.users):
                user_item = self.users[row]
            return user_item
        return self.current_user_item

    def add_user(self):
        if not self.can_manage_users:
            show_notice(self, "Acesso restrito", "Somente o administrador pode criar logins.", icon_name="warning")
            return
        dialog = UserDialog(self.api_client, parent=self)
        if dialog.exec():
            try:
                created = self.api_client.create_user(dialog.result_payload)
                show_notice(self, "Login criado", "Novo login cadastrado com sucesso.", icon_name="dashboard")
                self.refresh((created or {}).get("id") if isinstance(created, dict) else None)
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao criar", str(exc), icon_name="warning")

    def edit_selected(self):
        if not self.can_manage_users:
            show_notice(self, "Acesso restrito", "Somente o administrador pode alterar logins.", icon_name="warning")
            return
        target_user = self._selected_user()
        if not target_user:
            return
        self.current_user_item = target_user
        dialog = UserDialog(self.api_client, target_user, self)
        if dialog.exec():
            try:
                self.api_client.update_user(target_user["id"], dialog.result_payload)
                show_notice(self, "Login atualizado", "Dados do login atualizados com sucesso.", icon_name="dashboard")
                self.refresh(target_user.get("id"))
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def open_profile_selected(self):
        if not self.can_manage_users:
            show_notice(self, "Acesso restrito", "Somente o administrador pode gerenciar perfis.", icon_name="warning")
            return
        target_user = self._selected_user()
        if not target_user:
            show_notice(self, "Selecao obrigatoria", "Selecione um login para abrir o perfil.", icon_name="warning")
            return
        dialog = UserProfileDialog(self.api_client, target_user, self)
        if dialog.exec() and dialog.updated:
            self.refresh(target_user.get("id"))
            self.data_changed.emit()

    def delete_selected(self):
        if not self.can_manage_users:
            show_notice(self, "Acesso restrito", "Somente o administrador pode excluir logins.", icon_name="warning")
            return
        target_user = self._selected_user()
        if not target_user:
            show_notice(self, "Seleção obrigatória", "Selecione um login para excluir.", icon_name="warning")
            return

        self.current_user_item = target_user
        user = target_user
        confirm = ask_confirmation(
            self,
            "Excluir login",
            f"Deseja excluir o login {user['nome']} ({user['login']})?",
            confirm_text="Excluir",
            cancel_text="Cancelar",
            icon_name="warning",
        )
        if not confirm:
            return

        try:
            self.api_client.delete_user(user["id"])
            show_notice(self, "Login excluido", "Login removido com sucesso.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao excluir", str(exc), icon_name="warning")
