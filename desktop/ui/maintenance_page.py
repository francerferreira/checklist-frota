from __future__ import annotations

from collections import defaultdict
from math import ceil

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

from components import StatCard, TableSkeletonOverlay, show_notice
from theme import (
    build_dialog_layout,
    configure_dialog_window,
    configure_table,
    make_table_item,
    style_card,
    style_filter_bar,
    style_table_card,
)


SOURCE_LABELS = {
    "CHECKLIST_NC": "Nao conformidade",
    "ATIVIDADE": "Atividade",
    "PREVENTIVA": "Preventiva",
}

SCHEDULE_STATUS_LABELS = {
    "ABERTA": "Aberta",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "PROGRAMADA": "Programada",
    "EM_EXECUCAO": "Em execucao",
    "CONCLUIDA": "Concluida",
    "CANCELADA": "Cancelada",
}

ITEM_STATUS_LABELS = {
    "PENDENTE": "Pendente",
    "PROGRAMADO": "Programado",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "INSTALADO": "Instalado",
    "NAO_EXECUTADO": "Nao executado",
    "REPROGRAMADO": "Reprogramado",
    "CANCELADO": "Cancelado",
}


class MaintenanceScheduleCreateDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.activities: list[dict] = []
        self.vehicles: list[dict] = []
        self.result_payload: dict | None = None

        self.setWindowTitle("Nova programacao de manutencao")
        configure_dialog_window(self, width=1060, height=760, min_width=900, min_height=640)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=1120)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel("Criar programacao de manutencao")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            "Fase 2: abrir cronograma por atividades abertas ou preventiva por veiculos, com distribuicao diaria."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Atividades abertas", "ATIVIDADE")
        self.source_combo.addItem("Preventiva por veiculos", "PREVENTIVA")
        self.source_combo.currentIndexChanged.connect(self._render_source_rows)

        self.title_input = QLineEdit("Programacao de manutencao")
        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDate(QDate.currentDate())
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")

        self.daily_capacity_input = QSpinBox()
        self.daily_capacity_input.setMinimum(1)
        self.daily_capacity_input.setMaximum(999)
        self.daily_capacity_input.setValue(1)
        self.daily_capacity_input.valueChanged.connect(self._update_selection_summary)

        self.observation_input = QTextEdit()
        self.observation_input.setPlaceholderText("Contexto da programacao, prioridade e observacoes.")

        self.selection_badge = QLabel("0 selecionados | estimativa 0 dia(s)")
        self.selection_badge.setObjectName("TopBarPill")

        form.addWidget(QLabel("Origem"), 0, 0)
        form.addWidget(self.source_combo, 1, 0)
        form.addWidget(QLabel("Titulo"), 0, 1)
        form.addWidget(self.title_input, 1, 1)
        form.addWidget(QLabel("Data inicial"), 0, 2)
        form.addWidget(self.start_date_input, 1, 2)
        form.addWidget(QLabel("Capacidade diaria"), 0, 3)
        form.addWidget(self.daily_capacity_input, 1, 3)
        form.addWidget(QLabel("Observacao"), 2, 0, 1, 4)
        form.addWidget(self.observation_input, 3, 0, 1, 4)
        form.addWidget(self.selection_badge, 4, 0, 1, 4)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        actions = QHBoxLayout()
        self.source_title = QLabel("Base de selecao")
        self.source_title.setObjectName("SectionTitle")
        select_all_button = QPushButton("Selecionar todos")
        select_all_button.clicked.connect(self._select_all_rows)
        clear_button = QPushButton("Limpar selecao")
        clear_button.clicked.connect(self._clear_selection)
        actions.addWidget(self.source_title)
        actions.addStretch()
        actions.addWidget(select_all_button)
        actions.addWidget(clear_button)

        self.source_table = QTableWidget(0, 5)
        configure_table(self.source_table, stretch_last=True)
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_table.itemSelectionChanged.connect(self._update_selection_summary)
        self.source_table.setMinimumHeight(300)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()
        close_button = QPushButton("Cancelar")
        close_button.clicked.connect(self.reject)
        create_button = QPushButton("Criar programacao")
        create_button.setProperty("variant", "primary")
        create_button.clicked.connect(self._submit)
        footer_layout.addWidget(close_button)
        footer_layout.addWidget(create_button)

        table_layout.addLayout(actions)
        table_layout.addWidget(self.source_table)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(table_card, 1)
        layout.addWidget(footer)

        self._load_sources()
        self._render_source_rows()

    def _load_sources(self):
        self.activities = self.api_client.get_activities(status="ABERTA") or []
        self.vehicles = self.api_client.get_equipment(ativos=True) or []

    def _render_source_rows(self):
        source_type = self.source_combo.currentData()
        if source_type == "ATIVIDADE":
            self.source_title.setText("Atividades abertas para programacao")
            self.source_table.setColumnCount(5)
            self.source_table.setHorizontalHeaderLabels(["ID", "Atividade", "Modulo", "Tipo", "Abertas"])
            rows = self.activities
            self.source_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                item_rows = list(row.get("itens") or [])
                pending = sum(
                    1
                    for item in item_rows
                    if str(item.get("status_execucao") or "PENDENTE").upper() != "INSTALADO"
                )
                values = [
                    row.get("id"),
                    row.get("item_nome") or row.get("titulo") or "-",
                    row.get("modulo") or "-",
                    row.get("tipo") or "-",
                    pending,
                ]
                for column, value in enumerate(values):
                    payload = row if column == 0 else None
                    self.source_table.setItem(row_index, column, make_table_item(value, payload=payload))
        else:
            self.source_title.setText("Veiculos para preventiva")
            self.source_table.setColumnCount(5)
            self.source_table.setHorizontalHeaderLabels(["ID", "Frota", "Placa", "Modelo", "Tipo"])
            rows = self.vehicles
            self.source_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [
                    row.get("id"),
                    row.get("frota") or "-",
                    row.get("placa") or "-",
                    row.get("modelo") or "-",
                    row.get("tipo") or "-",
                ]
                for column, value in enumerate(values):
                    payload = row if column == 0 else None
                    self.source_table.setItem(row_index, column, make_table_item(value, payload=payload))

        self._clear_selection()
        self._update_selection_summary()

    def _selected_payloads(self) -> list[dict]:
        model = self.source_table.selectionModel()
        if not model:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        selected: list[dict] = []
        for row in rows:
            cell = self.source_table.item(row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                selected.append(payload)
        return selected

    def _select_all_rows(self):
        self.source_table.selectAll()
        self._update_selection_summary()

    def _clear_selection(self):
        self.source_table.clearSelection()
        self._update_selection_summary()

    def _update_selection_summary(self):
        total = len(self._selected_payloads())
        capacity = max(1, int(self.daily_capacity_input.value()))
        days = ceil(total / capacity) if total else 0
        self.selection_badge.setText(f"{total} selecionados | estimativa {days} dia(s)")

    def _submit(self):
        source_type = self.source_combo.currentData()
        selected = self._selected_payloads()
        if not selected:
            show_notice(self, "Selecao obrigatoria", "Selecione pelo menos um registro para criar a programacao.", icon_name="warning")
            return

        title = (self.title_input.text() or "").strip() or "Programacao de manutencao"
        start_date = self.start_date_input.date().toString("yyyy-MM-dd")
        daily_capacity = int(self.daily_capacity_input.value())
        observation = (self.observation_input.toPlainText() or "").strip()

        payload: dict = {
            "source_type": source_type,
            "title": title,
            "start_date": start_date,
            "daily_capacity": daily_capacity,
            "observation": observation,
        }
        if source_type == "ATIVIDADE":
            payload["activity_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
            payload["item_name"] = "Atividades selecionadas"
        else:
            payload["vehicle_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
            payload["item_name"] = "Preventiva de frota"

        self.result_payload = payload
        self.accept()


class MaintenancePage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.overview: dict = {"resumo": {}, "cronograma": {"days": []}, "programacoes": []}
        self.filtered_schedules: list[dict] = []
        self.selected_schedule_id: int | None = None
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Programacao de manutencao")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Fase 2 no desktop: criar cronograma, mover itens, retirar veiculos e redistribuir capacidade."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        self.new_schedule_button = QPushButton("Nova programacao")
        self.new_schedule_button.setProperty("variant", "primary")
        self.new_schedule_button.setMinimumHeight(42)
        self.new_schedule_button.clicked.connect(self.create_schedule)

        self.sync_nc_button = QPushButton("Sincronizar NC")
        self.sync_nc_button.setMinimumHeight(42)
        self.sync_nc_button.clicked.connect(self.sync_non_conformities)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setMinimumHeight(42)
        refresh_button.clicked.connect(self.refresh)

        header.addLayout(text_wrap, 1)
        header.addWidget(self.new_schedule_button)
        header.addWidget(self.sync_nc_button)
        header.addWidget(refresh_button)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)
        self.schedules_card = StatCard("Programacoes", "0", "Cronogramas ativos e historicos", icon_name="activities")
        self.items_card = StatCard("Itens no mes", "0", "Planejados no periodo selecionado", icon_name="reports")
        self.pending_card = StatCard("Pendentes", "0", "Programados, reprogramados e aguardando", icon_name="warning")
        self.installed_card = StatCard("Instalados", "0", "Concluidos com baixa de estoque", icon_name="ok")
        cards_layout.addWidget(self.schedules_card, 0, 0)
        cards_layout.addWidget(self.items_card, 0, 1)
        cards_layout.addWidget(self.pending_card, 0, 2)
        cards_layout.addWidget(self.installed_card, 0, 3)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filter_layout = QGridLayout(filter_card)
        filter_layout.setContentsMargins(14, 14, 14, 14)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(10)

        self.month_input = QDateEdit()
        self.month_input.setCalendarPopup(True)
        self.month_input.setDisplayFormat("MM/yyyy")
        self.month_input.setDate(QDate.currentDate())

        self.source_filter = QComboBox()
        self.source_filter.addItem("Todas as origens", "ALL")
        self.source_filter.addItem("Nao conformidade", "CHECKLIST_NC")
        self.source_filter.addItem("Atividade", "ATIVIDADE")
        self.source_filter.addItem("Preventiva", "PREVENTIVA")

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "ALL")
        self.status_filter.addItem("Aberta", "ABERTA")
        self.status_filter.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.status_filter.addItem("Programada", "PROGRAMADA")
        self.status_filter.addItem("Em execucao", "EM_EXECUCAO")
        self.status_filter.addItem("Concluida", "CONCLUIDA")
        self.status_filter.addItem("Cancelada", "CANCELADA")

        apply_button = QPushButton("Aplicar")
        apply_button.setProperty("variant", "primary")
        apply_button.setMinimumHeight(40)
        apply_button.clicked.connect(self.apply_filters)

        clear_button = QPushButton("Limpar filtros")
        clear_button.setMinimumHeight(40)
        clear_button.clicked.connect(self.clear_filters)

        filter_layout.addWidget(QLabel("Mes"), 0, 0)
        filter_layout.addWidget(self.month_input, 1, 0)
        filter_layout.addWidget(QLabel("Origem"), 0, 1)
        filter_layout.addWidget(self.source_filter, 1, 1)
        filter_layout.addWidget(QLabel("Status"), 0, 2)
        filter_layout.addWidget(self.status_filter, 1, 2)
        filter_layout.addWidget(apply_button, 1, 3)
        filter_layout.addWidget(clear_button, 1, 4)
        filter_layout.setColumnStretch(5, 1)

        schedules_card = QFrame()
        style_table_card(schedules_card)
        self.schedules_skeleton = TableSkeletonOverlay(schedules_card, rows=7)
        schedules_layout = QVBoxLayout(schedules_card)
        schedules_layout.setContentsMargins(14, 14, 14, 14)
        schedules_layout.setSpacing(10)

        schedules_title_row = QHBoxLayout()
        schedules_title = QLabel("Programacoes de manutencao")
        schedules_title.setObjectName("SectionTitle")
        self.schedules_badge = QLabel("0 registros")
        self.schedules_badge.setObjectName("TopBarPill")
        schedules_title_row.addWidget(schedules_title)
        schedules_title_row.addStretch()
        schedules_title_row.addWidget(self.schedules_badge)

        self.schedules_table = QTableWidget(0, 10)
        self.schedules_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Titulo",
                "Origem",
                "Status",
                "Itens",
                "Pendentes",
                "Instalados",
                "Data inicio",
                "Data fim",
                "Cap./dia",
            ]
        )
        configure_table(self.schedules_table, stretch_last=False)
        self.schedules_table.setMinimumHeight(240)
        self.schedules_table.itemSelectionChanged.connect(self._on_schedule_selection_changed)

        schedules_layout.addLayout(schedules_title_row)
        schedules_layout.addWidget(self.schedules_table)

        action_card = QFrame()
        style_filter_bar(action_card)
        action_layout = QGridLayout(action_card)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setHorizontalSpacing(12)
        action_layout.setVerticalSpacing(10)

        self.selected_schedule_badge = QLabel("Nenhuma programacao selecionada")
        self.selected_schedule_badge.setObjectName("TopBarPill")

        self.item_status_filter = QComboBox()
        self.item_status_filter.addItem("Itens: todos", "ALL")
        self.item_status_filter.addItem("Pendente", "PENDENTE")
        self.item_status_filter.addItem("Programado", "PROGRAMADO")
        self.item_status_filter.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.item_status_filter.addItem("Instalado", "INSTALADO")
        self.item_status_filter.addItem("Nao executado", "NAO_EXECUTADO")
        self.item_status_filter.addItem("Reprogramado", "REPROGRAMADO")
        self.item_status_filter.addItem("Cancelado", "CANCELADO")
        self.item_status_filter.currentIndexChanged.connect(self.render_selected_schedule_items)

        self.move_date_input = QDateEdit()
        self.move_date_input.setCalendarPopup(True)
        self.move_date_input.setDisplayFormat("dd/MM/yyyy")
        self.move_date_input.setDate(QDate.currentDate())

        self.move_button = QPushButton("Mover selecionados")
        self.move_button.clicked.connect(self.move_selected_items)

        self.remove_button = QPushButton("Retirar selecionados")
        self.remove_button.setProperty("variant", "danger")
        self.remove_button.clicked.connect(self.remove_selected_items)

        self.redistribute_start_input = QDateEdit()
        self.redistribute_start_input.setCalendarPopup(True)
        self.redistribute_start_input.setDisplayFormat("dd/MM/yyyy")
        self.redistribute_start_input.setDate(QDate.currentDate())

        self.redistribute_capacity_input = QSpinBox()
        self.redistribute_capacity_input.setMinimum(1)
        self.redistribute_capacity_input.setMaximum(999)
        self.redistribute_capacity_input.setValue(1)

        self.redistribute_button = QPushButton("Redistribuir cronograma")
        self.redistribute_button.setProperty("variant", "primary")
        self.redistribute_button.clicked.connect(self.redistribute_selected_schedule)

        action_layout.addWidget(self.selected_schedule_badge, 0, 0, 1, 5)
        action_layout.addWidget(QLabel("Filtro de itens"), 1, 0)
        action_layout.addWidget(self.item_status_filter, 1, 1)
        action_layout.addWidget(QLabel("Nova data"), 1, 2)
        action_layout.addWidget(self.move_date_input, 1, 3)
        action_layout.addWidget(self.move_button, 1, 4)
        action_layout.addWidget(self.remove_button, 2, 0, 1, 2)
        action_layout.addWidget(QLabel("Inicio da redistribuicao"), 2, 2)
        action_layout.addWidget(self.redistribute_start_input, 2, 3)
        action_layout.addWidget(QLabel("Cap./dia"), 3, 2)
        action_layout.addWidget(self.redistribute_capacity_input, 3, 3)
        action_layout.addWidget(self.redistribute_button, 2, 4, 2, 1)
        action_layout.setColumnStretch(1, 1)
        action_layout.setColumnStretch(4, 1)

        details_card = QFrame()
        style_table_card(details_card)
        self.details_skeleton = TableSkeletonOverlay(details_card, rows=8)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(14, 14, 14, 14)
        details_layout.setSpacing(10)

        detail_top = QHBoxLayout()
        detail_title = QLabel("Tabela por programacao")
        detail_title.setObjectName("SectionTitle")
        self.items_badge = QLabel("0 itens")
        self.items_badge.setObjectName("TopBarPill")
        detail_top.addWidget(detail_title)
        detail_top.addStretch()
        detail_top.addWidget(self.items_badge)

        self.items_table = QTableWidget(0, 11)
        self.items_table.setHorizontalHeaderLabels(
            [
                "ID item",
                "Frota",
                "Placa",
                "Modelo",
                "Origem",
                "Status",
                "Data",
                "Executado em",
                "Material",
                "Atividade/NC",
                "Observacao",
            ]
        )
        configure_table(self.items_table, stretch_last=True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.items_table.itemSelectionChanged.connect(self._update_items_badge)
        self.items_table.setMinimumHeight(260)

        details_layout.addLayout(detail_top)
        details_layout.addWidget(self.items_table)

        calendar_card = QFrame()
        style_table_card(calendar_card)
        self.calendar_skeleton = TableSkeletonOverlay(calendar_card, rows=6)
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(14, 14, 14, 14)
        calendar_layout.setSpacing(10)

        calendar_title_row = QHBoxLayout()
        calendar_title = QLabel("Tabela diaria do cronograma")
        calendar_title.setObjectName("SectionTitle")
        self.calendar_badge = QLabel("0 dias")
        self.calendar_badge.setObjectName("TopBarPill")
        calendar_title_row.addWidget(calendar_title)
        calendar_title_row.addStretch()
        calendar_title_row.addWidget(self.calendar_badge)

        self.calendar_table = QTableWidget(0, 6)
        self.calendar_table.setHorizontalHeaderLabels(
            [
                "Data",
                "Programados",
                "Pendentes",
                "Instalados",
                "Nao executados",
                "Aguardando material",
            ]
        )
        configure_table(self.calendar_table, stretch_last=True)
        self.calendar_table.setMinimumHeight(220)

        calendar_layout.addLayout(calendar_title_row)
        calendar_layout.addWidget(self.calendar_table)

        layout.addLayout(header)
        layout.addLayout(cards_layout)
        layout.addWidget(filter_card)
        layout.addWidget(schedules_card)
        layout.addWidget(action_card)
        layout.addWidget(details_card)
        layout.addWidget(calendar_card, 1)

        self._set_action_controls_enabled(False)

    def set_loading_state(self, loading: bool):
        if loading:
            self.schedules_skeleton.show_skeleton("Carregando programacao de manutencao")
            self.details_skeleton.show_skeleton("Carregando itens da programacao")
            self.calendar_skeleton.show_skeleton("Carregando calendario da manutencao")
        else:
            self.schedules_skeleton.hide_skeleton()
            self.details_skeleton.hide_skeleton()
            self.calendar_skeleton.hide_skeleton()

    def refresh(self):
        month = self.month_input.date()
        year = month.year()
        month_number = month.month()
        self.overview = self.api_client.get_maintenance_overview(year=year, month=month_number) or {}
        self.apply_filters()

    def clear_filters(self):
        self.source_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.apply_filters()

    def apply_filters(self):
        schedules = list((self.overview or {}).get("programacoes") or [])
        source_filter = self.source_filter.currentData()
        status_filter = self.status_filter.currentData()

        if source_filter and source_filter != "ALL":
            schedules = [row for row in schedules if str(row.get("source_type") or "").upper() == source_filter]
        if status_filter and status_filter != "ALL":
            schedules = [row for row in schedules if str(row.get("status") or "").upper() == status_filter]

        self.filtered_schedules = schedules
        if self.selected_schedule_id and not any(int(row.get("id") or 0) == self.selected_schedule_id for row in schedules):
            self.selected_schedule_id = None
        if self.selected_schedule_id is None and schedules:
            self.selected_schedule_id = int(schedules[0].get("id"))

        self._render_summary()
        self._render_schedules_table()
        self.render_selected_schedule_items()
        self._render_calendar_table()

    def create_schedule(self):
        try:
            dialog = MaintenanceScheduleCreateDialog(self.api_client, self)
        except Exception as exc:
            show_notice(self, "Falha ao abrir criacao", str(exc), icon_name="warning")
            return
        if not dialog.exec() or not dialog.result_payload:
            return

        button = self.new_schedule_button
        button.setEnabled(False)
        button.setText("Criando...")
        try:
            created = self.api_client.create_maintenance_schedule(dialog.result_payload)
            created_id = int((created or {}).get("id") or 0)
            if created_id:
                self.selected_schedule_id = created_id
            start_date = str(dialog.result_payload.get("start_date") or "")
            if start_date:
                date_value = QDate.fromString(start_date, "yyyy-MM-dd")
                if date_value.isValid():
                    self.month_input.setDate(date_value)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Programacao criada", "Cronograma criado e pronto para gestao na tabela.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao criar programacao", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Nova programacao")

    def sync_non_conformities(self):
        button = self.sync_nc_button
        button.setEnabled(False)
        button.setText("Sincronizando...")
        try:
            payload = self.api_client.sync_maintenance_from_non_conformities() or {}
            self.refresh()
            self.data_changed.emit()
            show_notice(
                self,
                "Sincronizacao concluida",
                f"{int(payload.get('updated') or 0)} programacao(oes) atualizada(s) a partir das NC.",
                icon_name="dashboard",
            )
        except Exception as exc:
            show_notice(self, "Falha na sincronizacao", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Sincronizar NC")

    def redistribute_selected_schedule(self):
        schedule = self._selected_schedule()
        if not schedule:
            show_notice(self, "Selecao obrigatoria", "Selecione uma programacao para redistribuir.", icon_name="warning")
            return

        start_date = self.redistribute_start_input.date().toString("yyyy-MM-dd")
        daily_capacity = int(self.redistribute_capacity_input.value())
        button = self.redistribute_button
        button.setEnabled(False)
        button.setText("Aplicando...")
        try:
            self.api_client.program_maintenance_schedule(
                int(schedule.get("id")),
                {"start_date": start_date, "daily_capacity": daily_capacity},
            )
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Cronograma redistribuido", "Distribuicao atualizada por data inicial e capacidade.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha na redistribuicao", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Redistribuir cronograma")

    def move_selected_items(self):
        selected_items = self._selected_item_payloads()
        if not selected_items:
            show_notice(self, "Selecao obrigatoria", "Selecione um ou mais itens para mover.", icon_name="warning")
            return

        target_date = self.move_date_input.date().toString("yyyy-MM-dd")
        moved = 0
        skipped = 0
        errors: list[str] = []
        for item in selected_items:
            status = str(item.get("status") or "").upper()
            if status in {"INSTALADO", "CANCELADO"}:
                skipped += 1
                continue
            try:
                self.api_client.reprogram_maintenance_item(int(item.get("id")), {"scheduled_date": target_date})
                moved += 1
            except Exception as exc:
                errors.append(str(exc))

        if moved:
            self.refresh()
            self.data_changed.emit()
        summary = f"Itens movidos: {moved} | ignorados: {skipped}"
        if errors:
            summary += f" | falhas: {len(errors)}"
        icon = "dashboard" if moved else "warning"
        show_notice(self, "Reprogramacao em lote", summary, icon_name=icon)

    def remove_selected_items(self):
        selected_items = self._selected_item_payloads()
        if not selected_items:
            show_notice(self, "Selecao obrigatoria", "Selecione um ou mais itens para retirar.", icon_name="warning")
            return

        removed = 0
        skipped = 0
        errors: list[str] = []
        for item in selected_items:
            status = str(item.get("status") or "").upper()
            if status == "INSTALADO":
                skipped += 1
                continue
            try:
                self.api_client.update_maintenance_item(
                    int(item.get("id")),
                    {
                        "status": "CANCELADO",
                        "observation": "Retirado do cronograma no desktop.",
                    },
                )
                removed += 1
            except Exception as exc:
                errors.append(str(exc))

        if removed:
            self.refresh()
            self.data_changed.emit()
        summary = f"Itens retirados: {removed} | ignorados: {skipped}"
        if errors:
            summary += f" | falhas: {len(errors)}"
        icon = "dashboard" if removed else "warning"
        show_notice(self, "Retirada do cronograma", summary, icon_name=icon)

    def _render_summary(self):
        summary = (self.overview or {}).get("resumo") or {}
        self.schedules_card.set_content("Programacoes", str(summary.get("programacoes", 0)), "Cronogramas ativos e historicos")
        self.items_card.set_content("Itens no mes", str(summary.get("itens", 0)), "Planejados no periodo selecionado")
        self.pending_card.set_content(
            "Pendentes",
            str(summary.get("pendentes", 0)),
            f"Aguardando material: {summary.get('aguardando_material', 0)}",
        )
        self.installed_card.set_content(
            "Instalados",
            str(summary.get("instalados", 0)),
            f"Nao executados: {summary.get('nao_executados', 0)}",
        )
        self.schedules_badge.setText(f"{len(self.filtered_schedules)} registros")

    def _render_schedules_table(self):
        rows = self.filtered_schedules
        selected_row = -1
        self.schedules_table.setSortingEnabled(False)
        self.schedules_table.setUpdatesEnabled(False)
        self.schedules_table.blockSignals(True)
        try:
            self.schedules_table.setRowCount(len(rows))
            for row_index, schedule in enumerate(rows):
                schedule_id = int(schedule.get("id") or 0)
                if self.selected_schedule_id and schedule_id == self.selected_schedule_id:
                    selected_row = row_index
                resumo = schedule.get("resumo") or {}
                values = [
                    schedule_id,
                    schedule.get("title") or "-",
                    SOURCE_LABELS.get(str(schedule.get("source_type") or "").upper(), schedule.get("source_type") or "-"),
                    SCHEDULE_STATUS_LABELS.get(str(schedule.get("status") or "").upper(), schedule.get("status") or "-"),
                    resumo.get("total", 0),
                    resumo.get("pendentes", 0),
                    resumo.get("instalados", 0),
                    self._format_date(schedule.get("start_date")),
                    self._format_date(schedule.get("end_date")),
                    schedule.get("daily_capacity") or 1,
                ]
                for column, value in enumerate(values):
                    payload = schedule if column == 0 else None
                    self.schedules_table.setItem(row_index, column, make_table_item(value, payload=payload))
            if selected_row >= 0:
                self.schedules_table.selectRow(selected_row)
            elif rows:
                self.schedules_table.selectRow(0)
        finally:
            self.schedules_table.blockSignals(False)
            self.schedules_table.setUpdatesEnabled(True)
            self.schedules_table.setSortingEnabled(True)

    def _render_calendar_table(self):
        rows = self._calendar_rows_for_selected_schedule()
        self.calendar_badge.setText(f"{len(rows)} dias")
        self.calendar_table.setSortingEnabled(False)
        self.calendar_table.setUpdatesEnabled(False)
        self.calendar_table.blockSignals(True)
        try:
            self.calendar_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [
                    self._format_date(row.get("date")),
                    row.get("total", 0),
                    row.get("pendentes", 0),
                    row.get("instalados", 0),
                    row.get("nao_executados", 0),
                    row.get("aguardando_material", 0),
                ]
                for column, value in enumerate(values):
                    self.calendar_table.setItem(row_index, column, make_table_item(value))
        finally:
            self.calendar_table.blockSignals(False)
            self.calendar_table.setUpdatesEnabled(True)
            self.calendar_table.setSortingEnabled(True)

    def _calendar_rows_for_selected_schedule(self) -> list[dict]:
        schedule = self._selected_schedule()
        if not schedule:
            days = list(((self.overview or {}).get("cronograma") or {}).get("days") or [])
            return [day for day in days if int(day.get("total") or 0) > 0]

        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "date": "",
                "total": 0,
                "pendentes": 0,
                "instalados": 0,
                "nao_executados": 0,
                "aguardando_material": 0,
            }
        )
        for item in schedule.get("itens") or []:
            date_key = item.get("scheduled_date")
            if not date_key:
                continue
            row = grouped[date_key]
            row["date"] = date_key
            row["total"] += 1
            status = str(item.get("status") or "").upper()
            if status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}:
                row["pendentes"] += 1
            if status == "INSTALADO":
                row["instalados"] += 1
            if status == "NAO_EXECUTADO":
                row["nao_executados"] += 1
            if status == "AGUARDANDO_MATERIAL":
                row["aguardando_material"] += 1
        rows = list(grouped.values())
        rows.sort(key=lambda row: row.get("date") or "")
        return rows

    def _on_schedule_selection_changed(self):
        row = self.schedules_table.currentRow()
        if row < 0:
            return
        first_cell = self.schedules_table.item(row, 0)
        payload = first_cell.data(Qt.UserRole) if first_cell else None
        if not payload:
            return
        self.selected_schedule_id = int(payload.get("id"))
        self.render_selected_schedule_items()
        self._render_calendar_table()

    def _selected_schedule(self) -> dict | None:
        schedule_id = self.selected_schedule_id
        if not schedule_id:
            return None
        for row in (self.overview or {}).get("programacoes") or []:
            if int(row.get("id") or 0) == schedule_id:
                return row
        return None

    def render_selected_schedule_items(self):
        schedule = self._selected_schedule()
        if not schedule:
            self.selected_schedule_badge.setText("Nenhuma programacao selecionada")
            self.items_table.setRowCount(0)
            self._set_action_controls_enabled(False)
            self._update_items_badge()
            return

        self._set_action_controls_enabled(True)
        title = str(schedule.get("title") or f"Programacao #{schedule.get('id')}")
        self.selected_schedule_badge.setText(f"#{schedule.get('id')} | {title}")

        start_date = str(schedule.get("start_date") or "")
        start_qdate = QDate.fromString(start_date, "yyyy-MM-dd")
        if start_qdate.isValid():
            self.redistribute_start_input.setDate(start_qdate)
            self.move_date_input.setDate(start_qdate)
        self.redistribute_capacity_input.setValue(max(1, int(schedule.get("daily_capacity") or 1)))

        status_filter = self.item_status_filter.currentData()
        items = list(schedule.get("itens") or [])
        if status_filter and status_filter != "ALL":
            items = [item for item in items if str(item.get("status") or "").upper() == status_filter]

        material_text = self._material_summary_for_schedule(schedule)
        self.items_table.setSortingEnabled(False)
        self.items_table.setUpdatesEnabled(False)
        self.items_table.blockSignals(True)
        try:
            self.items_table.setRowCount(len(items))
            for row_index, item in enumerate(items):
                vehicle = item.get("vehicle") or {}
                source_label = self._item_source_label(item, schedule)
                item_label = self._item_label(item, schedule)
                values = [
                    item.get("id"),
                    vehicle.get("frota") or "-",
                    vehicle.get("placa") or "-",
                    vehicle.get("modelo") or "-",
                    source_label,
                    ITEM_STATUS_LABELS.get(str(item.get("status") or "").upper(), item.get("status") or "-"),
                    self._format_date(item.get("scheduled_date")),
                    self._format_datetime(item.get("executed_at")),
                    material_text,
                    item_label,
                    item.get("observation") or "-",
                ]
                for column, value in enumerate(values):
                    payload = item if column == 0 else None
                    self.items_table.setItem(row_index, column, make_table_item(value, payload=payload))
        finally:
            self.items_table.blockSignals(False)
            self.items_table.setUpdatesEnabled(True)
            self.items_table.setSortingEnabled(True)

        self._update_items_badge()

    def _selected_item_payloads(self) -> list[dict]:
        model = self.items_table.selectionModel()
        if not model:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        selected: list[dict] = []
        for row in rows:
            cell = self.items_table.item(row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                selected.append(payload)
        if selected:
            return selected
        current_row = self.items_table.currentRow()
        if current_row >= 0:
            cell = self.items_table.item(current_row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                return [payload]
        return []

    def _update_items_badge(self):
        total = self.items_table.rowCount()
        selected = len(self._selected_item_payloads())
        self.items_badge.setText(f"{total} itens | {selected} selecionados")

    def _set_action_controls_enabled(self, enabled: bool):
        self.item_status_filter.setEnabled(enabled)
        self.move_date_input.setEnabled(enabled)
        self.move_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.redistribute_start_input.setEnabled(enabled)
        self.redistribute_capacity_input.setEnabled(enabled)
        self.redistribute_button.setEnabled(enabled)

    def _item_source_label(self, item: dict, schedule: dict) -> str:
        if item.get("checklist_item_id"):
            return "NC checklist"
        if item.get("activity_id"):
            return "Atividade"
        return SOURCE_LABELS.get(str(schedule.get("source_type") or "").upper(), "-")

    def _item_label(self, item: dict, schedule: dict) -> str:
        checklist_item = item.get("checklist_item") or {}
        if checklist_item.get("item_nome"):
            return checklist_item.get("item_nome")
        activity = item.get("activity") or {}
        if activity.get("item_nome"):
            return activity.get("item_nome")
        return schedule.get("item_name") or schedule.get("title") or "-"

    def _material_summary_for_schedule(self, schedule: dict) -> str:
        materials = list(schedule.get("materiais") or [])
        if not materials:
            return "Sem material"
        counters: dict[str, int] = defaultdict(int)
        for link in materials:
            counters[str(link.get("status") or "").upper()] += 1
        parts = []
        if counters.get("DISPONIVEL_EM_ESTOQUE"):
            parts.append(f"Disponivel {counters['DISPONIVEL_EM_ESTOQUE']}")
        if counters.get("AGUARDANDO_MATERIAL"):
            parts.append(f"Aguardando {counters['AGUARDANDO_MATERIAL']}")
        if counters.get("EM_COMPRAS"):
            parts.append(f"Compras {counters['EM_COMPRAS']}")
        if counters.get("RESERVADO"):
            parts.append(f"Reservado {counters['RESERVADO']}")
        if counters.get("UTILIZADO"):
            parts.append(f"Utilizado {counters['UTILIZADO']}")
        return " | ".join(parts) if parts else "Com material"

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        text = str(value)[:10]
        parts = text.split("-")
        if len(parts) != 3:
            return text
        return f"{parts[2]}/{parts[1]}/{parts[0]}"

    @staticmethod
    def _format_datetime(value: str | None) -> str:
        if not value:
            return "-"
        text = str(value).replace("T", " ")
        if len(text) >= 16:
            date_part = text[:10]
            time_part = text[11:16]
            parts = date_part.split("-")
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]} {time_part}"
        return text
