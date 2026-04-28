from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
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
    QWidget,
)

from services import severity_from_counts
from services import (
    build_item_message_package,
    build_macro_message_package,
    build_micro_message_package,
)
from services.export_service import (
    export_item_audit_pdf,
    export_rows_to_csv,
    export_rows_to_pdf,
    export_rows_to_xlsx,
    export_vehicle_detail_pdf,
    make_default_export_path,
)
from components import ExportProgressDialog, ExportWorker, MessageComposerDialog, TableSkeletonOverlay, open_exported_pdf
from components import show_notice
from runtime_paths import asset_path
from theme import (
    build_dialog_layout,
    configure_dialog_window,
    configure_table,
    make_table_item,
    style_card,
    style_filter_bar,
    style_table_card,
)
from ui.detail_dialogs import NonConformityDetailDialog, VehicleDetailDialog


def _apply_light_date_popup_style(date_edit: QDateEdit):
    calendar_widget = date_edit.calendarWidget()
    if not calendar_widget:
        return
    calendar_widget.setStyleSheet(
        """
        QCalendarWidget {
            background: #F4F8FE;
            color: #0F3A68;
        }
        QCalendarWidget QWidget {
            background: #F4F8FE;
            color: #0F3A68;
        }
        QCalendarWidget QToolButton {
            background: #E8F1FC;
            color: #0F3A68;
            border: 1px solid #8FB2D9;
            border-radius: 2px;
            padding: 4px 8px;
            font-weight: 700;
        }
        QCalendarWidget QToolButton:hover {
            background: #D9EAFF;
            border: 1px solid #5F92C9;
        }
        QCalendarWidget QMenu {
            background: #FFFFFF;
            color: #0F3A68;
        }
        QCalendarWidget QSpinBox {
            background: #FFFFFF;
            color: #0F3A68;
            border: 1px solid #8FB2D9;
            border-radius: 2px;
        }
        QCalendarWidget QAbstractItemView {
            background: #FFFFFF;
            color: #0F3A68;
            selection-background-color: #1F6FCA;
            selection-color: #FFFFFF;
            border: 1px solid #9FBFE1;
            outline: 0;
        }
        QCalendarWidget QAbstractItemView:enabled {
            selection-background-color: #1F6FCA;
            selection-color: #FFFFFF;
            background: #FFFFFF;
            color: #0F3A68;
            outline: 0;
        }
        QCalendarWidget QAbstractItemView:disabled {
            color: #8AA2BC;
        }
        """
    )


