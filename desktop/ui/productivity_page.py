from __future__ import annotations

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

from components import StatCard, TableSkeletonOverlay
from theme import configure_table, make_table_item, style_table_card


class ProductivityPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.report = {"resumo": {}, "usuarios": []}
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Produtividade")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Acompanhe atuações de motoristas e mecânicos em checklist, manutenção, não conformidades e lavagens."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setMinimumHeight(34)
        refresh_button.clicked.connect(self.refresh)

        header.addLayout(text_wrap, 1)
        header.addWidget(refresh_button)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)
        self.users_card = StatCard("Usuários monitorados", "0", "Motoristas e mecânicos ativos", icon_name="users")
        self.checklists_card = StatCard("Checklists", "0", "Registros feitos por motorista", icon_name="reports")
        self.resolved_card = StatCard("Não conformidades resolvidas", "0", "Checklist e não conformidade interna mecânica", icon_name="ok")
        self.actions_card = StatCard("Atuações totais", "0", "Soma operacional da produtividade", icon_name="dashboard")
        cards_layout.addWidget(self.users_card, 0, 0)
        cards_layout.addWidget(self.checklists_card, 0, 1)
        cards_layout.addWidget(self.resolved_card, 0, 2)
        cards_layout.addWidget(self.actions_card, 0, 3)

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=8)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        table_top = QHBoxLayout()
        table_title = QLabel("Ranking operacional")
        table_title.setObjectName("SectionTitle")
        self.badge = QLabel("0 registros")
        self.badge.setObjectName("TopBarPill")
        table_top.addWidget(table_title)
        table_top.addStretch()
        table_top.addWidget(self.badge)

        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(
            [
                "Usuário",
                "Perfil",
                "Pontos",
                "Checklists",
                "Não conformidades criadas",
                "Não conformidades resolvidas",
                "Ativ. exec.",
                "Instalados",
                "Não instal.",
                "Direcionadas",
                "Dir. abertas",
                "Não conformidades internas abertas",
                "Não conformidades internas resolvidas",
                "Lavagens",
            ]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(560)

        table_layout.addLayout(table_top)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addLayout(cards_layout)
        layout.addWidget(table_card, 1)

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando produtividade")
        else:
            self.table_skeleton.hide_skeleton()

    def refresh(self):
        self.report = self.api_client.get_productivity_report()
        resumo = self.report.get("resumo", {})
        rows = self.report.get("usuarios", [])

        self.users_card.set_content("Usuários monitorados", str(resumo.get("usuarios", 0)), "Motoristas e mecânicos ativos")
        self.checklists_card.set_content("Checklists", str(resumo.get("checklists", 0)), "Registros feitos por motorista")
        self.resolved_card.set_content("Não conformidades resolvidas", str(resumo.get("nc_resolvidas", 0)), "Checklist e não conformidade interna mecânica")
        self.actions_card.set_content("Atuações totais", str(resumo.get("pontuacao", 0)), "Soma operacional da produtividade")
        self.badge.setText(f"{len(rows)} usuários")

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                user = item.get("user", {})
                values = [
                    user.get("nome") or "-",
                    (user.get("tipo") or "-").title(),
                    str(item.get("pontuacao", 0)),
                    str(item.get("checklists", 0)),
                    str(item.get("nc_registradas", 0)),
                    str(item.get("nc_resolvidas", 0)),
                    str(item.get("atividades_executadas", 0)),
                    str(item.get("instalados", 0)),
                    str(item.get("nao_instalados", 0)),
                    str(item.get("atividades_direcionadas", 0)),
                    str(item.get("direcionadas_abertas", 0)),
                    str(item.get("nc_mecanico_abertas", 0)),
                    str(item.get("nc_mecanico_resolvidas", 0)),
                    str(item.get("lavagens", 0)),
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 2:
                        cell.setBackground(QBrush(QColor("#DBEAFE")))
                        cell.setForeground(QBrush(QColor("#1D4ED8")))
                    self.table.setItem(row_index, column, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)


