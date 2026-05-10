from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, show_notice
from theme import configure_table, make_table_item, style_card, style_filter_bar, style_table_card


class AdminRulesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.rules = {}
        self.compatibility = {}
        self.setObjectName("ContentSurface")
        style_card(self)

        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.timeout.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Configuração Administrativa")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Ajuste a régua das regras inteligentes e acompanhe se os dados antigos continuam compatíveis com o fluxo novo."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)
        header.addLayout(text_wrap)
        header.addStretch()

        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setMinimumHeight(34)
        self.refresh_button.clicked.connect(self.refresh)
        self.save_button = QPushButton("Salvar regras")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setMinimumHeight(34)
        self.save_button.clicked.connect(self.save_rules)
        header.addWidget(self.refresh_button)
        header.addWidget(self.save_button)

        summary_card = QFrame()
        style_filter_bar(summary_card)
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)
        self.window_badge = QLabel("Janela -")
        self.window_badge.setObjectName("TopBarPill")
        self.weight_badge = QLabel("Peso -")
        self.weight_badge.setObjectName("TopBarPill")
        self.alert_badge = QLabel("Alertas -")
        self.alert_badge.setObjectName("TopBarPill")
        self.compat_badge = QLabel("Compatibilidade -")
        self.compat_badge.setObjectName("TopBarPill")
        for badge in (self.window_badge, self.weight_badge, self.alert_badge, self.compat_badge):
            summary_layout.addWidget(badge)
        summary_layout.addStretch()

        form_card = QFrame()
        style_table_card(form_card)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(10)

        self.recurrence_window_spin = QSpinBox()
        self.recurrence_window_spin.setMinimum(1)
        self.recurrence_window_spin.setMaximum(180)
        self.recurrence_weight_spin = QSpinBox()
        self.recurrence_weight_spin.setMinimum(0)
        self.recurrence_weight_spin.setMaximum(100)
        self.critical_threshold_spin = QSpinBox()
        self.critical_threshold_spin.setMinimum(1)
        self.critical_threshold_spin.setMaximum(100)
        self.reserve_minimum_spin = QSpinBox()
        self.reserve_minimum_spin.setMinimum(1)
        self.reserve_minimum_spin.setMaximum(999)
        self.reserve_multiplier_spin = QSpinBox()
        self.reserve_multiplier_spin.setMinimum(1)
        self.reserve_multiplier_spin.setMaximum(20)
        self.reserve_divisor_spin = QSpinBox()
        self.reserve_divisor_spin.setMinimum(1)
        self.reserve_divisor_spin.setMaximum(20)

        fields = [
            ("Janela de reincidência (dias)", self.recurrence_window_spin),
            ("Peso da reincidência", self.recurrence_weight_spin),
            ("Limite de reincidência crítica", self.critical_threshold_spin),
            ("Reserva alta mínima", self.reserve_minimum_spin),
            ("Multiplicador da reserva alta", self.reserve_multiplier_spin),
            ("Divisor de consumo baixo", self.reserve_divisor_spin),
        ]
        for index, (label_text, widget) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            form_layout.addWidget(QLabel(label_text), row, column)
            form_layout.addWidget(widget, row, column + 1)

        compatibility_card = QFrame()
        style_table_card(compatibility_card)
        self.compatibility_skeleton = TableSkeletonOverlay(compatibility_card, rows=6)
        compatibility_layout = QVBoxLayout(compatibility_card)
        compatibility_layout.setContentsMargins(14, 14, 14, 14)
        compatibility_layout.setSpacing(10)
        compatibility_title = QLabel("Compatibilidade dos dados existentes")
        compatibility_title.setObjectName("SectionTitle")
        compatibility_hint = QLabel(
            "Leia aqui o que ainda está em formato legado e o que já conversa bem com o fluxo novo."
        )
        compatibility_hint.setObjectName("PageSubtitle")
        compatibility_hint.setWordWrap(True)
        self.compatibility_table = QTableWidget(0, 3)
        self.compatibility_table.setHorizontalHeaderLabels(["Indicador", "Quantidade", "Leitura"])
        configure_table(self.compatibility_table, stretch_last=True)
        self.compatibility_table.setMinimumHeight(240)
        compatibility_layout.addWidget(compatibility_title)
        compatibility_layout.addWidget(compatibility_hint)
        compatibility_layout.addWidget(self.compatibility_table)

        self.readings_table = QTableWidget(0, 1)
        self.readings_table.setHorizontalHeaderLabels(["Leituras de compatibilidade"])
        configure_table(self.readings_table, stretch_last=True)
        self.readings_table.setMinimumHeight(180)
        compatibility_layout.addWidget(self.readings_table)

        layout.addLayout(header)
        layout.addWidget(summary_card)
        layout.addWidget(form_card)
        layout.addWidget(compatibility_card, 1)

    def set_loading_state(self, loading: bool):
        if loading:
            self.compatibility_skeleton.show_skeleton("Carregando configuração administrativa")
        else:
            self.compatibility_skeleton.hide_skeleton()

    def refresh(self):
        if not self.api_client.user_has_management_access():
            self.compatibility_table.setRowCount(0)
            self.readings_table.setRowCount(0)
            return
        try:
            self.set_loading_state(True)
            payload = self.api_client.get_intelligent_rules() or {}
            self.rules = payload.get("rules") or {}
            self.compatibility = self.api_client.get_compatibility_status() or {}
            self._fill_rules()
            self._fill_summary()
            self._fill_compatibility()
        except Exception as exc:
            show_notice(self, "Falha ao carregar regras", str(exc), icon_name="warning")
        finally:
            self.set_loading_state(False)

    def _fill_rules(self):
        self.recurrence_window_spin.setValue(int(self.rules.get("recurrence_window_days", 15)))
        self.recurrence_weight_spin.setValue(int(self.rules.get("recurrence_weight", 5)))
        self.critical_threshold_spin.setValue(int(self.rules.get("critical_recurrence_threshold", 5)))
        self.reserve_minimum_spin.setValue(int(self.rules.get("reserve_high_quantity_minimum", 3)))
        self.reserve_multiplier_spin.setValue(int(self.rules.get("reserve_high_multiplier", 2)))
        self.reserve_divisor_spin.setValue(int(self.rules.get("reserve_low_consumption_divisor", 3)))

    def _fill_summary(self):
        resumo = (self.compatibility or {}).get("resumo") or {}
        self.window_badge.setText(f"Janela {self.recurrence_window_spin.value()} dias")
        self.weight_badge.setText(f"Peso {self.recurrence_weight_spin.value()}")
        self.alert_badge.setText(f"Crítico a partir de {self.critical_threshold_spin.value()}")
        self.compat_badge.setText(
            f"Compatibilidade {self.compatibility.get('status_geral', '-')} | Legados {int(resumo.get('programacoes_legadas', 0))}"
        )

    def _fill_compatibility(self):
        resumo = (self.compatibility or {}).get("resumo") or {}
        rows = [
            ("NC abertas", resumo.get("nao_conformidades_abertas", 0), "Base atual ainda viva no fluxo de resolução."),
            ("Checklists sem agrupamento", resumo.get("checklists_sem_agrupamento", 0), "Itens antigos usando fallback de agrupamento."),
            ("Pacotes abertos ou em execução", resumo.get("pacotes_abertos_ou_execucao", 0), "Pacotes já no fluxo novo."),
            ("Programações legadas", resumo.get("programacoes_legadas", 0), "Programações antigas continuam legíveis."),
            ("OS sem pacote", resumo.get("ordens_sem_pacote", 0), "Ordens antigas sem vínculo completo com pacote."),
            ("Materiais sem movimento", resumo.get("materiais_sem_movimento", 0), "Materiais ainda sem histórico operacional."),
        ]
        self.compatibility_table.setSortingEnabled(False)
        self.compatibility_table.setUpdatesEnabled(False)
        self.compatibility_table.blockSignals(True)
        try:
            self.compatibility_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for col_index, value in enumerate(row):
                    self.compatibility_table.setItem(row_index, col_index, make_table_item(value))
        finally:
            self.compatibility_table.blockSignals(False)
            self.compatibility_table.setUpdatesEnabled(True)
            self.compatibility_table.setSortingEnabled(True)

        readings = list((self.compatibility or {}).get("leituras") or [])
        self.readings_table.setRowCount(len(readings))
        for row_index, reading in enumerate(readings):
            self.readings_table.setItem(row_index, 0, make_table_item(reading))

    def save_rules(self):
        try:
            payload = {
                "recurrence_window_days": int(self.recurrence_window_spin.value()),
                "recurrence_weight": int(self.recurrence_weight_spin.value()),
                "critical_recurrence_threshold": int(self.critical_threshold_spin.value()),
                "reserve_high_quantity_minimum": int(self.reserve_minimum_spin.value()),
                "reserve_high_multiplier": int(self.reserve_multiplier_spin.value()),
                "reserve_low_consumption_divisor": int(self.reserve_divisor_spin.value()),
            }
            response = self.api_client.update_intelligent_rules(payload) or {}
            self.rules = response.get("rules") or payload
            self._fill_summary()
            self.data_changed.emit()
            show_notice(self, "Configuração salva", "As regras inteligentes foram atualizadas com sucesso.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao salvar regras", str(exc), icon_name="warning")
