from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from components import StatCard, TableSkeletonOverlay, show_notice
from theme import configure_table, make_table_item, style_filter_bar, style_table_card


SOURCE_LABELS = {
    "CHECKLIST_NC": "Não conformidade",
    "ATIVIDADE": "Atividade",
    "PREVENTIVA": "Preventiva",
}

STATUS_LABELS = {
    "ABERTA": "Aberta",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "PROGRAMADA": "Programada",
    "EM_EXECUCAO": "Em execução",
    "CONCLUIDA": "Concluída",
    "CANCELADA": "Cancelada",
}


class MaintenancePage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.overview: dict = {"resumo": {}, "cronograma": {"days": []}, "programacoes": []}
        self.filtered_schedules: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Programação de manutenção")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Gestão do cronograma no desktop. O web mobile fica somente para executar e responder as programações."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        self.sync_nc_button = QPushButton("Sincronizar NC")
        self.sync_nc_button.setMinimumHeight(42)
        self.sync_nc_button.clicked.connect(self.sync_non_conformities)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setMinimumHeight(42)
        refresh_button.clicked.connect(self.refresh)

        header.addLayout(text_wrap, 1)
        header.addWidget(self.sync_nc_button)
        header.addWidget(refresh_button)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)
        self.schedules_card = StatCard("Programações", "0", "Cronogramas ativos e históricos", icon_name="activities")
        self.items_card = StatCard("Itens no mês", "0", "Planejados no período selecionado", icon_name="reports")
        self.pending_card = StatCard("Pendentes", "0", "Programados, reprogramados e aguardando", icon_name="warning")
        self.installed_card = StatCard("Instalados", "0", "Concluídos com baixa de estoque", icon_name="ok")
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
        self.month_input.setDate(date.today())

        self.source_filter = QComboBox()
        self.source_filter.addItem("Todas as origens", "ALL")
        self.source_filter.addItem("Não conformidade", "CHECKLIST_NC")
        self.source_filter.addItem("Atividade", "ATIVIDADE")
        self.source_filter.addItem("Preventiva", "PREVENTIVA")

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "ALL")
        self.status_filter.addItem("Aberta", "ABERTA")
        self.status_filter.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.status_filter.addItem("Programada", "PROGRAMADA")
        self.status_filter.addItem("Em execução", "EM_EXECUCAO")
        self.status_filter.addItem("Concluída", "CONCLUIDA")
        self.status_filter.addItem("Cancelada", "CANCELADA")

        apply_button = QPushButton("Aplicar")
        apply_button.setProperty("variant", "primary")
        apply_button.setMinimumHeight(40)
        apply_button.clicked.connect(self.apply_filters)

        clear_button = QPushButton("Limpar filtros")
        clear_button.setMinimumHeight(40)
        clear_button.clicked.connect(self.clear_filters)

        filter_layout.addWidget(QLabel("Mês"), 0, 0)
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
        schedules_title = QLabel("Programações de manutenção")
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
                "Título",
                "Origem",
                "Status",
                "Itens",
                "Pendentes",
                "Instalados",
                "Data início",
                "Data fim",
                "Cap./dia",
            ]
        )
        configure_table(self.schedules_table, stretch_last=False)
        self.schedules_table.setMinimumHeight(300)

        schedules_layout.addLayout(schedules_title_row)
        schedules_layout.addWidget(self.schedules_table)

        calendar_card = QFrame()
        style_table_card(calendar_card)
        self.calendar_skeleton = TableSkeletonOverlay(calendar_card, rows=6)
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(14, 14, 14, 14)
        calendar_layout.setSpacing(10)

        calendar_title_row = QHBoxLayout()
        calendar_title = QLabel("Tabela diária do cronograma")
        calendar_title.setObjectName("SectionTitle")
        self.calendar_badge = QLabel("0 dias com programação")
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
                "Não executados",
                "Aguardando material",
            ]
        )
        configure_table(self.calendar_table, stretch_last=True)
        self.calendar_table.setMinimumHeight(260)

        calendar_layout.addLayout(calendar_title_row)
        calendar_layout.addWidget(self.calendar_table)

        layout.addLayout(header)
        layout.addLayout(cards_layout)
        layout.addWidget(filter_card)
        layout.addWidget(schedules_card)
        layout.addWidget(calendar_card, 1)

    def set_loading_state(self, loading: bool):
        if loading:
            self.schedules_skeleton.show_skeleton("Carregando programação de manutenção")
            self.calendar_skeleton.show_skeleton("Carregando calendário da manutenção")
        else:
            self.schedules_skeleton.hide_skeleton()
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
        self._render_summary()
        self._render_schedules_table()
        self._render_calendar_table()

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
                "Sincronização concluída",
                f"{int(payload.get('updated') or 0)} programação(ões) atualizada(s) a partir das NC.",
                icon_name="dashboard",
            )
        except Exception as exc:
            show_notice(self, "Falha na sincronização", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Sincronizar NC")

    def _render_summary(self):
        summary = (self.overview or {}).get("resumo") or {}
        self.schedules_card.set_content("Programações", str(summary.get("programacoes", 0)), "Cronogramas ativos e históricos")
        self.items_card.set_content("Itens no mês", str(summary.get("itens", 0)), "Planejados no período selecionado")
        self.pending_card.set_content(
            "Pendentes",
            str(summary.get("pendentes", 0)),
            f"Aguardando material: {summary.get('aguardando_material', 0)}",
        )
        self.installed_card.set_content(
            "Instalados",
            str(summary.get("instalados", 0)),
            f"Não executados: {summary.get('nao_executados', 0)}",
        )
        self.schedules_badge.setText(f"{len(self.filtered_schedules)} registros")

    def _render_schedules_table(self):
        rows = self.filtered_schedules
        self.schedules_table.setSortingEnabled(False)
        self.schedules_table.setUpdatesEnabled(False)
        self.schedules_table.blockSignals(True)
        try:
            self.schedules_table.setRowCount(len(rows))
            for row_index, schedule in enumerate(rows):
                resumo = schedule.get("resumo") or {}
                values = [
                    schedule.get("id"),
                    schedule.get("title") or "-",
                    SOURCE_LABELS.get(str(schedule.get("source_type") or "").upper(), schedule.get("source_type") or "-"),
                    STATUS_LABELS.get(str(schedule.get("status") or "").upper(), schedule.get("status") or "-"),
                    resumo.get("total", 0),
                    resumo.get("pendentes", 0),
                    resumo.get("instalados", 0),
                    self._format_date(schedule.get("start_date")),
                    self._format_date(schedule.get("end_date")),
                    schedule.get("daily_capacity") or 1,
                ]
                for column, value in enumerate(values):
                    item = make_table_item(value, payload=schedule if column == 0 else None)
                    self.schedules_table.setItem(row_index, column, item)
        finally:
            self.schedules_table.blockSignals(False)
            self.schedules_table.setUpdatesEnabled(True)
            self.schedules_table.setSortingEnabled(True)

    def _render_calendar_table(self):
        days = list(((self.overview or {}).get("cronograma") or {}).get("days") or [])
        selected_rows = [day for day in days if int(day.get("total") or 0) > 0]
        if not selected_rows:
            selected_rows = days
        self.calendar_badge.setText(f"{len([day for day in days if int(day.get('total') or 0) > 0])} dias com programação")

        self.calendar_table.setSortingEnabled(False)
        self.calendar_table.setUpdatesEnabled(False)
        self.calendar_table.blockSignals(True)
        try:
            self.calendar_table.setRowCount(len(selected_rows))
            for row_index, day in enumerate(selected_rows):
                values = [
                    self._format_date(day.get("date")),
                    day.get("total", 0),
                    day.get("pendentes", 0),
                    day.get("instalados", 0),
                    day.get("nao_executados", 0),
                    day.get("aguardando_material", 0),
                ]
                for column, value in enumerate(values):
                    self.calendar_table.setItem(row_index, column, make_table_item(value))
        finally:
            self.calendar_table.blockSignals(False)
            self.calendar_table.setUpdatesEnabled(True)
            self.calendar_table.setSortingEnabled(True)

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        text = str(value)[:10]
        parts = text.split("-")
        if len(parts) != 3:
            return text
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
