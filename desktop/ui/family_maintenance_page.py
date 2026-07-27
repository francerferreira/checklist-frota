from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, style_filter_bar, style_table_card


STATUS_LABELS = {
    "PENDENTE": "Pendente",
    "PROGRAMADO": "Programado",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "INSTALADO": "Concluído",
    "NAO_EXECUTADO": "Não executado",
    "REPROGRAMADO": "Reprogramado",
    "CANCELADO": "Cancelado",
}
PENDING_STATUSES = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}


def _text(value) -> str:
    return str(value or "").strip()


def _is_family(item: dict, family: str) -> bool:
    vehicle = item.get("vehicle") or {}
    family_data = vehicle.get("family") or {}
    values = (vehicle.get("tipo"), vehicle.get("frota"), family_data.get("code"), family_data.get("name"))
    return any(family in _text(value).upper() for value in values)


class FamilyMaintenancePage(QFrame):
    """Visão de manutenção filtrada por família, sem duplicar o cadastro central."""

    open_page_requested = Signal(str)

    def __init__(self, api_client, family: str, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = _text(family).upper()
        self.items: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(f"MANUTENÇÕES {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"Acompanhe programações, serviços e ordens da família {self.family} em uma visão operacional simples."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        full_button = QPushButton("Manutenção completa")
        full_button.setProperty("variant", "primary")
        full_button.clicked.connect(lambda: self.open_page_requested.emit("maintenance"))
        pcm_button = QPushButton("Abrir PCM")
        pcm_button.clicked.connect(lambda: self.open_page_requested.emit("pcm"))
        header.addWidget(full_button)
        header.addWidget(pcm_button)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.total_card = StatCard("Serviços", "0", f"Itens {self.family}", icon_name="maintenance")
        self.pending_card = StatCard("Pendentes", "0", "Aguardando execução", icon_name="warning")
        self.completed_card = StatCard("Concluídos", "0", "Serviços finalizados", icon_name="ok")
        self.orders_card = StatCard("OS abertas", "0", "Ordens vinculadas", icon_name="reports")
        for index, card in enumerate((self.total_card, self.pending_card, self.completed_card, self.orders_card)):
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        layout.addLayout(cards)

        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(8)
        self.month = QDateEdit(QDate.currentDate())
        self.month.setCalendarPopup(True)
        self.month.setDisplayFormat("MM/yyyy")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for key, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, key)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar equipamento, serviço ou OS")
        refresh = QPushButton("Atualizar")
        refresh.setProperty("variant", "primary")
        refresh.clicked.connect(self.refresh)
        self.month.dateChanged.connect(lambda _date: self.refresh())
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        self.search.textChanged.connect(self._render_rows)
        filter_layout.addWidget(QLabel("Período"), 0, 0)
        filter_layout.addWidget(self.month, 1, 0)
        filter_layout.addWidget(QLabel("Status"), 0, 1)
        filter_layout.addWidget(self.status_filter, 1, 1)
        filter_layout.addWidget(QLabel("Pesquisa"), 0, 2)
        filter_layout.addWidget(self.search, 1, 2)
        filter_layout.addWidget(refresh, 1, 3)
        for column in (0, 1, 2):
            filter_layout.setColumnStretch(column, 1)
        layout.addWidget(filters)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Data", "Equipamento", "Serviço", "Situação", "OS", "Responsável", "Observação", "Ação"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(440)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

    def refresh(self):
        try:
            selected = self.month.date()
            overview = self.api_client.get_maintenance_overview(selected.year(), selected.month()) or {}
            self.items = [item for item in overview.get("itens", []) if _is_family(item, self.family)]
            self._render_rows()
        except Exception as exc:
            show_notice(self, f"Falha ao carregar manutenção {self.family}", str(exc), icon_name="warning")

    def _matches(self, item: dict) -> bool:
        status = _text(item.get("status")).upper()
        selected_status = _text(self.status_filter.currentData())
        if selected_status and status != selected_status:
            return False
        vehicle = item.get("vehicle") or {}
        order = item.get("work_order") or {}
        schedule = item.get("schedule") or {}
        query = self.search.text().strip().casefold()
        if query:
            searchable = " ".join(
                _text(value)
                for value in (
                    vehicle.get("frota"), vehicle.get("placa"), schedule.get("title"),
                    order.get("order_number"), item.get("observation"),
                )
            ).casefold()
            if query not in searchable:
                return False
        return True

    def _render_rows(self):
        rows = [item for item in self.items if self._matches(item)]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        pending = completed = orders = 0
        for index, item in enumerate(rows):
            status = _text(item.get("status") or "PENDENTE").upper()
            if status in PENDING_STATUSES:
                pending += 1
            if status == "INSTALADO":
                completed += 1
            order = item.get("work_order") or {}
            if order and _text(order.get("status")).upper() not in {"CONCLUIDA", "CANCELADA"}:
                orders += 1
            vehicle = item.get("vehicle") or {}
            schedule = item.get("schedule") or {}
            mechanic = item.get("assigned_mechanic") or {}
            activity = item.get("activity") or {}
            checklist = item.get("checklist_item") or {}
            service = _text(schedule.get("title") or activity.get("titulo") or checklist.get("nome") or checklist.get("item_principal")) or "Serviço de manutenção"
            values = [
                item.get("scheduled_date") or "-",
                vehicle.get("frota") or vehicle.get("placa") or "-",
                service,
                STATUS_LABELS.get(status, status),
                order.get("order_number") or "-",
                mechanic.get("nome") or "Não atribuído",
                item.get("observation") or item.get("not_executed_reason") or "-",
            ]
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
            action = QPushButton("Abrir manutenção")
            action.clicked.connect(lambda _checked=False: self.open_page_requested.emit("maintenance"))
            self.table.setCellWidget(index, 7, action)
        self.total_card.set_content("Serviços", str(len(rows)), f"Itens {self.family}")
        self.pending_card.set_content("Pendentes", str(pending), "Aguardando execução")
        self.completed_card.set_content("Concluídos", str(completed), "Serviços finalizados")
        self.orders_card.set_content("OS abertas", str(orders), "Ordens vinculadas")
