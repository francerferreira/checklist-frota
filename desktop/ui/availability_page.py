from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QTableWidget, QVBoxLayout

from components import StatCard, TableSkeletonOverlay
from theme import configure_table, make_table_item, style_table_card


STATUS_LABELS = {
    "SEM_APONTAMENTO": "Sem apontamento",
    "DISPONIVEL": "Disponível",
    "INDISPONIVEL": "Indisponível",
    "RESTRICAO": "Com restrição",
    "MANUTENCAO": "Em manutenção",
}
STATUS_COLORS = {
    "DISPONIVEL": ("#DCFCE7", "#166534"),
    "INDISPONIVEL": ("#FEE2E2", "#991B1B"),
    "RESTRICAO": ("#FEF3C7", "#92400E"),
    "MANUTENCAO": ("#E2E8F0", "#334155"),
    "SEM_APONTAMENTO": ("#F1F5F9", "#64748B"),
}


class AvailabilityPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        title = QLabel("Disponibilidade Operacional")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Visão consolidada dos equipamentos por família e local. Os apontamentos são realizados no web mobile."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        cards = QGridLayout()
        cards.setSpacing(14)
        self.total_card = StatCard("Equipamentos", "0", "Ativos com cadastro unificado", icon_name="equipment")
        self.available_card = StatCard("Disponíveis", "0", "Operação normal ou com restrição", icon_name="dashboard")
        self.unavailable_card = StatCard("Indisponíveis", "0", "Indisponíveis ou em manutenção", icon_name="warning")
        self.average_card = StatCard("Disponibilidade média", "-", "Somente períodos com apontamento", icon_name="reports")
        for column, card in enumerate((self.total_card, self.available_card, self.unavailable_card, self.average_card)):
            cards.addWidget(card, 0, column)
            cards.setColumnStretch(column, 1)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_title = QLabel("Mapa operacional")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel("Sem apontamento significa que ainda não existe medição, e não que o equipamento está disponível.")
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Local", "Família", "Equipamento", "Status", "Atualizado em", "Horímetro", "Disponibilidade"]
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
        layout.addWidget(table_card, 1)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando disponibilidade")
        else:
            self.table_skeleton.hide_skeleton()

    @staticmethod
    def _datetime(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:16]

    def refresh(self):
        overview = self.api_client.get_availability_overview()
        summary = overview.get("summary", {})
        counts = summary.get("status_counts", {})
        available = int(counts.get("DISPONIVEL", 0)) + int(counts.get("RESTRICAO", 0))
        unavailable = int(counts.get("INDISPONIVEL", 0)) + int(counts.get("MANUTENCAO", 0))
        average = summary.get("average_availability_percentage")
        self.total_card.set_content("Equipamentos", str(summary.get("total", 0)), "Ativos com cadastro unificado")
        self.available_card.set_content("Disponíveis", str(available), "Operação normal ou com restrição")
        self.unavailable_card.set_content("Indisponíveis", str(unavailable), "Indisponíveis ou em manutenção")
        self.average_card.set_content(
            "Disponibilidade média", f"{average:.2f}%" if average is not None else "-",
            f"{summary.get('measured_equipment', 0)} equipamentos medidos",
        )
        rows = overview.get("rows", [])
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            status = state.get("operational_status") or "SEM_APONTAMENTO"
            availability = row.get("availability_percentage")
            values = [
                (row.get("location") or {}).get("full_name") or "Sem local",
                (row.get("family") or {}).get("name") or vehicle.get("tipo") or "-",
                vehicle.get("frota") or vehicle.get("placa") or "-",
                STATUS_LABELS.get(status, status), self._datetime(state.get("status_updated_at")),
                f"{state['latest_hourmeter']:.2f} h" if state.get("latest_hourmeter") is not None else "-",
                f"{availability:.2f}%" if availability is not None else "Sem medição",
            ]
            for column, value in enumerate(values):
                item = make_table_item(str(value))
                if column == 3:
                    background, foreground = STATUS_COLORS.get(status, STATUS_COLORS["SEM_APONTAMENTO"])
                    item.setBackground(QBrush(QColor(background)))
                    item.setForeground(QBrush(QColor(foreground)))
                self.table.setItem(row_index, column, item)
        self.table.setSortingEnabled(True)
