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
    "DISPONIVEL": "Disponível",
    "INDISPONIVEL": "Indisponível",
    "RESTRICAO": "Restrição",
    "MANUTENCAO": "Manutenção",
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


def _family_match(row: dict) -> bool:
    vehicle = row.get("vehicle") or {}
    family = row.get("family") or {}
    values = (family.get("code"), family.get("name"), vehicle.get("tipo"), vehicle.get("frota"))
    return any("LBS" in _text(value).upper() for value in values)


def _location_parts(row: dict) -> tuple[str, str]:
    location = row.get("location") or {}
    full_name = _text(location.get("full_name"))
    pieces = [piece.strip() for piece in full_name.split("/") if piece.strip()]
    source = f"{location.get('parent_name') or ''} {full_name}".upper()
    if "PROVIS" in source or "ITACOATIARA" in source:
        pier = "Píer Provisório / Itacoatiara"
    elif "ALFANDEGADO" in source:
        pier = "Píer Alfandegado"
    else:
        pier = _text(location.get("parent_name")) or (pieces[0] if len(pieces) > 1 else "Sem píer")
    berco = _text(location.get("name")) or (pieces[-1] if pieces else "Sem berço")
    if "PROVIS" in berco.upper() or "ITACOATIARA" in berco.upper():
        berco = "Píer Provisório / Itacoatiara"
    return pier, berco


def _vehicle_label(vehicle: dict | None) -> str:
    vehicle = vehicle or {}
    return _text(vehicle.get("frota") or vehicle.get("placa") or vehicle.get("modelo")) or "-"


