from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QHeaderView,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, ask_confirmation, make_icon, show_notice, start_export_task
from components import MessageComposerDialog
from runtime_paths import asset_path
from services.export_service import (
    export_material_report_pdf,
    export_material_report_xlsx,
    make_default_export_path,
)
from services import build_material_message_package
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card


class MaterialDialog(QDialog):
    def __init__(self, api_client, material: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.material = material or {}
        self.selected_file = ""
        self.result_payload = None

        self.setWindowTitle("Cadastro de material")
        configure_dialog_window(self, width=900, height=760, min_width=760, min_height=620)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=980)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("materials", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title = QLabel("Controle de material")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Cadastre referência, descrição, foto, aplicação e políticas de estoque do material.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.referencia_input = QLineEdit(self.material.get("referencia", ""))
        self.descricao_input = QLineEdit(self.material.get("descricao", ""))
        self.aplicacao_combo = QComboBox()
        self.aplicacao_combo.addItem("Cavalo", "cavalo")
        self.aplicacao_combo.addItem("Carreta", "carreta")
        self.aplicacao_combo.addItem("Ambos", "ambos")
        idx = self.aplicacao_combo.findData(self.material.get("aplicacao_tipo", "ambos"))
        if idx >= 0:
            self.aplicacao_combo.setCurrentIndex(idx)

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(0)
        self.quantidade_spin.setMaximum(999999)
        self.quantidade_spin.setValue(int(self.material.get("quantidade_estoque", 0)))
        if self.material:
            self.quantidade_spin.setEnabled(False)
            self.quantidade_spin.setToolTip("Para material já cadastrado, use o botão Ajustar estoque.")

        self.estoque_minimo_spin = QSpinBox()
        self.estoque_minimo_spin.setMinimum(0)
        self.estoque_minimo_spin.setMaximum(999999)
        self.estoque_minimo_spin.setValue(int(self.material.get("estoque_minimo", 0)))

        self.ativo_checkbox = QCheckBox("Material ativo")
        self.ativo_checkbox.setChecked(bool(self.material.get("ativo", True)))

        self.file_label = QLabel(self.material.get("foto_path") or "Nenhuma foto selecionada.")
        self.file_label.setObjectName("MutedText")
        self.file_label.setWordWrap(True)
        photo_button = QPushButton("Selecionar foto")
        photo_button.clicked.connect(self.select_file)

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1, *, highlight: bool = False):
            field = QFrame()
            if highlight:
                field.setObjectName("DialogInfoBlock")
                field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            margin = 12 if highlight else 0
            field_layout.setContentsMargins(margin, margin, margin, margin)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Referência", self.referencia_input, highlight=True)
        add_field(0, 1, "Descrição", self.descricao_input, highlight=True)
        add_field(1, 0, "Aplicação", self.aplicacao_combo, highlight=True)
        add_field(1, 1, "Quantidade em estoque", self.quantidade_spin, highlight=True)
        add_field(2, 0, "Estoque mínimo", self.estoque_minimo_spin)

        media_field = QFrame()
        media_field.setObjectName("DialogInfoBlock")
        media_field.setAttribute(Qt.WA_StyledBackground, True)
        media_layout = QVBoxLayout(media_field)
        media_layout.setContentsMargins(12, 12, 12, 12)
        media_layout.setSpacing(8)
        media_title = QLabel("Foto do material")
        media_title.setObjectName("SectionCaption")
        media_actions = QHBoxLayout()
        media_actions.setContentsMargins(0, 0, 0, 0)
        media_actions.setSpacing(10)
        media_actions.addWidget(photo_button, 0)
        media_actions.addWidget(self.file_label, 1)
        media_layout.addWidget(media_title)
        media_layout.addLayout(media_actions)
        media_layout.addWidget(self.ativo_checkbox, 0, Qt.AlignLeft)
        form.addWidget(media_field, 2, 1)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar material")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def select_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Selecionar foto do material", "", "Imagens (*.png *.jpg *.jpeg *.webp)")
        if filename:
            self.selected_file = filename
            self.file_label.setText(filename)

    def submit(self):
        try:
            payload = {
                "referencia": self.referencia_input.text().strip(),
                "descricao": self.descricao_input.text().strip(),
                "aplicacao_tipo": self.aplicacao_combo.currentData(),
                "quantidade_estoque": int(self.quantidade_spin.value()),
                "estoque_minimo": int(self.estoque_minimo_spin.value()),
                "ativo": self.ativo_checkbox.isChecked(),
            }
            if self.selected_file:
                upload = self.api_client.upload_file(
                    self.selected_file,
                    payload["referencia"] or "material",
                    "material",
                    self.api_client.user["login"],
                )
                payload["foto_path"] = upload["path"]
            elif self.material.get("foto_path"):
                payload["foto_path"] = self.material["foto_path"]
            self.result_payload = payload
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")


