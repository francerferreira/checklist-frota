from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from components import ImagePanel, choose_pdf_save_path, finalize_export_result, make_icon, show_notice, start_export_task_with_preset
from runtime_paths import asset_path
from services.export_service import export_non_conformity_pdf, export_vehicle_detail_pdf, make_default_export_path
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


def _nc_label(item: dict) -> str:
    return item.get("item_label") or item.get("item_nome") or "-"


class NonConformityDetailDialog(QDialog):
    def __init__(self, api_client, item: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.item = item
        self.logo_path = asset_path("sis-mmp-logo.png")

        self.setWindowTitle("Detalhe da não conformidade")
        configure_dialog_window(self, width=1260, height=800, min_width=980, min_height=680)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1320)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        top = QHBoxLayout(header)
        top.setContentsMargins(18, 18, 18, 18)
        top.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("warning", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title = QLabel(f"{item['veiculo']['frota']} - {_nc_label(item)}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"Ocorrência registrada em {self._format(item.get('created_at'))} - "
            f"{'Resolvida' if item.get('resolvido') else 'Aberta'}"
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        export_button = QPushButton("Exportar PDF")
        export_button.setProperty("variant", "primary")
        export_button.setMinimumHeight(48)
        export_button.setMinimumWidth(164)
        export_button.clicked.connect(self.export_pdf)

        top.addWidget(icon_badge, 0, Qt.AlignTop)
        top.addLayout(title_wrap, 1)
        top.addWidget(export_button)

        body = QGridLayout()
        body.setSpacing(16)

        before_image = self.api_client.fetch_image(item.get("foto_antes"))
        after_image = self.api_client.fetch_image(item.get("foto_depois"))

        self.before_panel = ImagePanel("Foto antes")
        self.before_panel.setMinimumHeight(360)
        self.before_panel.set_preview_height(300, minimum=230)
        self.before_panel.set_photo_role("Antes")
        self.before_panel.set_preview_title(f"Foto antes - {item['veiculo']['frota']}")
        self.before_panel.set_image_data(before_image, "Sem foto antes")

        self.after_panel = ImagePanel("Foto depois")
        self.after_panel.setMinimumHeight(360)
        self.after_panel.set_preview_height(300, minimum=230)
        self.after_panel.set_photo_role("Depois")
        self.after_panel.set_preview_title(f"Foto depois - {item['veiculo']['frota']}")
        self.after_panel.set_image_data(after_image, "Sem foto depois")

        info_card = QFrame()
        style_table_card(info_card)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(18, 18, 18, 18)
        info_layout.setSpacing(10)

        info_title = QLabel("Informacoes da ocorrencia")
        info_title.setObjectName("SectionTitle")
        info_text = QLabel(
            "\n".join(
                [
                    f"Veículo: {item['veiculo'].get('frota') or '-'}",
                    f"Placa: {item['veiculo'].get('placa') or '-'}",
                    f"Modelo: {item['veiculo'].get('modelo') or '-'}",
                    f"Item: {_nc_label(item)}",
                    f"Motorista: {item['usuario'].get('nome') or '-'}",
                    f"Status: {'Resolvida' if item.get('resolvido') else 'Aberta'}",
                    f"Código da peça: {item.get('codigo_peca') or '-'}",
                    f"Descrição da peça: {item.get('descricao_peca') or '-'}",
                    f"Data de resolução: {self._format(item.get('data_resolucao'))}",
                    f"Observação: {item.get('observacao') or '-'}",
                ]
            )
        )
        info_text.setWordWrap(True)
        info_text.setObjectName("DialogInfoValue")
        info_block = QFrame()
        info_block.setObjectName("DialogInfoBlock")
        info_block.setAttribute(Qt.WA_StyledBackground, True)
        info_block_layout = QVBoxLayout(info_block)
        info_block_layout.setContentsMargins(14, 14, 14, 14)
        info_block_layout.addWidget(info_text)
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_block)

        body.addWidget(self.before_panel, 0, 0)
        body.addWidget(self.after_panel, 0, 1)
        body.addWidget(info_card, 1, 0, 1, 2)
        body.setRowStretch(0, 5)
        body.setRowStretch(1, 2)

        layout.addWidget(header)
        layout.addLayout(body, 1)

        self._before_image = before_image
        self._after_image = after_image

    def export_pdf(self):
        default_path = make_default_export_path(
            f"ocorrencia_{self.item['veiculo'].get('frota', 'frota').lower()}",
            "pdf",
        )
        filename = choose_pdf_save_path(self, "Exportar ocorrencia em PDF", default_path)
        if not filename:
            return
        try:
            export_non_conformity_pdf(
                self.item,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=self.api_client.user.get("nome", ""),
                before_image=self._before_image,
                after_image=self._after_image,
            )
            finalize_export_result(self, filename)
        except Exception as exc:
            show_notice(self, "Falha ao exportar PDF", str(exc), icon_name="warning")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]