class LBSOperationalPage(QFrame):
    """Painel operacional de LBS organizado por píer, berço e Spreader."""

    open_page_requested = Signal(str)

    def __init__(self, api_client, downtime_page_key: str, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.downtime_page_key = downtime_page_key
        self.rows: list[dict] = []
        self.spreader_links: dict[int, dict[str, list[str]]] = {}
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("PAINEL OPERACIONAL LBS")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Acompanhe as LBS por píer e berço, com Spreader acoplado e reserva.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        downtime_button = QPushButton("Controle de paradas LBS")
        downtime_button.setProperty("variant", "primary")
        downtime_button.clicked.connect(lambda: self.open_page_requested.emit(self.downtime_page_key))
        header.addWidget(downtime_button, 0)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.total_card = StatCard("Equipamentos", "0", "Ativos LBS", icon_name="equipment")
        self.available_card = StatCard("Disponíveis", "0", "Disponível ou restrição", icon_name="dashboard")
        self.stopped_card = StatCard("Em parada", "0", "Indisponível ou manutenção", icon_name="warning")
        self.measured_card = StatCard("Disponibilidade", "-", "Média no período", icon_name="reports")
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
        self.pier_filter = QComboBox()
        self.berco_filter = QComboBox()
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for status, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, status)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar LBS, série, píer ou berço")
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        self.pier_filter.currentIndexChanged.connect(self._refresh_berco_filter)
        self.berco_filter.currentIndexChanged.connect(self._render_rows)
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        self.search.textChanged.connect(self._render_rows)
        filter_layout.addWidget(QLabel("Píer"), 0, 0)
        filter_layout.addWidget(self.pier_filter, 1, 0)
        filter_layout.addWidget(QLabel("Berço"), 0, 1)
        filter_layout.addWidget(self.berco_filter, 1, 1)
        filter_layout.addWidget(QLabel("Equipamento"), 0, 2)
        filter_layout.addWidget(self.search, 1, 2)
        filter_layout.addWidget(QLabel("Situação"), 0, 3)
        filter_layout.addWidget(self.status_filter, 1, 3)
        filter_layout.addWidget(refresh_button, 1, 4)
        for column in range(4):
            filter_layout.setColumnStretch(column, 1)
        layout.addWidget(filters)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["Píer", "Berço", "LBS", "Série", "Spreader acoplado", "Reserva", "Situação", "Horímetro", "Motivo", "Ação"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(440)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

    def _refresh_berco_filter(self):
        selected_pier = _text(self.pier_filter.currentData())
        current = self.berco_filter.currentData()
        values = sorted({row["berco"] for row in self.rows if not selected_pier or row["pier"] == selected_pier})
        self.berco_filter.blockSignals(True)
        self.berco_filter.clear()
        self.berco_filter.addItem("Todos os berços", "")
        for value in values:
            self.berco_filter.addItem(value, value)
        index = self.berco_filter.findData(current)
        self.berco_filter.setCurrentIndex(index if index >= 0 else 0)
        self.berco_filter.blockSignals(False)
        self._render_rows()

    def _matches_filters(self, row: dict) -> bool:
        pier = _text(self.pier_filter.currentData())
        berco = _text(self.berco_filter.currentData())
        if pier and row["pier"] != pier:
            return False
        if berco and row["berco"] != berco:
            return False
        vehicle = row.get("vehicle") or {}
        state = vehicle.get("operational_state") or {}
        selected_status = _text(self.status_filter.currentData())
        status = _text(state.get("operational_status") or "SEM_APONTAMENTO").upper()
        if selected_status and status != selected_status:
            return False
        query = self.search.text().strip().casefold()
        if query:
            searchable = " ".join(
                _text(value)
                for value in (
                    _vehicle_label(vehicle), vehicle.get("serial_number"), row["pier"], row["berco"],
                    " ".join(self.spreader_links.get(vehicle.get("id"), {}).get("ACOPLADO", [])),
                    " ".join(self.spreader_links.get(vehicle.get("id"), {}).get("RESERVA", [])),
                )
            ).casefold()
            if query not in searchable:
                return False
        return True

    def refresh(self):
        try:
            overview = self.api_client.get_availability_overview() or {}
            rows = []
            for raw_row in overview.get("rows", []):
                if not _family_match(raw_row):
                    continue
                pier, berco = _location_parts(raw_row)
                rows.append({**raw_row, "pier": pier, "berco": berco})
            self.rows = rows
            self._load_spreader_links()
            current_pier = self.pier_filter.currentData()
            self.pier_filter.blockSignals(True)
            self.pier_filter.clear()
            self.pier_filter.addItem("Todos os píeres", "")
            for pier in sorted({row["pier"] for row in rows}):
                self.pier_filter.addItem(pier, pier)
            index = self.pier_filter.findData(current_pier)
            self.pier_filter.setCurrentIndex(index if index >= 0 else 0)
            self.pier_filter.blockSignals(False)
            self._refresh_berco_filter()
        except Exception as exc:
            show_notice(self, "Falha ao carregar painel LBS", str(exc), icon_name="warning")

    def _load_spreader_links(self):
        self.spreader_links = {}
        getter = getattr(self.api_client, "get_equipment_links", None)
        if not getter:
            return
        try:
            links = getter(active=True) or []
        except Exception:
            return
        for link in links:
            parent_id = link.get("parent_vehicle_id")
            child = link.get("child_equipment") or {}
            if parent_id is None or not child:
                continue
            link_type = _text(link.get("link_type") or "OUTRO").upper()
            if link_type not in {"ACOPLADO", "RESERVA", "TITULAR"}:
                continue
            label = _vehicle_label(child)
            if child.get("serial_number"):
                label = f"{label} (série {child['serial_number']})"
            bucket = self.spreader_links.setdefault(int(parent_id), {"ACOPLADO": [], "RESERVA": []})
            bucket["ACOPLADO" if link_type == "ACOPLADO" else "RESERVA"].append(label)

    def _render_rows(self):
        visible_rows = [row for row in self.rows if self._matches_filters(row)]
        available = 0
        stopped = 0
        measured: list[float] = []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible_rows))
        for index, row in enumerate(visible_rows):
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            status = _text(state.get("operational_status") or "SEM_APONTAMENTO").upper()
            if status in {"DISPONIVEL", "RESTRICAO"}:
                available += 1
            if status in STOP_STATUSES:
                stopped += 1
            if row.get("availability_percentage") is not None:
                measured.append(float(row["availability_percentage"]))
            links = self.spreader_links.get(vehicle.get("id"), {})
            attached = ", ".join(links.get("ACOPLADO", [])) or "-"
            reserve = ", ".join(links.get("RESERVA", [])) or "-"
            values = [
                row["pier"], row["berco"], _vehicle_label(vehicle), _text(vehicle.get("serial_number")) or "-",
                attached, reserve, STATUS_LABELS.get(status, status),
                f"{state['latest_hourmeter']:.2f} h" if state.get("latest_hourmeter") is not None else "-",
                _text(state.get("status_reason")) or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 6:
                    background, foreground = STATUS_COLORS.get(status, STATUS_COLORS["SEM_APONTAMENTO"])
                    item.setBackground(QColor(background))
                    item.setForeground(QColor(foreground))
                self.table.setItem(index, column, item)
            action = QPushButton("Ver parada" if status in STOP_STATUSES else "Abrir controle")
            action.clicked.connect(lambda _checked=False: self.open_page_requested.emit(self.downtime_page_key))
            self.table.setCellWidget(index, 9, action)
        average = sum(measured) / len(measured) if measured else None
        self.total_card.set_content("Equipamentos", str(len(visible_rows)), "Ativos LBS")
        self.available_card.set_content("Disponíveis", str(available), "Disponível ou restrição")
        self.stopped_card.set_content("Em parada", str(stopped), "Indisponível ou manutenção")
        self.measured_card.set_content("Disponibilidade", f"{average:.2f}%" if average is not None else "-", "Média no período")
