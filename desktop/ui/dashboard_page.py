from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import MessageComposerDialog, StatCard, TableSkeletonOverlay, make_icon
from services import build_automation_alert_message_package, overall_executive_status, severity_from_counts
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


def _format_hours(value) -> str:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return "Sem dados"
    if hours < 0:
        return "Sem dados"
    whole_hours, minutes = divmod(int(round(hours * 60)), 60)
    return f"{whole_hours}h {minutes:02d}m"


class DashboardPage(QFrame):
    alert_open_requested = Signal(dict)
    web_mobile_requested = Signal()
    tv_dashboard_requested = Signal()

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
        self.hero_badge.setObjectName("BadgeStrong")

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

        quick_access_wrap = QVBoxLayout()
        quick_access_wrap.setContentsMargins(0, 0, 0, 0)
        quick_access_wrap.setSpacing(8)
        quick_access_title = QLabel("Acessos rápidos")
        quick_access_title.setObjectName("CardTitle")
        self.web_mobile_button = QPushButton("Web Mobile")
        self.web_mobile_button.setObjectName("open-web-mobile-button")
        self.web_mobile_button.setProperty("variant", "primary")
        self.web_mobile_button.setIcon(make_icon("dashboard", "#FFFFFF", "#115FC0", 18))
        self.web_mobile_button.setIconSize(QSize(18, 18))
        self.web_mobile_button.setToolTip("Abrir o Web Mobile no navegador")
        self.web_mobile_button.clicked.connect(self.web_mobile_requested.emit)
        self.tv_dashboard_button = QPushButton("Dashboard TV")
        self.tv_dashboard_button.setObjectName("open-tv-dashboard-button")
        self.tv_dashboard_button.setProperty("variant", "success")
        self.tv_dashboard_button.setIcon(make_icon("reports", "#FFFFFF", "#159789", 18))
        self.tv_dashboard_button.setIconSize(QSize(18, 18))
        self.tv_dashboard_button.setToolTip("Abrir o Dashboard TV no navegador")
        self.tv_dashboard_button.clicked.connect(self.tv_dashboard_requested.emit)
        quick_access_wrap.addWidget(quick_access_title)
        quick_access_wrap.addWidget(self.web_mobile_button)
        quick_access_wrap.addWidget(self.tv_dashboard_button)
        hero_layout.addLayout(quick_access_wrap, 0)

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
            "NC convertidas em inspeção",
            "0",
            "Ocorrências com tratativa formal iniciada",
            icon_name="activities",
        )
        self.unlinked_nc_card = StatCard(
            "NC sem inspeção",
            "0",
            "Ocorrências sem abertura no módulo de inspeções",
            icon_name="warning",
        )
        self.nc_to_activity_time_card = StatCard(
            "Tempo médio NC -> inspeção",
            "-",
            "Velocidade média para iniciar tratativa",
            icon_name="dashboard",
        )
        self.activity_to_resolution_time_card = StatCard(
            "Tempo médio inspeção -> resolução",
            "-",
            "Tempo médio da inspeção até a finalização",
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
        self.table_badge.setObjectName("BadgeSoft")

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

        intelligence_layout = QGridLayout()
        intelligence_layout.setSpacing(16)
        for column in range(4):
            intelligence_layout.setColumnStretch(column, 1)
        self.availability_card = StatCard("Disponibilidade média", "Sem dados", "Ativos com status medido no período", icon_name="equipment")
        self.mtbf_card = StatCard("MTBF", "Sem dados", "Tempo médio entre falhas comparáveis", icon_name="dashboard")
        self.mttr_card = StatCard("MTTR", "Sem dados", "Tempo médio de reparo até a liberação", icon_name="activities")
        self.backlog_card = StatCard("Backlog de manutenção", "0", "OS abertas, vencidas e bloqueadas", icon_name="warning")
        intelligence_layout.addWidget(self.availability_card, 0, 0)
        intelligence_layout.addWidget(self.mtbf_card, 0, 1)
        intelligence_layout.addWidget(self.mttr_card, 0, 2)
        intelligence_layout.addWidget(self.backlog_card, 0, 3)

        self.automation_card = QFrame()
        style_table_card(self.automation_card)
        automation_layout = QVBoxLayout(self.automation_card)
        automation_layout.setContentsMargins(14, 14, 14, 14)
        automation_layout.setSpacing(10)
        automation_header = QHBoxLayout()
        automation_title = QLabel("Alertas automáticos")
        automation_title.setObjectName("SectionTitle")
        self.automation_badge = QLabel("0 ativos")
        self.automation_badge.setObjectName("BadgeSoft")
        self.run_automation_button = QPushButton("Avaliar regras")
        self.run_automation_button.clicked.connect(self.evaluate_automations)
        self.share_automation_button = QPushButton("Compartilhar alertas")
        self.share_automation_button.clicked.connect(self.share_automation_alerts)
        automation_header.addWidget(automation_title)
        automation_header.addStretch()
        automation_header.addWidget(self.automation_badge)
        automation_header.addWidget(self.run_automation_button)
        automation_header.addWidget(self.share_automation_button)
        automation_hint = QLabel("Leitura auditável de emergenciais críticos, preventivas vencidas e estoque abaixo do mínimo.")
        automation_hint.setObjectName("SectionCaption")
        automation_hint.setWordWrap(True)
        self.automation_table = QTableWidget(0, 5)
        self.automation_table.setHorizontalHeaderLabels(["Regra", "Severidade", "Referência", "Alerta", "Estado"])
        configure_table(self.automation_table, stretch_last=False)
        self.automation_table.setMinimumHeight(220)
        self.automation_table.itemDoubleClicked.connect(self.open_automation_alert)
        automation_layout.addLayout(automation_header)
        automation_layout.addWidget(automation_hint)
        automation_layout.addWidget(self.automation_table)

        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addWidget(hero_card)
        layout.addLayout(cards_layout)
        layout.addLayout(conversion_layout)
        layout.addLayout(intelligence_layout)
        layout.addWidget(self.table_card, 1)
        layout.addWidget(self.automation_card)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando itens críticos")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self):
        dashboard = self.api_client.get_dashboard()
        intelligence = dashboard.get("manutencao_portuaria") or {}
        reliability = intelligence.get("confiabilidade") or {}
        availability = intelligence.get("disponibilidade") or {}
        backlog = intelligence.get("backlog") or {}
        automations = intelligence.get("automacoes") or {}
        self.automation_alerts = automations.get("alertas") or []
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
            "NC convertidas em inspeção",
            str(dashboard.get("nc_convertidas_em_atividade", 0)),
            "Ocorrências com tratativa formal iniciada",
        )
        self.unlinked_nc_card.set_content(
            "NC sem inspeção",
            str(dashboard.get("nc_sem_atividade", 0)),
            "Ocorrências sem abertura no módulo de inspeções",
        )
        self.nc_to_activity_time_card.set_content(
            "Tempo médio NC -> inspeção",
            _format_minutes(dashboard.get("tempo_medio_nc_para_atividade_minutos")),
            "Velocidade média para iniciar tratativa",
        )
        self.activity_to_resolution_time_card.set_content(
            "Tempo médio inspeção -> resolução",
            _format_minutes(dashboard.get("tempo_medio_atividade_para_resolucao_minutos")),
            "Tempo médio da inspeção até a finalização",
        )
        availability_value = availability.get("average_availability_percentage")
        self.availability_card.set_content(
            "Disponibilidade média",
            f"{availability_value:.2f}%" if isinstance(availability_value, (int, float)) else "Sem dados",
            f"{availability.get('measured_equipment', 0)} equipamentos com medição",
        )
        self.mtbf_card.set_content("MTBF", _format_hours(reliability.get("mtbf_horas")), "Tempo médio entre falhas comparáveis")
        self.mttr_card.set_content("MTTR", _format_hours(reliability.get("mttr_horas")), "Tempo médio de reparo até a liberação")
        self.backlog_card.set_content(
            "Backlog de manutenção",
            str(backlog.get("total", 0)),
            f"{backlog.get('vencidas', 0)} vencidas | {backlog.get('materiais_bloqueados', 0)} bloqueadas",
        )
        self.automation_badge.setText(f"{automations.get('alertas_ativos', 0)} ativos | {automations.get('alertas_criticos', 0)} críticos")
        self.run_automation_button.setVisible(bool(getattr(self.api_client, "user_has_management_access", lambda: False)()))
        self.share_automation_button.setVisible(bool(getattr(self.api_client, "user_has_management_access", lambda: False)()))
        self._fill_automation_alerts(self.automation_alerts)

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
                        if severity["label"] == "Alta":
                            cell.setBackground(QBrush(QColor("#E7E9EC")))
                            cell.setForeground(QBrush(QColor("#2F3A47")))
                        elif severity["label"] == "Moderada":
                            cell.setBackground(QBrush(QColor("#EFF1F4")))
                            cell.setForeground(QBrush(QColor("#44515F")))
                        else:
                            cell.setBackground(QBrush(QColor("#F4F5F7")))
                            cell.setForeground(QBrush(QColor("#5B6775")))
                    self.critical_table.setItem(row, column, cell)
        finally:
            self.critical_table.blockSignals(False)
            self.critical_table.setUpdatesEnabled(True)
            self.critical_table.setSortingEnabled(True)

    def _fill_automation_alerts(self, alerts):
        self.automation_table.setSortingEnabled(False)
        self.automation_table.setRowCount(len(alerts))
        for row_index, alert in enumerate(alerts):
            values = [
                str(alert.get("rule_code") or "-"),
                str(alert.get("severity") or "-"),
                f"{alert.get('entity_type') or '-'} #{alert.get('entity_id') or '-'}",
                str(alert.get("message") or "-"),
                str(alert.get("status") or "-"),
            ]
            for column, value in enumerate(values):
                self.automation_table.setItem(row_index, column, make_table_item(value, payload=alert if column == 0 else None))
        self.automation_table.setSortingEnabled(True)

    def open_automation_alert(self, *_):
        rows = self.automation_table.selectedRanges()
        if not rows:
            return
        item = self.automation_table.item(rows[0].topRow(), 0)
        alert = item.data(Qt.UserRole) if item else None
        if alert:
            self.alert_open_requested.emit(alert)

    def evaluate_automations(self):
        self.api_client.evaluate_automation_rules()
        self.refresh()

    def share_automation_alerts(self):
        user = getattr(self.api_client, "user", {}) or {}
        package = build_automation_alert_message_package(
            getattr(self, "automation_alerts", []),
            generated_by=str(user.get("nome") or user.get("login") or ""),
        )
        MessageComposerDialog(package, self).exec()


