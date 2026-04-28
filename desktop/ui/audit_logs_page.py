from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, show_notice
from theme import configure_table, make_table_item, style_card, style_filter_bar, style_table_card


def _apply_light_date_popup_style(date_edit: QDateEdit):
    calendar_widget = date_edit.calendarWidget()
    if not calendar_widget:
        return
    calendar_widget.setStyleSheet(
        """
        QCalendarWidget { background: #F4F8FE; color: #0F3A68; }
        QCalendarWidget QWidget { background: #F4F8FE; color: #0F3A68; }
        QCalendarWidget QToolButton {
            background: #E8F1FC; color: #0F3A68; border: 1px solid #8FB2D9; border-radius: 2px; padding: 4px 8px; font-weight: 700;
        }
        QCalendarWidget QToolButton:hover { background: #D9EAFF; border: 1px solid #5F92C9; }
        QCalendarWidget QMenu { background: #FFFFFF; color: #0F3A68; }
        QCalendarWidget QSpinBox { background: #FFFFFF; color: #0F3A68; border: 1px solid #8FB2D9; border-radius: 2px; }
        QCalendarWidget QAbstractItemView {
            background: #FFFFFF; color: #0F3A68; selection-background-color: #1F6FCA; selection-color: #FFFFFF; border: 1px solid #9FBFE1; outline: 0;
        }
        """
    )


class AuditLogsPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setObjectName("ContentSurface")
        style_card(self)

        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Logs de Auditoria")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Historico completo de login/logout, criacao, edicao e exclusao no sistema.")
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)
        header.addLayout(text_wrap)
        header.addStretch()

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(8)

        self.entity_filter = QComboBox()
        self.entity_filter.addItem("Todas as entidades", "")
        self.entity_filter.addItem("Sessoes (login/logout)", "SESSION")
        self.entity_filter.addItem("Usuarios", "USER")
        self.entity_filter.addItem("Veiculos", "VEHICLE")
        self.entity_filter.addItem("Checklist", "CHECKLIST")
        self.entity_filter.addItem("Itens de Checklist", "CHECKLIST_ITEM")
        self.entity_filter.addItem("Atividades", "ACTIVITY")
        self.entity_filter.addItem("Itens de Atividade", "ACTIVITY_ITEM")
        self.entity_filter.addItem("Manutencao", "MAINTENANCE_SCHEDULE")
        self.entity_filter.addItem("Itens de Manutencao", "MAINTENANCE_SCHEDULE_ITEM")
        self.entity_filter.addItem("Materiais", "MATERIAL")
        self.entity_filter.addItem("Movimentos de Material", "MATERIAL_MOVEMENT")
        self.entity_filter.addItem("Lavagens", "WASH_RECORD")
        self.entity_filter.setMinimumHeight(34)
        self.entity_filter.currentIndexChanged.connect(self._schedule_refresh)

        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.start_date_filter.setMinimumHeight(34)
        self.start_date_filter.setDate(QDate.currentDate().addDays(-30))
        self.start_date_filter.dateChanged.connect(self._schedule_refresh)
        _apply_light_date_popup_style(self.start_date_filter)

        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDisplayFormat("dd/MM/yyyy")
        self.end_date_filter.setMinimumHeight(34)
        self.end_date_filter.setDate(QDate.currentDate())
        self.end_date_filter.dateChanged.connect(self._schedule_refresh)
        _apply_light_date_popup_style(self.end_date_filter)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.setMinimumHeight(34)
        refresh_button.clicked.connect(self.refresh)

        filter_layout.addWidget(self.entity_filter, 2)
        filter_layout.addWidget(QLabel("De:"))
        filter_layout.addWidget(self.start_date_filter)
        filter_layout.addWidget(QLabel("Ate:"))
        filter_layout.addWidget(self.end_date_filter)
        filter_layout.addWidget(refresh_button)

        card = QFrame()
        style_table_card(card)
        self.audit_skeleton = TableSkeletonOverlay(card, rows=8)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        self.audit_table = QTableWidget(0, 6)
        self.audit_table.setHorizontalHeaderLabels(
            ["Data/Hora", "Usuario", "Entidade", "ID da Entidade", "Acao", "Valores (Antigo -> Novo)"]
        )
        configure_table(self.audit_table, stretch_last=False)
        self.audit_table.setMinimumHeight(520)

        card_layout.addWidget(self.audit_table)

        layout.addLayout(header)
        layout.addWidget(filter_card)
        layout.addWidget(card, 1)

    def _schedule_refresh(self, *_args):
        self._live_filter_timer.start(220)

    def set_loading_state(self, loading: bool):
        if loading:
            self.audit_skeleton.show_skeleton("Carregando logs de auditoria")
        else:
            self.audit_skeleton.hide_skeleton()

    def refresh(self):
        if not self.api_client.user_has_admin_access():
            self.audit_table.setRowCount(0)
            return
        try:
            self.audit_skeleton.show_skeleton("Carregando logs de auditoria")
            logs = self.api_client.get_audit_logs(
                entidade=self.entity_filter.currentData() or None,
                data_inicio=self.start_date_filter.date().toString("yyyy-MM-dd"),
                data_fim=self.end_date_filter.date().toString("yyyy-MM-dd"),
            )
            self.audit_table.setSortingEnabled(False)
            self.audit_table.setUpdatesEnabled(False)
            self.audit_table.setRowCount(len(logs))
            for row, log in enumerate(logs):
                values = [
                    self._format(log.get("created_at")),
                    log.get("user") or "Sistema",
                    log.get("entity_type") or "-",
                    str(log.get("entity_id") or "-"),
                    log.get("action") or "-",
                    f"{log.get('old_value')} -> {log.get('new_value')}",
                ]
                for col, val in enumerate(values):
                    self.audit_table.setItem(row, col, make_table_item(val))
        except Exception as exc:
            show_notice(self, "Falha ao carregar logs", str(exc), icon_name="warning")
        finally:
            self.audit_table.setUpdatesEnabled(True)
            self.audit_table.setSortingEnabled(True)
            self.audit_skeleton.hide_skeleton()

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return str(value).replace("T", " ")[:19]