class MacroMassActivityDialog(QDialog):
    def __init__(self, api_client, context: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.context = context
        self.result_payload = None
        self.created_activity = None

        modulo = context.get("modulo") or "all"
        modulo_material = modulo if modulo in {"cavalo", "carreta"} else None
        self.materials = self.api_client.get_materials(tipo=modulo_material, ativos="true")
        self.mechanics = self.api_client.get_mechanics()

        self.setWindowTitle("Criar atividade em massa por não conformidade")
        configure_dialog_window(self, width=980, height=760, min_width=840, min_height=660)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=1020)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel(f"Atividade em massa - {context.get('item_nome') or '-'}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"{context.get('abertas', 0)} ocorrência(s) em aberto no escopo atual. "
            "Novas NC do mesmo item entrarão automaticamente enquanto a atividade estiver aberta."
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

        self.titulo_input = QLineEdit(f"Tratativa em massa - {context.get('item_nome') or '-'}")
        self.item_input = QLineEdit(context.get("item_nome") or "")
        self.item_input.setReadOnly(True)
        self.codigo_input = QLineEdit()
        self.descricao_input = QLineEdit()

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

        self.allow_duplicate_check = QCheckBox("Permitir abrir nova atividade mesmo com outra igual em aberto")
        self.allow_duplicate_check.setChecked(False)

        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Critérios de execução, auditoria e rastreabilidade.")
        self.observacao_input.setPlainText(
            (
                f"Origem: Relatório por não conformidade\n"
                f"Item: {context.get('item_nome') or '-'}\n"
                f"Módulo: {context.get('modulo_label') or 'Todos'}\n"
                f"Status NC: {context.get('status_label') or 'NC abertas'}\n"
                f"Período: {context.get('period_label') or 'Todo período'}"
            )
        )

        self.scope_label = QLabel(
            f"Escopo atual: {context.get('abertas', 0)} NC abertas • módulo {context.get('modulo_label') or 'Todos'}"
        )
        self.scope_label.setObjectName("TopBarPill")

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
        add_field(1, 0, "Não conformidade (item)", self.item_input, 2, highlight=True)
        add_field(2, 0, "Material do estoque", self.material_combo, highlight=True)
        add_field(2, 1, "Quantidade por equipamento", self.quantidade_spin, highlight=True)
        add_field(3, 0, "Código da peça", self.codigo_input)
        add_field(3, 1, "Descrição da peça", self.descricao_input)
        add_field(4, 0, "Mecânico direcionado", self.mechanic_combo, 2, highlight=True)
        add_field(5, 0, "Observação da tratativa", self.observacao_input, 2)
        add_field(6, 0, "Regra de duplicidade", self.allow_duplicate_check, 2)
        add_field(7, 0, "Resumo de escopo", self.scope_label, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()

        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Criar atividade em massa")
        submit_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        submit_button.setMinimumWidth(224)
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

    def submit(self):
        item_nome = (self.context.get("item_nome") or "").strip()
        if not item_nome:
            show_notice(self, "Item obrigatório", "Selecione uma linha da tabela de não conformidades.", icon_name="warning")
            return

        status_nc = (self.context.get("status_nc") or "").strip().lower() or "abertas"
        if status_nc != "abertas":
            answer = QMessageBox.question(
                self,
                "Confirmar escopo",
                (
                    "O filtro atual não está em 'NC abertas'. "
                    "Deseja seguir com esse escopo mesmo assim?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        material = self.material_combo.currentData() or {}
        mechanic = self.mechanic_combo.currentData() or {}
        self.result_payload = {
            "titulo": self.titulo_input.text().strip(),
            "item_nome": item_nome,
            "modulo": self.context.get("modulo") or "all",
            "status_nc": status_nc,
            "date_from": self.context.get("date_from"),
            "date_to": self.context.get("date_to"),
            "material_id": material.get("id"),
            "quantidade_por_equipamento": int(self.quantidade_spin.value()),
            "codigo_peca": self.codigo_input.text().strip(),
            "descricao_peca": self.descricao_input.text().strip(),
            "observacao": self.observacao_input.toPlainText().strip(),
            "assigned_mechanic_user_id": mechanic.get("id"),
            "permitir_duplicada": self.allow_duplicate_check.isChecked(),
            "auto_link_nc": True,
        }
        try:
            self.created_activity = self.api_client.create_mass_activity_from_non_conformity_item(self.result_payload)
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao criar atividade em massa", str(exc), icon_name="warning")


class ReportsPage(QFrame):
    pdf_export_finished = Signal(object, object)
    pdf_export_failed = Signal(object, str)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setObjectName("ContentSurface")
        self.logo_path = asset_path("app-logo-cover.png")
        self.macro_rows = []
        self.micro_rows = []
        self.item_rows = []
        self.resolved_rows = []
        self.vehicle_cache = {}
        self.dirty_tabs: set[str] = {"macro", "micro", "item", "resolved", "vehicles"}
        self._export_jobs = []
        self._item_period_sync = False
        self._item_filter_timer = QTimer(self)
        self._item_filter_timer.setSingleShot(True)
        self._item_filter_timer.timeout.connect(self._refresh_filtered_tab)
        self.pdf_export_finished.connect(self._handle_pdf_export_finished)
        self.pdf_export_failed.connect(self._handle_pdf_export_failed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Relatórios")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Visão gerencial com tabelas amplas, exportação executiva e abertura de detalhes operacionais por linha."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        header.addLayout(text_wrap)
        header.addStretch()

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filter_layout = QVBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(8)

        top_filter_row = QHBoxLayout()
        top_filter_row.setContentsMargins(0, 0, 0, 0)
        top_filter_row.setSpacing(8)

        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Buscar NC, equipamento, motorista ou item")
        self.item_filter.setMinimumHeight(34)
        self.item_filter.returnPressed.connect(self._refresh_filtered_tab)
        self.item_filter.textChanged.connect(self._schedule_item_refresh)

        search_button = QPushButton("Aplicar")
        search_button.setProperty("variant", "primary")
        search_button.setMinimumHeight(34)
        search_button.clicked.connect(self._refresh_filtered_tab)

        top_filter_row.addWidget(self.item_filter, 1)
        top_filter_row.addWidget(search_button)

        bottom_filter_row = QHBoxLayout()
        bottom_filter_row.setContentsMargins(0, 0, 0, 0)
        bottom_filter_row.setSpacing(8)

        self.modulo_filter = QComboBox()
        self.modulo_filter.addItem("Todos os módulos", "")
        self.modulo_filter.addItem("Cavalos", "cavalo")
        self.modulo_filter.addItem("Carretas", "carreta")
        self.modulo_filter.addItem("Outros", "outros")
        self.modulo_filter.setMinimumHeight(34)
        self.modulo_filter.currentIndexChanged.connect(self._schedule_item_refresh)

        self.nc_status_filter = QComboBox()
        self.nc_status_filter.addItem("Todas as NC", "")
        self.nc_status_filter.addItem("NC abertas", "abertas")
        self.nc_status_filter.addItem("NC resolvidas", "resolvidas")
        self.nc_status_filter.setMinimumHeight(34)
        self.nc_status_filter.currentIndexChanged.connect(self._schedule_item_refresh)
        self.nc_status_filter.setCurrentIndex(1)

        self.period_mode_filter = QComboBox()
        self.period_mode_filter.addItem("Todo período", "all")
        self.period_mode_filter.addItem("Hoje", "today")
        self.period_mode_filter.addItem("Mês atual", "month")
        self.period_mode_filter.addItem("Período personalizado", "custom")
        self.period_mode_filter.setMinimumHeight(34)
        self.period_mode_filter.currentIndexChanged.connect(self._on_item_period_mode_changed)

        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.start_date_filter.setMinimumHeight(34)
        _apply_light_date_popup_style(self.start_date_filter)
        self.start_date_filter.dateChanged.connect(self._on_item_period_date_changed)

        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.end_date_filter.setMinimumHeight(34)
        _apply_light_date_popup_style(self.end_date_filter)
        self.end_date_filter.dateChanged.connect(self._on_item_period_date_changed)

        clear_filter_button = QPushButton("Limpar filtros")
        clear_filter_button.setMinimumHeight(34)
        clear_filter_button.clicked.connect(self._clear_item_filters)

        bottom_filter_row.addWidget(self.modulo_filter)
        bottom_filter_row.addWidget(self.nc_status_filter)
        bottom_filter_row.addWidget(self.period_mode_filter)
        bottom_filter_row.addWidget(self.start_date_filter)
        bottom_filter_row.addWidget(self.end_date_filter)
        bottom_filter_row.addWidget(clear_filter_button)

        filter_layout.addLayout(top_filter_row)
        filter_layout.addLayout(bottom_filter_row)
        self._on_item_period_mode_changed()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_macro_tab(), "Macro (por NC)")
        self.tabs.addTab(self._build_micro_tab(), "Micro")
        self.tabs.addTab(self._build_item_tab(), "Detalhe (ocor.)")
        self.tabs.addTab(self._build_resolved_tab(), "NC Resolvidas")
        self.tabs.addTab(self._build_audit_logs_tab(), "Logs de Auditoria")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Admin access for audit logs tab
        self.tabs.setTabVisible(4, self.api_client.user_has_admin_access())

        layout.addLayout(header)
        layout.addWidget(self.filter_card)
        layout.addWidget(self.tabs, 1)

    def _schedule_item_refresh(self, *_args):
        self._item_filter_timer.start(240)

    def _refresh_filtered_tab(self):
        if self.current_tab_key() == "resolved":
            self.refresh_resolved_table()
        else:
            self.refresh_item_table()

    def _on_item_period_mode_changed(self, *_args):
        mode = self.period_mode_filter.currentData() or "all"
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)

        self._item_period_sync = True
        if mode == "all":
            self.start_date_filter.setDate(first_day)
            self.end_date_filter.setDate(today)
            self.start_date_filter.setEnabled(False)
            self.end_date_filter.setEnabled(False)
        elif mode == "today":
            self.start_date_filter.setDate(today)
            self.end_date_filter.setDate(today)
            self.start_date_filter.setEnabled(False)
            self.end_date_filter.setEnabled(False)
        elif mode == "month":
            self.start_date_filter.setDate(first_day)
            self.end_date_filter.setDate(today)
            self.start_date_filter.setEnabled(False)
            self.end_date_filter.setEnabled(False)
        else:
            self.start_date_filter.setEnabled(True)
            self.end_date_filter.setEnabled(True)
            if self.start_date_filter.date() > self.end_date_filter.date():
                self.end_date_filter.setDate(self.start_date_filter.date())
        self._item_period_sync = False
        self._schedule_item_refresh()

    def _on_item_period_date_changed(self, *_args):
        if self._item_period_sync:
            return
        if self.start_date_filter.date() > self.end_date_filter.date():
            self._item_period_sync = True
            self.end_date_filter.setDate(self.start_date_filter.date())
            self._item_period_sync = False
        self._schedule_item_refresh()

    def _clear_item_filters(self):
        self.item_filter.clear()
        self.modulo_filter.setCurrentIndex(0)
        self.nc_status_filter.setCurrentIndex(0)
        self.period_mode_filter.setCurrentIndex(0)
        self._refresh_filtered_tab()

    def _build_macro_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.macro_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Por não conformidade")
        title.setObjectName("SectionTitle")
        caption = QLabel("Consolidado das não conformidades por item, com total, abertas, resolvidas e prioridade.")
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        export_csv = QPushButton("CSV")
        export_csv.setMinimumHeight(34)
        export_csv.clicked.connect(lambda: self.export_macro("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.setMinimumHeight(34)
        export_xlsx.clicked.connect(lambda: self.export_macro("xlsx"))
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.setMinimumHeight(34)
        export_pdf.clicked.connect(lambda: self.export_macro("pdf"))
        self.create_mass_activity_button = QPushButton("Criar atividade em massa")
        self.create_mass_activity_button.setProperty("variant", "primary")
        self.create_mass_activity_button.setMinimumHeight(34)
        self.create_mass_activity_button.clicked.connect(self.create_macro_mass_activity)
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(34)
        message_button.clicked.connect(self.generate_macro_message)
        top.addLayout(text_wrap, 1)
        top.addWidget(self.create_mass_activity_button)
        top.addWidget(message_button)
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        top.addWidget(export_pdf)

        self.macro_table = QTableWidget(0, 5)
        self.macro_table.setHorizontalHeaderLabels(
            ["Item", "Total de não conformidades", "Abertas", "Resolvidas", "Prioridade"]
        )
        configure_table(self.macro_table, stretch_last=False)
        self.macro_table.setMinimumHeight(520)
        self.macro_table.itemDoubleClicked.connect(self.open_macro_item)
        self.macro_table.itemSelectionChanged.connect(self._update_macro_action_state)

        card_layout.addLayout(top)
        card_layout.addWidget(self.macro_table)
        layout.addWidget(card)
        self._update_macro_action_state()
        return tab

    def _build_micro_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.micro_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Relatório micro")
        title.setObjectName("SectionTitle")
        caption = QLabel("Leitura por equipamento, com acesso direto a ficha operacional.")
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        export_csv = QPushButton("CSV")
        export_csv.setMinimumHeight(34)
        export_csv.clicked.connect(lambda: self.export_micro("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.setMinimumHeight(34)
        export_xlsx.clicked.connect(lambda: self.export_micro("xlsx"))
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.setMinimumHeight(34)
        export_pdf.clicked.connect(lambda: self.export_micro("pdf"))
        audit_pdf = QPushButton("PDF Auditoria do equipamento")
        audit_pdf.setMinimumHeight(34)
        audit_pdf.clicked.connect(self.export_selected_vehicle_audit_pdf)
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(34)
        message_button.clicked.connect(self.generate_micro_message)
        top.addLayout(text_wrap, 1)
        top.addWidget(message_button)
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        top.addWidget(export_pdf)
        top.addWidget(audit_pdf)

        self.micro_table = QTableWidget(0, 7)
        self.micro_table.setHorizontalHeaderLabels(
            ["Frota", "Placa", "Modelo", "Tipo", "Não conformidades", "Prioridade", "Último checklist"]
        )
        configure_table(self.micro_table, stretch_last=False)
        self.micro_table.setMinimumHeight(520)
        self.micro_table.itemDoubleClicked.connect(self.open_micro_vehicle)

        card_layout.addLayout(top)
        card_layout.addWidget(self.micro_table)
        layout.addWidget(card)
        return tab

    def _build_item_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.item_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Ocorrências detalhadas")
        title.setObjectName("SectionTitle")
        caption = QLabel("Lista detalhada por não conformidade com equipamento, data/hora, motorista, status, prioridade e evidências.")
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(34)
        message_button.clicked.connect(self.generate_item_message)
        audit_pdf = QPushButton("PDF Completo por NC")
        audit_pdf.setMinimumHeight(34)
        audit_pdf.clicked.connect(self.export_item_audit_pdf)
        top.addLayout(text_wrap, 1)
        top.addWidget(message_button)
        top.addWidget(audit_pdf)

        self.item_table = QTableWidget(0, 8)
        self.item_table.setHorizontalHeaderLabels(
            ["Veículo", "Item", "Data", "Motorista", "Status", "Prioridade", "Foto origem", "Foto resolução"]
        )
        configure_table(self.item_table, stretch_last=False)
        self.item_table.setMinimumHeight(520)
        self.item_table.itemDoubleClicked.connect(self.open_item_occurrence)

        card_layout.addLayout(top)
        card_layout.addWidget(self.item_table)
        layout.addWidget(card)
        return tab

    def _build_resolved_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.resolved_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Não conformidades resolvidas")
        title.setObjectName("SectionTitle")
        caption = QLabel("Área dedicada aos resolvidos com data de resolução, foto de origem, foto de resolução e filtros operacionais.")
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)

        export_csv = QPushButton("CSV")
        export_csv.setMinimumHeight(34)
        export_csv.clicked.connect(lambda: self.export_resolved("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.setMinimumHeight(34)
        export_xlsx.clicked.connect(lambda: self.export_resolved("xlsx"))
        export_pdf = QPushButton("PDF Resolvidos")
        export_pdf.setMinimumHeight(34)
        export_pdf.clicked.connect(self.export_resolved_audit_pdf)

        top.addLayout(text_wrap, 1)
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        top.addWidget(export_pdf)

        self.resolved_table = QTableWidget(0, 8)
        self.resolved_table.setHorizontalHeaderLabels(
            ["Não conformidade", "Veículo", "Resolvido em", "Motorista", "Resolvido por", "Módulo", "Foto origem", "Foto resolução"]
        )
        configure_table(self.resolved_table, stretch_last=False)
        self.resolved_table.setMinimumHeight(520)
        self.resolved_table.itemDoubleClicked.connect(self.open_resolved_occurrence)

        card_layout.addLayout(top)
        card_layout.addWidget(self.resolved_table)
        layout.addWidget(card)
        return tab

    def _build_audit_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.audit_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Logs de Auditoria")
        title.setObjectName("SectionTitle")
        caption = QLabel("Histórico de mudanças críticas no sistema (status de equipamentos, resolução de NCs, etc.).")
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)

        self.audit_entity_filter = QComboBox()
        self.audit_entity_filter.addItem("Todas as entidades", "")
        self.audit_entity_filter.addItem("Sessões (login/logout)", "SESSION")
        self.audit_entity_filter.addItem("Usuários", "USER")
        self.audit_entity_filter.addItem("Veículos", "VEHICLE")
        self.audit_entity_filter.addItem("Checklist", "CHECKLIST")
        self.audit_entity_filter.addItem("Itens de Checklist", "CHECKLIST_ITEM")
        self.audit_entity_filter.addItem("Atividades", "ACTIVITY")
        self.audit_entity_filter.addItem("Itens de Atividade", "ACTIVITY_ITEM")
        self.audit_entity_filter.addItem("Manutenção", "MAINTENANCE_SCHEDULE")
        self.audit_entity_filter.addItem("Itens de Manutenção", "MAINTENANCE_SCHEDULE_ITEM")
        self.audit_entity_filter.addItem("Materiais", "MATERIAL")
        self.audit_entity_filter.addItem("Movimentos de Material", "MATERIAL_MOVEMENT")
        self.audit_entity_filter.addItem("Lavagens", "WASH_RECORD")
        self.audit_entity_filter.setMinimumHeight(34)
        self.audit_entity_filter.currentIndexChanged.connect(self._schedule_audit_refresh)

        self.audit_start_date_filter = QDateEdit()
        self.audit_start_date_filter.setCalendarPopup(True)
        self.audit_start_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.audit_start_date_filter.setMinimumHeight(34)
        _apply_light_date_popup_style(self.audit_start_date_filter)
        self.audit_start_date_filter.setDate(QDate.currentDate().addDays(-30)) # Últimos 30 dias por padrão
        self.audit_start_date_filter.dateChanged.connect(self._schedule_audit_refresh)

        self.audit_end_date_filter = QDateEdit()
        self.audit_end_date_filter.setCalendarPopup(True)
        self.audit_end_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.audit_end_date_filter.setMinimumHeight(34)
        _apply_light_date_popup_style(self.audit_end_date_filter)
        self.audit_end_date_filter.setDate(QDate.currentDate())
        self.audit_end_date_filter.dateChanged.connect(self._schedule_audit_refresh)

        self.audit_live_filter_timer = QTimer(self)
        self.audit_live_filter_timer.setSingleShot(True)
        self.audit_live_filter_timer.timeout.connect(self.refresh_audit_logs)

        audit_filter_row = QHBoxLayout()
        audit_filter_row.setContentsMargins(0, 0, 0, 0)
        audit_filter_row.setSpacing(8)
        audit_filter_row.addWidget(self.audit_entity_filter)
        audit_filter_row.addWidget(QLabel("De:"))
        audit_filter_row.addWidget(self.audit_start_date_filter)
        audit_filter_row.addWidget(QLabel("Até:"))
        audit_filter_row.addWidget(self.audit_end_date_filter)
        audit_filter_row.addStretch()

        top.addLayout(text_wrap, 1)
        top.addLayout(audit_filter_row)

        self.audit_table = QTableWidget(0, 6)
        self.audit_table.setHorizontalHeaderLabels(
            ["Data/Hora", "Usuário", "Entidade", "ID da Entidade", "Ação", "Valores (Antigo -> Novo)"]
        )
        configure_table(self.audit_table, stretch_last=False)
        self.audit_table.setMinimumHeight(520)

        card_layout.addLayout(top)
        card_layout.addWidget(self.audit_table)
        layout.addWidget(card)
        return tab

    def refresh(self):
        self.dirty_tabs.update({"macro", "micro", "item", "resolved", "vehicles", "audit"})
        self._load_visible_tab()

    def _schedule_audit_refresh(self):
        self.audit_live_filter_timer.start(240)

    def refresh_audit_logs(self):
        self.dirty_tabs.add("audit")
        self._load_audit_logs_tab()

    def set_loading_state(self, loading: bool):
        overlay = self._overlay_for_tab(self.current_tab_key())
        if not overlay:
            return
        if loading:
            overlay.show_skeleton(self._loading_message_for_tab(self.current_tab_key()))
        else:
            overlay.hide_skeleton()

    def refresh_item_table(self):
        self.dirty_tabs.add("item")
        self._load_item_tab()

    def refresh_resolved_table(self):
        self.dirty_tabs.add("resolved")
        self._load_resolved_tab()
    
    def refresh_audit_logs_tab(self):
        self.dirty_tabs.add("audit")
        self._load_audit_logs_tab()

    def _on_tab_changed(self, _index: int):
        self._load_visible_tab()

    def _load_visible_tab(self):
        self._load_tab(self.current_tab_key())

    def _load_tab(self, tab_key: str):
        if tab_key == "macro":
            if "macro" in self.dirty_tabs:
                self.macro_skeleton.show_skeleton(self._loading_message_for_tab("macro"))
                self.macro_rows = self.api_client.get_macro_report()
                self._populate_macro(self.macro_rows)
                self.dirty_tabs.discard("macro")
                self.macro_skeleton.hide_skeleton()
            return
        if tab_key == "micro":
            if "micro" in self.dirty_tabs:
                self.micro_skeleton.show_skeleton(self._loading_message_for_tab("micro"))
                self._prime_vehicle_cache(force=True)
                fetched_rows = self.api_client.get_micro_report(ativos=True)
                self.micro_rows = self._filter_active_micro_rows(fetched_rows)
                self._populate_micro(self.micro_rows)
                self.dirty_tabs.discard("micro")
                self.micro_skeleton.hide_skeleton()
            return
        if tab_key == "item":
            if "item" in self.dirty_tabs:
                self.item_skeleton.show_skeleton(self._loading_message_for_tab("item"))
                self._load_item_tab()
                self.dirty_tabs.discard("item")
                self.item_skeleton.hide_skeleton()
            return
        if tab_key == "resolved":
            if "resolved" in self.dirty_tabs:
                self.resolved_skeleton.show_skeleton(self._loading_message_for_tab("resolved"))
                self._load_resolved_tab()
                self.dirty_tabs.discard("resolved")
                self.resolved_skeleton.hide_skeleton()
            return
        if tab_key == "audit" and self.api_client.user_has_admin_access():
            if "audit" in self.dirty_tabs:
                self.audit_skeleton.show_skeleton(self._loading_message_for_tab("audit"))
                self._load_audit_logs_tab()
                self.audit_skeleton.hide_skeleton()
            return

    def _load_item_tab(self):
        date_from = None
        date_to = None
        mode = self.period_mode_filter.currentData() or "all"
        if mode != "all":
            date_from = self.start_date_filter.date().toString("yyyy-MM-dd")
            date_to = self.end_date_filter.date().toString("yyyy-MM-dd")

        self.item_rows = self.api_client.get_item_report(
            self.item_filter.text().strip() or None,
            date_from=date_from,
            date_to=date_to,
            nc_status=self.nc_status_filter.currentData() or None,
            modulo=self.modulo_filter.currentData() or None,
        )
        self.item_table.setSortingEnabled(False)
        self.item_table.setUpdatesEnabled(False)
        self.item_table.blockSignals(True)
        try:
            self.item_table.setRowCount(len(self.item_rows))
            for row, item in enumerate(self.item_rows):
                severity = severity_from_counts(1, 0 if item["resolvido"] else 1)
                values = [
                    item["veiculo"]["frota"],
                    item["item_nome"],
                    item["created_at"].replace("T", " ")[:19],
                    item["usuario"]["nome"],
                    "Resolvida" if item["resolvido"] else "Aberta",
                    severity["label"],
                    "Sim" if self._origin_photo_path(item) else "Não",
                    "Sim" if self._resolution_photo_path(item) else "Não",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 0:
                        cell.setData(Qt.UserRole, item)
                    if column == 5:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.item_table.setItem(row, column, cell)
        finally:
            self.item_table.blockSignals(False)
            self.item_table.setUpdatesEnabled(True)
            self.item_table.setSortingEnabled(True)
        self.item_skeleton.hide_skeleton()

    def _load_resolved_tab(self):
        date_from = None
        date_to = None
        mode = self.period_mode_filter.currentData() or "all"
        if mode != "all":
            date_from = self.start_date_filter.date().toString("yyyy-MM-dd")
            date_to = self.end_date_filter.date().toString("yyyy-MM-dd")

        self.resolved_rows = self.api_client.get_item_report(
            self.item_filter.text().strip() or None,
            date_from=date_from,
            date_to=date_to,
            nc_status="resolvidas",
            modulo=self.modulo_filter.currentData() or None,
            data_base="resolucao",
        )
        self.resolved_table.setSortingEnabled(False)
        self.resolved_table.setUpdatesEnabled(False)
        self.resolved_table.blockSignals(True)
        try:
            self.resolved_table.setRowCount(len(self.resolved_rows))
            for row, item in enumerate(self.resolved_rows):
                vehicle = item.get("veiculo") or {}
                user = item.get("usuario") or {}
                resolved_by = item.get("resolved_by") or {}
                values = [
                    item.get("item_nome") or "-",
                    vehicle.get("frota") or "-",
                    self._format(item.get("data_resolucao")),
                    user.get("nome") or "-",
                    resolved_by.get("nome") or "-",
                    str(vehicle.get("tipo") or "-").title(),
                    "Sim" if self._origin_photo_path(item) else "Não",
                    "Sim" if self._resolution_photo_path(item) else "Não",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 0:
                        cell.setData(Qt.UserRole, item)
                    self.resolved_table.setItem(row, column, cell)
        finally:
            self.resolved_table.blockSignals(False)
            self.resolved_table.setUpdatesEnabled(True)
            self.resolved_table.setSortingEnabled(True)
        self.resolved_skeleton.hide_skeleton()

    def _load_audit_logs_tab(self):
        try:
            date_from = self.audit_start_date_filter.date().toString("yyyy-MM-dd")
            date_to = self.audit_end_date_filter.date().toString("yyyy-MM-dd")
            entidade = self.audit_entity_filter.currentData()

            logs = self.api_client.get_audit_logs(
                entidade=entidade or None,
                data_inicio=date_from,
                data_fim=date_to
            )

            self.audit_table.setSortingEnabled(False)
            self.audit_table.setUpdatesEnabled(False)
            self.audit_table.setRowCount(len(logs))

            for row, log in enumerate(logs):
                values = [
                    self._format(log.get("created_at")),
                    log.get("user") or "Sistema",
                    log.get("entity_type") or "-",
                    str(log.get("entity_id") or "-"),
                    log.get("action") or "-",
                    f"{log.get('old_value')} -> {log.get('new_value')}"
                ]
                for col, val in enumerate(values):
                    self.audit_table.setItem(row, col, make_table_item(val))

            self.dirty_tabs.discard("audit")
        except Exception as exc:
            show_notice(self, "Falha ao carregar logs", str(exc), icon_name="warning")
        finally:
            self.audit_table.setUpdatesEnabled(True)
            self.audit_table.setSortingEnabled(True)
            self.audit_skeleton.hide_skeleton()

    def _populate_macro(self, rows):
        self.macro_table.setSortingEnabled(False)
        self.macro_table.setUpdatesEnabled(False)
        self.macro_table.blockSignals(True)
        try:
            self.macro_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                severity = severity_from_counts(item["total_nc"], item["abertas"])
                values = [
                    item["item_nome"],
                    str(item["total_nc"]),
                    str(item["abertas"]),
                    str(item["resolvidas"]),
                    severity["label"],
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 0:
                        cell.setData(Qt.UserRole, item)
                    if column == 4:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.macro_table.setItem(row, column, cell)
        finally:
            self.macro_table.blockSignals(False)
            self.macro_table.setUpdatesEnabled(True)
            self.macro_table.setSortingEnabled(True)
        if rows:
            self.macro_table.selectRow(0)
        self._update_macro_action_state()

    def _selected_macro_row(self) -> dict | None:
        selected = self.macro_table.selectedRanges()
        if not selected:
            return None
        return self._payload_for_row(self.macro_table, selected[0].topRow(), self.macro_rows)

    def _update_macro_action_state(self):
        button = getattr(self, "create_mass_activity_button", None)
        if button is None:
            return
        row = self._selected_macro_row()
        has_open = bool(row and int(row.get("abertas") or 0) > 0)
        button.setEnabled(has_open)

    def _current_item_filter_scope(self) -> dict:
        mode = self.period_mode_filter.currentData() or "all"
        date_from = None
        date_to = None
        if mode != "all":
            date_from = self.start_date_filter.date().toString("yyyy-MM-dd")
            date_to = self.end_date_filter.date().toString("yyyy-MM-dd")
        return {
            "modulo": self.modulo_filter.currentData() or "all",
            "modulo_label": self.modulo_filter.currentText(),
            "status_nc": self.nc_status_filter.currentData() or "abertas",
            "status_label": self.nc_status_filter.currentText(),
            "date_from": date_from,
            "date_to": date_to,
            "period_label": self._item_period_label(),
        }

    def create_macro_mass_activity(self):
        row = self._selected_macro_row()
        if not row:
            show_notice(self, "Seleção obrigatória", "Selecione uma linha da tabela por não conformidade.", icon_name="warning")
            return
        if int(row.get("abertas") or 0) <= 0:
            show_notice(self, "Sem NC abertas", "A linha selecionada não possui ocorrências abertas para tratar.", icon_name="warning")
            return

        scope = self._current_item_filter_scope()
        context = {
            "item_nome": row.get("item_nome"),
            "abertas": int(row.get("abertas") or 0),
            **scope,
        }
        dialog = MacroMassActivityDialog(self.api_client, context, self)
        if not dialog.exec():
            return

        created = dialog.created_activity or {}
        activity_id = created.get("id")
        equipments = created.get("equipamentos_iniciais") or (created.get("resumo") or {}).get("total") or 0
        linked = created.get("nao_conformidades_iniciais") or (created.get("vinculos_nc") or {}).get("total") or 0
        message = (
            f"Atividade #{activity_id} criada com {equipments} equipamento(s) "
            f"e {linked} NC vinculada(s). Novas NC do mesmo item entrarão automaticamente enquanto estiver aberta."
            if activity_id
            else (
                f"Atividade criada com {equipments} equipamento(s) e {linked} NC vinculada(s). "
                "Novas NC do mesmo item entrarão automaticamente enquanto estiver aberta."
            )
        )
        show_notice(self, "Atividade em massa aberta", message, icon_name="activities")

        parent_window = self.window()
        if parent_window and hasattr(parent_window, "switch_page"):
            try:
                parent_window.switch_page("activities")
            except Exception:
                pass

    def _populate_micro(self, rows):
        self.micro_table.setSortingEnabled(False)
        self.micro_table.setUpdatesEnabled(False)
        self.micro_table.blockSignals(True)
        try:
            self.micro_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                severity = severity_from_counts(item["total_nc"], 0)
                values = [
                    item["frota"],
                    item["placa"],
                    item["modelo"],
                    item["tipo"].title(),
                    str(item["total_nc"]),
                    severity["label"],
                    self._format(item.get("ultimo_checklist")),
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 0:
                        cell.setData(Qt.UserRole, item)
                    if column == 5:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.micro_table.setItem(row, column, cell)
        finally:
            self.micro_table.blockSignals(False)
            self.micro_table.setUpdatesEnabled(True)
            self.micro_table.setSortingEnabled(True)

    def _prime_vehicle_cache(self, *, force: bool = False):
        if not force and "vehicles" not in self.dirty_tabs and self.vehicle_cache:
            return
        try:
            vehicles = self.api_client.get_equipment(ativos=True)
            self.vehicle_cache = {vehicle["id"]: vehicle for vehicle in vehicles}
            self.dirty_tabs.discard("vehicles")
        except Exception:
            self.vehicle_cache = {}

    def _filter_active_micro_rows(self, rows: list[dict]) -> list[dict]:
        if not self.vehicle_cache:
            return rows
        active_ids = set(self.vehicle_cache.keys())
        return [row for row in rows if row.get("vehicle_id") in active_ids]

    def open_macro_item(self, *_args):
        selected = self.macro_table.selectedRanges()
        if not selected:
            return
        row_item = self._payload_for_row(self.macro_table, selected[0].topRow(), self.macro_rows)
        if not row_item:
            return
        item_name = row_item["item_nome"]
        self.tabs.setCurrentIndex(1)
        self.item_filter.setText(item_name)
        self.refresh_item_table()

    def open_micro_vehicle(self, *_args):
        selected = self.micro_table.selectedRanges()
        if not selected:
            return
        row = self._payload_for_row(self.micro_table, selected[0].topRow(), self.micro_rows)
        if not row:
            return
        vehicle = self.vehicle_cache.get(row.get("vehicle_id"))
        if not vehicle:
            show_notice(
                self,
                "Ficha indisponível",
                "Não foi possível localizar os dados completos do equipamento.",
                icon_name="warning",
            )
            return
        dialog = VehicleDetailDialog(self.api_client, vehicle, self)
        dialog.exec()

    def open_item_occurrence(self, item=None):
        if item is not None:
            row_index = item.row()
        else:
            selected = self.item_table.selectedRanges()
            if not selected:
                return
            row_index = selected[0].topRow()

        if row_index < 0 or row_index >= len(self.item_rows):
            return
        row_item = self._payload_for_row(self.item_table, row_index, self.item_rows)
        if not row_item:
            return
        dialog = NonConformityDetailDialog(self.api_client, row_item, self)
        dialog.exec()

    def open_resolved_occurrence(self, item=None):
        if item is not None:
            row_index = item.row()
        else:
            selected = self.resolved_table.selectedRanges()
            if not selected:
                return
            row_index = selected[0].topRow()

        if row_index < 0 or row_index >= len(self.resolved_rows):
            return
        row_item = self._payload_for_row(self.resolved_table, row_index, self.resolved_rows)
        if not row_item:
            return
        dialog = NonConformityDetailDialog(self.api_client, row_item, self)
        dialog.exec()

    def generate_macro_message(self):
        if not self.macro_rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_macro_message_package(
            self.macro_rows,
            self._build_period_label("relatorio_macro", self.macro_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def generate_micro_message(self):
        if not self.micro_rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_micro_message_package(
            self.micro_rows,
            self._build_period_label("relatorio_micro", self.micro_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def _item_scope_label(self) -> str:
        item_name = self.item_filter.text().strip()
        if item_name:
            return f"Não conformidade: {item_name}"
        status = self.nc_status_filter.currentData()
        if status == "abertas":
            return "Não conformidades abertas"
        if status == "resolvidas":
            return "Não conformidades resolvidas"
        return "Todas as não conformidades"

    def _item_period_label(self) -> str:
        mode = self.period_mode_filter.currentData() or "all"
        if mode == "all":
            return "Todo período"
        start = self.start_date_filter.date().toString("dd/MM/yyyy")
        end = self.end_date_filter.date().toString("dd/MM/yyyy")
        if start == end:
            return start
        return f"{start} a {end}"

    def _item_filter_context(self) -> dict[str, str]:
        return {
            "Módulo": self.modulo_filter.currentText(),
            "Status NC": self.nc_status_filter.currentText(),
            "Período": self._item_period_label(),
        }

    def _resolved_filter_context(self) -> dict[str, str]:
        return {
            "Módulo": self.modulo_filter.currentText(),
            "Status NC": "NC resolvidas",
            "Período (resolução)": self._item_period_label(),
        }

    def generate_item_message(self):
        if not self.item_rows:
            show_notice(self, "Sem dados", "Não há ocorrências disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_item_message_package(
            self.item_rows,
            self._item_scope_label(),
            self._build_period_label("relatorio_item", self.item_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def export_selected_vehicle_audit_pdf(self):
        selected = self.micro_table.selectedRanges()
        if not selected:
            show_notice(self, "Seleção obrigatória", "Selecione um equipamento no relatório micro.", icon_name="warning")
            return
        row = self._payload_for_row(self.micro_table, selected[0].topRow(), self.micro_rows)
        if not row:
            return
        vehicle = self.vehicle_cache.get(row.get("vehicle_id"))
        if not vehicle:
            try:
                self._prime_vehicle_cache()
                vehicle = self.vehicle_cache.get(row.get("vehicle_id"))
            except Exception:
                vehicle = None
        if not vehicle:
            show_notice(self, "Ficha indisponível", "Não foi possível localizar os dados completos do equipamento.", icon_name="warning")
            return

        default_path = make_default_export_path(f"auditoria_{vehicle.get('frota', 'frota').lower()}", "pdf")
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar auditoria do equipamento", default_path, "PDF (*.pdf)")
        if not filename:
            return

        def task(progress):
            progress(5, "Preparando auditoria do equipamento")
            history = self.api_client.get_vehicle_history(vehicle["id"])
            occurrences = history.get("nao_conformidades") or []
            progress(18, f"Histórico carregado: {len(occurrences)} ocorrência(s)")
            vehicle_image = self.api_client.fetch_image(vehicle.get("foto_path"))
            progress(26, "Foto do equipamento carregada")
            occurrence_images = self._collect_occurrence_images_with_progress(occurrences, progress, start=26, end=78)
            progress(86, "Montando páginas do PDF")
            export_vehicle_detail_pdf(
                vehicle,
                occurrences,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=self.api_client.user.get("nome", ""),
                vehicle_image=vehicle_image,
                operational_history=self._build_operational_history(history, occurrences),
                occurrence_images=occurrence_images,
            )
            return filename

        self._run_pdf_export("Exportando auditoria do equipamento", task)

    def export_item_audit_pdf(self):
        if not self.item_rows:
            show_notice(self, "Sem dados", "Aplique os filtros e carregue ocorrências antes de gerar o PDF de auditoria.", icon_name="warning")
            return
        scope_label = self._item_scope_label()
        safe_name = "".join(char if char.isalnum() else "_" for char in scope_label.lower()).strip("_") or "nao_conformidades"
        default_path = make_default_export_path(f"auditoria_item_{safe_name}", "pdf")
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar auditoria por item", default_path, "PDF (*.pdf)")
        if not filename:
            return
        rows = list(self.item_rows)
        filter_context = self._item_filter_context()

        def task(progress):
            progress(5, "Preparando auditoria por item")
            occurrence_images = self._collect_occurrence_images_with_progress(rows, progress, start=12, end=78)
            progress(86, "Montando páginas do PDF")
            export_item_audit_pdf(
                scope_label,
                rows,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=self.api_client.user.get("nome", ""),
                occurrence_images=occurrence_images,
                filter_context=filter_context,
                resolved_mode=False,
                include_resolution_details=False,
                include_part_details=False,
            )
            return filename

        self._run_pdf_export("Exportando auditoria por item", task)

    def export_resolved_audit_pdf(self):
        if not self.resolved_rows:
            show_notice(self, "Sem dados", "Aplique os filtros e carregue não conformidades resolvidas antes de exportar.", icon_name="warning")
            return
        scope_label = self.item_filter.text().strip() or "Não conformidades resolvidas"
        safe_name = "".join(char if char.isalnum() else "_" for char in scope_label.lower()).strip("_") or "nao_conformidades_resolvidas"
        default_path = make_default_export_path(f"resolvidos_{safe_name}", "pdf")
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar PDF de resolvidos", default_path, "PDF (*.pdf)")
        if not filename:
            return
        rows = list(self.resolved_rows)
        filter_context = self._resolved_filter_context()

        def task(progress):
            progress(5, "Preparando PDF de resolvidos")
            occurrence_images = self._collect_occurrence_images_with_progress(rows, progress, start=12, end=78)
            progress(86, "Montando páginas do PDF")
            export_item_audit_pdf(
                "Não conformidades resolvidas",
                rows,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=self.api_client.user.get("nome", ""),
                occurrence_images=occurrence_images,
                filter_context=filter_context,
                resolved_mode=True,
                include_resolution_details=True,
                include_part_details=False,
            )
            return filename

        self._run_pdf_export("Exportando PDF de resolvidos", task)

    def export_macro(self, file_type: str):
        columns = [
            ("Item", "item_nome"),
            ("Total de não conformidades", "total_nc"),
            ("Abertas", "abertas"),
            ("Resolvidas", "resolvidas"),
        ]
        self._export_dataset(
            "relatorio_macro",
            "Relatório por Não Conformidade",
            "Consolidado executivo por item de não conformidade",
            columns,
            self.macro_rows,
            file_type,
        )

    def export_micro(self, file_type: str):
        rows = []
        for row in self.micro_rows:
            rows.append(
                {
                    "frota": row["frota"],
                    "placa": row["placa"],
                    "modelo": row["modelo"],
                    "tipo": row["tipo"].title(),
                    "total_nc": row["total_nc"],
                    "ultimo_checklist": self._format(row.get("ultimo_checklist")),
                }
            )
        columns = [
            ("Frota", "frota"),
            ("Placa", "placa"),
            ("Modelo", "modelo"),
            ("Tipo", "tipo"),
            ("Não conformidades", "total_nc"),
            ("Último checklist", "ultimo_checklist"),
        ]
        self._export_dataset(
            "relatorio_micro",
            "Relatório Micro por Equipamento",
            "Visão operacional por unidade da frota",
            columns,
            rows,
            file_type,
        )

    def export_resolved(self, file_type: str):
        rows = []
        for item in self.resolved_rows:
            vehicle = item.get("veiculo") or {}
            user = item.get("usuario") or {}
            resolved_by = item.get("resolved_by") or {}
            rows.append(
                {
                    "item_nome": item.get("item_nome") or "-",
                    "frota": vehicle.get("frota") or "-",
                    "data_resolucao": self._format(item.get("data_resolucao")),
                    "motorista": user.get("nome") or "-",
                    "resolved_by": resolved_by.get("nome") or "-",
                    "modulo": str(vehicle.get("tipo") or "-").title(),
                    "foto_origem": "Sim" if self._origin_photo_path(item) else "Não",
                    "foto_resolucao": "Sim" if self._resolution_photo_path(item) else "Não",
                }
            )

        columns = [
            ("Não conformidade", "item_nome"),
            ("Veículo", "frota"),
            ("Resolvido em", "data_resolucao"),
            ("Motorista", "motorista"),
            ("Resolvido por", "resolved_by"),
            ("Módulo", "modulo"),
            ("Foto origem", "foto_origem"),
            ("Foto resolução", "foto_resolucao"),
        ]
        self._export_dataset(
            "relatorio_resolvidos",
            "Relatório de Não Conformidades Resolvidas",
            "Visão operacional de resolvidos por ocorrência",
            columns,
            rows,
            file_type,
        )

    def _export_dataset(self, prefix: str, title: str, subtitle: str, columns, rows, file_type: str):
        if not rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para exportação.", icon_name="warning")
            return

        default_path = make_default_export_path(prefix, file_type)
        filters = {
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
            "pdf": "PDF (*.pdf)",
        }
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório",
            default_path,
            filters[file_type],
        )
        if not filename:
            return

        try:
            if file_type == "csv":
                export_rows_to_csv(columns, rows, filename)
            elif file_type == "xlsx":
                export_rows_to_xlsx(title, columns, rows, filename)
            else:
                period_label = self._build_period_label(prefix, rows)

                def task(progress):
                    progress(12, "Organizando dados do relatório")
                    progress(42, "Montando capa, gráficos e tabela")
                    export_rows_to_pdf(
                        title,
                        subtitle,
                        columns,
                        rows,
                        filename,
                        logo_path=self.logo_path,
                        generated_by=self.api_client.user.get("nome", ""),
                        period_label=period_label,
                    )
                    return filename

                self._run_pdf_export("Exportando PDF executivo", task)
                return
            show_notice(self, "Exportação concluída", f"Arquivo salvo em:\n{filename}", icon_name="reports")
        except Exception as exc:
            show_notice(self, "Falha na exportação", str(exc), icon_name="warning")

    def _build_period_label(self, prefix: str, rows: list[dict]) -> str:
        today = datetime.now().strftime("%d/%m/%Y")
        if prefix == "relatorio_micro":
            dates = [row.get("ultimo_checklist") for row in rows if row.get("ultimo_checklist") and row.get("ultimo_checklist") != "-"]
            if dates:
                normalized = sorted(date.replace("T", " ")[:10] for date in dates)
                start = self._format_date_only(normalized[0])
                end = self._format_date_only(normalized[-1])
                return f"{start} a {end}"
        if prefix == "relatorio_item":
            dates = [row.get("created_at") for row in rows if row.get("created_at")]
            if dates:
                normalized = sorted(date.replace("T", " ")[:10] for date in dates)
                start = self._format_date_only(normalized[0])
                end = self._format_date_only(normalized[-1])
                return f"{start} a {end}"
        return f"Base consolidada até {today}"

    def _collect_occurrence_images(self, occurrences: list[dict]) -> dict[int, dict[str, bytes | None]]:
        images: dict[int, dict[str, bytes | None]] = {}
        for item in occurrences:
            item_id = item.get("id")
            if not item_id:
                continue
            images[item_id] = {
                "before": self.api_client.fetch_image(self._origin_photo_path(item)),
                "after": self.api_client.fetch_image(self._resolution_photo_path(item)),
            }
        return images

    def _collect_occurrence_images_with_progress(
        self,
        occurrences: list[dict],
        progress,
        *,
        start: int,
        end: int,
    ) -> dict[int, dict[str, bytes | None]]:
        images: dict[int, dict[str, bytes | None]] = {}
        total = max(1, len(occurrences))
        if not occurrences:
            progress(end, "Nenhuma foto de evidência para carregar")
            return images

        for index, item in enumerate(occurrences, start=1):
            item_id = item.get("id")
            percent = start + int(((index - 1) / total) * (end - start))
            label = item.get("item_nome") or f"ocorrência {item_id or index}"
            progress(percent, f"Carregando evidências {index}/{len(occurrences)}: {label}")
            if not item_id:
                continue
            images[item_id] = {
                "before": self.api_client.fetch_image(self._origin_photo_path(item)),
                "after": self.api_client.fetch_image(self._resolution_photo_path(item)),
            }
        progress(end, "Evidências fotográficas carregadas")
        return images

    @staticmethod
    def _origin_photo_path(item: dict | None) -> str | None:
        payload = item or {}
        return payload.get("foto_origem") or payload.get("foto_antes")

    @staticmethod
    def _resolution_photo_path(item: dict | None) -> str | None:
        payload = item or {}
        return payload.get("foto_resolucao") or payload.get("foto_depois")

    def _run_pdf_export(self, title: str, task):
        dialog = ExportProgressDialog(title, self)
        thread = QThread(self)
        worker = ExportWorker(task)
        worker.moveToThread(thread)

        job = {"thread": thread, "worker": worker, "dialog": dialog}
        self._export_jobs.append(job)

        def cleanup():
            if job in self._export_jobs:
                self._export_jobs.remove(job)

        thread.started.connect(worker.run)
        worker.progress.connect(dialog.set_progress)
        worker.finished.connect(lambda path, current_job=job: self.pdf_export_finished.emit(current_job, path))
        worker.failed.connect(lambda message, current_job=job: self.pdf_export_failed.emit(current_job, message))
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(cleanup)
        thread.finished.connect(thread.deleteLater)

        dialog.show()
        thread.start()

    def _handle_pdf_export_finished(self, job: dict, path):
        dialog = job.get("dialog")
        thread = job.get("thread")
        if dialog:
            dialog.mark_finished()
        if thread and thread.isRunning():
            thread.quit()
        show_notice(self, "PDF gerado", f"Arquivo salvo em:\n{path}", icon_name="reports")
        open_exported_pdf(path)
        if dialog:
            dialog.accept()

    def _handle_pdf_export_failed(self, job: dict, message: str):
        dialog = job.get("dialog")
        thread = job.get("thread")
        if dialog:
            dialog.mark_failed(message)
        if thread and thread.isRunning():
            thread.quit()
        show_notice(self, "Falha ao exportar PDF", message, icon_name="warning")
        if dialog:
            dialog.accept()

    @staticmethod
    def _payload_for_row(table: QTableWidget, row: int, fallback_rows: list[dict]):
        if row < 0:
            return None
        first_cell = table.item(row, 0)
        if first_cell:
            payload = first_cell.data(Qt.UserRole)
            if payload:
                return payload
        if row < len(fallback_rows):
            return fallback_rows[row]
        return None

    def _build_operational_history(self, history: dict, occurrences: list[dict]) -> list[dict]:
        rows = []
        for item in occurrences:
            rows.append(
                {
                    "date": item.get("created_at"),
                    "origin": "Não conformidade",
                    "item": item.get("item_nome") or "-",
                    "status": "Resolvida" if item.get("resolvido") else "Aberta",
                    "owner": item.get("usuario", {}).get("nome") or "-",
                }
            )
        for item in history.get("manutencoes", []):
            schedule = item.get("schedule") or {}
            rows.append(
                {
                    "date": item.get("executed_at") or item.get("scheduled_date") or item.get("created_at"),
                    "origin": "Manutenção",
                    "item": schedule.get("title") or "-",
                    "status": str(item.get("status") or "-").replace("_", " "),
                    "owner": (item.get("executed_by") or item.get("assigned_mechanic") or {}).get("nome") or "-",
                }
            )
        for item in history.get("lavagens", []):
            rows.append(
                {
                    "date": item.get("wash_date"),
                    "origin": "Lavagem",
                    "item": item.get("tipo_equipamento") or "Lavagem",
                    "status": item.get("status") or "-",
                    "owner": (item.get("created_by") or {}).get("nome") or "-",
                }
            )
        for item in history.get("atividades", []):
            activity = item.get("atividade") or {}
            rows.append(
                {
                    "date": item.get("instalado_em") or item.get("updated_at"),
                    "origin": "Atividade",
                    "item": activity.get("item_nome") or activity.get("titulo") or f"Atividade #{item.get('activity_id') or '-'}",
                    "status": str(item.get("status_execucao") or "-").replace("_", " "),
                    "owner": item.get("executado_por_nome") or "-",
                }
            )
        return sorted(rows, key=lambda item: item.get("date") or "", reverse=True)

    def current_tab_key(self) -> str:
        return {0: "macro", 1: "micro", 2: "item", 3: "resolved", 4: "audit"}.get(
            self.tabs.currentIndex(), "macro"
        )

    def _overlay_for_tab(self, tab_key: str):
        return {
            "macro": self.macro_skeleton,
            "micro": self.micro_skeleton,
            "item": self.item_skeleton,
            "resolved": self.resolved_skeleton,
            "audit": self.audit_skeleton,
        }.get(tab_key)

    @staticmethod
    def _loading_message_for_tab(tab_key: str) -> str:
        return {
            "macro": "Montando relatório macro",
            "micro": "Montando relatório micro",
            "item": "Montando consulta por item",
            "resolved": "Montando área de resolvidos",
            "audit": "Carregando logs de auditoria",
        }.get(tab_key, "Montando relatório executivo")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    @staticmethod
    def _format_date_only(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value
