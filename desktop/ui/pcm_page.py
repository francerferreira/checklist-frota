from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, make_table_item, style_table_card


class PreventivePlanDialog(QDialog):
    def __init__(self, vehicles: list[dict], mechanics: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo plano preventivo")
        form = QFormLayout(self)
        self.vehicle = QComboBox()
        for row in vehicles:
            if row.get("ativo", True):
                self.vehicle.addItem(row.get("frota") or row.get("placa") or row.get("modelo"), row.get("id"))
        self.title = QLineEdit()
        self.description = QLineEdit()
        self.description.setPlaceholderText("Ex.: lubrificar articulações e conferir vazamentos")
        self.trigger = QComboBox()
        self.trigger.addItem("Por calendário", "CALENDARIO")
        self.trigger.addItem("Por horímetro", "HORIMETRO")
        self.trigger.addItem("Calendário e horímetro", "AMBOS")
        self.trigger.currentIndexChanged.connect(self._sync_trigger_fields)
        self.interval_days = QSpinBox(); self.interval_days.setRange(1, 3650); self.interval_days.setValue(30)
        self.next_due_date = QDateEdit(); self.next_due_date.setCalendarPopup(True); self.next_due_date.setDate(date.today())
        self.tolerance_days = QSpinBox(); self.tolerance_days.setRange(0, 3650); self.tolerance_days.setValue(0); self.tolerance_days.setSuffix(" dia(s)")
        self.interval_hourmeter = QLineEdit(); self.interval_hourmeter.setPlaceholderText("Ex.: 250")
        self.next_due_hourmeter = QLineEdit(); self.next_due_hourmeter.setPlaceholderText("Obrigatório se não houver leitura")
        self.tolerance_hourmeter = QDoubleSpinBox(); self.tolerance_hourmeter.setRange(0, 1_000_000); self.tolerance_hourmeter.setDecimals(2); self.tolerance_hourmeter.setSuffix(" h")
        self.estimated_duration_minutes = QSpinBox(); self.estimated_duration_minutes.setRange(1, 10_080); self.estimated_duration_minutes.setValue(60); self.estimated_duration_minutes.setSuffix(" min")
        self.priority = QComboBox()
        for value in ("BAIXA", "MEDIA", "ALTA", "CRITICA"):
            self.priority.addItem(value, value)
        self.mechanic = QComboBox(); self.mechanic.addItem("Não atribuir agora", None)
        for row in mechanics:
            self.mechanic.addItem(row.get("nome") or row.get("login"), row.get("id"))
        form.addRow("Equipamento", self.vehicle); form.addRow("Título", self.title); form.addRow("Descrição", self.description); form.addRow("Gatilho", self.trigger)
        form.addRow("Periodicidade (dias)", self.interval_days); form.addRow("Próxima data", self.next_due_date); form.addRow("Tolerância de data", self.tolerance_days)
        form.addRow("Periodicidade (horímetro)", self.interval_hourmeter); form.addRow("Próximo horímetro", self.next_due_hourmeter); form.addRow("Tolerância de horímetro", self.tolerance_hourmeter)
        form.addRow("Duração estimada", self.estimated_duration_minutes); form.addRow("Prioridade", self.priority); form.addRow("Mecânico", self.mechanic)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        self._sync_trigger_fields()

    def _sync_trigger_fields(self):
        trigger = self.trigger.currentData()
        calendar_enabled = trigger in {"CALENDARIO", "AMBOS"}
        hourmeter_enabled = trigger in {"HORIMETRO", "AMBOS"}
        for field in (self.interval_days, self.next_due_date, self.tolerance_days):
            field.setEnabled(calendar_enabled)
        for field in (self.interval_hourmeter, self.next_due_hourmeter, self.tolerance_hourmeter):
            field.setEnabled(hourmeter_enabled)

    def payload(self) -> dict:
        trigger = self.trigger.currentData()
        data = {
            "vehicle_id": self.vehicle.currentData(), "title": self.title.text().strip(), "trigger_type": trigger,
            "description": self.description.text().strip(), "priority": self.priority.currentData(),
            "assigned_mechanic_user_id": self.mechanic.currentData(),
            "estimated_duration_minutes": self.estimated_duration_minutes.value(),
        }
        if trigger in {"CALENDARIO", "AMBOS"}:
            data.update({"interval_days": self.interval_days.value(), "next_due_date": self.next_due_date.date().toString("yyyy-MM-dd"), "tolerance_days": self.tolerance_days.value()})
        if trigger in {"HORIMETRO", "AMBOS"}:
            data.update({"interval_hourmeter": self.interval_hourmeter.text().strip(), "next_due_hourmeter": self.next_due_hourmeter.text().strip() or None, "tolerance_hourmeter": self.tolerance_hourmeter.value()})
        return data


class PCMPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.plans: list[dict] = []
        self.programming: dict = {}
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(14)
        title = QLabel("PCM - Planos, Agenda e Backlog"); title.setObjectName("PageTitle")
        subtitle = QLabel("O plano preventivo é a agenda de revisão; o backlog mostra apenas OS abertas, sem duplicar dados.")
        subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        cards = QHBoxLayout()
        self.plan_card = StatCard("Planos ativos", "0", "Preventivas cadastradas", icon_name="maintenance")
        self.due_card = StatCard("Vencendo", "0", "Planos que já podem gerar OS", icon_name="warning")
        self.backlog_card = StatCard("Backlog", "0", "Ordens de serviço em aberto", icon_name="reports")
        self.capacity_card = StatCard("Capacidade livre", "0 min", "Horizonte operacional selecionado", icon_name="dashboard")
        self.compliance_card = StatCard("Cumprimento", "0%", "Preventivas concluídas no período", icon_name="maintenance")
        for card in (self.plan_card, self.due_card, self.backlog_card, self.capacity_card, self.compliance_card): cards.addWidget(card)
        actions = QHBoxLayout(); actions.addStretch()
        create = QPushButton("Novo plano preventivo"); create.setProperty("variant", "primary"); create.clicked.connect(self.create_plan)
        generate = QPushButton("Gerar preventivas vencidas"); generate.clicked.connect(self.generate_due)
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        actions.addWidget(create); actions.addWidget(generate); actions.addWidget(refresh)
        programming_card = QFrame(); style_table_card(programming_card); programming_layout = QVBoxLayout(programming_card)
        programming_title = QLabel("Capacidade e janelas de programação"); programming_title.setObjectName("SectionTitle")
        programming_hint = QLabel("Projeção somente leitura: carga diária, capacidade livre e a melhor janela para preventiva vencida."); programming_hint.setObjectName("SectionCaption"); programming_hint.setWordWrap(True)
        programming_filters = QHBoxLayout()
        self.programming_start = QDateEdit(); self.programming_start.setCalendarPopup(True); self.programming_start.setDate(date.today())
        self.programming_end = QDateEdit(); self.programming_end.setCalendarPopup(True); self.programming_end.setDate(date.today().fromordinal(date.today().toordinal() + 14))
        self.daily_capacity = QSpinBox(); self.daily_capacity.setRange(60, 1440); self.daily_capacity.setValue(480); self.daily_capacity.setSuffix(" min/dia")
        programming_refresh = QPushButton("Atualizar capacidade"); programming_refresh.clicked.connect(self.refresh)
        programming_filters.addWidget(QLabel("Início")); programming_filters.addWidget(self.programming_start); programming_filters.addWidget(QLabel("Fim")); programming_filters.addWidget(self.programming_end); programming_filters.addWidget(QLabel("Capacidade")); programming_filters.addWidget(self.daily_capacity); programming_filters.addStretch(); programming_filters.addWidget(programming_refresh)
        self.capacity_table = QTableWidget(0, 7); self.capacity_table.setHorizontalHeaderLabels(["Data", "Capacidade", "Ocupada", "Livre", "Excesso", "OS", "Concluídas"]); configure_table(self.capacity_table, stretch_last=False); self.capacity_table.setMinimumHeight(220)
        self.window_table = QTableWidget(0, 7); self.window_table.setHorizontalHeaderLabels(["Plano", "Equipamento", "Prioridade", "Janela", "Duração", "Data sugerida", "Situação"]); configure_table(self.window_table, stretch_last=False); self.window_table.setMinimumHeight(200)
        programming_layout.addWidget(programming_title); programming_layout.addWidget(programming_hint); programming_layout.addLayout(programming_filters); programming_layout.addWidget(self.capacity_table); programming_layout.addWidget(QLabel("Preventivas aguardando programação")); programming_layout.addWidget(self.window_table)
        plans_card = QFrame(); style_table_card(plans_card); plans_layout = QVBoxLayout(plans_card)
        plans_layout.addWidget(QLabel("Planos preventivos"))
        self.plan_table = QTableWidget(0, 8); self.plan_table.setHorizontalHeaderLabels(["Código", "Equipamento", "Plano", "Gatilho", "Próxima data", "Próx. h", "Situação", "Mecânico"]); configure_table(self.plan_table, stretch_last=False)
        plans_layout.addWidget(self.plan_table)
        backlog_card = QFrame(); style_table_card(backlog_card); backlog_layout = QVBoxLayout(backlog_card)
        backlog_layout.addWidget(QLabel("Backlog derivado das OS abertas"))
        self.backlog_table = QTableWidget(0, 7); self.backlog_table.setHorizontalHeaderLabels(["OS", "Equipamento", "Origem", "Prioridade", "Programada", "Idade", "Bloqueios"]); configure_table(self.backlog_table, stretch_last=False)
        backlog_layout.addWidget(self.backlog_table)
        layout.addWidget(title); layout.addWidget(subtitle); layout.addLayout(cards); layout.addLayout(actions); layout.addWidget(programming_card, 1); layout.addWidget(plans_card, 1); layout.addWidget(backlog_card, 1)

    def refresh(self):
        agenda = self.api_client.get_pcm_agenda()
        self.plans = agenda.get("preventive_plans", [])
        backlog = self.api_client.get_pcm_backlog()
        self.programming = self.api_client.get_pcm_programming(
            date_from=self.programming_start.date().toString("yyyy-MM-dd"),
            date_to=self.programming_end.date().toString("yyyy-MM-dd"),
            daily_capacity_minutes=self.daily_capacity.value(),
        )
        self.plan_card.set_content("Planos ativos", str(sum(1 for plan in self.plans if plan.get("status") == "ATIVO")), "Preventivas cadastradas")
        self.due_card.set_content("Vencendo", str(agenda.get("summary", {}).get("vencendo_ou_vencidos", 0)), "Planos que já podem gerar OS")
        self.backlog_card.set_content("Backlog", str(len(backlog)), "Ordens de serviço em aberto")
        programming_summary = self.programming.get("summary") or {}
        self.capacity_card.set_content("Capacidade livre", f"{programming_summary.get('free_minutes', 0)} min", f"{programming_summary.get('overloaded_days', 0)} dia(s) acima da capacidade")
        self.compliance_card.set_content("Cumprimento", f"{programming_summary.get('preventive_compliance_percent', 0):.1f}%", f"Base: {programming_summary.get('compliance_base', 0)} OS passadas")
        self.plan_table.setRowCount(len(self.plans))
        for index, plan in enumerate(self.plans):
            due = plan.get("due") or {}; vehicle = plan.get("vehicle") or {}; mechanic = plan.get("assigned_mechanic") or {}
            values = [plan.get("code"), vehicle.get("frota") or vehicle.get("placa") or "-", plan.get("title"), plan.get("trigger_type"), plan.get("next_due_date") or "-", plan.get("next_due_hourmeter") or "-", due.get("status") or "-", mechanic.get("nome") or "Não atribuído"]
            for column, value in enumerate(values): self.plan_table.setItem(index, column, make_table_item(str(value)))
        self.backlog_table.setRowCount(len(backlog))
        for index, row in enumerate(backlog):
            order = row.get("work_order") or {}; vehicle = order.get("vehicle") or {}; blockers = row.get("blockers") or {}
            values = [order.get("order_number"), vehicle.get("frota") or "-", row.get("source"), row.get("priority"), order.get("scheduled_date") or "-", f"{row.get('age_days', 0)} dia(s)", "Material" if blockers.get("materiais_bloqueados") else "-"]
            for column, value in enumerate(values): self.backlog_table.setItem(index, column, make_table_item(str(value)))
        days = self.programming.get("days") or []
        self.capacity_table.setRowCount(len(days))
        for index, row in enumerate(days):
            values = [row.get("date"), f"{row.get('capacity_minutes', 0)} min", f"{row.get('occupied_minutes', 0)} min", f"{row.get('free_minutes', 0)} min", f"{row.get('overloaded_minutes', 0)} min", row.get("scheduled_items", 0), row.get("completed_items", 0)]
            for column, value in enumerate(values): self.capacity_table.setItem(index, column, make_table_item(str(value)))
        windows = self.programming.get("recommended_windows") or []
        self.window_table.setRowCount(len(windows))
        for index, row in enumerate(windows):
            vehicle = row.get("vehicle") or {}
            values = [row.get("code"), vehicle.get("frota") or "-", row.get("priority"), f"{row.get('window_start')} a {row.get('window_end')}", f"{row.get('estimated_duration_minutes', 0)} min", row.get("recommended_date") or "-", row.get("status")]
            for column, value in enumerate(values): self.window_table.setItem(index, column, make_table_item(str(value)))
        self.capacity_table.resizeColumnsToContents(); self.window_table.resizeColumnsToContents()

    def create_plan(self):
        try:
            dialog = PreventivePlanDialog(self.api_client.get_equipment(ativos=True), self.api_client.get_mechanics(), self)
            if dialog.exec() != QDialog.Accepted: return
            self.api_client.create_preventive_plan(dialog.payload()); self.refresh(); self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao criar plano", str(exc), icon_name="warning")

    def generate_due(self):
        try:
            generated = self.api_client.generate_due_preventives(); self.refresh(); self.data_changed.emit()
            show_notice(self, "Preventivas geradas", f"{len(generated)} programação(ões) e OS foram criadas.", icon_name="maintenance")
        except Exception as exc:
            show_notice(self, "Falha na geração", str(exc), icon_name="warning")
