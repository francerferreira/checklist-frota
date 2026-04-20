from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import severity_from_counts
from services import (
    build_item_message_package,
    build_macro_message_package,
    build_micro_message_package,
)
from services.export_service import (
    export_rows_to_csv,
    export_rows_to_pdf,
    export_rows_to_xlsx,
    make_default_export_path,
)
from components import MessageComposerDialog, TableSkeletonOverlay
from components import show_notice
from runtime_paths import asset_path
from theme import configure_table, style_filter_bar, style_table_card
from ui.detail_dialogs import NonConformityDetailDialog, VehicleDetailDialog


class ReportsPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setObjectName("ContentSurface")
        self.logo_path = asset_path("logo_grupo.png")
        self.macro_rows = []
        self.micro_rows = []
        self.item_rows = []
        self.vehicle_cache = {}
        self.dirty_tabs: set[str] = {"macro", "micro", "item", "vehicles"}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Relatorios")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Visao gerencial com tabelas amplas, exportacao executiva e abertura de detalhes operacionais por linha."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        subtitle.setMaximumHeight(24)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        header.addLayout(text_wrap)
        header.addStretch()

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filter_layout = QHBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(8)

        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Buscar item especifico")
        self.item_filter.setMinimumHeight(40)
        self.item_filter.returnPressed.connect(self.refresh_item_table)

        search_button = QPushButton("Consultar item")
        search_button.setProperty("variant", "primary")
        search_button.setMinimumHeight(40)
        search_button.clicked.connect(self.refresh_item_table)

        filter_layout.addWidget(self.item_filter, 1)
        filter_layout.addWidget(search_button)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_macro_tab(), "Macro")
        self.tabs.addTab(self._build_micro_tab(), "Micro")
        self.tabs.addTab(self._build_item_tab(), "Por item")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addLayout(header)
        layout.addWidget(self.filter_card)
        layout.addWidget(self.tabs, 1)

    def _build_macro_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.macro_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Relatorio macro")
        title.setObjectName("SectionTitle")
        caption = QLabel("Ranking consolidado de não conformidades por item.")
        caption.setObjectName("SectionCaption")
        caption.setMaximumHeight(20)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        export_csv = QPushButton("CSV")
        export_csv.setMinimumHeight(42)
        export_csv.clicked.connect(lambda: self.export_macro("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.setMinimumHeight(42)
        export_xlsx.clicked.connect(lambda: self.export_macro("xlsx"))
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.setMinimumHeight(42)
        export_pdf.clicked.connect(lambda: self.export_macro("pdf"))
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(42)
        message_button.clicked.connect(self.generate_macro_message)
        top.addLayout(text_wrap, 1)
        top.addWidget(message_button)
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        top.addWidget(export_pdf)

        self.macro_table = QTableWidget(0, 5)
        self.macro_table.setHorizontalHeaderLabels(
            ["Item", "Total de não conformidades", "Abertas", "Resolvidas", "Prioridade"]
        )
        configure_table(self.macro_table, stretch_last=False)
        self.macro_table.setMinimumHeight(520)
        self.macro_table.itemDoubleClicked.connect(self.open_macro_item)

        card_layout.addLayout(top)
        card_layout.addWidget(self.macro_table)
        layout.addWidget(card)
        return tab

    def _build_micro_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.micro_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Relatorio micro")
        title.setObjectName("SectionTitle")
        caption = QLabel("Leitura por equipamento, com acesso direto a ficha operacional.")
        caption.setObjectName("SectionCaption")
        caption.setMaximumHeight(20)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        export_csv = QPushButton("CSV")
        export_csv.setMinimumHeight(42)
        export_csv.clicked.connect(lambda: self.export_micro("csv"))
        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.setMinimumHeight(42)
        export_xlsx.clicked.connect(lambda: self.export_micro("xlsx"))
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.setMinimumHeight(42)
        export_pdf.clicked.connect(lambda: self.export_micro("pdf"))
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(42)
        message_button.clicked.connect(self.generate_micro_message)
        top.addLayout(text_wrap, 1)
        top.addWidget(message_button)
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        top.addWidget(export_pdf)

        self.micro_table = QTableWidget(0, 7)
        self.micro_table.setHorizontalHeaderLabels(
            ["Frota", "Placa", "Modelo", "Tipo", "Não conformidades", "Prioridade", "Último checklist"]
        )
        configure_table(self.micro_table, stretch_last=False)
        self.micro_table.setMinimumHeight(520)
        self.micro_table.itemDoubleClicked.connect(self.open_micro_vehicle)

        card_layout.addLayout(top)
        card_layout.addWidget(self.micro_table)
        layout.addWidget(card)
        return tab

    def _build_item_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = QFrame()
        style_table_card(card)
        self.item_skeleton = TableSkeletonOverlay(card, rows=6)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title = QLabel("Consulta por item")
        title.setObjectName("SectionTitle")
        caption = QLabel("Ocorrencias detalhadas por item, com acesso ao registro completo e fotos.")
        caption.setObjectName("SectionCaption")
        caption.setMaximumHeight(20)
        text_wrap = QVBoxLayout()
        text_wrap.addWidget(title)
        text_wrap.addWidget(caption)
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.setMinimumHeight(42)
        message_button.clicked.connect(self.generate_item_message)
        top.addLayout(text_wrap, 1)
        top.addWidget(message_button)

        self.item_table = QTableWidget(0, 8)
        self.item_table.setHorizontalHeaderLabels(
            ["Veiculo", "Item", "Data", "Motorista", "Status", "Prioridade", "Foto antes", "Foto depois"]
        )
        configure_table(self.item_table, stretch_last=False)
        self.item_table.setMinimumHeight(520)
        self.item_table.itemDoubleClicked.connect(self.open_item_occurrence)

        card_layout.addLayout(top)
        card_layout.addWidget(self.item_table)
        layout.addWidget(card)
        return tab

    def refresh(self):
        self.dirty_tabs.update({"macro", "micro", "item", "vehicles"})
        self._load_visible_tab()

    def set_loading_state(self, loading: bool):
        overlay = self._overlay_for_tab(self.current_tab_key())
        if not overlay:
            return
        if loading:
            overlay.show_skeleton(self._loading_message_for_tab(self.current_tab_key()))
        else:
            overlay.hide_skeleton()

    def refresh_item_table(self):
        self.dirty_tabs.add("item")
        self._load_item_tab()

    def _on_tab_changed(self, _index: int):
        self._load_visible_tab()

    def _load_visible_tab(self):
        self._load_tab(self.current_tab_key())

    def _load_tab(self, tab_key: str):
        if tab_key == "macro":
            if "macro" in self.dirty_tabs:
                self.macro_skeleton.show_skeleton(self._loading_message_for_tab("macro"))
                self.macro_rows = self.api_client.get_macro_report()
                self._populate_macro(self.macro_rows)
                self.dirty_tabs.discard("macro")
                self.macro_skeleton.hide_skeleton()
            return
        if tab_key == "micro":
            if "micro" in self.dirty_tabs:
                self.micro_skeleton.show_skeleton(self._loading_message_for_tab("micro"))
                self.micro_rows = self.api_client.get_micro_report()
                self._populate_micro(self.micro_rows)
                self.dirty_tabs.discard("micro")
                self.micro_skeleton.hide_skeleton()
                self._prime_vehicle_cache()
            return
        if tab_key == "item":
            if "item" in self.dirty_tabs:
                self.item_skeleton.show_skeleton(self._loading_message_for_tab("item"))
                self._load_item_tab()
                self.dirty_tabs.discard("item")
                self.item_skeleton.hide_skeleton()
            return

    def _load_item_tab(self):
        self.item_rows = self.api_client.get_item_report(self.item_filter.text().strip() or None)
        self.item_table.setUpdatesEnabled(False)
        self.item_table.blockSignals(True)
        try:
            self.item_table.setRowCount(len(self.item_rows))
            for row, item in enumerate(self.item_rows):
                severity = severity_from_counts(1, 0 if item["resolvido"] else 1)
                values = [
                    item["veiculo"]["frota"],
                    item["item_nome"],
                    item["created_at"].replace("T", " ")[:19],
                    item["usuario"]["nome"],
                    "Resolvida" if item["resolvido"] else "Aberta",
                    severity["label"],
                    "Sim" if item.get("foto_antes") else "Não",
                    "Sim" if item.get("foto_depois") else "Não",
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    if column == 5:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.item_table.setItem(row, column, cell)
        finally:
            self.item_table.blockSignals(False)
            self.item_table.setUpdatesEnabled(True)
        self.item_skeleton.hide_skeleton()

    def _populate_macro(self, rows):
        self.macro_table.setUpdatesEnabled(False)
        self.macro_table.blockSignals(True)
        try:
            self.macro_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                severity = severity_from_counts(item["total_nc"], item["abertas"])
                values = [
                    item["item_nome"],
                    str(item["total_nc"]),
                    str(item["abertas"]),
                    str(item["resolvidas"]),
                    severity["label"],
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    if column == 4:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.macro_table.setItem(row, column, cell)
        finally:
            self.macro_table.blockSignals(False)
            self.macro_table.setUpdatesEnabled(True)

    def _populate_micro(self, rows):
        self.micro_table.setUpdatesEnabled(False)
        self.micro_table.blockSignals(True)
        try:
            self.micro_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                severity = severity_from_counts(item["total_nc"], 0)
                values = [
                    item["frota"],
                    item["placa"],
                    item["modelo"],
                    item["tipo"].title(),
                    str(item["total_nc"]),
                    severity["label"],
                    self._format(item.get("ultimo_checklist")),
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    if column == 5:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    self.micro_table.setItem(row, column, cell)
        finally:
            self.micro_table.blockSignals(False)
            self.micro_table.setUpdatesEnabled(True)

    def _prime_vehicle_cache(self):
        if "vehicles" not in self.dirty_tabs and self.vehicle_cache:
            return
        try:
            vehicles = self.api_client.get_equipment()
            self.vehicle_cache = {vehicle["id"]: vehicle for vehicle in vehicles}
            self.dirty_tabs.discard("vehicles")
        except Exception:
            self.vehicle_cache = {}

    def open_macro_item(self, *_args):
        selected = self.macro_table.selectedRanges()
        if not selected:
            return
        item_name = self.macro_rows[selected[0].topRow()]["item_nome"]
        self.tabs.setCurrentIndex(2)
        self.item_filter.setText(item_name)
        self.refresh_item_table()

    def open_micro_vehicle(self, *_args):
        selected = self.micro_table.selectedRanges()
        if not selected:
            return
        row = self.micro_rows[selected[0].topRow()]
        vehicle = self.vehicle_cache.get(row.get("vehicle_id"))
        if not vehicle:
            show_notice(
                self,
                "Ficha indisponivel",
                "Não foi possível localizar os dados completos do equipamento.",
                icon_name="warning",
            )
            return
        dialog = VehicleDetailDialog(self.api_client, vehicle, self)
        dialog.exec()

    def open_item_occurrence(self, item=None):
        if item is not None:
            row_index = item.row()
        else:
            selected = self.item_table.selectedRanges()
            if not selected:
                return
            row_index = selected[0].topRow()

        if row_index < 0 or row_index >= len(self.item_rows):
            return
        dialog = NonConformityDetailDialog(self.api_client, self.item_rows[row_index], self)
        dialog.exec()

    def generate_macro_message(self):
        if not self.macro_rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_macro_message_package(
            self.macro_rows,
            self._build_period_label("relatorio_macro", self.macro_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def generate_micro_message(self):
        if not self.micro_rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_micro_message_package(
            self.micro_rows,
            self._build_period_label("relatorio_micro", self.micro_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def generate_item_message(self):
        if not self.item_rows:
            show_notice(self, "Sem dados", "Não há ocorrências disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_item_message_package(
            self.item_rows,
            self.item_filter.text().strip() or "Item selecionado",
            self._build_period_label("relatorio_item", self.item_rows),
            generated_by=self.api_client.user.get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def export_macro(self, file_type: str):
        columns = [
            ("Item", "item_nome"),
            ("Total de não conformidades", "total_nc"),
            ("Abertas", "abertas"),
            ("Resolvidas", "resolvidas"),
        ]
        self._export_dataset(
            "relatorio_macro",
            "Relatorio Macro de Não conformidades",
            "Consolidado executivo por item",
            columns,
            self.macro_rows,
            file_type,
        )

    def export_micro(self, file_type: str):
        rows = []
        for row in self.micro_rows:
            rows.append(
                {
                    "frota": row["frota"],
                    "placa": row["placa"],
                    "modelo": row["modelo"],
                    "tipo": row["tipo"].title(),
                    "total_nc": row["total_nc"],
                    "ultimo_checklist": self._format(row.get("ultimo_checklist")),
                }
            )
        columns = [
            ("Frota", "frota"),
            ("Placa", "placa"),
            ("Modelo", "modelo"),
            ("Tipo", "tipo"),
            ("Não conformidades", "total_nc"),
            ("Último checklist", "ultimo_checklist"),
        ]
        self._export_dataset(
            "relatorio_micro",
            "Relatorio Micro por Equipamento",
            "Visao operacional por unidade da frota",
            columns,
            rows,
            file_type,
        )

    def _export_dataset(self, prefix: str, title: str, subtitle: str, columns, rows, file_type: str):
        if not rows:
            show_notice(self, "Sem dados", "Não há dados disponíveis para exportação.", icon_name="warning")
            return

        default_path = make_default_export_path(prefix, file_type)
        filters = {
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
            "pdf": "PDF (*.pdf)",
        }
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório",
            default_path,
            filters[file_type],
        )
        if not filename:
            return

        try:
            if file_type == "csv":
                export_rows_to_csv(columns, rows, filename)
            elif file_type == "xlsx":
                export_rows_to_xlsx(title, columns, rows, filename)
            else:
                export_rows_to_pdf(
                    title,
                    subtitle,
                    columns,
                    rows,
                    filename,
                    logo_path=self.logo_path,
                    generated_by=self.api_client.user.get("nome", ""),
                    period_label=self._build_period_label(prefix, rows),
                )
            show_notice(self, "Exportacao concluida", f"Arquivo salvo em:\n{filename}", icon_name="reports")
        except Exception as exc:
            show_notice(self, "Falha na exportacao", str(exc), icon_name="warning")

    def _build_period_label(self, prefix: str, rows: list[dict]) -> str:
        today = datetime.now().strftime("%d/%m/%Y")
        if prefix == "relatorio_micro":
            dates = [row.get("ultimo_checklist") for row in rows if row.get("ultimo_checklist") and row.get("ultimo_checklist") != "-"]
            if dates:
                normalized = sorted(date.replace("T", " ")[:10] for date in dates)
                start = self._format_date_only(normalized[0])
                end = self._format_date_only(normalized[-1])
                return f"{start} a {end}"
        if prefix == "relatorio_item":
            dates = [row.get("created_at") for row in rows if row.get("created_at")]
            if dates:
                normalized = sorted(date.replace("T", " ")[:10] for date in dates)
                start = self._format_date_only(normalized[0])
                end = self._format_date_only(normalized[-1])
                return f"{start} a {end}"
        return f"Base consolidada ate {today}"

    def current_tab_key(self) -> str:
        return {0: "macro", 1: "micro", 2: "item"}.get(self.tabs.currentIndex(), "macro")

    def _overlay_for_tab(self, tab_key: str):
        return {
            "macro": self.macro_skeleton,
            "micro": self.micro_skeleton,
            "item": self.item_skeleton,
        }.get(tab_key)

    @staticmethod
    def _loading_message_for_tab(tab_key: str) -> str:
        return {
            "macro": "Montando relatório macro",
            "micro": "Montando relatório micro",
            "item": "Montando consulta por item",
        }.get(tab_key, "Montando relatório executivo")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    @staticmethod
    def _format_date_only(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value

