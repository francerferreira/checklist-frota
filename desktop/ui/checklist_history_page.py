from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDateEdit,
)

from components import choose_pdf_save_path, finalize_export_result, show_notice
from runtime_paths import asset_path
from services import export_checklist_detail_pdf
from services.export_service import make_default_export_path
from theme import configure_dialog_window, configure_table, make_table_item, style_filter_bar, style_table_card


class ChecklistSelectionDialog(QDialog):
    def __init__(self, entries: list[dict], parent=None):
        super().__init__(parent)
        self.selected_checklist_id: int | None = None
        self.setWindowTitle("Selecionar checklist do dia")
        configure_dialog_window(self, width=520, height=420, min_width=460, min_height=360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Checklists registrados nesta data")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        for entry in entries:
            label = (
                f"{entry.get('time') or '--:--'} - {entry.get('user') or '-'} | "
                f"{entry.get('total_itens', 0)} itens | {entry.get('total_nc', 0)} NC"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, int(entry.get("id") or 0))
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._accept_item)
        layout.addWidget(self.list_widget, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        open_button = QPushButton("Abrir checklist")
        open_button.setProperty("variant", "primary")
        cancel.clicked.connect(self.reject)
        open_button.clicked.connect(self.accept_selected)
        actions.addWidget(cancel)
        actions.addWidget(open_button)
        layout.addLayout(actions)

        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _accept_item(self, item: QListWidgetItem):
        self.selected_checklist_id = int(item.data(Qt.UserRole) or 0)
        self.accept()

    def accept_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        self._accept_item(item)


class ChecklistDetailDialog(QDialog):
    def __init__(self, api_client, checklist: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.checklist = checklist
        self.setWindowTitle("Detalhe do checklist")
        configure_dialog_window(self, width=1180, height=760, min_width=980, min_height=640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        vehicle = checklist.get("vehicle") or {}
        user = checklist.get("user") or {}
        title = QLabel(f"{vehicle.get('frota') or '-'} - Checklist completo")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"{vehicle.get('placa') or '-'} | {vehicle.get('modelo') or '-'} | "
            f"{_format_datetime(checklist.get('created_at'))} | {user.get('nome') or user.get('login') or '-'}"
        )
        subtitle.setObjectName("SectionCaption")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        summary = QLabel(
            f"{checklist.get('total_itens', 0)} itens | "
            f"{checklist.get('total_nc', 0)} não conformidade(s)"
        )
        summary.setObjectName("TopBarPill")
        layout.addWidget(summary)

        self.nc_table = self._make_table()
        self.ok_table = self._make_table()
        self._fill_tables()

        nc_card = self._wrap_table("Não conformidades", self.nc_table)
        ok_card = self._wrap_table("Itens OK", self.ok_table)
        layout.addWidget(nc_card, 1)
        layout.addWidget(ok_card, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        export_button = QPushButton("Exportar PDF compacto")
        export_button.setProperty("variant", "danger")
        export_button.clicked.connect(self.export_pdf)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        actions.addWidget(export_button)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _make_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Item", "Status", "Observação", "Peça", "Resolução"])
        configure_table(table, stretch_last=True)
        table.setSortingEnabled(True)
        table.setMinimumHeight(170)
        return table

    def _wrap_table(self, title_text: str, table: QTableWidget) -> QFrame:
        card = QFrame()
        style_table_card(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(table, 1)
        return card

    def _fill_tables(self):
        items = self.checklist.get("itens") or []
        self._fill_table(self.nc_table, [item for item in items if item.get("status") == "NC"])
        self._fill_table(self.ok_table, [item for item in items if item.get("status") == "OK"])

    @staticmethod
    def _fill_table(table: QTableWidget, rows: list[dict]):
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            piece = " ".join(
                value for value in [item.get("codigo_peca") or "", item.get("descricao_peca") or ""] if value
            ) or "-"
            values = [
                item.get("item_label") or item.get("item_nome") or "-",
                item.get("status") or "-",
                item.get("observacao") or "-",
                piece,
                _format_datetime(item.get("data_resolucao")) if item.get("data_resolucao") else ("Resolvido" if item.get("resolvido") else "-"),
            ]
            for column, value in enumerate(values):
                table.setItem(row_index, column, make_table_item(value))
        table.setSortingEnabled(True)

    def export_pdf(self):
        vehicle = self.checklist.get("vehicle") or {}
        default_path = make_default_export_path(f"checklist_{vehicle.get('frota', 'frota').lower()}", "pdf")
        filename = choose_pdf_save_path(self, "Exportar checklist em PDF", default_path)
        if not filename:
            return
        try:
            logo_path = asset_path("app-logo-cover.png")
            if not logo_path.exists():
                logo_path = asset_path("cf-logo-cover.png")
            item_images = self._collect_non_conformity_images()
            path = export_checklist_detail_pdf(
                self.checklist,
                output_path=filename,
                logo_path=logo_path if logo_path.exists() else None,
                generated_by=(self.api_client.user or {}).get("nome") or (self.api_client.user or {}).get("login") or "",
                item_images=item_images,
            )
            finalize_export_result(self, path)
        except Exception as exc:
            show_notice(self, "Falha ao exportar PDF", str(exc), icon_name="warning")

    def _collect_non_conformity_images(self) -> dict[int, dict[str, bytes | None]]:
        images: dict[int, dict[str, bytes | None]] = {}
        for item in self.checklist.get("itens") or []:
            if item.get("status") != "NC" or item.get("id") is None:
                continue
            item_id = int(item.get("id"))
            images[item_id] = {
                "before": self._fetch_checklist_image(item.get("foto_antes")),
                "after": self._fetch_checklist_image(item.get("foto_depois")),
            }
        return images

    def _fetch_checklist_image(self, relative_path: str | None) -> bytes | None:
        try:
            return self.api_client.fetch_image(relative_path)
        except Exception:
            return None


class ChecklistHistoryPage(QWidget):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.payload: dict = {"columns": [], "rows": []}
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Histórico de Checklist")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Matriz por frota e data, com abertura do checklist completo pelo horário.")
        subtitle.setObjectName("SectionCaption")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap)
        header.addStretch()
        root.addLayout(header)

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filters = QHBoxLayout(self.filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Frota, placa, modelo ou descrição")
        self.search_input.textChanged.connect(self.render_table)
        self.type_filter = QComboBox()
        self.type_filter.addItem("TODOS", "")
        self.type_filter.addItem("CAVALO", "cavalo")
        self.type_filter.addItem("CARRETA", "carreta")
        self.type_filter.currentIndexChanged.connect(self._schedule_refresh)
        today = date.today()
        self.start_date = _date_edit(today - timedelta(days=32))
        self.end_date = _date_edit(today)
        self.start_date.dateChanged.connect(self._schedule_refresh)
        self.end_date.dateChanged.connect(self._schedule_refresh)

        filters.addWidget(self._field("EQUIPAMENTO", self.search_input), 1)
        filters.addWidget(self._field("TIPO", self.type_filter), 1)
        filters.addWidget(self._field("DATA INICIAL", self.start_date), 1)
        filters.addWidget(self._field("DATA FINAL", self.end_date), 1)
        root.addWidget(self.filter_card)

        self.summary_card = QFrame()
        style_table_card(self.summary_card)
        summary_layout = QHBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        self.period_label = QLabel("PERÍODO\n-")
        self.days_label = QLabel("DATAS NA MATRIZ\n0 DIAS")
        self.records_label = QLabel("CHECKLISTS NO FILTRO\n0 REGISTROS")
        for label in (self.period_label, self.days_label, self.records_label):
            label.setObjectName("TopBarPill")
            summary_layout.addWidget(label, 1)
        root.addWidget(self.summary_card)

        self.table = QTableWidget(0, 2)
        configure_table(self.table, stretch_last=False, auto_fit=False)
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.SolidLine)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(False)
        self.table.itemDoubleClicked.connect(self.open_cell_checklist)
        self.table.horizontalHeader().setMinimumSectionSize(44)
        root.addWidget(self.table, 1)

    def _field(self, label_text: str, widget: QWidget) -> QWidget:
        box = QFrame()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("SectionCaption")
        layout.addWidget(label)
        layout.addWidget(widget)
        return box

    def _schedule_refresh(self):
        self._filter_timer.start(280)

    def refresh(self):
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        if end < start:
            show_notice(self, "Filtro inválido", "A data final deve ser maior ou igual à data inicial.", icon_name="warning")
            return
        self.payload = self.api_client.get_checklist_history_matrix(
            tipo=self.type_filter.currentData() or None,
            data_inicio=start,
            data_fim=end,
        ) or {"columns": [], "rows": []}
        self.render_table()

    def render_table(self):
        columns = self.payload.get("columns") or []
        rows = self._visible_rows()
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(2 + len(columns))
        self.table.setHorizontalHeaderLabels(["FROTA", "Nº"] + [column.get("label") or "-" for column in columns])
        self.table.setRowCount(len(rows))
        total_records = sum(int(row.get("checklist_count") or 0) for row in rows)
        self.period_label.setText(f"PERÍODO\n{self.start_date.date().toString('dd/MM/yyyy')} A {self.end_date.date().toString('dd/MM/yyyy')}")
        self.days_label.setText(f"DATAS NA MATRIZ\n{len(columns)} DIAS")
        self.records_label.setText(f"CHECKLISTS NO FILTRO\n{total_records} REGISTROS")

        for row_index, row in enumerate(rows):
            frota_text = "\n".join(filter(None, [
                str(row.get("frota") or "-"),
                str(row.get("placa") or "-"),
                str(row.get("modelo") or row.get("descricao") or "-"),
            ]))
            self.table.setItem(row_index, 0, make_table_item(frota_text, payload=row))
            self.table.setItem(row_index, 1, make_table_item(row.get("checklist_count") or 0))
            for column_index, value in enumerate(row.get("cells") or [], start=2):
                details = (row.get("cell_details") or [])[column_index - 2] if column_index - 2 < len(row.get("cell_details") or []) else []
                display = value or ""
                if display and len(details) > 1:
                    display = f"{display} (+{len(details) - 1})"
                item = make_table_item(display, payload={"entries": details})
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column_index, item)
            self.table.setRowHeight(row_index, 74)

        self.table.setColumnWidth(0, 128)
        self.table.setColumnWidth(1, 44)
        self._resize_date_columns_to_contents()
        self.table.setSortingEnabled(True)

    def _resize_date_columns_to_contents(self):
        for column in range(2, self.table.columnCount()):
            self.table.resizeColumnToContents(column)
            content_width = self.table.columnWidth(column)
            self.table.setColumnWidth(column, max(72, content_width + 8))

    def _visible_rows(self) -> list[dict]:
        query = _normalize(self.search_input.text())
        rows = list(self.payload.get("rows") or [])
        if not query:
            return rows
        return [
            row for row in rows
            if query in _normalize(" ".join(str(row.get(key) or "") for key in ("frota", "placa", "modelo", "descricao")))
        ]

    def open_cell_checklist(self, item: QTableWidgetItem):
        if item.column() < 2:
            return
        entries = (item.data(Qt.UserRole) or {}).get("entries") or []
        if not entries:
            return
        checklist_id = int(entries[0].get("id") or 0)
        if len(entries) > 1:
            dialog = ChecklistSelectionDialog(entries, self)
            if dialog.exec() != QDialog.Accepted or not dialog.selected_checklist_id:
                return
            checklist_id = dialog.selected_checklist_id
        try:
            checklist = self.api_client.get_checklist_detail(checklist_id)
            ChecklistDetailDialog(self.api_client, checklist, self).exec()
        except Exception as exc:
            show_notice(self, "Falha ao abrir checklist", str(exc), icon_name="warning")


def _date_edit(value: date) -> QDateEdit:
    editor = QDateEdit()
    editor.setCalendarPopup(True)
    editor.setDisplayFormat("dd/MM/yyyy")
    editor.setDate(QDate(value.year, value.month, value.day))
    editor.setMinimumHeight(34)
    return editor


def _normalize(value: str) -> str:
    return str(value or "").strip().upper()


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return value.replace("T", " ")[:16]
    except Exception:
        return str(value)
