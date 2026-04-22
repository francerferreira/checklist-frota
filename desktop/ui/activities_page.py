from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, make_icon, show_notice, start_export_task
from components import MessageComposerDialog
from runtime_paths import asset_path
from services.export_service import (
    export_activity_pdf,
    export_rows_to_csv,
    export_rows_to_xlsx,
    make_default_export_path,
)
from services import build_activity_message_package
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card


class ActivityDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.result_payload = None
        self.all_equipment = []
        self.filtered_equipment = []
        self.materials = []
        self.mechanics = []
        self._equipment_filter_timer = QTimer(self)
        self._equipment_filter_timer.setSingleShot(True)
        self._equipment_filter_timer.timeout.connect(self.apply_equipment_filters)

        self.setWindowTitle("Nova atividade em massa")
        configure_dialog_window(self, width=1320, height=820, min_width=980, min_height=700)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1420)

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
        icon_label.setPixmap(make_icon("activities", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title = QLabel("Abertura de atividade em massa")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            "Selecione os equipamentos, defina o componente e abra uma atividade auditável para execução em lote."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(14)

        self.titulo_input = QLineEdit()
        self.titulo_input.setPlaceholderText("Ex.: Troca programada de lanterna dianteira")

        self.item_input = QLineEdit()
        self.item_input.setPlaceholderText("Ex.: Lanterna")

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Cavalos", "cavalo")
        self.tipo_combo.addItem("Carretas", "carreta")
        self.tipo_combo.currentIndexChanged.connect(self.refresh_equipment)
        self.tipo_combo.currentIndexChanged.connect(self.refresh_materials)

        self.material_combo = QComboBox()
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)

        self.mechanic_combo = QComboBox()

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(1)

        self.codigo_input = QLineEdit()
        self.codigo_input.setPlaceholderText("Código da peça")

        self.descricao_input = QLineEdit()
        self.descricao_input.setPlaceholderText("Descrição da peça ou kit aplicado")

        self.fornecedor_input = QLineEdit()
        self.fornecedor_input.setPlaceholderText("Fornecedor da peça")

        self.lote_input = QLineEdit()
        self.lote_input.setPlaceholderText("Lote da peça")

        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Escopo da troca, fornecedor, lote, observações gerais.")

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1, *, highlight: bool = False):
            field = QFrame()
            if highlight:
                field.setObjectName("DialogInfoBlock")
                field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            margin = 12 if highlight else 0
            field_layout.setContentsMargins(margin, margin, margin, margin)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form_layout.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Título da atividade", self.titulo_input, highlight=True)
        add_field(0, 1, "Módulo / componente", self.item_input, highlight=True)
        add_field(1, 0, "Tipo de equipamento", self.tipo_combo, highlight=True)
        add_field(1, 1, "Material do estoque", self.material_combo, highlight=True)
        add_field(2, 0, "Código da peça", self.codigo_input)
        add_field(2, 1, "Quantidade por equipamento", self.quantidade_spin, highlight=True)
        add_field(3, 0, "Descrição da peça", self.descricao_input, 2)
        add_field(4, 0, "Fornecedor", self.fornecedor_input)
        add_field(4, 1, "Lote", self.lote_input)
        add_field(5, 0, "Mecânico direcionado", self.mechanic_combo, 2, highlight=True)
        add_field(6, 0, "Observação geral", self.observacao_input, 2)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 14, 14, 14)
        filter_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por frota, placa, modelo, chassi ou atividade")
        self.search_input.returnPressed.connect(self.apply_equipment_filters)
        self.search_input.textChanged.connect(self._schedule_equipment_filter)

        self.active_filter = QComboBox()
        self.active_filter.addItem("Ativos", "true")
        self.active_filter.addItem("Todos", "all")
        self.active_filter.currentIndexChanged.connect(self.refresh_equipment)

        select_all_button = QPushButton("Selecionar todos")
        select_all_button.clicked.connect(self.select_all)
        clear_button = QPushButton("Limpar seleção")
        clear_button.clicked.connect(self.clear_selection)
        filter_button = QPushButton("Aplicar filtros")
        filter_button.clicked.connect(self.apply_equipment_filters)

        filter_layout.addWidget(self.search_input, 1)
        filter_layout.addWidget(self.active_filter)
        filter_layout.addWidget(select_all_button)
        filter_layout.addWidget(clear_button)
        filter_layout.addWidget(filter_button)

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        table_top = QHBoxLayout()
        table_top.setContentsMargins(0, 0, 0, 0)
        table_top.setSpacing(12)
        table_title = QLabel("Equipamentos selecionáveis")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel(
            "Marque todos ou apenas os equipamentos desejados. A atividade vai auditar individualmente cada unidade."
        )
        table_caption.setObjectName("SectionCaption")
        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        text_wrap.addWidget(table_title)
        text_wrap.addWidget(table_caption)
        self.selection_badge = QLabel("0 selecionados")
        self.selection_badge.setObjectName("TopBarPill")
        table_top.addLayout(text_wrap, 1)
        table_top.addWidget(self.selection_badge)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Selecionar", "Frota", "Placa", "Modelo", "Status", "Local"])
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(360)
        self.table.itemChanged.connect(self._handle_item_changed)

        table_layout.addLayout(table_top)
        table_layout.addWidget(self.table)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Abrir atividade")
        save_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        save_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        save_button.setMinimumWidth(182)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(filter_card)
        layout.addWidget(table_card, 1)
        layout.addWidget(footer)

        self.refresh_materials()
        self.refresh_mechanics()
        self.refresh_equipment()

    def refresh_equipment(self):
        ativos_data = self.active_filter.currentData()
        ativos = None if ativos_data == "all" else ativos_data == "true"
        self.all_equipment = self.api_client.get_equipment(self.tipo_combo.currentData(), ativos)
        self.apply_equipment_filters()

    def _schedule_equipment_filter(self, *_args):
        self._equipment_filter_timer.start(140)

    def refresh_materials(self):
        self.materials = self.api_client.get_materials(tipo=self.tipo_combo.currentData(), ativos="true")
        self.material_combo.blockSignals(True)
        self.material_combo.clear()
        self.material_combo.addItem("Selecionar material", None)
        for material in self.materials:
            label = f"{material['referencia']} • {material['descricao']} • Saldo {material['quantidade_estoque']}"
            self.material_combo.addItem(label, material)
        self.material_combo.blockSignals(False)
        self._sync_material_fields()

    def refresh_mechanics(self):
        self.mechanics = self.api_client.get_mechanics()
        self.mechanic_combo.clear()
        self.mechanic_combo.addItem("Sem direcionamento específico", None)
        for user in self.mechanics:
            self.mechanic_combo.addItem(f"{user.get('nome') or '-'} ({user.get('login') or '-'})", user)

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        self.codigo_input.setText(material.get("referencia") or "")
        self.descricao_input.setText(material.get("descricao") or "")

    def apply_equipment_filters(self):
        term = self.search_input.text().strip().lower()
        self.filtered_equipment = []
        for item in self.all_equipment:
            haystack = " ".join(
                str(item.get(field) or "")
                for field in ("frota", "placa", "modelo", "chassi", "atividade", "local")
            ).lower()
            if term and term not in haystack:
                continue
            self.filtered_equipment.append(item)
        self._populate_table()

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.filtered_equipment))
            for row, item in enumerate(self.filtered_equipment):
                selector = QTableWidgetItem()
                selector.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                selector.setCheckState(Qt.Unchecked)
                selector.setData(Qt.UserRole, item["id"])
                self.table.setItem(row, 0, selector)
                self.table.setItem(row, 1, make_table_item(item.get("frota") or "-"))
                self.table.setItem(row, 2, make_table_item(item.get("placa") or "-"))
                self.table.setItem(row, 3, make_table_item(item.get("modelo") or "-"))
                self.table.setItem(row, 4, make_table_item(item.get("status") or "-"))
                self.table.setItem(row, 5, make_table_item(item.get("local") or "-"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        self._update_selection_badge()

    def _handle_item_changed(self, item):
        if item.column() == 0:
            self._update_selection_badge()

    def _update_selection_badge(self):
        self.selection_badge.setText(f"{len(self.selected_vehicle_ids())} selecionados")

    def select_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)
        self.table.blockSignals(False)
        self._update_selection_badge()

    def clear_selection(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_selection_badge()

    def selected_vehicle_ids(self) -> list[int]:
        vehicle_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                vehicle_ids.append(int(item.data(Qt.UserRole)))
        return vehicle_ids

    def submit(self):
        item_nome = self.item_input.text().strip()
        vehicle_ids = self.selected_vehicle_ids()
        if not item_nome:
            show_notice(self, "Modulo obrigatorio", "Informe o modulo ou componente da atividade.", icon_name="warning")
            return
        if not vehicle_ids:
            show_notice(
                self,
                "Selecao obrigatoria",
                "Selecione ao menos um equipamento para abrir a atividade.",
                icon_name="warning",
            )
            return

        titulo = self.titulo_input.text().strip() or f"Troca em massa - {item_nome}"
        self.result_payload = {
            "titulo": titulo,
            "item_nome": item_nome,
            "tipo_equipamento": self.tipo_combo.currentData(),
            "material_id": (self.material_combo.currentData() or {}).get("id"),
            "quantidade_por_equipamento": int(self.quantidade_spin.value()),
            "codigo_peca": self.codigo_input.text().strip(),
            "descricao_peca": self.descricao_input.text().strip(),
            "fornecedor_peca": self.fornecedor_input.text().strip(),
            "lote_peca": self.lote_input.text().strip(),
            "observacao": self.observacao_input.toPlainText().strip(),
            "assigned_mechanic_user_id": (self.mechanic_combo.currentData() or {}).get("id"),
            "vehicle_ids": vehicle_ids,
        }
        self.accept()


class ActivityItemUpdateDialog(QDialog):
    def __init__(self, api_client, activity: dict, item: dict, parent=None, *, allow_material_edit: bool = True):
        super().__init__(parent)
        self.api_client = api_client
        self.activity = activity
        self.item = item
        self.allow_material_edit = bool(allow_material_edit)
        origin_locked_flag = item.get("foto_origem_bloqueada")
        if isinstance(origin_locked_flag, bool):
            self.origin_photo_locked = origin_locked_flag
        else:
            source_type = str(activity.get("source_type") or "").strip().upper()
            observation = str(activity.get("observacao") or "").upper()
            self.origin_photo_locked = source_type == "NC_ITEM" or "[ORIGEM:NC#" in observation
        self.before_file = ""
        self.after_file = ""
        self.result_payload = None
        self.materials = []

        veiculo = item.get("veiculo", {})
        item_tipo = str((veiculo.get("tipo") or activity.get("tipo_equipamento") or "")).strip().lower()
        material_tipo = item_tipo if item_tipo in {"cavalo", "carreta"} else None
        self.materials = self.api_client.get_materials(tipo=material_tipo, ativos="true")

        self.setWindowTitle("Atualizar execução da atividade")
        configure_dialog_window(self, width=1240, height=880, min_width=1060, min_height=760)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1280)

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
        icon_label.setPixmap(make_icon("activities", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title = QLabel(f"{veiculo.get('frota') or '-'} - {activity.get('item_nome') or '-'}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Registre se a peça foi instalada, não instalada ou permanece pendente, com evidências.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)
        form_layout.setColumnStretch(0, 1)
        form_layout.setColumnStretch(1, 1)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Pendente", "PENDENTE")
        self.status_combo.addItem("Instalado", "INSTALADO")
        self.status_combo.addItem("Não instalado", "NAO_INSTALADO")
        existing_status = item.get("status_execucao") or "PENDENTE"
        index = self.status_combo.findData(existing_status)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)

        self.observacao_input = QTextEdit(item.get("observacao") or "")
        self.observacao_input.setPlaceholderText("Descreva a execução, pendência, restrição ou apontamento de auditoria.")
        self.observacao_input.setMinimumHeight(220)

        self.material_combo = QComboBox()
        self.material_combo.addItem("Sem material específico (usar padrão da atividade)", None)
        for material in self.materials:
            label = f"{material.get('referencia') or '-'} • {material.get('descricao') or '-'} • Saldo {material.get('quantidade_estoque') or 0}"
            self.material_combo.addItem(label, material)

        current_material_id = item.get("material_id")
        if not current_material_id:
            current_material_id = activity.get("material_id")
        if current_material_id:
            for idx in range(self.material_combo.count()):
                data = self.material_combo.itemData(idx) or {}
                if data.get("id") == current_material_id:
                    self.material_combo.setCurrentIndex(idx)
                    break
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(int(item.get("quantidade_peca") or activity.get("quantidade_por_equipamento") or 1))
        self.quantidade_spin.setMinimumWidth(120)

        self.codigo_input = QLineEdit(item.get("codigo_peca") or activity.get("codigo_peca") or "")
        self.codigo_input.setPlaceholderText("Código da peça")
        self.codigo_input.setMinimumWidth(170)

        self.descricao_input = QLineEdit(item.get("descricao_peca") or activity.get("descricao_peca") or "")
        self.descricao_input.setPlaceholderText("Descrição da peça")
        self.descricao_input.setMinimumWidth(280)
        if not self.allow_material_edit:
            self.material_combo.setEnabled(False)
            self.quantidade_spin.setEnabled(False)
            self.codigo_input.setEnabled(False)
            self.descricao_input.setEnabled(False)

        self.before_label = QLabel(item.get("foto_origem") or item.get("foto_antes") or "Sem foto de origem vinculada.")
        self.before_label.setObjectName("MutedText")
        self.before_label.setWordWrap(True)
        self.after_label = QLabel(item.get("foto_resolucao") or item.get("foto_depois") or "Sem foto de resolução vinculada.")
        self.after_label.setObjectName("MutedText")
        self.after_label.setWordWrap(True)

        before_button = QPushButton("Selecionar foto de origem")
        before_button.setMinimumHeight(42)
        before_button.clicked.connect(lambda: self._select_file("before"))
        if self.origin_photo_locked:
            before_button.setText("Foto de origem preservada")
            before_button.setEnabled(False)
        after_button = QPushButton("Selecionar foto de resolução")
        after_button.setMinimumHeight(42)
        after_button.clicked.connect(lambda: self._select_file("after"))

        def add_field(row: int, label_text: str, widget, *, highlight: bool = False):
            field = QFrame()
            if highlight:
                field.setObjectName("DialogInfoBlock")
                field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            margin = 12 if highlight else 0
            field_layout.setContentsMargins(margin, margin, margin, margin)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form_layout.addWidget(field, row, 0, 1, 2)

        add_field(0, "Status da execução", self.status_combo, highlight=True)
        add_field(1, "Observação da atividade", self.observacao_input)
        material_label = "Material específico deste equipamento"
        if not self.allow_material_edit:
            material_label += " (somente leitura)"
        add_field(2, material_label, self.material_combo, highlight=True)

        material_meta_row = QFrame()
        material_meta_layout = QGridLayout(material_meta_row)
        material_meta_layout.setContentsMargins(0, 0, 0, 0)
        material_meta_layout.setHorizontalSpacing(10)
        material_meta_layout.setVerticalSpacing(6)
        material_meta_layout.addWidget(QLabel("Qtd. peça"), 0, 0)
        material_meta_layout.addWidget(QLabel("Código"), 0, 1)
        material_meta_layout.addWidget(QLabel("Descrição"), 0, 2)
        material_meta_layout.addWidget(self.quantidade_spin, 1, 0)
        material_meta_layout.addWidget(self.codigo_input, 1, 1)
        material_meta_layout.addWidget(self.descricao_input, 1, 2)
        material_meta_layout.setColumnStretch(2, 1)
        add_field(3, "Detalhes do material", material_meta_row)

        evidence_row = QFrame()
        evidence_layout = QGridLayout(evidence_row)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        evidence_layout.setHorizontalSpacing(12)
        evidence_layout.setVerticalSpacing(0)

        before_field = QFrame()
        before_field.setObjectName("DialogInfoBlock")
        before_field.setAttribute(Qt.WA_StyledBackground, True)
        before_layout = QVBoxLayout(before_field)
        before_layout.setContentsMargins(12, 12, 12, 12)
        before_layout.setSpacing(8)
        before_title = QLabel("Evidência de origem (antes)")
        before_title.setObjectName("SectionCaption")
        before_layout.addWidget(before_title)
        before_actions = QVBoxLayout()
        before_actions.setContentsMargins(0, 0, 0, 0)
        before_actions.setSpacing(8)
        before_actions.addWidget(before_button, 0, Qt.AlignLeft)
        before_actions.addWidget(self.before_label, 1)
        before_layout.addLayout(before_actions)

        after_field = QFrame()
        after_field.setObjectName("DialogInfoBlock")
        after_field.setAttribute(Qt.WA_StyledBackground, True)
        after_layout = QVBoxLayout(after_field)
        after_layout.setContentsMargins(12, 12, 12, 12)
        after_layout.setSpacing(8)
        after_title = QLabel("Evidência de resolução (depois)")
        after_title.setObjectName("SectionCaption")
        after_layout.addWidget(after_title)
        after_actions = QVBoxLayout()
        after_actions.setContentsMargins(0, 0, 0, 0)
        after_actions.setSpacing(8)
        after_actions.addWidget(after_button, 0, Qt.AlignLeft)
        after_actions.addWidget(self.after_label, 1)
        after_layout.addLayout(after_actions)

        evidence_layout.addWidget(before_field, 0, 0)
        evidence_layout.addWidget(after_field, 0, 1)
        evidence_layout.setColumnStretch(0, 1)
        evidence_layout.setColumnStretch(1, 1)
        add_field(4, "Evidências", evidence_row, highlight=True)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar atualização")
        save_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        save_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        save_button.setMinimumWidth(182)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)
        self._sync_material_fields()

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        if not self.codigo_input.text().strip():
            self.codigo_input.setText(material.get("referencia") or "")
        if not self.descricao_input.text().strip():
            self.descricao_input.setText(material.get("descricao") or "")

    def _select_file(self, target: str):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar evidencia",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if not filename:
            return
        if target == "before":
            self.before_file = filename
            self.before_label.setText(filename)
        else:
            self.after_file = filename
            self.after_label.setText(filename)

    def submit(self):
        try:
            payload = {
                "status_execucao": self.status_combo.currentData(),
                "observacao": self.observacao_input.toPlainText().strip(),
            }
            if self.allow_material_edit:
                payload.update(
                    {
                        "material_id": (self.material_combo.currentData() or {}).get("id"),
                        "quantidade_peca": int(self.quantidade_spin.value()),
                        "codigo_peca": self.codigo_input.text().strip(),
                        "descricao_peca": self.descricao_input.text().strip(),
                    }
                )
            veiculo = self.item.get("veiculo", {})
            item_nome = self.activity.get("item_nome") or "atividade"
            user_login = (self.api_client.user or {}).get("login", "sistema")
            vehicle_name = veiculo.get("frota") or "equipamento"

            if not self.origin_photo_locked:
                if self.before_file:
                    upload = self.api_client.upload_file(self.before_file, vehicle_name, item_nome, user_login)
                    payload["foto_antes"] = upload["path"]
                elif self.item.get("foto_origem") or self.item.get("foto_antes"):
                    payload["foto_antes"] = self.item.get("foto_origem") or self.item.get("foto_antes")

            if self.after_file:
                upload = self.api_client.upload_file(self.after_file, vehicle_name, f"{item_nome}_depois", user_login)
                payload["foto_depois"] = upload["path"]
            elif self.item.get("foto_resolucao") or self.item.get("foto_depois"):
                payload["foto_depois"] = self.item.get("foto_resolucao") or self.item.get("foto_depois")

            self.result_payload = payload
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")


class ActivityMaterialBatchDialog(QDialog):
    def __init__(self, api_client, activity: dict, selected_count: int, total_count: int, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.activity = activity
        self.selected_count = selected_count
        self.total_count = total_count
        self.result_payload = None

        activity_tipo = str(activity.get("tipo_equipamento") or "").strip().lower()
        material_tipo = activity_tipo if activity_tipo in {"cavalo", "carreta"} else None
        self.materials = self.api_client.get_materials(tipo=material_tipo, ativos="true")

        self.setWindowTitle("Editar material da atividade")
        configure_dialog_window(self, width=940, height=620, min_width=780, min_height=560)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=980)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel("Material por equipamento")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"Selecionados: {selected_count} de {total_count}. "
            "Você pode aplicar o mesmo material nos selecionados ou em toda a atividade."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(12)

        self.material_combo = QComboBox()
        self.material_combo.addItem("Sem material específico (manual)", None)
        for material in self.materials:
            label = f"{material.get('referencia') or '-'} • {material.get('descricao') or '-'} • Saldo {material.get('quantidade_estoque') or 0}"
            self.material_combo.addItem(label, material)
        if activity.get("material_id"):
            for idx in range(self.material_combo.count()):
                data = self.material_combo.itemData(idx) or {}
                if data.get("id") == activity.get("material_id"):
                    self.material_combo.setCurrentIndex(idx)
                    break
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(int(activity.get("quantidade_por_equipamento") or 1))

        self.codigo_input = QLineEdit(activity.get("codigo_peca") or "")
        self.codigo_input.setPlaceholderText("Código da peça")

        self.descricao_input = QLineEdit(activity.get("descricao_peca") or "")
        self.descricao_input.setPlaceholderText("Descrição da peça")

        self.apply_all_check = QCheckBox("Aplicar em todos os equipamentos da atividade")
        self.apply_all_check.setChecked(selected_count <= 0)

        def add_field(row: int, label_text: str, widget):
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            form_layout.addWidget(label, row, 0)
            form_layout.addWidget(widget, row, 1)

        add_field(0, "Material", self.material_combo)
        add_field(1, "Quantidade por equipamento", self.quantidade_spin)
        add_field(2, "Código da peça", self.codigo_input)
        add_field(3, "Descrição da peça", self.descricao_input)
        form_layout.addWidget(self.apply_all_check, 4, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Aplicar material")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)
        self._sync_material_fields()

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        if not self.codigo_input.text().strip():
            self.codigo_input.setText(material.get("referencia") or "")
        if not self.descricao_input.text().strip():
            self.descricao_input.setText(material.get("descricao") or "")

    def submit(self):
        self.result_payload = {
            "material_id": (self.material_combo.currentData() or {}).get("id"),
            "quantidade_peca": int(self.quantidade_spin.value()),
            "codigo_peca": self.codigo_input.text().strip(),
            "descricao_peca": self.descricao_input.text().strip(),
            "apply_to_all": bool(self.apply_all_check.isChecked()),
        }
        self.accept()


class ActivityDetailDialog(QDialog):
    def __init__(self, api_client, activity_id: int, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.activity_id = activity_id
        self.logo_path = asset_path("app-logo-cover.png")
        self.activity = {}
        self.items = []
        self.updated = False
        user_tipo = str((self.api_client.user or {}).get("tipo") or "").strip().lower()
        self.can_manage_materials = user_tipo in {"admin", "gestor"}

        self.setWindowTitle("Detalhes da atividade")
        configure_dialog_window(self, width=1760, height=940, min_width=1240, min_height=760)
        style_card(self)

        layout = build_dialog_layout(
            self,
            max_content_width=0,
            margins=(10, 10, 10, 10),
            spacing=12,
        )

        self.header = QFrame()
        self.header.setObjectName("DialogHeader")
        self.header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("activities", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        self.title_label = QLabel("Atividade em massa")
        self.title_label.setObjectName("DialogHeaderTitle")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("DialogHeaderSubtitle")
        self.subtitle_label.setWordWrap(True)
        title_wrap.addWidget(self.title_label)
        title_wrap.addWidget(self.subtitle_label)

        header_actions = QHBoxLayout()
        header_actions.setContentsMargins(0, 0, 0, 0)
        header_actions.setSpacing(8)
        export_csv = QPushButton("CSV")
        export_csv.clicked.connect(lambda: self.export_activity("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.clicked.connect(lambda: self.export_activity("xlsx"))
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.clicked.connect(lambda: self.export_activity("pdf"))
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.clicked.connect(self.generate_message)
        header_actions.addWidget(export_csv)
        header_actions.addWidget(export_xlsx)
        header_actions.addWidget(export_pdf)
        header_actions.addWidget(message_button)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)
        header_layout.addLayout(header_actions)

        summary_card = QFrame()
        style_filter_bar(summary_card)
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(10)
        self.total_badge = QLabel("0 equipamentos")
        self.total_badge.setObjectName("TopBarPill")
        self.installed_badge = QLabel("0 instalados")
        self.installed_badge.setObjectName("TopBarPill")
        self.not_installed_badge = QLabel("0 não instalados")
        self.not_installed_badge.setObjectName("TopBarPill")
        self.pending_badge = QLabel("0 pendentes")
        self.pending_badge.setObjectName("TopBarPill")
        summary_layout.addWidget(self.total_badge)
        summary_layout.addWidget(self.installed_badge)
        summary_layout.addWidget(self.not_installed_badge)
        summary_layout.addWidget(self.pending_badge)
        summary_layout.addStretch()

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_top = QHBoxLayout()
        table_top.setContentsMargins(0, 0, 0, 0)
        table_top.setSpacing(12)
        title = QLabel("Auditoria por equipamento")
        title.setObjectName("SectionTitle")
        caption = QLabel(
            "Clique duas vezes em uma linha para registrar instalação, não instalação, observações e evidências."
        )
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)

        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.refresh)
        edit_button = QPushButton("Marcar selecionado")
        edit_button.setProperty("variant", "primary")
        edit_button.clicked.connect(self.edit_selected_item)
        material_button = QPushButton("Editar material")
        material_button.clicked.connect(self.edit_material_for_selected)
        material_button.setVisible(self.can_manage_materials)

        table_top.addLayout(text_wrap, 1)
        table_top.addWidget(refresh_button)
        table_top.addWidget(material_button)
        table_top.addWidget(edit_button)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Frota",
                "Placa",
                "Modelo",
                "Material",
                "Qtd peça",
                "Status da atividade",
                "Executado em",
                "Executado por",
                "Foto origem",
                "Foto resolução",
                "Observação",
            ]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setMinimumHeight(660)
        self._configure_activity_table_columns()
        self.table.itemDoubleClicked.connect(self.edit_selected_item)

        table_layout.addLayout(table_top)
        table_layout.addWidget(self.table)

        layout.addWidget(self.header)
        layout.addWidget(summary_card)
        layout.addWidget(table_card, 1)

        self.refresh()

    def _configure_activity_table_columns(self):
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(88)
        header.setDefaultSectionSize(134)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Frota
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Placa
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Modelo
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Material
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Qtd peça
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status da atividade
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Executado em
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Executado por
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Foto origem
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # Foto resolução
        header.setSectionResizeMode(10, QHeaderView.Stretch)  # Observação

    def refresh(self):
        self.activity = self.api_client.get_activity(self.activity_id)
        self.items = self.activity.get("itens", [])
        resumo = self.activity.get("resumo", {})

        self.title_label.setText(self.activity.get("titulo") or "Atividade em massa")
        self.subtitle_label.setText(
            f"{(self.activity.get('tipo_equipamento') or '-').title()} • "
            f"{self.activity.get('item_nome') or '-'} • "
            f"{self._format(self.activity.get('created_at'))} • "
            f"Status {self._format_activity_status(self.activity.get('status'))}"
        )
        self.total_badge.setText(f"{resumo.get('total', 0)} equipamentos")
        self.installed_badge.setText(f"{resumo.get('instalados', 0)} instalados")
        self.not_installed_badge.setText(f"{resumo.get('nao_instalados', 0)} não instalados")
        self.pending_badge.setText(f"{resumo.get('pendentes', 0)} pendentes")
        self.total_badge.setToolTip(
            f"Código: {self.activity.get('codigo_peca') or '-'}\n"
            f"Fornecedor: {self.activity.get('fornecedor_peca') or '-'}\n"
            f"Lote: {self.activity.get('lote_peca') or '-'}"
        )

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            for row, item in enumerate(self.items):
                veiculo = item.get("veiculo", {})
                material = item.get("material") or {}
                values = [
                    veiculo.get("frota") or "-",
                    veiculo.get("placa") or "-",
                    veiculo.get("modelo") or "-",
                    item.get("descricao_peca") or material.get("descricao") or item.get("codigo_peca") or "-",
                    str(item.get("quantidade_peca") or self.activity.get("quantidade_por_equipamento") or 1),
                    self._format_item_status(item.get("status_execucao")),
                    self._format(item.get("instalado_em")),
                    item.get("executado_por_nome") or "-",
                    "Sim" if self._origin_photo_path(item) else "Não",
                    "Sim" if self._resolution_photo_path(item) else "Não",
                    item.get("observacao") or "-",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value, payload=item if column == 0 else None)
                    if column == 5:
                        colors = self._status_colors(item.get("status_execucao"))
                        cell.setBackground(QBrush(QColor(colors["background"])))
                        cell.setForeground(QBrush(QColor(colors["color"])))
                    self.table.setItem(row, column, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        if self.items:
            self.table.selectRow(0)

    def _selected_item(self):
        selected = self.table.selectedRanges()
        if not selected:
            return None
        row = selected[0].topRow()
        return self._item_for_row(row)

    def _selected_rows(self) -> list[int]:
        model = self.table.selectionModel()
        if not model:
            return []
        return sorted({index.row() for index in model.selectedRows()})

    def _selected_items(self) -> list[dict]:
        rows = self._selected_rows()
        if not rows:
            item = self._selected_item()
            return [item] if item else []
        selected_items = []
        for row in rows:
            payload = self._item_for_row(row)
            if payload:
                selected_items.append(payload)
        return selected_items

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

    def edit_selected_item(self, *_args):
        item = self._selected_item()
        if not item:
            return
        dialog = ActivityItemUpdateDialog(
            self.api_client,
            self.activity,
            item,
            self,
            allow_material_edit=self.can_manage_materials,
        )
        if dialog.exec():
            response = self.api_client.update_activity_item(self.activity_id, item["id"], dialog.result_payload)
            message = "Registro da atividade atualizado com sucesso."
            if isinstance(response, dict) and response.get("aviso_foto_origem_preservada"):
                message = response.get("mensagem_foto_origem") or "Evidência de origem preservada e atualização concluída."
            show_notice(self, "Atividade atualizada", message, icon_name="dashboard")
            self.updated = True
            self.refresh()

    def edit_material_for_selected(self):
        if not self.can_manage_materials:
            show_notice(self, "Acesso restrito", "Somente admin ou gestor podem editar materiais da atividade.", icon_name="warning")
            return
        selected_items = self._selected_items()
        if not selected_items:
            show_notice(self, "Seleção obrigatória", "Selecione ao menos um equipamento para editar material.", icon_name="warning")
            return
        dialog = ActivityMaterialBatchDialog(
            self.api_client,
            self.activity,
            selected_count=len(selected_items),
            total_count=len(self.items),
            parent=self,
        )
        if not dialog.exec():
            return
        payload = dict(dialog.result_payload or {})
        payload["activity_item_ids"] = [int(item.get("id")) for item in selected_items if item.get("id")]
        try:
            self.api_client.update_activity_materials(self.activity_id, payload)
            show_notice(self, "Materiais atualizados", "Material aplicado aos equipamentos selecionados.", icon_name="dashboard")
            self.updated = True
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao atualizar material", str(exc), icon_name="warning")

    def export_activity(self, file_type: str):
        if not self.items:
            show_notice(self, "Sem dados", "Não há equipamentos registrados nesta atividade.", icon_name="warning")
            return

        rows = []
        for item in self.items:
            veiculo = item.get("veiculo", {})
            material = item.get("material") or {}
            rows.append(
                {
                    "frota": veiculo.get("frota") or "-",
                    "placa": veiculo.get("placa") or "-",
                    "modelo": veiculo.get("modelo") or "-",
                    "material": item.get("descricao_peca") or material.get("descricao") or item.get("codigo_peca") or "-",
                    "quantidade_peca": str(item.get("quantidade_peca") or self.activity.get("quantidade_por_equipamento") or 1),
                    "status_execucao": self._format_item_status(item.get("status_execucao")),
                    "instalado_em": self._format(item.get("instalado_em")),
                    "executado_por": item.get("executado_por_nome") or "-",
                    "foto_origem": "Sim" if self._origin_photo_path(item) else "Não",
                    "foto_resolucao": "Sim" if self._resolution_photo_path(item) else "Não",
                    "observacao": item.get("observacao") or "-",
                }
            )

        columns = [
            ("Frota", "frota"),
            ("Placa", "placa"),
            ("Modelo", "modelo"),
            ("Material", "material"),
            ("Qtd peça", "quantidade_peca"),
            ("Status da atividade", "status_execucao"),
            ("Instalado em", "instalado_em"),
            ("Executado por", "executado_por"),
            ("Foto origem", "foto_origem"),
            ("Foto resolução", "foto_resolucao"),
            ("Observação", "observacao"),
        ]

        default_path = make_default_export_path(
            f"atividade_{(self.activity.get('item_nome') or 'massa').lower().replace(' ', '_')}",
            file_type,
        )
        filters = {"csv": "CSV (*.csv)", "xlsx": "Excel (*.xlsx)", "pdf": "PDF (*.pdf)"}
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar atividade", default_path, filters[file_type])
        if not filename:
            return

        try:
            if file_type == "csv":
                export_rows_to_csv(columns, rows, filename)
            elif file_type == "xlsx":
                export_rows_to_xlsx(self.activity.get("titulo") or "Atividade em massa", columns, rows, filename)
            else:
                activity = dict(self.activity)
                activity_items = list(self.items)

                def task(progress):
                    progress(8, "Preparando PDF da atividade")
                    item_images = {}
                    total = max(1, len(activity_items))
                    for index, activity_item in enumerate(activity_items, start=1):
                        progress(12 + int(((index - 1) / total) * 62), f"Carregando evidências {index}/{len(activity_items)}")
                        item_images[activity_item["id"]] = {
                            "before": self.api_client.fetch_image(self._origin_photo_path(activity_item)),
                            "after": self.api_client.fetch_image(self._resolution_photo_path(activity_item)),
                        }
                    progress(82, "Montando páginas do PDF")
                    export_activity_pdf(
                        activity,
                        output_path=filename,
                        logo_path=self.logo_path,
                        generated_by=(self.api_client.user or {}).get("nome", ""),
                        item_images=item_images,
                    )
                    return filename

                start_export_task(
                    self,
                    "Exportando PDF da atividade",
                    task,
                    success_title="Exportação concluída",
                    failure_title="Falha na exportação",
                )
                return
            show_notice(self, "Exportação concluída", f"Arquivo salvo em:\n{filename}", icon_name="reports")
        except Exception as exc:
            show_notice(self, "Falha na exportação", str(exc), icon_name="warning")

    def generate_message(self):
        if not self.activity or not self.items:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_activity_message_package(
            self.activity,
            generated_by=(self.api_client.user or {}).get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    @staticmethod
    def _format_activity_status(value: str | None) -> str:
        return {"ABERTA": "Aberta", "FINALIZADA": "Finalizada"}.get(value or "", value or "-")

    @staticmethod
    def _format_item_status(value: str | None) -> str:
        return {
            "PENDENTE": "Pendente",
            "INSTALADO": "Instalado",
            "NAO_INSTALADO": "Não instalado",
        }.get(value or "", value or "-")

    @staticmethod
    def _status_colors(value: str | None) -> dict[str, str]:
        mapping = {
            "INSTALADO": {"background": "#DCFCE7", "color": "#166534"},
            "NAO_INSTALADO": {"background": "#FEE2E2", "color": "#B91C1C"},
            "PENDENTE": {"background": "#FEF3C7", "color": "#B45309"},
        }
        return mapping.get(value or "", {"background": "#E2E8F0", "color": "#334155"})

    @staticmethod
    def _origin_photo_path(item: dict | None) -> str | None:
        payload = item or {}
        return payload.get("foto_origem") or payload.get("foto_antes")

    @staticmethod
    def _resolution_photo_path(item: dict | None) -> str | None:
        payload = item or {}
        return payload.get("foto_resolucao") or payload.get("foto_depois")


class ActivitiesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.items = []
        self.mechanics = []
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Atividades")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Abra trocas em massa por módulo, selecione vários equipamentos e acompanhe a execução individual com auditoria."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_button = QPushButton("Nova atividade")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setMinimumHeight(42)
        self.add_button.clicked.connect(self.add_activity)
        self.open_button = QPushButton("Abrir selecionada")
        self.open_button.setMinimumHeight(42)
        self.open_button.clicked.connect(self.open_selected)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setMinimumHeight(42)
        self.refresh_button.clicked.connect(self.refresh)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.refresh_button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(buttons)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(8)

        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Buscar por titulo, modulo ou componente")
        self.item_filter.setMinimumHeight(40)
        self.item_filter.returnPressed.connect(self.refresh)
        self.item_filter.textChanged.connect(self._schedule_live_refresh)

        self.type_filter = QComboBox()
        self.type_filter.addItem("Todos os tipos", "")
        self.type_filter.addItem("Cavalos", "cavalo")
        self.type_filter.addItem("Carretas", "carreta")
        self.type_filter.setMinimumHeight(40)
        self.type_filter.currentIndexChanged.connect(self._schedule_live_refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todas", "")
        self.status_filter.addItem("Abertas", "ABERTA")
        self.status_filter.addItem("Finalizadas", "FINALIZADA")
        self.status_filter.setMinimumHeight(40)
        self.status_filter.currentIndexChanged.connect(self._schedule_live_refresh)

        self.mechanic_filter = QComboBox()
        self.mechanic_filter.addItem("Todos os mecânicos", None)
        self.mechanic_filter.setMinimumHeight(40)
        self.mechanic_filter.currentIndexChanged.connect(self._schedule_live_refresh)

        filter_button = QPushButton("Aplicar filtros")
        filter_button.setMinimumHeight(40)
        filter_button.clicked.connect(self.refresh)

        filter_layout.addWidget(self.item_filter, 1)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(self.mechanic_filter)
        filter_layout.addWidget(filter_button)

        table_card = QFrame()
        style_table_card(table_card)
        self.activities_table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_top = QHBoxLayout()
        table_top.setContentsMargins(0, 0, 0, 0)
        table_top.setSpacing(12)
        table_title = QLabel("Atividades em massa registradas")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel(
            "Clique duas vezes em uma linha para abrir os detalhes, ver a auditoria por equipamento e exportar o relatório."
        )
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(table_title)
        title_wrap.addWidget(table_caption)
        self.summary_badge = QLabel("Nenhuma atividade carregada")
        self.summary_badge.setObjectName("TopBarPill")
        table_top.addLayout(title_wrap, 1)
        table_top.addWidget(self.summary_badge)

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels(
            [
                "Título",
                "Módulo",
                "Origem",
                "Tipo",
                "Status",
                "Mecânico",
                "Equipamentos",
                "NC vinculadas",
                "Instalados",
                "Não instalados",
                "Pendentes",
                "Abertura",
            ]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(580)
        self.table.itemDoubleClicked.connect(self.open_activity_details)

        table_layout.addLayout(table_top)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addWidget(filter_card)
        layout.addWidget(table_card, 1)
        self.open_button.setEnabled(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(220)

    def refresh(self):
        self._refresh_mechanic_filter()
        self.items = self.api_client.get_activities(
            tipo=self.type_filter.currentData() or None,
            status=self.status_filter.currentData() or None,
            item_name=self.item_filter.text().strip() or None,
            mechanic_id=self.mechanic_filter.currentData() or None,
        )
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            for row, item in enumerate(self.items):
                resumo = item.get("resumo", {})
                values = [
                    item.get("titulo") or "-",
                    item.get("item_nome") or "-",
                    self._format_origin(item.get("origem")),
                    (item.get("tipo_equipamento") or "-").title(),
                    self._format_status(item.get("status")),
                    (item.get("assigned_mechanic") or {}).get("nome") or "-",
                    str(resumo.get("total", 0)),
                    str((item.get("vinculos_nc") or {}).get("total", 0)),
                    str(resumo.get("instalados", 0)),
                    str(resumo.get("nao_instalados", 0)),
                    str(resumo.get("pendentes", 0)),
                    self._format(item.get("created_at")),
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value, payload=item if column == 0 else None)
                    if column == 4:
                        colors = self._status_colors(item.get("status"))
                        cell.setBackground(QBrush(QColor(colors["background"])))
                        cell.setForeground(QBrush(QColor(colors["color"])))
                    self.table.setItem(row, column, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.summary_badge.setText(f"{len(self.items)} atividades")
        self.open_button.setEnabled(bool(self.items))
        if self.items:
            self.table.selectRow(0)

    def _refresh_mechanic_filter(self):
        current = self.mechanic_filter.currentData()
        try:
            self.mechanics = self.api_client.get_mechanics()
        except Exception:
            self.mechanics = []
        self.mechanic_filter.blockSignals(True)
        self.mechanic_filter.clear()
        self.mechanic_filter.addItem("Todos os mecânicos", None)
        for user in self.mechanics:
            self.mechanic_filter.addItem(user.get("nome") or user.get("login") or "-", user.get("id"))
        if current:
            index = self.mechanic_filter.findData(current)
            if index >= 0:
                self.mechanic_filter.setCurrentIndex(index)
        self.mechanic_filter.blockSignals(False)

    def set_loading_state(self, loading: bool):
        if loading:
            self.activities_table_skeleton.show_skeleton("Carregando atividades em massa")
        else:
            self.activities_table_skeleton.hide_skeleton()

    def _selected_row(self):
        selected = self.table.selectedRanges()
        if not selected:
            return None
        row = selected[0].topRow()
        return self._activity_for_row(row)

    def _activity_for_row(self, row: int | None):
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

    def add_activity(self):
        dialog = ActivityDialog(self.api_client, self)
        if dialog.exec():
            self.api_client.create_activity(dialog.result_payload)
            show_notice(
                self,
                "Atividade aberta",
                "Atividade em massa criada com sucesso.",
                icon_name="dashboard",
            )
            self.refresh()
            self.data_changed.emit()

    def open_selected(self, *_args):
        self.open_activity_details()

    def open_activity_details(self, item=None):
        if item is not None:
            activity = self._activity_for_row(item.row())
        else:
            activity = self._selected_row()
        if not activity:
            return
        dialog = ActivityDetailDialog(self.api_client, activity["id"], self)
        dialog.exec()
        self.refresh()
        if dialog.updated:
            self.data_changed.emit()

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    @staticmethod
    def _format_status(value: str | None) -> str:
        return {"ABERTA": "Aberta", "FINALIZADA": "Finalizada"}.get(value or "", value or "-")

    @staticmethod
    def _format_origin(value: dict | None) -> str:
        if not value:
            return "Manual"
        return value.get("descricao") or "Manual"

    @staticmethod
    def _status_colors(value: str | None) -> dict[str, str]:
        mapping = {
            "ABERTA": {"background": "#FEF3C7", "color": "#B45309"},
            "FINALIZADA": {"background": "#DCFCE7", "color": "#166534"},
        }
        return mapping.get(value or "", {"background": "#E2E8F0", "color": "#334155"})

