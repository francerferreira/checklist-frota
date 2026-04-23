from __future__ import annotations

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import StatCard, TableSkeletonOverlay
from services import overall_executive_status, severity_from_counts
from theme import configure_table, make_table_item, style_card, style_table_card


def _format_minutes(value) -> str:
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        return "-"
    if minutes < 0:
        return "-"
    rounded = int(round(minutes))
    hours, rem_minutes = divmod(rounded, 60)
    if hours > 0:
        return f"{hours}h {rem_minutes:02d}m"
    return f"{rem_minutes}m"


class DashboardPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        heading = QLabel("Dashboard Executivo")
        heading.setObjectName("PageTitle")

        subtitle = QLabel(
            "Vis\u00e3o consolidada da opera\u00e7\u00e3o, com foco em n\u00e3o conformidades, ativos afetados e velocidade de resposta."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        hero_card = QFrame()
        style_card(hero_card)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(18)

        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(4)

        hero_title = QLabel("Indicadores cr\u00edticos do turno")
        hero_title.setObjectName("SectionTitle")

        hero_caption = QLabel(
            "Acompanhe rapidamente a sa\u00fade da frota, priorize gargalos e direcione a manuten\u00e7\u00e3o para os itens mais sens\u00edveis."
        )
        hero_caption.setObjectName("SectionCaption")
        hero_caption.setWordWrap(True)

        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_caption)

        self.hero_badge = QLabel("Status operacional")
        self.hero_badge.setStyleSheet(
            "background:#0F172A; color:#FFFFFF; border-radius:16px; padding:10px 14px; font-size:12px; font-weight:700;"
        )

        hero_layout.addLayout(hero_text, 1)
        semaforo_wrap = QVBoxLayout()
        semaforo_wrap.setContentsMargins(0, 0, 0, 0)
        semaforo_wrap.setSpacing(8)
        semaforo_title = QLabel("Semáforo executivo")
        semaforo_title.setObjectName("CardTitle")
        self.hero_badge.setMinimumWidth(170)
        self.severity_strip = QLabel("Alta: 0  •  Moderada: 0  •  Controlada: 0")
        self.severity_strip.setObjectName("MutedText")
        self.severity_strip.setWordWrap(True)
        semaforo_wrap.addWidget(semaforo_title)
        semaforo_wrap.addWidget(self.hero_badge)
        semaforo_wrap.addWidget(self.severity_strip)
        hero_layout.addLayout(semaforo_wrap, 0)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)
        cards_layout.setColumnStretch(0, 1)
        cards_layout.setColumnStretch(1, 1)
        cards_layout.setColumnStretch(2, 1)

        self.total_nc_card = StatCard(
            "Total de não conformidades",
            "0",
            "Ocorr\u00eancias acumuladas na base operacional",
            icon_name="warning",
        )
        self.open_nc_card = StatCard(
            "Não conformidades em aberto",
            "0",
            "Demandas pendentes de tratativa ou pe\u00e7a",
            icon_name="reports",
        )
        self.vehicles_card = StatCard(
            "Ve\u00edculos com falha",
            "0",
            "Ativos impactados por n\u00e3o conformidades",
            icon_name="equipment",
        )

        cards_layout.addWidget(self.total_nc_card, 0, 0)
        cards_layout.addWidget(self.open_nc_card, 0, 1)
        cards_layout.addWidget(self.vehicles_card, 0, 2)

        conversion_layout = QGridLayout()
        conversion_layout.setSpacing(16)
        for column in range(4):
            conversion_layout.setColumnStretch(column, 1)

        self.converted_nc_card = StatCard(
            "NC convertidas em atividade",
            "0",
            "Ocorrencias com tratativa formal iniciada",
            icon_name="activities",
        )
        self.unlinked_nc_card = StatCard(
            "NC sem atividade",
            "0",
            "Ocorrencias sem abertura no modulo de atividades",
            icon_name="warning",
        )
        self.nc_to_activity_time_card = StatCard(
            "Tempo medio NC -> atividade",
            "-",
            "Velocidade media para iniciar tratativa",
            icon_name="dashboard",
        )
        self.activity_to_resolution_time_card = StatCard(
            "Tempo medio atividade -> resolucao",
            "-",
            "Tempo medio da atividade ate a finalizacao",
            icon_name="reports",
        )
        conversion_layout.addWidget(self.converted_nc_card, 0, 0)
        conversion_layout.addWidget(self.unlinked_nc_card, 0, 1)
        conversion_layout.addWidget(self.nc_to_activity_time_card, 0, 2)
        conversion_layout.addWidget(self.activity_to_resolution_time_card, 0, 3)

        self.table_card = QFrame()
        style_table_card(self.table_card)
        self.table_skeleton = TableSkeletonOverlay(self.table_card, rows=6)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        table_title = QLabel("Itens cr\u00edticos")
        table_title.setObjectName("SectionTitle")

        self.table_badge = QLabel("Top recorr\u00eancia")
        self.table_badge.setStyleSheet(
            "background:#EFF6FF; color:#1D4ED8; border-radius:14px; padding:7px 12px; font-size:12px; font-weight:700;"
        )

        top_row.addWidget(table_title)
        top_row.addStretch()
        top_row.addWidget(self.table_badge)

        table_caption = QLabel(
            "Componentes com maior incid\u00eancia de falha e distribui\u00e7\u00e3o entre registros abertos e resolvidos."
        )
        table_caption.setObjectName("SectionCaption")

        self.critical_table = QTableWidget(0, 5)
        self.critical_table.setHorizontalHeaderLabels(
            ["Item", "Não conformidades", "Abertas", "Resolvidas", "Prioridade"]
        )
        configure_table(self.critical_table, stretch_last=False)
        self.critical_table.setMinimumHeight(500)

        table_layout.addLayout(top_row)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.critical_table)

        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addWidget(hero_card)
        layout.addLayout(cards_layout)
        layout.addLayout(conversion_layout)
        layout.addWidget(self.table_card, 1)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando itens críticos")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self):
        dashboard = self.api_client.get_dashboard()
        self.total_nc_card.set_content(
            "Total de não conformidades",
            str(dashboard["total_nc"]),
            "Ocorr\u00eancias acumuladas na base operacional",
        )
        self.open_nc_card.set_content(
            "Não conformidades em aberto",
            str(dashboard["nc_abertas"]),
            "Demandas pendentes de tratativa ou pe\u00e7a",
        )
        self.vehicles_card.set_content(
            "Ve\u00edculos com falha",
            str(dashboard["veiculos_com_falha"]),
            "Ativos impactados por n\u00e3o conformidades",
        )
        self.converted_nc_card.set_content(
            "NC convertidas em atividade",
            str(dashboard.get("nc_convertidas_em_atividade", 0)),
            "Ocorrencias com tratativa formal iniciada",
        )
        self.unlinked_nc_card.set_content(
            "NC sem atividade",
            str(dashboard.get("nc_sem_atividade", 0)),
            "Ocorrencias sem abertura no modulo de atividades",
        )
        self.nc_to_activity_time_card.set_content(
            "Tempo medio NC -> atividade",
            _format_minutes(dashboard.get("tempo_medio_nc_para_atividade_minutos")),
            "Velocidade media para iniciar tratativa",
        )
        self.activity_to_resolution_time_card.set_content(
            "Tempo medio atividade -> resolucao",
            _format_minutes(dashboard.get("tempo_medio_atividade_para_resolucao_minutos")),
            "Tempo medio da atividade ate a finalizacao",
        )

        critical_items = dashboard.get("itens_criticos", [])
        executive = overall_executive_status(
            critical_items,
            total=dashboard.get("total_nc", 0),
            open_total=dashboard.get("nc_abertas", 0),
        )
        self.hero_badge.setText(executive["label"])
        self.hero_badge.setStyleSheet(executive["style"])

        severity_counts = {"Alta": 0, "Moderada": 0, "Controlada": 0}
        for item in critical_items:
            severity_counts[severity_from_counts(item.get("total_nc", 0), item.get("abertas", 0))["label"]] += 1
        self.severity_strip.setText(
            f"Alta: {severity_counts['Alta']}  •  Moderada: {severity_counts['Moderada']}  •  Controlada: {severity_counts['Controlada']}"
        )

        if critical_items:
            self.table_badge.setText(f"L\u00edder: {critical_items[0]['item_nome']}")
        else:
            self.table_badge.setText("Sem itens cr\u00edticos")

        self.critical_table.setSortingEnabled(False)
        self.critical_table.setUpdatesEnabled(False)
        self.critical_table.blockSignals(True)
        try:
            self.critical_table.setRowCount(len(critical_items))
            for row, item in enumerate(critical_items):
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
                    if column == 4:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.critical_table.setItem(row, column, cell)
        finally:
            self.critical_table.blockSignals(False)
            self.critical_table.setUpdatesEnabled(True)
            self.critical_table.setSortingEnabled(True)


