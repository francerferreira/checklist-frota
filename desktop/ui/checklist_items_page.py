from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, ask_confirmation, make_icon, show_notice
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card


class ChecklistItemDialog(QDialog):
    def __init__(self, api_client, item: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.item = item or {}
        self.selected_file = ""
        self.result_payload = None

        self.setWindowTitle("Item do checklist")
        configure_dialog_window(self, width=860, height=620, min_width=720, min_height=520)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=920)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("equipment", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title = QLabel("Configuração de item")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Cadastre o nome, tipo de equipamento, ordem e foto de referência mostrada no celular.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.name_input = QLineEdit(self.item.get("item_nome", ""))
        self.name_input.setPlaceholderText("Ex.: Lanterna traseira esquerda")

        self.type_combo = QComboBox()
        self.type_combo.addItem("Cavalo", "cavalo")
        self.type_combo.addItem("Carreta", "carreta")
        current_type = self.item.get("tipo") or self.item.get("vehicle_type") or "cavalo"
        type_index = self.type_combo.findData(current_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        self.position_spin = QSpinBox()
        self.position_spin.setMinimum(1)
        self.position_spin.setMaximum(999)
        self.position_spin.setValue(int(self.item.get("position") or 1))

        self.active_checkbox = QCheckBox("Item ativo")
        self.active_checkbox.setChecked(bool(self.item.get("ativo", True)))

        self.file_label = QLabel(self.item.get("foto_path") or "Nenhuma foto selecionada.")
        self.file_label.setObjectName("MutedText")
        self.file_label.setWordWrap(True)
        photo_button = QPushButton("Selecionar foto")
        photo_button.clicked.connect(self.select_file)
        clear_photo_button = QPushButton("Remover foto")
        clear_photo_button.clicked.connect(self.clear_photo)

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1):
            field = QFrame()
            field.setObjectName("DialogInfoBlock")
            field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(12, 12, 12, 12)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Nome do item", self.name_input)
        add_field(0, 1, "Tipo de equipamento", self.type_combo)
        add_field(1, 0, "Ordem", self.position_spin)

        photo_field = QFrame()
        photo_field.setObjectName("DialogInfoBlock")
        photo_field.setAttribute(Qt.WA_StyledBackground, True)
        photo_layout = QVBoxLayout(photo_field)
        photo_layout.setContentsMargins(12, 12, 12, 12)
        photo_layout.setSpacing(8)
        photo_title = QLabel("Foto de referência")
        photo_title.setObjectName("SectionCaption")
        photo_actions = QHBoxLayout()
        photo_actions.setContentsMargins(0, 0, 0, 0)
        photo_actions.setSpacing(8)
        photo_actions.addWidget(photo_button)
        photo_actions.addWidget(clear_photo_button)
        photo_actions.addWidget(self.file_label, 1)
        photo_layout.addWidget(photo_title)
        photo_layout.addLayout(photo_actions)
        photo_layout.addWidget(self.active_checkbox, 0, Qt.AlignLeft)
        form.addWidget(photo_field, 1, 1)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar item")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def select_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto do item",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if filename:
            self.selected_file = filename
            self.file_label.setText(filename)

    def clear_photo(self):
        self.selected_file = ""
        self.file_label.setText("Nenhuma foto selecionada.")
        self.item["foto_path"] = ""

    def submit(self):
        try:
            payload = {
                "item_nome": self.name_input.text().strip(),
                "tipo": self.type_combo.currentData(),
                "position": int(self.position_spin.value()),
                "ativo": self.active_checkbox.isChecked(),
            }
            if not payload["item_nome"]:
                show_notice(self, "Nome obrigatório", "Informe o nome do item do checklist.", icon_name="warning")
                return
            if self.selected_file:
                upload = self.api_client.upload_file(
                    self.selected_file,
                    "catalogo",
                    payload["item_nome"],
                    self.api_client.user["login"],
                )
                payload["foto_path"] = upload["path"]
            else:
                payload["foto_path"] = self.item.get("foto_path") or None
            self.result_payload = payload
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")


class ChecklistItemsPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.items = []
        self.current_item = None
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Itens do checklist")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Configure os itens de cavalo e carreta, incluindo fotos de referência para o motorista.")
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_button = QPushButton("Adicionar")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setMinimumHeight(42)
        self.add_button.clicked.connect(self.add_item)
        self.edit_button = QPushButton("Editar")
        self.edit_button.setMinimumHeight(42)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button = QPushButton("Inativar")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.setMinimumHeight(42)
        self.delete_button.clicked.connect(self.delete_selected)
        for button in (self.add_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(buttons)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.type_filter = QComboBox()
        self.type_filter.addItem("Todos", "")
        self.type_filter.addItem("Cavalo", "cavalo")
        self.type_filter.addItem("Carreta", "carreta")
        self.type_filter.setMinimumHeight(40)
        self.active_filter = QComboBox()
        self.active_filter.addItem("Ativos", "true")
        self.active_filter.addItem("Todos", "all")
        self.active_filter.setMinimumHeight(40)
        self.type_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        self.active_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        filter_button = QPushButton("Aplicar filtros")
        filter_button.setMinimumHeight(40)
        filter_button.clicked.connect(self.refresh)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.active_filter)
        filters.addWidget(filter_button)
        filters.addStretch()

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        top = QHBoxLayout()
        title_label = QLabel("Catálogo de itens")
        title_label.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Nenhum item carregado")
        self.summary_badge.setObjectName("TopBarPill")
        top.addWidget(title_label)
        top.addStretch()
        top.addWidget(self.summary_badge)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Ordem", "Tipo", "Item", "Foto", "Ativo", "ID"])
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(560)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(self.edit_selected)

        table_layout.addLayout(top)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addWidget(filter_card)
        layout.addWidget(table_card, 1)
        self._set_action_state(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(120)

    def _set_action_state(self, enabled: bool):
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def refresh(self):
        self.items = self.api_client.get_checklist_items(
            tipo=self.type_filter.currentData() or None,
            ativos=self.active_filter.currentData(),
        )
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            for row, item in enumerate(self.items):
                values = [
                    str(item.get("position") or ""),
                    (item.get("tipo") or item.get("vehicle_type") or "-").title(),
                    item.get("item_nome") or "-",
                    "Sim" if item.get("foto_path") else "Não",
                    "Sim" if item.get("ativo") else "Não",
                    str(item.get("id") or ""),
                ]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, make_table_item(value, payload=item if col == 0 else None))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.summary_badge.setText(f"{len(self.items)} itens")
        if self.items:
            self.table.selectRow(0)
        else:
            self.current_item = None
            self._set_action_state(False)

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_item = None
            self._set_action_state(False)
            return
        self.current_item = self._item_for_row(selected[0].topRow())
        self._set_action_state(True)

    def _item_for_row(self, row: int | None):
        if row is None or row < 0:
            return None
        first_cell = self.table.item(row, 0)
        if first_cell:
            payload = first_cell.data(Qt.UserRole)
            if payload:
                return payload
        if row < len(self.items):
            return self.items[row]
        return None

    def add_item(self):
        dialog = ChecklistItemDialog(self.api_client, parent=self)
        if dialog.exec():
            self.api_client.create_checklist_item(dialog.result_payload)
            show_notice(self, "Item salvo", "Item cadastrado com sucesso.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()

    def edit_selected(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self.current_item
        if not row_item:
            return
        self.current_item = row_item
        dialog = ChecklistItemDialog(self.api_client, row_item, self)
        if dialog.exec():
            self.api_client.update_checklist_item(row_item["id"], dialog.result_payload)
            show_notice(self, "Item atualizado", "Item atualizado com sucesso.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()

    def delete_selected(self):
        if not self.current_item:
            return
        confirm = ask_confirmation(
            self,
            "Inativar item",
            f"Deseja retirar o item {self.current_item['item_nome']} do checklist ativo?",
            confirm_text="Sim",
            cancel_text="Não",
            icon_name="warning",
        )
        if confirm:
            self.api_client.delete_checklist_item(self.current_item["id"])
            show_notice(self, "Item inativado", "Item retirado do checklist ativo.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando itens do checklist")
        else:
            self.table_skeleton.hide_skeleton()
