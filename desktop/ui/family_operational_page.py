from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
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
    "SEM_APONTAMENTO": "Sem apontamento",
    "DISPONIVEL": "Disponivel",
    "INDISPONIVEL": "Indisponivel",
    "RESTRICAO": "Restricao",
    "MANUTENCAO": "Manutencao",
}
STATUS_COLORS = {
    "SEM_APONTAMENTO": ("#F1F5F9", "#64748B"),
    "DISPONIVEL": ("#DCFCE7", "#166534"),
    "INDISPONIVEL": ("#FEE2E2", "#991B1B"),
    "RESTRICAO": ("#FEF3C7", "#92400E"),
    "MANUTENCAO": ("#E2E8F0", "#334155"),
}
STOP_STATUSES = {"INDISPONIVEL", "MANUTENCAO"}


def _text(value) -> str:
    return str(value or "").strip()


def _family_match(row: dict, family: str) -> bool:
    vehicle = row.get("vehicle") or {}
    family_data = row.get("family") or {}
    values = (family_data.get("code"), family_data.get("name"), vehicle.get("tipo"), vehicle.get("frota"))
    return any(family in _text(value).upper() for value in values)


def _location_parts(row: dict) -> tuple[str, str]:
    location = row.get("location") or {}
    full_name = _text(location.get("full_name"))
    pieces = [piece.strip() for piece in full_name.split("/") if piece.strip()]
    parent = _text(location.get("parent_name")) or (pieces[0] if len(pieces) > 1 else "")
    name = _text(location.get("name")) or (pieces[-1] if pieces else "Sem local")
    area_source = f"{parent} {full_name}".upper()
    if "ALFANDEGADO" in area_source:
        area = "ALFANDEGADO"
    elif "ATR" in area_source:
        area = "ATR"
    else:
        area = parent or "SEM AREA"
    patio = name or "SEM PATIO"
    if "PATIO" not in patio.upper() and len(pieces) > 1:
        patio = pieces[-1]
    return area, patio


