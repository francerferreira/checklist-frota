from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, make_table_item, style_table_card


class SupplierDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo fornecedor")
        form = QFormLayout(self)
        self.code, self.name, self.contact, self.email, self.phone = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        form.addRow("Código", self.code)
        form.addRow("Nome", self.name)
        form.addRow("Contato", self.contact)
        form.addRow("E-mail", self.email)
        form.addRow("Telefone", self.phone)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict:
        return {"code": self.code.text().strip(), "name": self.name.text().strip(), "contact_name": self.contact.text().strip(), "email": self.email.text().strip(), "phone": self.phone.text().strip()}


class PurchaseRequestDialog(QDialog):
    def __init__(self, materials: list[dict], suppliers: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nova solicitação de compra")
        form = QFormLayout(self)
        self.material = QComboBox()
        for row in materials:
            if row.get("ativo", True):
                self.material.addItem(f"{row.get('referencia')} - {row.get('descricao')}", row.get("id"))
        self.supplier = QComboBox()
        self.supplier.addItem("Definir depois", None)
        for row in suppliers:
            if row.get("active", True):
                self.supplier.addItem(row.get("name"), row.get("id"))
        self.quantity = QSpinBox(); self.quantity.setRange(1, 999999); self.quantity.setValue(1)
        self.priority = QComboBox()
        for value in ("BAIXA", "MEDIA", "ALTA", "CRITICA"):
            self.priority.addItem(value, value)
        self.expected_date = QDateEdit(); self.expected_date.setCalendarPopup(True); self.expected_date.setDate(QDate.currentDate().addDays(7))
        self.observation = QLineEdit(); self.observation.setPlaceholderText("Necessidade, OS ou observação")
        form.addRow("Material", self.material)
        form.addRow("Fornecedor", self.supplier)
        form.addRow("Quantidade", self.quantity)
        form.addRow("Prioridade", self.priority)
        form.addRow("Previsão", self.expected_date)
        form.addRow("Observação", self.observation)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def payload(self) -> dict:
        return {"material_id": self.material.currentData(), "supplier_id": self.supplier.currentData(), "requested_quantity": self.quantity.value(), "priority": self.priority.currentData(), "expected_date": self.expected_date.date().toString("yyyy-MM-dd"), "observation": self.observation.text().strip()}


class ReceiptDialog(QDialog):
    def __init__(self, remaining_quantity: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar recebimento")
        form = QFormLayout(self)
        self.quantity = QSpinBox(); self.quantity.setRange(1, max(1, remaining_quantity)); self.quantity.setValue(min(1, max(1, remaining_quantity)))
        self.notes = QLineEdit(); self.notes.setPlaceholderText("Nota, lote ou observação")
        form.addRow("Quantidade recebida", self.quantity)
        form.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def payload(self) -> dict:
        return {"quantity": self.quantity.value(), "notes": self.notes.text().strip(), "idempotency_key": str(uuid4())}


class PurchaseDetailDialog(QDialog):
    def __init__(self, api_client, purchase_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalhe da solicitacao de compra")
        self.setMinimumSize(840, 560)
        data = api_client.get_purchase_request(purchase_id)
        layout = QVBoxLayout(self)
        title = QLabel(f"Solicitacao {data.get('code') or '-'}")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Material, aprovacao, recebimentos e saldo reunidos em uma unica ficha.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(subtitle)
        card = QFrame(); style_table_card(card)
        grid = QGridLayout(card); grid.setContentsMargins(16, 16, 16, 16); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        material = data.get("material") or {}; supplier = data.get("supplier") or {}; creator = data.get("created_by") or {}; approver = data.get("approved_by") or {}
        fields = [("Material", f"{material.get('referencia') or '-'} - {material.get('descricao') or '-'}"), ("Fornecedor", supplier.get("name") or "A definir"), ("Situacao", data.get("status") or "-"), ("Prioridade", data.get("priority") or "-"), ("Quantidade", str(data.get("requested_quantity") or 0)), ("Recebida", str(data.get("received_quantity") or 0)), ("Saldo", str(data.get("remaining_quantity") or 0)), ("Previsao", data.get("expected_date") or "-"), ("Solicitada por", creator.get("nome") or creator.get("login") or "-"), ("Aprovada por", approver.get("nome") or approver.get("login") or "-"), ("Observacao", data.get("observation") or "-")]
        for index, (label_text, value_text) in enumerate(fields):
            label = QLabel(label_text); label.setObjectName("SectionCaption")
            value = QLabel(str(value_text)); value.setWordWrap(True); value.setObjectName("DialogInfoValue")
            row, column = divmod(index, 2)
            grid.addWidget(label, row * 2, column); grid.addWidget(value, row * 2 + 1, column)
        layout.addWidget(card)
        receipts_title = QLabel("Recebimentos registrados"); receipts_title.setObjectName("SectionTitle")
        table = QTableWidget(0, 4); table.setHorizontalHeaderLabels(["Data", "Quantidade", "Recebido por", "Observacao"]); configure_table(table)
        receipts = data.get("receipts") or []; table.setRowCount(len(receipts))
        for row, receipt in enumerate(receipts):
            receiver = receipt.get("received_by") or {}
            values = [str(receipt.get("received_at") or "").replace("T", " ")[:19], receipt.get("quantity"), receiver.get("nome") or receiver.get("login") or "-", receipt.get("notes") or "-"]
            for column, value in enumerate(values): table.setItem(row, column, make_table_item(value))
        table.resizeColumnsToContents()
        layout.addWidget(receipts_title); layout.addWidget(table, 1)
        close = QPushButton("Fechar"); close.clicked.connect(self.accept); layout.addWidget(close)


class PurchasesPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.suppliers: list[dict] = []
        self.requests: list[dict] = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(14)
        title = QLabel("Compras e fornecedores"); title.setObjectName("PageTitle")
        subtitle = QLabel("Solicite o material, aprove a compra e registre recebimentos parciais sem duplicar saldo."); subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        cards = QHBoxLayout()
        self.open_card = StatCard("Solicitações abertas", "0", "Aguardando compra ou entrega", icon_name="materials")
        self.delayed_card = StatCard("Atrasadas", "0", "Fora da data prevista", icon_name="warning")
        self.received_card = StatCard("Recebidas", "0", "Compras concluídas", icon_name="dashboard")
        for card in (self.open_card, self.delayed_card, self.received_card): cards.addWidget(card)
        actions = QHBoxLayout(); actions.addStretch()
        supplier_button = QPushButton("Novo fornecedor"); supplier_button.clicked.connect(self.create_supplier)
        request_button = QPushButton("Nova solicitação"); request_button.setProperty("variant", "primary"); request_button.clicked.connect(self.create_request)
        approve_button = QPushButton("Aprovar selecionada"); approve_button.clicked.connect(self.approve_selected)
        receive_button = QPushButton("Receber selecionada"); receive_button.clicked.connect(self.receive_selected)
        details_button = QPushButton("Ver detalhes"); details_button.clicked.connect(self.open_details)
        refresh_button = QPushButton("Atualizar"); refresh_button.clicked.connect(self.refresh)
        for button in (supplier_button, request_button, approve_button, receive_button, details_button, refresh_button): actions.addWidget(button)
        suppliers_card = QFrame(); style_table_card(suppliers_card); suppliers_layout = QVBoxLayout(suppliers_card); suppliers_layout.addWidget(QLabel("Fornecedores"))
        self.suppliers_table = QTableWidget(0, 4); self.suppliers_table.setHorizontalHeaderLabels(["Código", "Fornecedor", "Contato", "Ativo"]); configure_table(self.suppliers_table, stretch_last=False); suppliers_layout.addWidget(self.suppliers_table)
        requests_card = QFrame(); style_table_card(requests_card); requests_layout = QVBoxLayout(requests_card); requests_layout.addWidget(QLabel("Solicitações de compra"))
        self.requests_table = QTableWidget(0, 8); self.requests_table.setHorizontalHeaderLabels(["Código", "Material", "Fornecedor", "Qtd.", "Recebido", "Status", "Previsão", "Atraso"]); configure_table(self.requests_table, stretch_last=False); self.requests_table.itemDoubleClicked.connect(lambda *_: self.open_details()); requests_layout.addWidget(self.requests_table)
        layout.addWidget(title); layout.addWidget(subtitle); layout.addLayout(cards); layout.addLayout(actions); layout.addWidget(suppliers_card, 1); layout.addWidget(requests_card, 2)

    def refresh(self):
        self.suppliers = self.api_client.get_suppliers()
        self.requests = self.api_client.get_purchase_requests()
        self.open_card.set_content("Solicitações abertas", str(sum(row.get("status") not in {"RECEBIDA", "CANCELADA"} for row in self.requests)), "Aguardando compra ou entrega")
        self.delayed_card.set_content("Atrasadas", str(sum(bool(row.get("delayed")) for row in self.requests)), "Fora da data prevista")
        self.received_card.set_content("Recebidas", str(sum(row.get("status") == "RECEBIDA" for row in self.requests)), "Compras concluídas")
        self._fill(self.suppliers_table, self.suppliers, lambda row: [row.get("code"), row.get("name"), row.get("contact_name") or "-", "Sim" if row.get("active") else "Não"])
        self._fill(self.requests_table, self.requests, lambda row: [row.get("code"), (row.get("material") or {}).get("referencia"), (row.get("supplier") or {}).get("name") or "-", row.get("requested_quantity"), row.get("received_quantity"), row.get("status"), row.get("expected_date") or "-", "Sim" if row.get("delayed") else "-"])

    def _fill(self, table, rows, value_builder):
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(value_builder(row)):
                table.setItem(row_index, column, make_table_item(value, payload=row if column == 0 else None))

    def _selected_request(self) -> dict | None:
        item = self.requests_table.currentItem()
        if not item: return None
        first = self.requests_table.item(item.row(), 0)
        return first.data(Qt.UserRole) if first else None

    def create_supplier(self):
        dialog = SupplierDialog(self)
        if dialog.exec() != QDialog.Accepted: return
        try:
            self.api_client.create_supplier(dialog.payload()); self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao criar fornecedor", str(exc), icon_name="warning")

    def create_request(self):
        try:
            dialog = PurchaseRequestDialog(self.api_client.get_materials(ativos=True), self.suppliers, self)
            if dialog.exec() != QDialog.Accepted: return
            self.api_client.create_purchase_request(dialog.payload()); self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao criar solicitação", str(exc), icon_name="warning")

    def approve_selected(self):
        purchase = self._selected_request()
        if not purchase:
            show_notice(self, "Solicitação obrigatória", "Selecione uma solicitação para aprovar.", icon_name="warning"); return
        try:
            self.api_client.approve_purchase_request(int(purchase["id"])); self.refresh()
        except Exception as exc:
            show_notice(self, "Aprovação não concluída", str(exc), icon_name="warning")

    def receive_selected(self):
        purchase = self._selected_request()
        if not purchase:
            show_notice(self, "Solicitação obrigatória", "Selecione uma solicitação para receber.", icon_name="warning"); return
        remaining = int(purchase.get("remaining_quantity") or 0)
        if remaining <= 0:
            show_notice(self, "Recebimento concluído", "Esta solicitação já foi totalmente recebida.", icon_name="warning"); return
        dialog = ReceiptDialog(remaining, self)
        if dialog.exec() != QDialog.Accepted: return
        try:
            self.api_client.receive_purchase_request(int(purchase["id"]), dialog.payload()); self.refresh()
        except Exception as exc:
            show_notice(self, "Recebimento não concluído", str(exc), icon_name="warning")

    def open_details(self):
        purchase = self._selected_request()
        if not purchase:
            show_notice(self, "Solicitação obrigatória", "Selecione uma solicitação para ver os detalhes.", icon_name="warning")
            return
        try:
            PurchaseDetailDialog(self.api_client, int(purchase["id"]), self).exec()
        except Exception as exc:
            show_notice(self, "Detalhes indisponíveis", str(exc), icon_name="warning")