class VehicleDetailDialog(QDialog):
    def __init__(self, api_client, vehicle: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.vehicle = vehicle
        self.logo_path = asset_path("sis-mmp-logo.png")
        try:
            self.history = self.api_client.get_vehicle_history(vehicle["id"])
        except Exception:
            self.history = {}
        self.occurrences = self.history.get("nao_conformidades") or self.api_client.get_non_conformities(vehicle=vehicle.get("frota"))
        self.operational_history = self._build_operational_history()
        self.status_history = self._safe_list(lambda: self.api_client.get_equipment_status_history(vehicle["id"]))
        self.hourmeter_history = self._safe_list(lambda: self.api_client.get_equipment_hourmeters(vehicle["id"]))
        self.technical_documents = self._safe_list(lambda: self.api_client.get_technical_documents(vehicle["id"]))
        self.equipment_links = self._safe_list(lambda: self.api_client.get_equipment_links(parent_id=vehicle["id"]))
        self.equipment_links.extend(self._safe_list(lambda: self.api_client.get_equipment_links(child_id=vehicle["id"])))

        self.setWindowTitle("Ficha do equipamento")
        configure_dialog_window(self, width=1280, height=820, min_width=980, min_height=700)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1340)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        top = QHBoxLayout(header)
        top.setContentsMargins(18, 18, 18, 18)
        top.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("equipment", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title = QLabel(f"{vehicle.get('frota') or '-'} - {vehicle.get('modelo') or '-'}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"{(vehicle.get('tipo') or '-').title()} - {vehicle.get('placa') or '-'} - {vehicle.get('status') or '-'}"
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        export_button = QPushButton("PDF auditoria")
        export_button.setProperty("variant", "primary")
        export_button.setMinimumHeight(48)
        export_button.setMinimumWidth(172)
        export_button.clicked.connect(self.export_pdf)

        top.addWidget(icon_badge, 0, Qt.AlignTop)
        top.addLayout(title_wrap, 1)
        top.addWidget(export_button)

        content = QGridLayout()
        content.setSpacing(16)

        image_card = ImagePanel("Foto do equipamento")
        image_card.setMinimumHeight(450)
        image_card.set_preview_height(390, minimum=300)
        image_card.set_photo_role("Frota")
        self.vehicle_image = self.api_client.fetch_image(vehicle.get("foto_path"))
        image_card.set_preview_title(f"Equipamento {vehicle.get('frota')}")
        image_card.set_image_data(self.vehicle_image, "Sem foto cadastrada")

        info_card = QFrame()
        style_table_card(info_card)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(18, 18, 18, 18)
        info_layout.setSpacing(10)

        info_title = QLabel("Dados do equipamento")
        info_title.setObjectName("SectionTitle")
        family = vehicle.get("family") or {}
        operational_location = vehicle.get("operational_location") or {}
        active_link = vehicle.get("active_link") or {}
        parent_equipment = active_link.get("parent_equipment") or {}
        info_text = QLabel(
            "\n".join(
                [
                    f"Frota: {vehicle.get('frota') or '-'}",
                    f"Módulo: {family.get('name') or vehicle.get('tipo') or '-'}",
                    f"Tipo: {(vehicle.get('tipo') or '-').title()}",
                    f"Placa: {vehicle.get('placa') or '-'}",
                    f"Modelo: {vehicle.get('modelo') or '-'}",
                    f"Ano: {vehicle.get('ano') or '-'}",
                    f"Chassi: {vehicle.get('chassi') or '-'}",
                    f"Número de série: {vehicle.get('serial_number') or '-'}",
                    f"Fabricante: {vehicle.get('manufacturer') or '-'}",
                    f"Capacidade: {vehicle.get('capacity') or '-'}",
                    f"Criticidade: {vehicle.get('criticality') or 'MEDIA'}",
                    f"Configuração: {vehicle.get('configuracao') or '-'}",
                    f"Atividade: {vehicle.get('atividade') or '-'}",
                    f"Local: {operational_location.get('full_name') or vehicle.get('local') or '-'}",
                    f"Vínculo ativo: {parent_equipment.get('frota') or '-'} ({active_link.get('link_type') or '-'})",
                    f"Descrição: {vehicle.get('descricao') or '-'}",
                ]
            )
        )
        info_text.setWordWrap(True)
        info_text.setObjectName("DialogInfoValue")
        info_block = QFrame()
        info_block.setObjectName("DialogInfoBlock")
        info_block.setAttribute(Qt.WA_StyledBackground, True)
        info_block_layout = QVBoxLayout(info_block)
        info_block_layout.setContentsMargins(14, 14, 14, 14)
        info_block_layout.addWidget(info_text)
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_block)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(16, 16, 16, 16)
        table_layout.setSpacing(10)

        table_title = QLabel("Histórico operacional")
        table_title.setObjectName("SectionTitle")
        table_caption = QLabel("Não conformidades, manutenções, inspeções e lavagens associadas a este equipamento.")
        table_caption.setObjectName("SectionCaption")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Data", "Origem", "Item", "Status", "Responsável"])
        configure_table(self.table)
        self.table.itemDoubleClicked.connect(self.open_selected_occurrence)
        self._fill_history()

        open_occurrence_button = QPushButton("Abrir ocorrência selecionada")
        open_occurrence_button.setMinimumHeight(48)
        open_occurrence_button.clicked.connect(self.open_selected_occurrence)

        table_layout.addWidget(table_title)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table)
        table_layout.addWidget(open_occurrence_button)

        content.addWidget(image_card, 0, 0)
        content.addWidget(info_card, 0, 1)
        content.setColumnStretch(0, 5)
        content.setColumnStretch(1, 5)

        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.addLayout(content)
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(table_card)
        tabs = QTabWidget()
        tabs.addTab(summary_tab, "Resumo")
        tabs.addTab(history_tab, "Historico operacional")
        tabs.addTab(self._build_operational_tabs(), "Condicao e documentos")

        layout.addWidget(header)
        layout.addWidget(tabs, 1)

    @staticmethod
    def _safe_list(loader) -> list[dict]:
        try:
            value = loader()
            return value if isinstance(value, list) else []
        except Exception:
            return []

    def _make_table(self, headers: list[str], rows: list[list[object]]) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        configure_table(table)
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                table.setItem(row_index, column, make_table_item(str(value or "-")))
        table.resizeColumnsToContents()
        return table

    def _table_tab(self, title: str, caption: str, headers: list[str], rows: list[list[object]]) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        hint = QLabel(caption)
        hint.setObjectName("SectionCaption")
        hint.setWordWrap(True)
        tab_layout.addWidget(heading)
        tab_layout.addWidget(hint)
        tab_layout.addWidget(self._make_table(headers, rows), 1)
        return tab

    def _build_operational_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        current_state = self.vehicle.get("operational_state") or {}
        status_rows = [[self._format(current_state.get("status_updated_at")), current_state.get("operational_status") or "SEM APONTAMENTO", current_state.get("status_reason") or "-", "Atual"]]
        status_rows.extend([[self._format(row.get("started_at")), row.get("status"), row.get("reason"), row.get("source")] for row in self.status_history])
        tabs.addTab(self._table_tab("Status operacional", "Linha do tempo do estado do equipamento. A primeira linha mostra a situacao atual.", ["Data", "Status", "Motivo", "Origem"], status_rows), "Status")
        hourmeter_rows = [[self._format(row.get("recorded_at")), row.get("reading"), row.get("source"), row.get("notes")] for row in self.hourmeter_history]
        tabs.addTab(self._table_tab("Horimetro", "Leituras registradas sem sobrescrever o historico.", ["Data", "Leitura", "Origem", "Observacao"], hourmeter_rows), "Horimetro")
        document_rows = [[row.get("code"), row.get("title"), row.get("document_type"), row.get("revision"), row.get("valid_until") or "Sem validade", row.get("effective_status") or row.get("status")] for row in self.technical_documents]
        tabs.addTab(self._table_tab("Documentos tecnicos", "Manuais, diagramas e certificados vinculados ao equipamento ou ao seu módulo.", ["Codigo", "Documento", "Tipo", "Revisao", "Validade", "Situacao"], document_rows), "Documentos")
        seen_ids: set[int] = set()
        link_rows = []
        for row in self.equipment_links:
            link_id = int(row.get("id") or 0)
            if link_id in seen_ids:
                continue
            seen_ids.add(link_id)
            parent = row.get("parent_equipment") or {}
            child = row.get("child_equipment") or {}
            link_rows.append([parent.get("frota"), child.get("frota"), row.get("link_type"), "Ativo" if row.get("active") else "Encerrado"])
        tabs.addTab(self._table_tab("Vinculos", "Relacionamentos operacionais atuais e historicos com outros equipamentos.", ["Origem", "Destino", "Tipo", "Situacao"], link_rows), "Vinculos")
        return tabs

    def _build_operational_history(self):
        rows = []
        for item in self.occurrences:
            rows.append(
                {
                    "date": item.get("created_at"),
                    "origin": "Não conformidade",
                    "item": _nc_label(item),
                    "status": "Resolvida" if item.get("resolvido") else "Aberta",
                    "owner": item.get("usuario", {}).get("nome") or "-",
                    "occurrence": item,
                }
            )
        for item in self.history.get("manutencoes", []):
            schedule = item.get("schedule") or {}
            rows.append(
                {
                    "date": item.get("executed_at") or item.get("scheduled_date") or item.get("created_at"),
                    "origin": "Manutenção",
                    "item": schedule.get("title") or "-",
                    "status": str(item.get("status") or "-").replace("_", " "),
                    "owner": (item.get("executed_by") or item.get("assigned_mechanic") or {}).get("nome") or "-",
                    "occurrence": None,
                }
            )
        for item in self.history.get("lavagens", []):
            rows.append(
                {
                    "date": item.get("wash_date"),
                    "origin": "Lavagem",
                    "item": item.get("tipo_equipamento") or "Lavagem",
                    "status": item.get("status") or "-",
                    "owner": (item.get("created_by") or {}).get("nome") or "-",
                    "occurrence": None,
                }
            )
        for item in self.history.get("atividades", []):
            activity = item.get("atividade") or {}
            rows.append(
                {
                    "date": item.get("instalado_em") or item.get("updated_at"),
                    "origin": "Inspeção",
                    "item": activity.get("item_nome") or activity.get("titulo") or f"Inspeção #{item.get('activity_id') or '-'}",
                    "status": str(item.get("status_execucao") or "-").replace("_", " "),
                    "owner": item.get("executado_por_nome") or "-",
                    "occurrence": None,
                }
            )
        return sorted(rows, key=lambda row: row.get("date") or "", reverse=True)

    def _fill_history(self):
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.operational_history))
            for row, item in enumerate(self.operational_history):
                self.table.setItem(row, 0, make_table_item(self._format(item.get("date")), payload=item))
                self.table.setItem(row, 1, make_table_item(item.get("origin") or "-"))
                self.table.setItem(row, 2, make_table_item(item.get("item") or "-"))
                self.table.setItem(row, 3, make_table_item(item.get("status") or "-"))
                self.table.setItem(row, 4, make_table_item(item.get("owner") or "-"))
            self.table.resizeColumnsToContents()
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
        if self.operational_history:
            self.table.selectRow(0)

    def open_selected_occurrence(self, *_args):
        selected = self.table.selectedRanges()
        if not selected:
            return
        row = selected[0].topRow()
        first_cell = self.table.item(row, 0)
        history_item = first_cell.data(Qt.UserRole) if first_cell else None
        if not history_item and 0 <= row < len(self.operational_history):
            history_item = self.operational_history[row]
        occurrence = (history_item or {}).get("occurrence")
        if not occurrence:
            return
        dialog = NonConformityDetailDialog(self.api_client, occurrence, self)
        dialog.exec()

    def export_pdf(self):
        default_path = make_default_export_path(
            f"equipamento_{self.vehicle.get('frota', 'frota').lower()}",
            "pdf",
        )
        filename = choose_pdf_save_path(self, "Exportar ficha do equipamento", default_path)
        if not filename:
            return

        def task(progress):
            progress(8, "Preparando auditoria do equipamento")
            occurrence_images = self._collect_occurrence_images_with_progress(self.occurrences, progress, start=14, end=76)
            progress(86, "Montando páginas do PDF")
            export_vehicle_detail_pdf(
                self.vehicle,
                self.occurrences,
                output_path=filename,
                logo_path=self.logo_path,
                generated_by=self.api_client.user.get("nome", ""),
                vehicle_image=self.vehicle_image,
                operational_history=self.operational_history,
                occurrence_images=occurrence_images,
            )
            return filename

        start_export_task_with_preset(self, "vehicle_audit_pdf", task)

    def _collect_occurrence_images_with_progress(self, occurrences: list[dict], progress, *, start: int, end: int):
        images = {}
        total = max(1, len(occurrences))
        if not occurrences:
            progress(end, "Nenhuma evidência fotográfica para carregar")
            return images
        for index, item in enumerate(occurrences, start=1):
            progress(start + int(((index - 1) / total) * (end - start)), f"Carregando evidências {index}/{len(occurrences)}")
            item_id = item.get("id")
            if not item_id:
                continue
            images[item_id] = {
                "before": self.api_client.fetch_image(item.get("foto_antes")),
                "after": self.api_client.fetch_image(item.get("foto_depois")),
            }
        progress(end, "Evidências fotográficas carregadas")
        return images

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    def _collect_occurrence_images(self, occurrences: list[dict]) -> dict[int, dict[str, bytes | None]]:
        images: dict[int, dict[str, bytes | None]] = {}
        for item in occurrences:
            item_id = item.get("id")
            if not item_id:
                continue
            images[item_id] = {
                "before": self.api_client.fetch_image(item.get("foto_antes")),
                "after": self.api_client.fetch_image(item.get("foto_depois")),
            }
        return images