class FamilyOperationalPage(QFrame):
    data_changed = Signal()
    open_page_requested = Signal(str)

    def __init__(self, api_client, family: str, downtime_page_key: str, maintenance_page_key: str | None = None, parent=None, preventive_page_key: str | None = None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = _text(family).upper()
        self.downtime_page_key = downtime_page_key
        self.maintenance_page_key = maintenance_page_key
        self.preventive_page_key = preventive_page_key
        self.rows: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(f"PAINEL OPERACIONAL {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"Acompanhe os equipamentos {self.family} separados por area e patio, com a situacao operacional atual."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        downtime_button = QPushButton(f"Controle de paradas {self.family}")
        downtime_button.setProperty("variant", "primary")
        downtime_button.clicked.connect(lambda: self.open_page_requested.emit(self.downtime_page_key))
        if self.maintenance_page_key:
            maintenance_button = QPushButton(f"Manutenções {self.family}")
            maintenance_button.clicked.connect(lambda: self.open_page_requested.emit(self.maintenance_page_key))
            header.addWidget(maintenance_button, 0)
        if self.preventive_page_key:
            preventive_button = QPushButton(f"Preventiva {self.family}")
            preventive_button.setProperty("variant", "primary")
            preventive_button.clicked.connect(lambda: self.open_page_requested.emit(self.preventive_page_key))
            header.addWidget(preventive_button, 0)
        header.addWidget(downtime_button, 0)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.total_card = StatCard("Equipamentos", "0", f"Ativos {self.family}", icon_name="equipment")
        self.available_card = StatCard("Disponiveis", "0", "Disponivel ou restricao", icon_name="dashboard")
        self.stopped_card = StatCard("Em parada", "0", "Indisponivel ou manutencao", icon_name="warning")
        self.measured_card = StatCard("Disponibilidade", "-", "Media no periodo", icon_name="reports")
        for index, card in enumerate((self.total_card, self.available_card, self.stopped_card, self.measured_card)):
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        layout.addLayout(cards)

        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(8)
        self.area_filter = QComboBox()
        self.patio_filter = QComboBox()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar RTG, serie ou local")
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        self.area_filter.currentIndexChanged.connect(self._refresh_patio_filter)
        filter_layout.addWidget(QLabel("Area"), 0, 0)
        filter_layout.addWidget(self.area_filter, 1, 0)
        filter_layout.addWidget(QLabel("Patio"), 0, 1)
        filter_layout.addWidget(self.patio_filter, 1, 1)
        filter_layout.addWidget(QLabel("Pesquisa"), 0, 2)
        filter_layout.addWidget(self.search, 1, 2)
        filter_layout.addWidget(refresh_button, 1, 3)
        for column in (0, 1, 2):
            filter_layout.setColumnStretch(column, 1)
        layout.addWidget(filters)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Area", "Patio", "Equipamento", "Situacao", "Horimetro", "Motivo", "Acao"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(440)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

    def set_loading_state(self, loading: bool):
        self.setEnabled(not loading)

    def _refresh_patio_filter(self):
        selected_area = str(self.area_filter.currentData() or "")
        patios = sorted({row["patio"] for row in self.rows if not selected_area or row["area"] == selected_area})
        current = self.patio_filter.currentData()
        self.patio_filter.blockSignals(True)
        self.patio_filter.clear()
        self.patio_filter.addItem("Todos os patios", "")
        for patio in patios:
            self.patio_filter.addItem(patio, patio)
        index = self.patio_filter.findData(current)
        self.patio_filter.setCurrentIndex(index if index >= 0 else 0)
        self.patio_filter.blockSignals(False)
        self._render_rows()

    def _matches_filters(self, row: dict) -> bool:
        selected_area = str(self.area_filter.currentData() or "")
        selected_patio = str(self.patio_filter.currentData() or "")
        if selected_area and row["area"] != selected_area:
            return False
        if selected_patio and row["patio"] != selected_patio:
            return False
        query = self.search.text().strip().casefold()
        if query:
            vehicle = row.get("vehicle") or {}
            searchable = " ".join(
                _text(value)
                for value in (vehicle.get("frota"), vehicle.get("modelo"), vehicle.get("serial_number"), row["area"], row["patio"])
            ).casefold()
            if query not in searchable:
                return False
        return True

    def refresh(self):
        try:
            overview = self.api_client.get_availability_overview()
            rows = []
            for raw_row in overview.get("rows", []):
                if not _family_match(raw_row, self.family):
                    continue
                area, patio = _location_parts(raw_row)
                rows.append({**raw_row, "area": area, "patio": patio})
            self.rows = rows
            current_area = self.area_filter.currentData()
            self.area_filter.blockSignals(True)
            self.area_filter.clear()
            self.area_filter.addItem("Todas as areas", "")
            for area in sorted({row["area"] for row in rows}):
                self.area_filter.addItem(area, area)
            index = self.area_filter.findData(current_area)
            self.area_filter.setCurrentIndex(index if index >= 0 else 0)
            self.area_filter.blockSignals(False)
            self._refresh_patio_filter()
            self._render_rows()
        except Exception as exc:
            show_notice(self, "Falha ao carregar painel operacional", str(exc), icon_name="warning")

    def _render_rows(self):
        visible_rows = [row for row in self.rows if self._matches_filters(row)]
        total = len(visible_rows)
        available = 0
        stopped = 0
        measured: list[float] = []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(total)
        for index, row in enumerate(visible_rows):
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            status = str(state.get("operational_status") or "SEM_APONTAMENTO").upper()
            if status in {"DISPONIVEL", "RESTRICAO"}:
                available += 1
            if status in STOP_STATUSES:
                stopped += 1
            percentage = row.get("availability_percentage")
            if percentage is not None:
                measured.append(float(percentage))
            values = [
                row["area"], row["patio"],
                vehicle.get("frota") or vehicle.get("placa") or f"ID {vehicle.get('id')}",
                STATUS_LABELS.get(status, status),
                f"{state['latest_hourmeter']:.2f} h" if state.get("latest_hourmeter") is not None else "-",
                state.get("status_reason") or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 3:
                    background, foreground = STATUS_COLORS.get(status, STATUS_COLORS["SEM_APONTAMENTO"])
                    item.setBackground(QColor(background))
                    item.setForeground(QColor(foreground))
                self.table.setItem(index, column, item)
            action = QPushButton("Ver parada" if status in STOP_STATUSES else "Abrir controle")
            action.clicked.connect(lambda _checked=False: self.open_page_requested.emit(self.downtime_page_key))
            self.table.setCellWidget(index, 6, action)

        average = sum(measured) / len(measured) if measured else None
        self.total_card.set_content("Equipamentos", str(total), f"Ativos {self.family}")
        self.available_card.set_content("Disponiveis", str(available), "Disponivel ou restricao")
        self.stopped_card.set_content("Em parada", str(stopped), "Indisponivel ou manutencao")
        self.measured_card.set_content("Disponibilidade", f"{average:.2f}%" if average is not None else "-", "Media no periodo")
