from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from components import show_notice
from theme import configure_table, make_table_item, style_table_card


class EmergencyAssignmentDialog(QDialog):
    def __init__(self, mechanics: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Triagem emergencial")
        layout = QFormLayout(self)
        self.mechanic = QComboBox()
        for row in mechanics:
            self.mechanic.addItem(row.get("nome") or row.get("login"), row.get("id"))
        layout.addRow("Mecânico responsável", self.mechanic)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def mechanic_id(self) -> int | None:
        return self.mechanic.currentData()


class EmergenciesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.rows: list[dict] = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        title = QLabel("Emergenciais e Ordens de Serviço")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Abertura operacional no web mobile; triagem e conversão em OS no desktop.")
        subtitle.setObjectName("PageSubtitle")
        actions = QHBoxLayout()
        actions.addStretch()
        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.refresh)
        self.convert_button = QPushButton("Triar e gerar OS")
        self.convert_button.setProperty("variant", "primary")
        self.convert_button.clicked.connect(self.convert_selected)
        actions.addWidget(refresh_button)
        actions.addWidget(self.convert_button)
        card = QFrame()
        style_table_card(card)
        card_layout = QVBoxLayout(card)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Número", "Equipamento", "Criticidade", "Parado", "Status", "Responsável", "OS", "Abertura"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        card_layout.addWidget(self.table)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(actions)
        layout.addWidget(card, 1)

    def refresh(self):
        self.rows = self.api_client.get_emergencies()
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            vehicle = row.get("vehicle") or {}
            mechanic = row.get("assigned_mechanic") or {}
            work_order = row.get("work_order") or {}
            values = [
                row.get("event_number") or "-",
                vehicle.get("frota") or vehicle.get("placa") or "-",
                row.get("severity") or "-",
                "SIM" if row.get("equipment_stopped") else "NÃO",
                row.get("status") or "-",
                mechanic.get("nome") or "Não definido",
                work_order.get("order_number") or "-",
                str(row.get("opened_at") or "-").replace("T", " ")[:16],
            ]
            for column, value in enumerate(values):
                self.table.setItem(index, column, make_table_item(str(value)))

    def convert_selected(self):
        selected = self.table.currentRow()
        if selected < 0 or selected >= len(self.rows):
            show_notice(self, "Selecione uma emergência", "Escolha uma linha para realizar a triagem.", icon_name="warning")
            return
        emergency = self.rows[selected]
        if emergency.get("work_order_id"):
            show_notice(self, "OS já gerada", "Esta emergência já está vinculada a uma ordem de serviço.", icon_name="warning")
            return
        try:
            dialog = EmergencyAssignmentDialog(self.api_client.get_mechanics(), self)
            if dialog.exec() != QDialog.Accepted:
                return
            mechanic_id = dialog.mechanic_id()
            if not mechanic_id:
                raise RuntimeError("Nenhum mecânico ativo disponível.")
            payload = {"assigned_mechanic_user_id": mechanic_id}
            self.api_client.triage_emergency(emergency["id"], payload)
            self.api_client.convert_emergency_to_work_order(emergency["id"], payload)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "OS gerada", "A emergência foi triada e encaminhada à manutenção.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha na triagem", str(exc), icon_name="warning")
