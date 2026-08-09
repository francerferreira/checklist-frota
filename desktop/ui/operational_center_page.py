from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from components import StatCard, TableSkeletonOverlay
from theme import configure_table, make_table_item, style_filter_bar, style_table_card
from ui.availability_page import STATUS_COLORS, STATUS_LABELS


class OperationalCenterPage(QFrame):
    """Read-only operational view built from existing availability contracts."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.rows: list[dict] = []
        self.critical_by_vehicle: dict[int, dict] = {}
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Central Operacional")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Visão de RTGs, LBS e demais ativos por status operacional. "
            "A central consulta a base atual e não altera equipamentos."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        cards = QGridLayout()
        cards.setSpacing(14)
        self.rtg_card = StatCard("RTGs", "0", "Ativos cadastrados", icon_name="equipment")
        self.lbs_card = StatCard("LBS", "0", "Ativos cadastrados", icon_name="equipment")
        self.available_card = StatCard("Disponíveis", "0", "Operação normal ou restrita", icon_name="dashboard")
        self.critical_card = StatCard("Atenção operacional", "0", "Parados, em manutenção ou com OS", icon_name="warning")
        for column, card in enumerate((self.rtg_card, self.lbs_card, self.available_card, self.critical_card)):
            cards.addWidget(card, 0, column)
            cards.setColumnStretch(column, 1)

        filter_bar = QFrame()
        style_filter_bar(filter_bar)
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(10)
        filter_layout.addWidget(QLabel("Módulo"))
        self.family_filter = QComboBox()
        self.family_filter.addItem("Todos os ativos", "ALL")
        self.family_filter.addItem("RTG", "RTG")
        self.family_filter.addItem("LBS", "LBS")
        self.family_filter.addItem("Demais módulos", "OTHER")
        filter_layout.addWidget(self.family_filter)
        filter_layout.addWidget(QLabel("Pesquisar"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Frota, modelo, local ou status")
        filter_layout.addWidget(self.search_input, 1)
        self.refresh_button = QPushButton("Atualizar visão")
        self.refresh_button.setProperty("variant", "secondary")
        filter_layout.addWidget(self.refresh_button)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_title = QLabel("Situação dos ativos")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel(
            "Sem apontamento não significa disponível. OS e emergências aparecem somente quando informadas pela API atual."
        )
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Equipamento",
                "Módulo",
                "Status",
                "Local",
                "Criticidade",
                "Horímetro",
                "OS / emergência",
                "Atualizado em",
            ]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(480)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=8)
        table_layout.addWidget(table_title)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(cards)
        layout.addWidget(filter_bar)
        layout.addWidget(table_card, 1)

        self.family_filter.currentIndexChanged.connect(self.apply_filters)
        self.search_input.textChanged.connect(self.apply_filters)
        self.refresh_button.clicked.connect(self.refresh)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando central operacional")
        else:
            self.table_skeleton.hide_skeleton()

    @staticmethod
    def _datetime(value: str | None) -> str:
        return value.replace("T", " ")[:16] if value else "-"

    @staticmethod
    def _family_code(row: dict) -> str:
        family = row.get("family") or {}
        vehicle = row.get("vehicle") or {}
        return str(family.get("code") or vehicle.get("tipo") or "").strip().upper()

    @staticmethod
    def _incident_label(item: dict | None) -> str:
        if not item:
            return "-"
        orders = item.get("open_work_orders") or []
        emergencies = item.get("open_emergencies") or []
        labels = []
        if orders:
            order = orders[0].get("work_order") or orders[0]
            labels.append(str(order.get("order_number") or "OS aberta"))
        if emergencies:
            labels.append(str(emergencies[0].get("event_number") or "Emergência aberta"))
        return " / ".join(labels) if labels else "-"

    def refresh(self):
        overview = self.api_client.get_availability_overview() or {}
        self.rows = list(overview.get("rows") or [])
        get_critical = getattr(self.api_client, "get_critical_equipment", None)
        critical = get_critical() if callable(get_critical) else {}
        self.critical_by_vehicle = {
            int((item.get("vehicle") or {}).get("id")): item
            for item in (critical or {}).get("items") or []
            if (item.get("vehicle") or {}).get("id") is not None
        }
        self._update_cards(overview.get("summary") or {})
        self.apply_filters()

    def _update_cards(self, summary: dict):
        rtg_total = sum(1 for row in self.rows if self._family_code(row) == "RTG")
        lbs_total = sum(1 for row in self.rows if self._family_code(row) == "LBS")
        counts = summary.get("status_counts") or {}
        available = int(counts.get("DISPONIVEL", 0)) + int(counts.get("RESTRICAO", 0))
        critical = len(self.critical_by_vehicle) or (
            int(counts.get("INDISPONIVEL", 0)) + int(counts.get("MANUTENCAO", 0))
        )
        self.rtg_card.set_content("RTGs", str(rtg_total), "Ativos cadastrados")
        self.lbs_card.set_content("LBS", str(lbs_total), "Ativos cadastrados")
        self.available_card.set_content("Disponíveis", str(available), "Operação normal ou restrita")
        self.critical_card.set_content("Atenção operacional", str(critical), "Parados, em manutenção ou com OS")

    def apply_filters(self):
        family_filter = self.family_filter.currentData()
        search = self.search_input.text().strip().casefold()
        filtered = []
        for row in self.rows:
            family_code = self._family_code(row)
            if family_filter == "RTG" and family_code != "RTG":
                continue
            if family_filter == "LBS" and family_code != "LBS":
                continue
            if family_filter == "OTHER" and family_code in {"RTG", "LBS"}:
                continue
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            searchable = " ".join(
                (
                    str(vehicle.get("frota") or ""),
                    str(vehicle.get("modelo") or ""),
                    str((row.get("location") or {}).get("full_name") or vehicle.get("local") or ""),
                    str(state.get("operational_status") or ""),
                )
            ).casefold()
            if search and search not in searchable:
                continue
            filtered.append(row)
        self._render_rows(filtered)

    def _render_rows(self, rows: list[dict]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            status = state.get("operational_status") or "SEM_APONTAMENTO"
            vehicle_id = vehicle.get("id")
            critical = self.critical_by_vehicle.get(int(vehicle_id)) if vehicle_id is not None else None
            values = [
                vehicle.get("frota") or vehicle.get("placa") or "-",
                (row.get("family") or {}).get("name") or vehicle.get("tipo") or "-",
                STATUS_LABELS.get(status, status),
                (row.get("location") or {}).get("full_name") or vehicle.get("local") or "Sem local",
                vehicle.get("criticality") or "MEDIA",
                f"{state['latest_hourmeter']:.2f} h" if state.get("latest_hourmeter") is not None else "-",
                self._incident_label(critical),
                self._datetime(state.get("status_updated_at")),
            ]
            for column, value in enumerate(values):
                item = make_table_item(value, payload=vehicle if column == 0 else None)
                if column == 2:
                    background, foreground = STATUS_COLORS.get(status, STATUS_COLORS["SEM_APONTAMENTO"])
                    item.setBackground(QBrush(QColor(background)))
                    item.setForeground(QBrush(QColor(foreground)))
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
