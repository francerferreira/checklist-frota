from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

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
        self.tipo_combo.addItems(["admin", "gestor", "motorista", "mecanico"])
        if user:
            self.tipo_combo.setCurrentText(user.get("tipo", "motorista"))

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


class UsersPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_user = current_user or {}
        self.is_admin = self.current_user.get("tipo") == "admin"
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
            "Gerencie acessos de admin, gestor, motorista e mecânico com uma visão clara e centralizada."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        add_button = QPushButton("Novo login")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.add_user)
        add_button.setVisible(self.is_admin)

        edit_button = QPushButton("Editar selecionado")
        edit_button.clicked.connect(self.edit_selected)
        edit_button.setVisible(self.is_admin)

        delete_button = QPushButton("Excluir selecionado")
        delete_button.setProperty("variant", "danger")
        delete_button.clicked.connect(self.delete_selected)
        delete_button.setVisible(self.is_admin)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addWidget(add_button)
        header.addWidget(edit_button)
        header.addWidget(delete_button)
        self.add_button = add_button
        self.edit_button = edit_button
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

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "Login", "Tipo", "Ativo"])
        configure_table(self.table)
        self.table.setMinimumHeight(500)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())

        self.info_label = QLabel(
            "Somente o administrador pode criar ou alterar logins." if not self.is_admin else "Selecione um login para editar."
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
        self.delete_button.setEnabled(False)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando acessos cadastrados")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self):
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
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        enable_actions = self.is_admin and bool(self.users)
        self.edit_button.setEnabled(enable_actions)
        self.delete_button.setEnabled(enable_actions)
        if self.users:
            self.table.selectRow(0)

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_user_item = None
            self.info_label.setText(
                "Somente o administrador pode criar ou alterar logins."
                if not self.is_admin
                else "Selecione um login para editar."
            )
            self.edit_button.setEnabled(False)
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
            self.delete_button.setEnabled(False)
            return
        self.info_label.setText(
            f"{self.current_user_item['nome']} ({self.current_user_item['login']}) \u2022 "
            f"perfil {self.current_user_item['tipo']} \u2022 "
            f"{'ativo' if self.current_user_item['ativo'] else 'inativo'}"
        )
        allow_actions = self.is_admin
        self.edit_button.setEnabled(allow_actions)
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
        if not self.is_admin:
            show_notice(self, "Acesso restrito", "Somente o administrador pode criar logins.", icon_name="warning")
            return
        dialog = UserDialog(self.api_client, parent=self)
        if dialog.exec():
            self.api_client.create_user(dialog.result_payload)
            show_notice(self, "Login criado", "Novo login cadastrado com sucesso.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()

    def edit_selected(self):
        if not self.is_admin:
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
                self.refresh()
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def delete_selected(self):
        if not self.is_admin:
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



