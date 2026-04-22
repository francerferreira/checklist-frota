from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush
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
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, make_icon, show_notice
from services import severity_from_occurrence
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card
from ui.detail_dialogs import NonConformityDetailDialog


class ResolveDialog(QDialog):
    def __init__(self, api_client, nc_item: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.nc_item = nc_item
        self.selected_file = ""
        self.result_payload = None
        self.materials = self.api_client.get_materials(
            tipo=nc_item["veiculo"].get("tipo"),
            ativos="true",
        )
        self.setWindowTitle("Resolver não conformidade")
        configure_dialog_window(self, width=920, height=720, min_width=760, min_height=600)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=980)

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
        icon_label.setPixmap(make_icon("warning", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title = QLabel(f"{nc_item['veiculo']['frota']} - {nc_item['item_nome']}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Informe peça, observação do reparo e foto depois em uma estrutura mais objetiva.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_row.addWidget(icon_badge, 0, Qt.AlignTop)
        header_row.addLayout(title_wrap, 1)
        header_layout.addLayout(header_row)

        self.codigo_input = QLineEdit(nc_item.get("codigo_peca") or "")
        self.descricao_input = QLineEdit(nc_item.get("descricao_peca") or "")
        self.material_combo = QComboBox()
        self.material_combo.addItem("Selecionar material do estoque", None)
        for material in self.materials:
            label = f"{material['referencia']} • {material['descricao']} • Saldo {material['quantidade_estoque']}"
            self.material_combo.addItem(label, material)
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)
        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(1)
        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Descreva o reparo executado.")

        self.file_label = QLabel("Nenhuma imagem selecionada.")
        self.file_label.setObjectName("MutedText")
        self.file_label.setWordWrap(True)
        select_button = QPushButton("Selecionar foto depois")
        select_button.setMinimumHeight(46)
        select_button.clicked.connect(self.select_file)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1, highlight: bool = False):
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
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Código da peça", self.codigo_input, highlight=True)
        add_field(0, 1, "Descrição da peça", self.descricao_input)
        add_field(1, 0, "Material do estoque", self.material_combo, 2, True)
        add_field(2, 0, "Quantidade do material", self.quantidade_spin, highlight=True)
        add_field(2, 1, "Observação", self.observacao_input)

        media_field = QFrame()
        media_field.setObjectName("DialogInfoBlock")
        media_field.setAttribute(Qt.WA_StyledBackground, True)
        media_layout = QVBoxLayout(media_field)
        media_layout.setContentsMargins(12, 12, 12, 12)
        media_layout.setSpacing(8)
        media_label = QLabel("Foto depois")
        media_label.setObjectName("SectionCaption")
        media_actions = QHBoxLayout()
        media_actions.setContentsMargins(0, 0, 0, 0)
        media_actions.setSpacing(12)
        media_actions.addWidget(select_button, 0)
        media_actions.addWidget(self.file_label, 1)
        media_layout.addWidget(media_label)
        media_layout.addLayout(media_actions)
        form.addWidget(media_field, 3, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Marcar como resolvido")
        submit_button.setProperty("variant", "success")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        submit_button.setMinimumWidth(210)
        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(submit_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def select_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto depois",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if filename:
            self.selected_file = filename
            self.file_label.setText(filename)

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        self.codigo_input.setText(material.get("referencia") or "")
        self.descricao_input.setText(material.get("descricao") or "")

    def submit(self):
        try:
            foto_depois = None
            if self.selected_file:
                upload = self.api_client.upload_file(
                    self.selected_file,
                    self.nc_item["veiculo"]["frota"],
                    self.nc_item["item_nome"],
                    self.api_client.user["login"],
                )
                foto_depois = upload["path"]

            material = self.material_combo.currentData()
            self.result_payload = self.api_client.resolve_non_conformity(
                self.nc_item["id"],
                {
                    "codigo_peca": self.codigo_input.text().strip(),
                    "descricao_peca": self.descricao_input.text().strip(),
                    "observacao": self.observacao_input.toPlainText().strip(),
                    "foto_depois": foto_depois,
                    "material_id": material.get("id") if material else None,
                    "quantidade_material": int(self.quantidade_spin.value()),
                },
            )
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao resolver", str(exc), icon_name="warning")


class CreateActivityFromNCDialog(QDialog):
    def __init__(self, api_client, nc_item: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.nc_item = nc_item
        self.created_activity = None
        self.materials = self.api_client.get_materials(
            tipo=nc_item["veiculo"].get("tipo"),
            ativos="true",
        )
        self.mechanics = self.api_client.get_mechanics()

        self.setWindowTitle("Criar atividade da não conformidade")
        configure_dialog_window(self, width=980, height=760, min_width=820, min_height=640)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=1040)

        vehicle = nc_item.get("veiculo") or {}
        user = nc_item.get("usuario") or {}

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)

        title = QLabel(f"Criar atividade - NC #{nc_item.get('id')}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"{vehicle.get('frota') or '-'} • {nc_item.get('item_nome') or '-'} • Motorista {user.get('nome') or '-'}"
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.titulo_input = QLineEdit(f"Tratativa NC - {vehicle.get('frota') or '-'} - {nc_item.get('item_nome') or '-'}")
        self.item_input = QLineEdit(nc_item.get("item_nome") or "")
        self.item_input.setPlaceholderText("Módulo / componente")

        self.codigo_input = QLineEdit(nc_item.get("codigo_peca") or "")
        self.descricao_input = QLineEdit(nc_item.get("descricao_peca") or "")

        self.material_combo = QComboBox()
        self.material_combo.addItem("Selecionar material do estoque", None)
        for material in self.materials:
            label = f"{material['referencia']} • {material['descricao']} • Saldo {material['quantidade_estoque']}"
            self.material_combo.addItem(label, material)
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(1)

        self.mechanic_combo = QComboBox()
        self.mechanic_combo.addItem("Sem direcionamento", None)
        for mechanic in self.mechanics:
            self.mechanic_combo.addItem(
                f"{mechanic.get('nome') or '-'} ({mechanic.get('login') or '-'})",
                mechanic,
            )

        self.allow_duplicate_check = QCheckBox("Permitir duplicidade se já existir atividade aberta para esta NC")
        self.allow_duplicate_check.setChecked(False)

        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Descreva o plano da tratativa, materiais e critérios de auditoria.")
        self.observacao_input.setPlainText(
            (
                f"NC #{nc_item.get('id')} - {nc_item.get('item_nome') or '-'}\n"
                f"Equipamento: {vehicle.get('frota') or '-'} | Placa: {vehicle.get('placa') or '-'}\n"
                f"Abertura: {self._format(nc_item.get('created_at'))}\n"
                f"Motorista: {user.get('nome') or '-'}"
            )
        )

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
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Título da atividade", self.titulo_input, 2, highlight=True)
        add_field(1, 0, "Módulo / componente", self.item_input, highlight=True)
        add_field(1, 1, "Material do estoque", self.material_combo, highlight=True)
        add_field(2, 0, "Código da peça", self.codigo_input)
        add_field(2, 1, "Descrição da peça", self.descricao_input)
        add_field(3, 0, "Mecânico direcionado", self.mechanic_combo, highlight=True)
        add_field(3, 1, "Quantidade por equipamento", self.quantidade_spin, highlight=True)
        add_field(4, 0, "Observação da tratativa", self.observacao_input, 2)
        add_field(5, 0, "Regra de duplicidade", self.allow_duplicate_check, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Criar atividade")
        submit_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        submit_button.setMinimumWidth(184)
        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(submit_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        self.codigo_input.setText(material.get("referencia") or "")
        self.descricao_input.setText(material.get("descricao") or "")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    def submit(self):
        item_nome = self.item_input.text().strip()
        if not item_nome:
            show_notice(self, "Módulo obrigatório", "Informe o módulo/componente da atividade.", icon_name="warning")
            return

        try:
            material = self.material_combo.currentData() or {}
            mechanic = self.mechanic_combo.currentData() or {}
            payload = {
                "titulo": self.titulo_input.text().strip(),
                "item_nome": item_nome,
                "material_id": material.get("id"),
                "quantidade_por_equipamento": int(self.quantidade_spin.value()),
                "codigo_peca": self.codigo_input.text().strip(),
                "descricao_peca": self.descricao_input.text().strip(),
                "observacao": self.observacao_input.toPlainText().strip(),
                "assigned_mechanic_user_id": mechanic.get("id"),
                "permitir_duplicada": self.allow_duplicate_check.isChecked(),
            }
            self.created_activity = self.api_client.create_activity_from_non_conformity(self.nc_item["id"], payload)
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao criar atividade", str(exc), icon_name="warning")


class NonConformitiesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.items = []
        self.mechanic_items = []
        self.current_item = None
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Não conformidades")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Consulta rápida, abertura e resolução de ocorrências."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = QPushButton("Abrir ocorrência")
        self.open_button.setMinimumHeight(42)
        self.open_button.clicked.connect(self.open_selected_item)
        self.create_activity_button = QPushButton("Criar atividade")
        self.create_activity_button.setMinimumHeight(42)
        self.create_activity_button.setProperty("variant", "primary")
        self.create_activity_button.clicked.connect(self.create_activity_from_current_item)
        self.resolve_button = QPushButton("Resolver")
        self.resolve_button.setMinimumHeight(42)
        self.resolve_button.setProperty("variant", "success")
        self.resolve_button.clicked.connect(self.resolve_current_item)
        actions.addWidget(self.open_button)
        actions.addWidget(self.create_activity_button)
        actions.addWidget(self.resolve_button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(actions)

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filters = QHBoxLayout(self.filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.vehicle_filter = QLineEdit()
        self.vehicle_filter.setPlaceholderText("Filtrar por veículo")
        self.vehicle_filter.setMinimumHeight(40)
        self.vehicle_filter.returnPressed.connect(self.refresh)
        self.vehicle_filter.textChanged.connect(self._schedule_live_refresh)

        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Filtrar por item")
        self.item_filter.setMinimumHeight(40)
        self.item_filter.returnPressed.connect(self.refresh)
        self.item_filter.textChanged.connect(self._schedule_live_refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todas", "")
        self.status_filter.addItem("Abertas", "abertas")
        self.status_filter.addItem("Resolvidas", "resolvidas")
        self.status_filter.setMinimumHeight(40)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.setMinimumHeight(40)
        refresh_button.clicked.connect(self.refresh)

        filters.addWidget(self.vehicle_filter, 1)
        filters.addWidget(self.item_filter, 1)
        filters.addWidget(self.status_filter)
        filters.addWidget(refresh_button)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)

        occurrences_tab = QFrame()
        occurrences_tab.setObjectName("TableCard")
        occurrences_tab.setAttribute(Qt.WA_StyledBackground, True)
        self.table_skeleton = TableSkeletonOverlay(occurrences_tab, rows=10)
        table_layout = QVBoxLayout(occurrences_tab)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)
        table_title = QLabel("Ocorrências registradas")
        table_title.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Nenhuma ocorrência carregada")
        self.summary_badge.setObjectName("TopBarPill")
        top_row.addWidget(table_title)
        top_row.addStretch()
        top_row.addWidget(self.summary_badge)

        table_caption = QLabel(
            "Clique duas vezes em uma linha para abrir fotos, histórico, peça aplicada e exportação de PDF."
        )
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Veículo", "Item", "Status", "Prioridade", "Data", "Motorista", "Peça", "Foto antes", "Foto depois"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(620)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(self.open_item_details)

        table_layout.addLayout(top_row)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table, 1)

        mechanic_tab = QFrame()
        mechanic_tab.setObjectName("TableCard")
        mechanic_tab.setAttribute(Qt.WA_StyledBackground, True)
        mechanic_layout = QVBoxLayout(mechanic_tab)
        mechanic_layout.setContentsMargins(10, 10, 10, 10)
        mechanic_layout.setSpacing(8)

        mechanic_top = QHBoxLayout()
        mechanic_title = QLabel("Atividades dos mecânicos")
        mechanic_title.setObjectName("SectionTitle")
        self.mechanic_badge = QLabel("0 registros")
        self.mechanic_badge.setObjectName("TopBarPill")
        mechanic_top.addWidget(mechanic_title)
        mechanic_top.addStretch()
        mechanic_top.addWidget(self.mechanic_badge)

        mechanic_caption = QLabel(
            "Registros internos abertos e resolvidos pelo módulo mecânico, separados das não conformidades do checklist."
        )
        mechanic_caption.setObjectName("SectionCaption")
        mechanic_caption.setWordWrap(True)

        self.mechanic_table = QTableWidget(0, 8)
        self.mechanic_table.setHorizontalHeaderLabels(
            ["Referência", "Item", "Status", "Aberta por", "Resolvida por", "Abertura", "Resolução", "Peça"]
        )
        configure_table(self.mechanic_table, stretch_last=False)
        self.mechanic_table.setMinimumHeight(620)

        mechanic_layout.addLayout(mechanic_top)
        mechanic_layout.addWidget(mechanic_caption)
        mechanic_layout.addWidget(self.mechanic_table, 1)

        self.tabs.addTab(occurrences_tab, "Ocorrências registradas")
        self.tabs.addTab(mechanic_tab, "Atividades dos mecânicos")

        outer.addLayout(header)
        outer.addWidget(self.filter_card)
        outer.addWidget(self.tabs, 1)
        self._set_action_state(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(240)

    def _set_action_state(self, enabled: bool):
        self.open_button.setEnabled(enabled)
        self.create_activity_button.setEnabled(enabled and not (self.current_item or {}).get("resolvido", False))
        self.resolve_button.setEnabled(enabled and not (self.current_item or {}).get("resolvido", False))

    def refresh(self):
        self.items = self.api_client.get_non_conformities(
            vehicle=self.vehicle_filter.text().strip() or None,
            item_type=self.item_filter.text().strip() or None,
            status=self.status_filter.currentData() or None,
        )
        self.mechanic_items = self.api_client.get_mechanic_non_conformities(
            status=self.status_filter.currentData() or None,
        )
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))

            for row, item in enumerate(self.items):
                created_at = item["created_at"].replace("T", " ")[:19]
                status_label = "Resolvida" if item["resolvido"] else "Aberta"
                severity = severity_from_occurrence(item)
                values = [
                    item["veiculo"]["frota"],
                    item["item_nome"],
                    status_label,
                    severity["label"],
                    created_at,
                    item["usuario"]["nome"],
                    item.get("codigo_peca") or "-",
                    "Sim" if item.get("foto_antes") else "Não",
                    "Sim" if item.get("foto_depois") else "Não",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value, payload=item if column == 0 else None)
                    if column == 3:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.table.setItem(row, column, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.summary_badge.setText(f"{len(self.items)} ocorrências")
        self._populate_mechanic_table()
        if self.items:
            self.table.selectRow(0)
        else:
            self.current_item = None
            self._set_action_state(False)

    def _populate_mechanic_table(self):
        self.mechanic_table.setSortingEnabled(False)
        self.mechanic_table.setUpdatesEnabled(False)
        self.mechanic_table.blockSignals(True)
        try:
            self.mechanic_table.setRowCount(len(self.mechanic_items))
            for row, item in enumerate(self.mechanic_items):
                values = [
                    item.get("veiculo_referencia") or "-",
                    item.get("item_nome") or "-",
                    "Resolvida" if item.get("resolvido") else "Aberta",
                    (item.get("created_by") or {}).get("nome") or "-",
                    (item.get("resolved_by") or {}).get("nome") or "-",
                    self._format(item.get("created_at")),
                    self._format(item.get("data_resolucao")),
                    item.get("codigo_peca") or "-",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 2:
                        if item.get("resolvido"):
                            cell.setBackground(QBrush(QColor("#DCFCE7")))
                            cell.setForeground(QBrush(QColor("#166534")))
                        else:
                            cell.setBackground(QBrush(QColor("#FEF3C7")))
                            cell.setForeground(QBrush(QColor("#B45309")))
                    self.mechanic_table.setItem(row, column, cell)
        finally:
            self.mechanic_table.blockSignals(False)
            self.mechanic_table.setUpdatesEnabled(True)
            self.mechanic_table.setSortingEnabled(True)
        self.mechanic_badge.setText(f"{len(self.mechanic_items)} registros")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando não conformidades")
        else:
            self.table_skeleton.hide_skeleton()

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_item = None
            self._set_action_state(False)
            return

        row = selected[0].topRow()
        self.current_item = self._item_for_row(row)
        self._set_action_state(True)

    def _item_for_row(self, row: int | None):
        if row is None or row < 0 or row >= len(self.items):
            return None
        first_cell = self.table.item(row, 0)
        if first_cell:
            payload = first_cell.data(Qt.UserRole)
            if payload:
                return payload
        return self.items[row]

    def _selected_item(self):
        selected = self.table.selectedRanges()
        if selected:
            return self._item_for_row(selected[0].topRow())
        return self.current_item

    def open_item_details(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self._selected_item()
        if not row_item:
            return
        self.current_item = row_item
        dialog = NonConformityDetailDialog(self.api_client, row_item, self)
        dialog.exec()

    def open_selected_item(self, *_args):
        self.open_item_details()

    def resolve_current_item(self):
        if not self.current_item:
            return
        dialog = ResolveDialog(self.api_client, self.current_item, self)
        if dialog.exec():
            show_notice(
                self,
                "Resolvida",
                "Não conformidade atualizada com sucesso.",
                icon_name="dashboard",
            )
            self.refresh()
            self.data_changed.emit()

    def create_activity_from_current_item(self):
        if not self.current_item:
            return
        dialog = CreateActivityFromNCDialog(self.api_client, self.current_item, self)
        if dialog.exec():
            created = dialog.created_activity or {}
            activity_id = created.get("id")
            message = "Atividade criada com sucesso a partir da não conformidade."
            if activity_id:
                message = f"Atividade #{activity_id} criada com sucesso a partir da não conformidade."
            show_notice(self, "Atividade aberta", message, icon_name="activities")
            self.refresh()
            self.data_changed.emit()

            parent_window = self.window()
            if parent_window and hasattr(parent_window, "switch_page"):
                try:
                    parent_window.switch_page("activities")
                except Exception:
                    pass

