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


def _grouping_labels(item: dict) -> tuple[str, str, str]:
    grouping = item.get("agrupamento") or {}
    group_type = (grouping.get("tipo_agrupamento") or "simples").replace("_", " ").title()
    parent_item = grouping.get("item_principal") or item.get("item_nome") or "-"
    part = grouping.get("parte") or "-"
    return group_type, parent_item, part


class ChecklistItemDialog(QDialog):
    def __init__(self, api_client, item: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.item = item or {}
        self.group_children = list(self.item.get("_children") or [])
        self.is_group_edit = len(self.group_children) > 1
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
        icon_label.setPixmap(make_icon("equipment", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
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

        grouping = self.item.get("agrupamento") or {}
        self.name_input = QLineEdit(
            grouping.get("item_principal") if self.is_group_edit else self.item.get("item_nome", "")
        )
        self.name_input.setPlaceholderText("Ex.: Lanterna traseira esquerda")

        self.type_combo = QComboBox()
        self.type_combo.addItem("Cavalo", "cavalo")
        self.type_combo.addItem("Carreta", "carreta")
        self.type_combo.addItem("Carro simples", "carro_simples")
        self.type_combo.addItem("Cavalo auxiliar", "cavalo_auxiliar")
        self.type_combo.addItem("Ambulancia", "ambulancia")
        self.type_combo.addItem("Caminhao pipa", "caminhao_pipa")
        self.type_combo.addItem("Caminhao brigada", "caminhao_brigada")
        self.type_combo.addItem("Onibus", "onibus")
        self.type_combo.addItem("Van", "van")
        current_type = self.item.get("tipo") or self.item.get("vehicle_type") or "cavalo"
        type_index = self.type_combo.findData(current_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

        self.position_spin = QSpinBox()
        self.position_spin.setMinimum(1)
        self.position_spin.setMaximum(999)
        self.position_spin.setValue(int(self.item.get("position") or 1))
        self.position_spin.setEnabled(False)

        self.active_checkbox = QCheckBox("Item ativo")
        self.active_checkbox.setChecked(bool(self.item.get("ativo", True)))
        self.group_type_combo = QComboBox()
        self.group_type_combo.addItem("Simples", "simples")
        self.group_type_combo.addItem("Lado", "lado")
        self.group_type_combo.addItem("Compartimento", "compartimento")
        group_type_value = (grouping.get("tipo_agrupamento") or self.item.get("tipo_agrupamento") or "simples").lower()
        group_index = self.group_type_combo.findData(group_type_value)
        if group_index >= 0:
            self.group_type_combo.setCurrentIndex(group_index)
        self.parent_item_input = QLineEdit(grouping.get("item_principal") or self.item.get("item_principal") or self.item.get("item_nome", ""))
        self.parent_item_input.setPlaceholderText("Ex.: PARALAMAS")
        self.part_input = QLineEdit(grouping.get("parte") or self.item.get("parte") or "")
        self.part_input.setPlaceholderText("Ex.: LADO DIREITO")
        self.part_inputs: list[tuple[dict, QLineEdit]] = []

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
        add_field(2, 0, "Regra de agrupamento", self.group_type_combo)
        add_field(2, 1, "Item principal", self.parent_item_input)
        if self.is_group_edit:
            parts_box = QFrame()
            parts_box.setAttribute(Qt.WA_StyledBackground, True)
            parts_layout = QVBoxLayout(parts_box)
            parts_layout.setContentsMargins(0, 0, 0, 0)
            parts_layout.setSpacing(8)
            for child in self.group_children:
                child_grouping = child.get("agrupamento") or {}
                row = QFrame()
                row.setObjectName("DialogInfoBlock")
                row.setAttribute(Qt.WA_StyledBackground, True)
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(10, 8, 10, 8)
                row_layout.setSpacing(6)
                label = QLabel(f"ID {child.get('id')} - {child.get('item_nome')}")
                label.setObjectName("SectionCaption")
                part_input = QLineEdit(child_grouping.get("parte") or child.get("parte") or "")
                part_input.setPlaceholderText("Ex.: LADO DIREITO")
                row_layout.addWidget(label)
                row_layout.addWidget(part_input)
                parts_layout.addWidget(row)
                self.part_inputs.append((child, part_input))
            add_field(3, 0, "Partes internas do agrupamento", parts_box)
        else:
            add_field(3, 0, "Parte interna", self.part_input)

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
        form.addWidget(photo_field, 3, 1)

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
                "ativo": self.active_checkbox.isChecked(),
                "tipo_agrupamento": self.group_type_combo.currentData(),
                "item_principal": self.parent_item_input.text().strip(),
                "parte": self.part_input.text().strip(),
            }
            if self.is_group_edit:
                payload["item_principal"] = payload["item_nome"] or payload["item_principal"]
                payload["item_nome"] = payload["item_principal"]
                payload["partes"] = [
                    {"id": child.get("id"), "parte": part_input.text().strip()}
                    for child, part_input in self.part_inputs
                ]
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
        self.display_items = []
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
        subtitle = QLabel("Configure os itens de checklist por tipo de equipamento, incluindo os auxiliares.")
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_button = QPushButton("Adicionar")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setMinimumHeight(34)
        self.add_button.clicked.connect(self.add_item)
        self.edit_button = QPushButton("Editar")
        self.edit_button.setMinimumHeight(34)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button = QPushButton("Inativar")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.setMinimumHeight(34)
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
        self.type_filter.addItem("Carro simples", "carro_simples")
        self.type_filter.addItem("Cavalo auxiliar", "cavalo_auxiliar")
        self.type_filter.addItem("Ambulancia", "ambulancia")
        self.type_filter.addItem("Caminhao pipa", "caminhao_pipa")
        self.type_filter.addItem("Caminhao brigada", "caminhao_brigada")
        self.type_filter.addItem("Onibus", "onibus")
        self.type_filter.addItem("Van", "van")
        self.type_filter.setMinimumHeight(34)
        self.active_filter = QComboBox()
        self.active_filter.addItem("Ativos", "true")
        self.active_filter.addItem("Todos", "all")
        self.active_filter.setMinimumHeight(34)
        self.type_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        self.active_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        filter_button = QPushButton("Aplicar filtros")
        filter_button.setMinimumHeight(34)
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

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Ordem", "Tipo", "Item", "Agrupamento", "Parte", "Foto", "Ativo", "ID"])
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(560)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())
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

    def _build_display_items(self, items: list[dict]) -> list[dict]:
        grouped: dict[tuple, dict] = {}
        display: list[dict] = []
        for item in items:
            grouping = item.get("agrupamento") or {}
            group_type = (grouping.get("tipo_agrupamento") or "simples").lower()
            parent_item = grouping.get("item_principal") or item.get("item_nome") or "-"
            if group_type == "simples":
                display.append(item)
                continue

            key = (
                item.get("tipo") or item.get("vehicle_type") or "",
                group_type,
                parent_item,
            )
            row = grouped.get(key)
            if not row:
                row = dict(item)
                row["_children"] = []
                row["_is_grouped"] = True
                row["item_nome"] = parent_item
                row["id"] = item.get("id")
                row["position"] = item.get("position")
                row["foto_path"] = item.get("foto_path")
                row["ativo"] = bool(item.get("ativo"))
                row["agrupamento"] = {
                    "tipo_agrupamento": group_type,
                    "item_principal": parent_item,
                    "parte": "",
                }
                grouped[key] = row
                display.append(row)
            row["_children"].append(item)
            parts = [
                child.get("agrupamento", {}).get("parte")
                for child in row["_children"]
                if child.get("agrupamento", {}).get("parte")
            ]
            row["agrupamento"]["parte"] = " / ".join(dict.fromkeys(parts)) or "-"
            row["foto_path"] = row.get("foto_path") or item.get("foto_path")
            row["ativo"] = row.get("ativo") or bool(item.get("ativo"))
            try:
                row["position"] = min(int(row.get("position") or item.get("position") or 1), int(item.get("position") or 1))
            except (TypeError, ValueError):
                pass
            row["id"] = ", ".join(str(child.get("id")) for child in row["_children"] if child.get("id"))

        return display

    def refresh(self, preferred_item_id: int | None = None):
        self.items = self.api_client.get_checklist_items(
            tipo=self.type_filter.currentData() or None,
            ativos=self.active_filter.currentData(),
        )
        self.display_items = self._build_display_items(self.items)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.display_items))
            for row, item in enumerate(self.display_items):
                group_type, parent_item, part = _grouping_labels(item)
                children = item.get("_children") or []
                item_name = item.get("item_nome") or "-"
                if children and len(children) > 1:
                    item_name = f"{item_name} ({len(children)} partes)"
                values = [
                    str(item.get("position") or ""),
                    (item.get("tipo") or item.get("vehicle_type") or "-").title(),
                    item_name,
                    parent_item if group_type != "Simples" else "Simples",
                    part,
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
            selected_row = 0
            if preferred_item_id is not None:
                for row_index, row_item in enumerate(self.display_items):
                    child_ids = [
                        int(child.get("id") or 0)
                        for child in (row_item.get("_children") or [row_item])
                    ]
                    if int(preferred_item_id) in child_ids:
                        selected_row = row_index
                        break
            self.table.selectRow(selected_row)
            self.current_item = self._item_for_row(selected_row)
            self._set_action_state(self.current_item is not None)
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
        if row < len(self.display_items):
            return self.display_items[row]
        return None

    def _selected_item(self):
        selected = self.table.selectedRanges()
        if selected:
            return self._item_for_row(selected[0].topRow())
        return self.current_item

    def add_item(self):
        default_type = self.type_filter.currentData() or "cavalo"
        dialog = ChecklistItemDialog(self.api_client, {"tipo": default_type, "vehicle_type": default_type}, parent=self)
        if dialog.exec():
            try:
                created = self.api_client.create_checklist_item(dialog.result_payload)
                show_notice(self, "Item salvo", "Item cadastrado com sucesso.", icon_name="dashboard")
                self.refresh((created or {}).get("id") if isinstance(created, dict) else None)
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")

    def edit_selected(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self._selected_item()
        if not row_item:
            return
        self.current_item = row_item
        grouped_children = row_item.get("_children") or []
        dialog = ChecklistItemDialog(self.api_client, row_item, self)
        if dialog.exec():
            try:
                if grouped_children:
                    parts_by_id = {
                        int(part.get("id") or 0): part.get("parte")
                        for part in dialog.result_payload.get("partes", [])
                    }
                    base_payload = {
                        "tipo": dialog.result_payload.get("tipo"),
                        "ativo": dialog.result_payload.get("ativo"),
                        "tipo_agrupamento": dialog.result_payload.get("tipo_agrupamento"),
                        "item_principal": dialog.result_payload.get("item_principal"),
                    }
                    for child in grouped_children:
                        child_id = int(child.get("id") or 0)
                        child_payload = dict(base_payload)
                        child_payload["parte"] = parts_by_id.get(child_id) or (child.get("agrupamento") or {}).get("parte") or child.get("parte")
                        if dialog.result_payload.get("foto_path") is not None:
                            child_payload["foto_path"] = dialog.result_payload.get("foto_path")
                        self.api_client.update_checklist_item(child_id, child_payload)
                    preferred_id = grouped_children[0].get("id")
                else:
                    self.api_client.update_checklist_item(row_item["id"], dialog.result_payload)
                    preferred_id = row_item.get("id")
                show_notice(self, "Item atualizado", "Item atualizado com sucesso.", icon_name="dashboard")
                self.refresh(preferred_id)
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def delete_selected(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        children = target_item.get("_children") or [target_item]
        target_name = target_item.get("item_nome") or target_item.get("agrupamento", {}).get("item_principal") or "item"
        confirm = ask_confirmation(
            self,
            "Inativar item",
            f"Deseja retirar o item {target_name} do checklist ativo?",
            confirm_text="Sim",
            cancel_text="Não",
            icon_name="warning",
        )
        if confirm:
            try:
                for child in children:
                    self.api_client.delete_checklist_item(child["id"])
                show_notice(self, "Item inativado", "Item retirado do checklist ativo.", icon_name="dashboard")
                self.refresh()
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao inativar", str(exc), icon_name="warning")

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando itens do checklist")
        else:
            self.table_skeleton.hide_skeleton()