class StockAdjustDialog(QDialog):
    def __init__(self, api_client, material: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.material = material
        self.result_payload = None

        self.setWindowTitle("Ajustar estoque")
        configure_dialog_window(self, width=960, height=680, min_width=840, min_height=620)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=760)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel(f"{material.get('referencia')} - {material.get('descricao')}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Registre entrada, saída ou ajuste manual de estoque.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Entrada", "ENTRADA")
        self.tipo_combo.addItem("Saida", "SAIDA")
        self.tipo_combo.addItem("Ajuste", "AJUSTE")

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999999)
        self.quantidade_spin.setValue(1)

        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Motivo do ajuste de estoque.")

        form.addWidget(QLabel("Tipo"), 0, 0)
        form.addWidget(self.tipo_combo, 0, 1)
        form.addWidget(QLabel("Quantidade"), 1, 0)
        form.addWidget(self.quantidade_spin, 1, 1)
        form.addWidget(QLabel("Observação"), 2, 0, 1, 2)
        form.addWidget(self.observacao_input, 3, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Aplicar ajuste")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def submit(self):
        self.result_payload = {
            "tipo_movimento": self.tipo_combo.currentData(),
            "quantidade": int(self.quantidade_spin.value()),
            "observacao": self.observacao_input.toPlainText().strip(),
        }
        self.accept()


class MaterialMovementsDialog(QDialog):
    def __init__(self, api_client, material: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.material = material
        self.movements = self.api_client.get_material_movements(material["id"])

        self.setWindowTitle("Histórico de estoque")
        configure_dialog_window(self, width=1640, height=940, min_width=1280, min_height=760)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=0)

        dialog_header = QFrame()
        dialog_header.setObjectName("DialogHeader")
        dialog_header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(dialog_header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel(f"{material.get('referencia')} - {material.get('descricao')}")
        title.setObjectName("DialogHeaderTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Movimentações de estoque, consumo por atividade e saídas para resolução de não conformidade.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        table_card = QFrame()
        style_table_card(table_card)
        table_card.setMinimumHeight(620)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.setSpacing(10)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Data", "Tipo", "Quantidade", "Saldo anterior", "Saldo posterior", "Usuário", "Observação"])
        configure_table(self.table, stretch_last=False)
        table_header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            table_header.setSectionResizeMode(col, QHeaderView.Interactive)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setMinimumHeight(680)
        self._populate()

        table_layout.addWidget(self.table)
        layout.addWidget(dialog_header)
        layout.addWidget(table_card, 1)

    def _populate(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.movements))
            for row, movement in enumerate(self.movements):
                values = [
                    (movement.get("created_at") or "-").replace("T", " ")[:19],
                    movement.get("tipo_movimento") or "-",
                    str(movement.get("quantidade") or 0),
                    str(movement.get("saldo_anterior") or 0),
                    str(movement.get("saldo_posterior") or 0),
                    movement.get("usuario", {}).get("nome") or "-",
                    movement.get("observacao") or "-",
                ]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, make_table_item(value))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)


class MaterialReportDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.logo_path = asset_path("app-logo-cover.png")
        self.report = {}
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)

        self.setWindowTitle("Relatório de estoque")
        configure_dialog_window(self, width=1320, height=820, min_width=980, min_height=680)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1360)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        title_wrap = QVBoxLayout()
        title = QLabel("Relatório de estoque")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Análise de materiais abaixo do mínimo, consumo no período e ranking dos mais utilizados.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        export_xlsx = QPushButton("Excel")
        export_xlsx.setProperty("variant", "primary")
        export_xlsx.clicked.connect(self.export_xlsx)
        export_pdf = QPushButton("PDF Executivo")
        export_pdf.clicked.connect(self.export_pdf)
        message_button = QPushButton("Gerar mensagem")
        message_button.setProperty("variant", "primary")
        message_button.clicked.connect(self.generate_message)

        header_layout.addLayout(title_wrap, 1)
        header_layout.addWidget(message_button)
        header_layout.addWidget(export_xlsx)
        header_layout.addWidget(export_pdf)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(14, 14, 14, 14)
        filters.setSpacing(10)

        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("Data inicial (YYYY-MM-DD)")
        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("Data final (YYYY-MM-DD)")
        self.start_input.textChanged.connect(self._schedule_live_refresh)
        self.end_input.textChanged.connect(self._schedule_live_refresh)
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)

        filters.addWidget(self.start_input)
        filters.addWidget(self.end_input)
        filters.addWidget(refresh_button)

        summary_card = QFrame()
        style_filter_bar(summary_card)
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(10)
        self.total_badge = QLabel("0 materiais")
        self.total_badge.setObjectName("TopBarPill")
        self.low_badge = QLabel("0 abaixo do mínimo")
        self.low_badge.setObjectName("TopBarPill")
        self.stock_badge = QLabel("Saldo 0")
        self.stock_badge.setObjectName("TopBarPill")
        self.consumption_badge = QLabel("Consumo 0")
        self.consumption_badge.setObjectName("TopBarPill")
        summary_layout.addWidget(self.total_badge)
        summary_layout.addWidget(self.low_badge)
        summary_layout.addWidget(self.stock_badge)
        summary_layout.addWidget(self.consumption_badge)
        summary_layout.addStretch()

        self.low_table = self._make_table(["Referência", "Descrição", "Aplicação", "Estoque", "Mínimo", "Déficit"])
        self.consumption_table = self._make_table(["Referência", "Descrição", "Consumo", "Último consumo"])
        self.ranking_table = self._make_table(["Referência", "Descrição", "Consumo", "Último consumo"])

        layout.addWidget(header)
        layout.addWidget(filter_card)
        layout.addWidget(summary_card)
        layout.addWidget(self._wrap_table("Materiais abaixo do mínimo", self.low_table), 1)
        layout.addWidget(self._wrap_table("Consumo no periodo", self.consumption_table), 1)
        layout.addWidget(self._wrap_table("Ranking Top 5", self.ranking_table), 1)

        self.refresh()

    def _schedule_live_refresh(self, *_args):
        start = self.start_input.text().strip()
        end = self.end_input.text().strip()
        if (start and len(start) < 10) or (end and len(end) < 10):
            return
        self._live_filter_timer.start(280)

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        configure_table(table, stretch_last=False)
        table.setMinimumHeight(170)
        return table

    def _wrap_table(self, title_text: str, table: QTableWidget) -> QFrame:
        card = QFrame()
        style_table_card(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(table)
        return card

    def refresh(self):
        self.report = self.api_client.get_material_report(
            self.start_input.text().strip() or None,
            self.end_input.text().strip() or None,
        )
        resumo = self.report.get("resumo", {})
        self.total_badge.setText(f"{resumo.get('total_materiais', 0)} materiais")
        self.low_badge.setText(f"{resumo.get('abaixo_minimo', 0)} abaixo do mínimo")
        self.stock_badge.setText(f"Saldo {resumo.get('saldo_total', 0)}")
        self.consumption_badge.setText(f"Consumo {resumo.get('consumo_total_periodo', 0)}")
        self._fill_table(self.low_table, self.report.get("baixo_estoque", []), ["referencia", "descricao", "aplicacao_tipo", "quantidade_estoque", "estoque_minimo", "deficit"])
        self._fill_table(self.consumption_table, self.report.get("consumo_periodo", []), ["referencia", "descricao", "consumo_total", "ultimo_consumo"])
        self._fill_table(self.ranking_table, self.report.get("ranking_uso", []), ["referencia", "descricao", "consumo_total", "ultimo_consumo"])

    def _fill_table(self, table: QTableWidget, rows: list[dict], keys: list[str]):
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for col_index, key in enumerate(keys):
                    value = row.get(key)
                    if key == "ultimo_consumo" and value:
                        value = value.replace("T", " ")[:19]
                    table.setItem(row_index, col_index, make_table_item(value if value is not None else "-"))
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.setSortingEnabled(True)

    def export_xlsx(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório de estoque",
            make_default_export_path("relatorio_estoque", "xlsx"),
            "Excel (*.xlsx)",
        )
        if not filename:
            return
        try:
            export_material_report_xlsx(self.report, output_path=filename)
            show_notice(self, "Exportação concluída", f"Arquivo salvo em:\n{filename}", icon_name="reports")
        except Exception as exc:
            show_notice(self, "Falha na exportação", str(exc), icon_name="warning")

    def export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório de estoque",
            make_default_export_path("relatorio_estoque", "pdf"),
            "PDF (*.pdf)",
        )
        if not filename:
            return
        report = dict(self.report)

        def task(progress):
            progress(14, "Preparando relatório de estoque")
            progress(48, "Montando tabelas e indicadores")
            export_material_report_pdf(
                report,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=(self.api_client.user or {}).get("nome", ""),
            )
            return filename

        start_export_task(
            self,
            "Exportando PDF de estoque",
            task,
            success_title="Exportação concluída",
            failure_title="Falha na exportação",
        )

    def generate_message(self):
        if not self.report:
            show_notice(self, "Sem dados", "Não há dados disponíveis para gerar mensagem.", icon_name="warning")
            return
        package = build_material_message_package(
            self.report,
            self._period_label(),
            generated_by=(self.api_client.user or {}).get("nome", ""),
        )
        MessageComposerDialog(package, self).exec()

    def _period_label(self) -> str:
        periodo = self.report.get("periodo", {}) if isinstance(self.report, dict) else {}
        start = periodo.get("data_inicial")
        end = periodo.get("data_final")
        if start and end:
            return f"{self._format_date(start)} a {self._format_date(end)}"
        if start:
            return f"A partir de {self._format_date(start)}"
        return "Base consolidada"

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value


class MaterialsPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.items = []
        self.current_item = None
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Controle de material")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Cadastre materiais, acompanhe estoque mínimo e ajuste saldo para suportar atividades e manutenções.")
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_button = QPushButton("Adicionar")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setMinimumHeight(34)
        self.add_button.clicked.connect(self.add_material)
        self.edit_button = QPushButton("Editar")
        self.edit_button.setMinimumHeight(34)
        self.edit_button.clicked.connect(self.edit_selected)
        self.adjust_button = QPushButton("Ajustar estoque")
        self.adjust_button.setMinimumHeight(34)
        self.adjust_button.clicked.connect(self.adjust_stock)
        self.report_button = QPushButton("Relatório")
        self.report_button.setMinimumHeight(34)
        self.report_button.clicked.connect(self.open_report)
        self.history_button = QPushButton("Histórico")
        self.history_button.setMinimumHeight(34)
        self.history_button.clicked.connect(self.open_history)
        self.delete_button = QPushButton("Excluir")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.setMinimumHeight(34)
        self.delete_button.clicked.connect(self.delete_selected)
        for button in (self.add_button, self.edit_button, self.adjust_button, self.report_button, self.history_button, self.delete_button):
            buttons.addWidget(button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(buttons)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por referência ou descrição")
        self.search_input.setMinimumHeight(34)
        self.search_input.returnPressed.connect(self.refresh)
        self.search_input.textChanged.connect(self._schedule_live_refresh)
        self.type_filter = QComboBox()
        self.type_filter.addItem("Todos", "")
        self.type_filter.addItem("Cavalo", "cavalo")
        self.type_filter.addItem("Carreta", "carreta")
        self.type_filter.addItem("Ambos", "ambos")
        self.type_filter.setMinimumHeight(34)
        self.type_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        self.active_filter = QComboBox()
        self.active_filter.addItem("Ativos", "true")
        self.active_filter.addItem("Todos", "all")
        self.active_filter.setMinimumHeight(34)
        self.active_filter.currentIndexChanged.connect(self._schedule_live_refresh)
        self.low_stock_check = QCheckBox("Somente baixo estoque")
        self.low_stock_check.toggled.connect(self._schedule_live_refresh)
        filter_button = QPushButton("Aplicar filtros")
        filter_button.setMinimumHeight(34)
        filter_button.clicked.connect(self.refresh)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.active_filter)
        filters.addWidget(self.low_stock_check)
        filters.addWidget(filter_button)

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Base de materiais")
        title_label.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Nenhum material carregado")
        self.summary_badge.setObjectName("TopBarPill")
        top.addWidget(title_label)
        top.addStretch()
        top.addWidget(self.summary_badge)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Referência", "Descrição", "Aplicação", "Estoque", "Mínimo", "Status do estoque", "Foto", "Ativo"])
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(560)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())
        self.table.itemDoubleClicked.connect(self.open_history)

        table_layout.addLayout(top)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addWidget(filter_card)
        layout.addWidget(table_card, 1)
        self._set_action_state(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(220)

    def _set_action_state(self, enabled: bool):
        self.edit_button.setEnabled(enabled)
        self.adjust_button.setEnabled(enabled)
        self.history_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def refresh(self, preferred_item_id: int | None = None):
        self.items = self.api_client.get_materials(
            tipo=self.type_filter.currentData() or None,
            search=self.search_input.text().strip() or None,
            ativos=self.active_filter.currentData(),
            baixo_estoque=self.low_stock_check.isChecked(),
        )
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            for row, item in enumerate(self.items):
                stock_label = "Baixo estoque" if item.get("baixo_estoque") else "Controlado"
                values = [
                    item.get("referencia") or "-",
                    item.get("descricao") or "-",
                    (item.get("aplicacao_tipo") or "-").title(),
                    str(item.get("quantidade_estoque") or 0),
                    str(item.get("estoque_minimo") or 0),
                    stock_label,
                    "Sim" if item.get("foto_path") else "Não",
                    "Sim" if item.get("ativo") else "Não",
                ]
                for col, value in enumerate(values):
                    cell = make_table_item(value, payload=item if col == 0 else None)
                    if col == 5:
                        colors = {"background": "#FEE2E2", "color": "#B91C1C"} if item.get("baixo_estoque") else {"background": "#DCFCE7", "color": "#166534"}
                        cell.setBackground(QBrush(QColor(colors["background"])))
                        cell.setForeground(QBrush(QColor(colors["color"])))
                    self.table.setItem(row, col, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        self.summary_badge.setText(f"{len(self.items)} materiais")
        if self.items:
            selected_row = 0
            if preferred_item_id is not None:
                for row_index, row_item in enumerate(self.items):
                    if int(row_item.get("id") or 0) == int(preferred_item_id):
                        selected_row = row_index
                        break
            self.table.selectRow(selected_row)
            self.current_item = self._item_for_row(selected_row)
            self._set_action_state(self.current_item is not None)
        else:
            self.current_item = None
            self._set_action_state(False)

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_item = None
            self._set_action_state(False)
            return
        self.current_item = self._item_for_row(selected[0].topRow())
        self._set_action_state(True)

    def _item_for_row(self, row: int | None):
        if row is None or row < 0:
            return None
        first_cell = self.table.item(row, 0)
        if first_cell:
            payload = first_cell.data(Qt.UserRole)
            if payload:
                return payload
        if row < len(self.items):
            return self.items[row]
        return None

    def _selected_item(self):
        selected = self.table.selectedRanges()
        if selected:
            return self._item_for_row(selected[0].topRow())
        return self.current_item

    def add_material(self):
        dialog = MaterialDialog(self.api_client, parent=self)
        if dialog.exec():
            try:
                created = self.api_client.create_material(dialog.result_payload)
                show_notice(self, "Material salvo", "Material cadastrado com sucesso.", icon_name="dashboard")
                self.refresh((created or {}).get("id") if isinstance(created, dict) else None)
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")

    def edit_selected(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        dialog = MaterialDialog(self.api_client, target_item, self)
        if dialog.exec():
            try:
                self.api_client.update_material(target_item["id"], dialog.result_payload)
                show_notice(self, "Material atualizado", "Material atualizado com sucesso.", icon_name="dashboard")
                self.refresh(target_item.get("id"))
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def adjust_stock(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        dialog = StockAdjustDialog(self.api_client, target_item, self)
        if dialog.exec():
            try:
                self.api_client.adjust_material_stock(target_item["id"], dialog.result_payload)
                show_notice(self, "Estoque atualizado", "Movimentação registrada com sucesso.", icon_name="dashboard")
                self.refresh(target_item.get("id"))
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha no ajuste", str(exc), icon_name="warning")

    def open_history(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self._selected_item()
        if not row_item:
            return
        self.current_item = row_item
        dialog = MaterialMovementsDialog(self.api_client, row_item, self)
        dialog.exec()

    def open_report(self):
        dialog = MaterialReportDialog(self.api_client, self)
        dialog.exec()

    def delete_selected(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        confirm = ask_confirmation(
            self,
            "Excluir material",
            f"Deseja inativar o material {target_item['referencia']}?",
            confirm_text="Sim",
            cancel_text="Não",
            icon_name="warning",
        )
        if confirm:
            try:
                self.api_client.delete_material(target_item["id"])
                show_notice(self, "Material inativado", "Material removido da base ativa.", icon_name="dashboard")
                self.refresh()
                self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao inativar", str(exc), icon_name="warning")

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando controle de material")
        else:
            self.table_skeleton.hide_skeleton()



