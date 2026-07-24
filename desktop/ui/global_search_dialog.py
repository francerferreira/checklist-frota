from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout

from components import show_notice
from theme import configure_dialog_window, configure_table, make_table_item, style_card


class GlobalSearchDialog(QDialog):
    result_selected = Signal(dict)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.results: list[dict] = []
        self.setWindowTitle("Busca global")
        configure_dialog_window(self, width=840, height=560, min_width=700, min_height=460)
        style_card(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title = QLabel("Busca global")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Localize telas, equipamentos, materiais, colaboradores e alertas. Digite ao menos 2 caracteres.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        controls = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ex.: frota, placa, material, colaborador ou alerta")
        self.query_input.returnPressed.connect(self.search)
        search_button = QPushButton("Buscar")
        search_button.setProperty("variant", "primary")
        search_button.clicked.connect(self.search)
        controls.addWidget(self.query_input, 1)
        controls.addWidget(search_button)
        layout.addLayout(controls)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tipo", "Resultado", "Detalhe"])
        configure_table(self.table)
        self.table.setMinimumHeight(310)
        self.table.itemDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.table, 1)
        footer = QHBoxLayout()
        self.info = QLabel("Use Ctrl+K para abrir esta busca rapidamente.")
        self.info.setObjectName("MutedText")
        footer.addWidget(self.info)
        footer.addStretch()
        cancel = QPushButton("Fechar")
        open_button = QPushButton("Abrir selecionado")
        open_button.setProperty("variant", "primary")
        cancel.clicked.connect(self.reject)
        open_button.clicked.connect(self.open_selected)
        footer.addWidget(cancel)
        footer.addWidget(open_button)
        layout.addLayout(footer)

    def search(self):
        query = self.query_input.text().strip()
        if len(query) < 2:
            show_notice(self, "Busca curta", "Informe pelo menos 2 caracteres.", icon_name="warning")
            return
        try:
            self.results = self.api_client.search_global_records(query)
        except Exception as exc:
            show_notice(self, "Busca indisponivel", str(exc), icon_name="warning")
            return
        self.table.setRowCount(len(self.results))
        for row_index, row in enumerate(self.results):
            self.table.setItem(row_index, 0, make_table_item(str(row.get("kind") or ""), payload=row))
            self.table.setItem(row_index, 1, make_table_item(str(row.get("title") or "")))
            self.table.setItem(row_index, 2, make_table_item(str(row.get("subtitle") or "")))
        self.table.resizeColumnsToContents()
        self.info.setText(f"{len(self.results)} resultado(s) encontrado(s).")
        if self.results:
            self.table.selectRow(0)

    def open_selected(self, *_):
        rows = self.table.selectedRanges()
        if not rows:
            return
        item = self.table.item(rows[0].topRow(), 0)
        result = item.data(Qt.UserRole) if item else None
        if not result:
            return
        self.result_selected.emit(result)
        self.accept()
