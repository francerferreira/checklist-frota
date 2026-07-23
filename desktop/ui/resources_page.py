from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, make_table_item, style_table_card


class ResourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo recurso")
        form = QFormLayout(self)
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.resource_type = QComboBox()
        self.resource_type.addItem("Ferramenta", "FERRAMENTA")
        self.resource_type.addItem("Instrumento", "INSTRUMENTO")
        self.resource_type.addItem("Equipamento", "EQUIPAMENTO")
        self.calibration_required = QCheckBox("Exige calibração válida")
        self.calibration_due_date = QDateEdit()
        self.calibration_due_date.setCalendarPopup(True)
        self.calibration_due_date.setDate(QDate.currentDate())
        self.calibration_due_date.setEnabled(False)
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Observações de uso ou restrições")
        self.calibration_required.toggled.connect(self.calibration_due_date.setEnabled)
        form.addRow("Código", self.code)
        form.addRow("Nome", self.name)
        form.addRow("Tipo", self.resource_type)
        form.addRow(self.calibration_required)
        form.addRow("Calibração válida até", self.calibration_due_date)
        form.addRow("Observações", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict:
        calibration_required = self.calibration_required.isChecked()
        return {
            "code": self.code.text().strip(),
            "name": self.name.text().strip(),
            "resource_type": self.resource_type.currentData(),
            "calibration_required": calibration_required,
            "calibration_due_date": self.calibration_due_date.date().toString("yyyy-MM-dd") if calibration_required else None,
            "notes": self.notes.text().strip(),
        }


class ResourceReservationDialog(QDialog):
    def __init__(self, resource: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Reservar {resource.get('name') or 'recurso'}")
        form = QFormLayout(self)
        now = QDateTime.currentDateTime()
        self.starts_at = QDateTimeEdit(now)
        self.ends_at = QDateTimeEdit(now.addSecs(3600))
        for field in (self.starts_at, self.ends_at):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.work_order_id = QLineEdit()
        self.work_order_id.setPlaceholderText("Opcional")
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Motivo ou serviço planejado")
        form.addRow("Início", self.starts_at)
        form.addRow("Fim", self.ends_at)
        form.addRow("OS", self.work_order_id)
        form.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict:
        return {
            "starts_at": self.starts_at.dateTime().toPython().isoformat(timespec="minutes"),
            "ends_at": self.ends_at.dateTime().toPython().isoformat(timespec="minutes"),
            "work_order_id": self.work_order_id.text().strip() or None,
            "notes": self.notes.text().strip(),
        }


class ResourcesPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.resources: list[dict] = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Recursos, ferramentas e calibração")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Cadastre o recurso e reserve a janela. O sistema bloqueia conflito de horário e calibração vencida.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        cards = QHBoxLayout()
        self.total_card = StatCard("Recursos ativos", "0", "Ferramentas e instrumentos", icon_name="maintenance")
        self.calibrated_card = StatCard("Calibração em dia", "0", "Itens que exigem controle", icon_name="dashboard")
        self.expired_card = StatCard("Bloqueados", "0", "Calibração vencida", icon_name="warning")
        for card in (self.total_card, self.calibrated_card, self.expired_card):
            cards.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch()
        add_button = QPushButton("Novo recurso")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.create_resource)
        reserve_button = QPushButton("Reservar selecionado")
        reserve_button.clicked.connect(self.reserve_selected)
        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.refresh)
        actions.addWidget(add_button)
        actions.addWidget(reserve_button)
        actions.addWidget(refresh_button)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.addWidget(QLabel("Recursos cadastrados"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Código", "Recurso", "Tipo", "Calibração", "Situação", "Observações"])
        configure_table(self.table, stretch_last=False)
        table_layout.addWidget(self.table)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(cards)
        layout.addLayout(actions)
        layout.addWidget(table_card, 1)

    def refresh(self):
        self.resources = self.api_client.get_maintenance_resources()
        active = [row for row in self.resources if row.get("active")]
        calibration_required = [row for row in active if row.get("calibration_required")]
        expired = [row for row in calibration_required if row.get("calibration_status") == "VENCIDA"]
        self.total_card.set_content("Recursos ativos", str(len(active)), "Ferramentas e instrumentos")
        self.calibrated_card.set_content("Calibração em dia", str(sum(row.get("calibration_status") == "EM_DIA" for row in calibration_required)), "Itens que exigem controle")
        self.expired_card.set_content("Bloqueados", str(len(expired)), "Calibração vencida")
        self.table.setRowCount(len(self.resources))
        for row_index, row in enumerate(self.resources):
            calibration = row.get("calibration_due_date") or "Não aplicável"
            values = [
                row.get("code"),
                row.get("name"),
                row.get("resource_type"),
                calibration,
                row.get("calibration_status"),
                row.get("notes") or "-",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, make_table_item(value, payload=row if column == 0 else None))

    def create_resource(self):
        dialog = ResourceDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.api_client.create_maintenance_resource(dialog.payload())
            self.refresh()
            show_notice(self, "Recurso criado", "O recurso está disponível para reserva conforme suas regras.", icon_name="maintenance")
        except Exception as exc:
            show_notice(self, "Falha ao criar recurso", str(exc), icon_name="warning")

    def reserve_selected(self):
        item = self.table.currentItem()
        resource = item.data(Qt.UserRole) if item and item.column() == 0 else None
        if resource is None and item:
            first_cell = self.table.item(item.row(), 0)
            resource = first_cell.data(Qt.UserRole) if first_cell else None
        if not resource:
            show_notice(self, "Recurso obrigatório", "Selecione um recurso para reservar.", icon_name="warning")
            return
        dialog = ResourceReservationDialog(resource, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.api_client.reserve_maintenance_resource(int(resource["id"]), dialog.payload())
            show_notice(self, "Reserva criada", "A janela foi reservada sem conflito de horário.", icon_name="maintenance")
        except Exception as exc:
            show_notice(self, "Reserva não criada", str(exc), icon_name="warning")
