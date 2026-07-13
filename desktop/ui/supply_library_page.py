from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QTableWidget, QVBoxLayout, QWidget,
)

from components import show_notice
from theme import configure_table, make_table_item, style_table_card


class SimpleFormDialog(QDialog):
    def __init__(self, title: str, fields: list[tuple[str, QWidget]], parent=None):
        super().__init__(parent); self.setWindowTitle(title)
        layout = QFormLayout(self); self.fields = {name: widget for name, widget in fields}
        for name, widget in fields: layout.addRow(name, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addRow(buttons)


class SupplyLibraryPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client; self.materials = []; self.families = []; self.vehicles = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Suprimentos e Biblioteca Técnica"); title.setObjectName("PageTitle")
        subtitle = QLabel("Depósitos distribuem o estoque atual; reservas protegem material para a OS; documentos ficam vinculados ao ativo ou sua família.")
        subtitle.setObjectName("PageSubtitle"); subtitle.setWordWrap(True)
        actions = QHBoxLayout(); actions.addStretch()
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh); actions.addWidget(refresh)
        tabs = QTabWidget(); tabs.setDocumentMode(True)
        self.warehouse_table = self._table(["Código", "Depósito", "Local", "Ativo"])
        self.stock_table = self._table(["Depósito", "Material", "Saldo", "Reservado", "Disponível"])
        self.application_table = self._table(["Material", "Aplicações por família"])
        self.reservation_table = self._table(["Programação", "Material", "Depósito", "Qtd.", "Consumido", "Status"])
        self.document_table = self._table(["Código", "Título", "Tipo", "Rev.", "Vínculo", "Validade", "Situação"])
        tabs.addTab(self._tab("Depósitos", self.warehouse_table, [("Novo depósito", self.create_warehouse)]), "Depósitos")
        tabs.addTab(self._tab("Saldo por depósito", self.stock_table, [("Distribuir saldo", self.initialize_stock)]), "Estoques")
        tabs.addTab(self._tab("Aplicação por família", self.application_table, [("Vincular família", self.link_material_family)]), "Aplicações")
        tabs.addTab(self._tab("Reservas de OS", self.reservation_table, []), "Reservas")
        tabs.addTab(self._tab("Manuais e procedimentos", self.document_table, [("Novo documento", self.create_document)]), "Biblioteca")
        layout.addWidget(title); layout.addWidget(subtitle); layout.addLayout(actions); layout.addWidget(tabs, 1)

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); configure_table(table, stretch_last=False); return table

    def _tab(self, caption, table, buttons):
        host = QWidget(); layout = QVBoxLayout(host); layout.setContentsMargins(10, 10, 10, 10)
        row = QHBoxLayout(); row.addWidget(QLabel(caption)); row.addStretch()
        for text, action in buttons:
            button = QPushButton(text); button.setProperty("variant", "primary"); button.clicked.connect(action); row.addWidget(button)
        layout.addLayout(row); layout.addWidget(table); return host

    @staticmethod
    def _fill(table, rows, values):
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(values(row)):
                table.setItem(row_index, column, make_table_item(str(value if value not in (None, "") else "-"), payload=row if column == 0 else None))

    def refresh(self):
        self.materials = self.api_client.get_materials(ativos=True)
        structure = self.api_client.get_equipment_structure(); self.families = structure.get("families", [])
        self.vehicles = self.api_client.get_equipment(ativos=True)
        warehouses, stocks, reservations, documents = self.api_client.get_warehouses(), self.api_client.get_warehouse_stocks(), self.api_client.get_warehouse_reservations(), self.api_client.get_technical_documents(include_archived=True)
        self._fill(self.warehouse_table, warehouses, lambda row: [row.get("code"), row.get("name"), row.get("location"), "Sim" if row.get("active") else "Não"])
        self._fill(self.stock_table, stocks, lambda row: [(row.get("warehouse") or {}).get("name"), (row.get("material") or {}).get("referencia"), row.get("quantity"), row.get("reserved_quantity"), row.get("available_quantity")])
        self._fill(self.application_table, self.materials, lambda row: [row.get("referencia"), ", ".join((item.get("family") or {}).get("name", "") for item in row.get("family_applications", [])) or "Legado: aplicação geral"])
        self._fill(self.reservation_table, reservations, lambda row: [row.get("schedule_id"), (row.get("warehouse_stock") or {}).get("material", {}).get("referencia"), (row.get("warehouse_stock") or {}).get("warehouse", {}).get("name"), row.get("quantity"), row.get("consumed_quantity"), row.get("status")])
        self._fill(self.document_table, documents, lambda row: [row.get("code"), row.get("title"), row.get("document_type"), row.get("revision"), (row.get("vehicle") or {}).get("frota") or (row.get("family") or {}).get("name"), row.get("valid_until"), row.get("effective_status")])

    def create_warehouse(self):
        dialog = SimpleFormDialog("Novo depósito", [("Código", QLineEdit()), ("Nome", QLineEdit()), ("Local", QLineEdit())], self)
        if dialog.exec() != QDialog.Accepted: return
        try:
            self.api_client.create_warehouse({"code": dialog.fields["Código"].text(), "name": dialog.fields["Nome"].text(), "location": dialog.fields["Local"].text()}); self._changed()
        except Exception as exc: show_notice(self, "Falha no depósito", str(exc), icon_name="warning")

    def initialize_stock(self):
        warehouse, material = QComboBox(), QComboBox()
        for row in self.api_client.get_warehouses(): warehouse.addItem(row.get("name"), row.get("id"))
        for row in self.materials: material.addItem(f"{row.get('referencia')} | {row.get('descricao')}", row.get("id"))
        quantity = QSpinBox(); quantity.setRange(0, 999999)
        dialog = SimpleFormDialog("Distribuir saldo existente", [("Depósito", warehouse), ("Material", material), ("Quantidade", quantity)], self)
        if dialog.exec() != QDialog.Accepted: return
        try:
            self.api_client.initialize_warehouse_stock({"warehouse_id": warehouse.currentData(), "material_id": material.currentData(), "quantity": quantity.value()}); self._changed()
        except Exception as exc: show_notice(self, "Falha no saldo", str(exc), icon_name="warning")

    def link_material_family(self):
        material, family = QComboBox(), QComboBox()
        for row in self.materials: material.addItem(f"{row.get('referencia')} | {row.get('descricao')}", row)
        for row in self.families: family.addItem(row.get("name"), row.get("id"))
        dialog = SimpleFormDialog("Vincular material à família", [("Material", material), ("Família", family)], self)
        if dialog.exec() != QDialog.Accepted: return
        try:
            selected = material.currentData(); family_ids = [item.get("family_id") for item in selected.get("family_applications", [])] + [family.currentData()]
            self.api_client.set_material_family_applications(selected["id"], sorted(set(family_ids))); self._changed()
        except Exception as exc: show_notice(self, "Falha na aplicação", str(exc), icon_name="warning")

    def create_document(self):
        code, title, doc_type, family, vehicle, revision = QLineEdit(), QLineEdit(), QComboBox(), QComboBox(), QComboBox(), QLineEdit("1")
        for value in ("MANUAL", "PROCEDIMENTO", "DIAGRAMA", "CERTIFICADO", "OUTRO"): doc_type.addItem(value, value)
        family.addItem("Sem vínculo", None); vehicle.addItem("Sem vínculo", None)
        for row in self.families: family.addItem(row.get("name"), row.get("id"))
        for row in self.vehicles: vehicle.addItem(row.get("frota") or row.get("placa"), row.get("id"))
        dialog = SimpleFormDialog("Novo documento técnico", [("Código", code), ("Título", title), ("Tipo", doc_type), ("Revisão", revision), ("Família", family), ("Equipamento", vehicle)], self)
        if dialog.exec() != QDialog.Accepted: return
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar PDF ou imagem", "", "Documentos (*.pdf *.jpg *.jpeg *.png *.webp)")
        if not file_path: return
        try:
            uploaded = self.api_client.upload_file(file_path, "biblioteca_tecnica", code.text() or "documento", "biblioteca")
            self.api_client.create_technical_document({"code": code.text(), "title": title.text(), "document_type": doc_type.currentData(), "revision": revision.text(), "family_id": family.currentData(), "vehicle_id": vehicle.currentData(), "file_path": uploaded.get("path")}); self._changed()
        except Exception as exc: show_notice(self, "Falha no documento", str(exc), icon_name="warning")

    def _changed(self):
        self.refresh(); self.data_changed.emit()
