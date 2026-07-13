from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout,
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
        self.trigger = QComboBox()
        self.trigger.addItem("Por calendário", "CALENDARIO")
        self.trigger.addItem("Por horímetro", "HORIMETRO")
        self.trigger.addItem("Calendário e horímetro", "AMBOS")
        self.interval_days = QSpinBox(); self.interval_days.setRange(1, 3650); self.interval_days.setValue(30)
        self.next_due_date = QDateEdit(); self.next_due_date.setCalendarPopup(True); self.next_due_date.setDate(date.today())
        self.interval_hourmeter = QLineEdit(); self.interval_hourmeter.setPlaceholderText("Ex.: 250")
        self.next_due_hourmeter = QLineEdit(); self.next_due_hourmeter.setPlaceholderText("Obrigatório se não houver leitura")
        self.priority = QComboBox()
        for value in ("BAIXA", "MEDIA", "ALTA", "CRITICA"):
            self.priority.addItem(value, value)
        self.mechanic = QComboBox(); self.mechanic.addItem("Não atribuir agora", None)
        for row in mechanics:
            self.mechanic.addItem(row.get("nome") or row.get("login"), row.get("id"))
        form.addRow("Equipamento", self.vehicle); form.addRow("Título", self.title); form.addRow("Gatilho", self.trigger)
        form.addRow("Periodicidade (dias)", self.interval_days); form.addRow("Próxima data", self.next_due_date)
        form.addRow("Periodicidade (horímetro)", self.interval_hourmeter); form.addRow("Próximo horímetro", self.next_due_hourmeter)
        form.addRow("Prioridade", self.priority); form.addRow("Mecânico", self.mechanic)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def payload(self) -> dict:
        trigger = self.trigger.currentData()
        data = {
            "vehicle_id": self.vehicle.currentData(), "title": self.title.text().strip(), "trigger_type": trigger,
            "priority": self.priority.currentData(), "assigned_mechanic_user_id": self.mechanic.currentData(),
        }
        if trigger in {"CALENDARIO", "AMBOS"}:
            data.update({"interval_days": self.interval_days.value(), "next_due_date": self.next_due_date.date().toString("yyyy-MM-dd")})
        if trigger in {"HORIMETRO", "AMBOS"}:
            data.update({"interval_hourmeter": self.interval_hourmeter.text().strip(), "next_due_hourmeter": self.next_due_hourmeter.text().strip() or None})
        return data


class PCMPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.plans: list[dict] = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(14)
        title = QLabel("PCM - Planos, Agenda e Backlog"); title.setObjectName("PageTitle")
        subtitle = QLabel("O plano preventivo é a agenda de revisão; o backlog mostra apenas OS abertas, sem duplicar dados.")
        subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        cards = QHBoxLayout()
        self.plan_card = StatCard("Planos ativos", "0", "Preventivas cadastradas", icon_name="maintenance")
        self.due_card = StatCard("Vencendo", "0", "Planos que já podem gerar OS", icon_name="warning")
        self.backlog_card = StatCard("Backlog", "0", "Ordens de serviço em aberto", icon_name="reports")
        for card in (self.plan_card, self.due_card, self.backlog_card): cards.addWidget(card)
        actions = QHBoxLayout(); actions.addStretch()
        create = QPushButton("Novo plano preventivo"); create.setProperty("variant", "primary"); create.clicked.connect(self.create_plan)
        generate = QPushButton("Gerar preventivas vencidas"); generate.clicked.connect(self.generate_due)
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        actions.addWidget(create); actions.addWidget(generate); actions.addWidget(refresh)
        plans_card = QFrame(); style_table_card(plans_card); plans_layout = QVBoxLayout(plans_card)
        plans_layout.addWidget(QLabel("Planos preventivos"))
        self.plan_table = QTableWidget(0, 8); self.plan_table.setHorizontalHeaderLabels(["Código", "Equipamento", "Plano", "Gatilho", "Próxima data", "Próx. h", "Situação", "Mecânico"]); configure_table(self.plan_table, stretch_last=False)
        plans_layout.addWidget(self.plan_table)
        backlog_card = QFrame(); style_table_card(backlog_card); backlog_layout = QVBoxLayout(backlog_card)
        backlog_layout.addWidget(QLabel("Backlog derivado das OS abertas"))
        self.backlog_table = QTableWidget(0, 7); self.backlog_table.setHorizontalHeaderLabels(["OS", "Equipamento", "Origem", "Prioridade", "Programada", "Idade", "Bloqueios"]); configure_table(self.backlog_table, stretch_last=False)
        backlog_layout.addWidget(self.backlog_table)
        layout.addWidget(title); layout.addWidget(subtitle); layout.addLayout(cards); layout.addLayout(actions); layout.addWidget(plans_card, 1); layout.addWidget(backlog_card, 1)

    def refresh(self):
        agenda = self.api_client.get_pcm_agenda()
        self.plans = agenda.get("preventive_plans", [])
        backlog = self.api_client.get_pcm_backlog()
        self.plan_card.set_content("Planos ativos", str(sum(1 for plan in self.plans if plan.get("status") == "ATIVO")), "Preventivas cadastradas")
        self.due_card.set_content("Vencendo", str(agenda.get("summary", {}).get("vencendo_ou_vencidos", 0)), "Planos que já podem gerar OS")
        self.backlog_card.set_content("Backlog", str(len(backlog)), "Ordens de serviço em aberto")
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
