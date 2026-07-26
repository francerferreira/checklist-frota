from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from components import TableSkeletonOverlay, ask_confirmation, make_icon
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card
from ui.detail_dialogs import VehicleDetailDialog


class OperationalLocationDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("Novo local operacional")
        configure_dialog_window(self, width=620, height=430, min_width=560, min_height=390)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=680)
        title = QLabel("Estrutura operacional")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Cadastre áreas, píeres, berços e pátios para organizar os equipamentos.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Ex.: ALFA-PATIO-01")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex.: Pátio 01 Alfandegado")
        self.type_combo = QComboBox()
        for label, value in (
            ("Terminal", "TERMINAL"),
            ("Área", "AREA"),
            ("Píer", "PIER"),
            ("Berço", "BERCO"),
            ("Pátio", "PATIO"),
            ("Outro", "OUTRO"),
        ):
            self.type_combo.addItem(label, value)
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("Sem local superior", None)
        try:
            locations = (self.api_client.get_equipment_structure() or {}).get("locations") or []
        except Exception:
            locations = []
        for location in locations:
            self.parent_combo.addItem(
                location.get("full_name") or location.get("name") or "-",
                location.get("id"),
            )

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Código"), 0, 0)
        form.addWidget(self.code_input, 1, 0)
        form.addWidget(QLabel("Nome"), 0, 1)
        form.addWidget(self.name_input, 1, 1)
        form.addWidget(QLabel("Tipo"), 2, 0)
        form.addWidget(self.type_combo, 3, 0)
        form.addWidget(QLabel("Local superior"), 2, 1)
        form.addWidget(self.parent_combo, 3, 1)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar local")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)

    def submit(self):
        try:
            self.api_client.create_operational_location(
                {
                    "code": self.code_input.text().strip(),
                    "name": self.name_input.text().strip(),
                    "location_type": self.type_combo.currentData(),
                    "parent_id": self.parent_combo.currentData(),
                }
            )
            self.accept()
        except Exception as exc:
            from components import show_notice
            show_notice(self, "Falha ao salvar local", str(exc), icon_name="warning")


class EquipmentDialog(QDialog):
    def __init__(self, api_client, equipment: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.equipment = equipment
        self.selected_file = ""
        self.result_payload = None
        self.setWindowTitle("Cadastro de Equipamento")
        configure_dialog_window(self, width=1040, height=860, min_width=820, min_height=700)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1080)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)
        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("equipment", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        header_title = QLabel("Cadastro de equipamento")
        header_title.setObjectName("DialogHeaderTitle")
        header_subtitle = QLabel(
            "Cadastre Frota, RTG, LBS, Spreader e apoio na mesma base, preservando a identificação atual."
        )
        header_subtitle.setObjectName("DialogHeaderSubtitle")
        header_subtitle.setWordWrap(True)
        title_wrap.addWidget(header_title)
        title_wrap.addWidget(header_subtitle)
        header_row.addWidget(icon_badge, 0, Qt.AlignTop)
        header_row.addLayout(title_wrap, 1)
        header_layout.addLayout(header_row)

        self.frota_input = QLineEdit((equipment or {}).get("frota", ""))
        try:
            structure = self.api_client.get_equipment_structure() or {}
        except Exception:
            structure = {}
        families = structure.get("families") or []
        locations = structure.get("locations") or []

        self.family_combo = QComboBox()
        for family in families:
            self.family_combo.addItem(family.get("name") or family.get("code") or "-", family)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(
            [
                "cavalo",
                "carreta",
                "carro_simples",
                "cavalo_auxiliar",
                "ambulancia",
                "caminhao_pipa",
                "caminhao_brigada",
                "onibus",
                "van",
                "auxiliar",
                "rtg",
                "lbs",
                "spreader",
            ]
        )
        if equipment:
            self.tipo_combo.setCurrentText(equipment.get("tipo", "cavalo"))

        selected_family_id = (equipment or {}).get("family_id")
        selected_family_code = (equipment or {}).get("tipo")
        for index in range(self.family_combo.count()):
            family = self.family_combo.itemData(index) or {}
            if family.get("id") == selected_family_id or family.get("code") == selected_family_code:
                self.family_combo.setCurrentIndex(index)
                break
        self.family_combo.currentIndexChanged.connect(self._sync_type_from_family)
        self._sync_type_from_family()

        self.placa_input = QLineEdit((equipment or {}).get("placa", ""))
        self.ano_input = QLineEdit((equipment or {}).get("ano", "") or "")
        self.modelo_input = QLineEdit((equipment or {}).get("modelo", ""))
        self.chassi_input = QLineEdit((equipment or {}).get("chassi", "") or "")
        self.configuracao_input = QLineEdit((equipment or {}).get("configuracao", "") or "")
        self.atividade_input = QLineEdit((equipment or {}).get("atividade", "") or "")
        self.serial_number_input = QLineEdit((equipment or {}).get("serial_number", "") or "")
        self.manufacturer_input = QLineEdit((equipment or {}).get("manufacturer", "") or "")
        self.capacity_input = QLineEdit((equipment or {}).get("capacity", "") or "")

        self.criticality_combo = QComboBox()
        self.criticality_combo.addItems(["BAIXA", "MEDIA", "ALTA", "CRITICA"])
        self.criticality_combo.setCurrentText((equipment or {}).get("criticality") or "MEDIA")

        self.status_combo = QComboBox()
        self.status_combo.addItems(["ON", "OFF", "RETIRADO"])
        if equipment and equipment.get("status"):
            self.status_combo.setCurrentText(equipment["status"])

        self.local_input = QLineEdit((equipment or {}).get("local", "") or "")
        self.location_combo = QComboBox()
        self.location_combo.addItem("Sem local estruturado", None)
        for location in locations:
            self.location_combo.addItem(location.get("full_name") or location.get("name") or "-", location.get("id"))
        selected_location_id = (equipment or {}).get("operational_location_id")
        if selected_location_id:
            index = self.location_combo.findData(selected_location_id)
            if index >= 0:
                self.location_combo.setCurrentIndex(index)

        self.parent_equipment_combo = QComboBox()
        self.parent_equipment_combo.addItem("Sem vínculo com LBS", None)
        try:
            lbs_rows = self.api_client.get_equipment("lbs", True)
        except Exception:
            lbs_rows = []
        for lbs in lbs_rows:
            if int(lbs.get("id") or 0) == int((equipment or {}).get("id") or 0):
                continue
            self.parent_equipment_combo.addItem(
                f"{lbs.get('frota') or '-'} - {lbs.get('modelo') or '-'}",
                lbs.get("id"),
            )
        active_link = (equipment or {}).get("active_link") or {}
        parent_id = active_link.get("parent_vehicle_id")
        if parent_id:
            index = self.parent_equipment_combo.findData(parent_id)
            if index >= 0:
                self.parent_equipment_combo.setCurrentIndex(index)

        self.link_type_combo = QComboBox()
        self.link_type_combo.addItems(["ACOPLADO", "TITULAR", "RESERVA", "OUTRO"])
        if active_link.get("link_type"):
            self.link_type_combo.setCurrentText(active_link["link_type"])
        self.descricao_input = QTextEdit((equipment or {}).get("descricao", "") or "")
        self.ativo_checkbox = QCheckBox("Equipamento ativo")
        self.ativo_checkbox.setChecked((equipment or {}).get("ativo", True))

        current_file = (equipment or {}).get("foto_path", "Nenhuma foto selecionada.") or "Nenhuma foto selecionada."
        self.file_label = QLabel(current_file)
        self.file_label.setObjectName("MutedText")
        self.file_label.setWordWrap(True)

        select_file_button = QPushButton("Selecionar foto")
        select_file_button.setMinimumHeight(46)
        select_file_button.clicked.connect(self.select_file)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(14)

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1, highlight: bool = False):
            field = QFrame()
            if highlight:
                field.setObjectName("DialogInfoBlock")
                field.setAttribute(Qt.WA_StyledBackground, True)
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(12 if highlight else 0, 12 if highlight else 0, 12 if highlight else 0, 12 if highlight else 0)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            form_layout.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Identificação / Frota", self.frota_input, highlight=True)
        add_field(0, 1, "Família", self.family_combo, highlight=True)
        add_field(1, 0, "Tipo técnico", self.tipo_combo)
        add_field(1, 1, "Placa", self.placa_input)
        add_field(2, 0, "Ano", self.ano_input)
        add_field(2, 1, "Modelo", self.modelo_input)
        add_field(3, 0, "Número de série", self.serial_number_input, highlight=True)
        add_field(3, 1, "Fabricante", self.manufacturer_input)
        add_field(4, 0, "Capacidade", self.capacity_input)
        add_field(4, 1, "Criticidade", self.criticality_combo, highlight=True)
        add_field(5, 0, "Chassi", self.chassi_input)
        add_field(5, 1, "Configuração", self.configuracao_input)
        add_field(6, 0, "Atividade", self.atividade_input)
        add_field(6, 1, "Status cadastral", self.status_combo, highlight=True)
        add_field(7, 0, "Local operacional", self.location_combo, highlight=True)
        add_field(7, 1, "Local legado / observação", self.local_input)
        add_field(8, 0, "LBS vinculada (para Spreader)", self.parent_equipment_combo)
        add_field(8, 1, "Tipo do vínculo", self.link_type_combo)
        add_field(9, 0, "Descrição", self.descricao_input, 2)

        media_field = QFrame()
        media_field.setObjectName("DialogInfoBlock")
        media_field.setAttribute(Qt.WA_StyledBackground, True)
        media_layout = QVBoxLayout(media_field)
        media_layout.setContentsMargins(12, 12, 12, 12)
        media_layout.setSpacing(8)
        media_label = QLabel("Foto do equipamento")
        media_label.setObjectName("SectionCaption")
        media_layout.addWidget(media_label)
        media_actions = QHBoxLayout()
        media_actions.setContentsMargins(0, 0, 0, 0)
        media_actions.setSpacing(12)
        media_actions.addWidget(select_file_button, 0)
        media_actions.addWidget(self.file_label, 1)
        media_layout.addLayout(media_actions)
        media_layout.addWidget(self.ativo_checkbox, 0, Qt.AlignLeft)
        form_layout.addWidget(media_field, 10, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar equipamento")
        save_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        save_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        save_button.setMinimumWidth(196)
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)

        actions.addWidget(cancel_button)
        actions.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def _sync_type_from_family(self):
        family = self.family_combo.currentData() or {}
        family_code = family.get("code")
        if family_code:
            self.tipo_combo.setCurrentText(family_code)

    def select_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto do equipamento",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if filename:
            self.selected_file = filename
            self.file_label.setText(filename)

    def submit(self):
        try:
            family = self.family_combo.currentData() or {}
            payload = {
                "frota": self.frota_input.text().strip(),
                "tipo": family.get("code") or self.tipo_combo.currentText(),
                "family_id": family.get("id"),
                "family_code": family.get("code") or self.tipo_combo.currentText(),
                "placa": self.placa_input.text().strip(),
                "ano": self.ano_input.text().strip(),
                "modelo": self.modelo_input.text().strip(),
                "chassi": self.chassi_input.text().strip(),
                "configuracao": self.configuracao_input.text().strip(),
                "atividade": self.atividade_input.text().strip(),
                "serial_number": self.serial_number_input.text().strip(),
                "manufacturer": self.manufacturer_input.text().strip(),
                "capacity": self.capacity_input.text().strip(),
                "criticality": self.criticality_combo.currentText(),
                "status": self.status_combo.currentText(),
                "local": self.local_input.text().strip(),
                "operational_location_id": self.location_combo.currentData(),
                "parent_equipment_id": self.parent_equipment_combo.currentData(),
                "link_type": self.link_type_combo.currentText(),
                "descricao": self.descricao_input.toPlainText().strip(),
                "ativo": self.ativo_checkbox.isChecked(),
            }

            if self.selected_file:
                upload = self.api_client.upload_file(
                    self.selected_file,
                    payload["frota"] or "equipamento",
                    "equipamento",
                    self.api_client.user["login"],
                )
                payload["foto_path"] = upload["path"]
            elif self.equipment and self.equipment.get("foto_path"):
                payload["foto_path"] = self.equipment["foto_path"]

            self.result_payload = payload
            self.accept()
        except Exception as exc:
            from components import show_notice
            show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")


class SpreaderTimelineDialog(QDialog):
    """Consulta o histórico de acoplamentos e reservas dos Spreaders."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("Linha do tempo de Spreaders")
        configure_dialog_window(self, width=1180, height=760, min_width=940, min_height=620)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1220)
        title = QLabel("Linha do tempo de Spreaders")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            "Acompanhe quando cada Spreader foi acoplado a uma LBS, passou para reserva ou teve o vínculo encerrado."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.spreader_filter = QComboBox()
        self.spreader_filter.setMinimumHeight(34)
        self.lbs_filter = QComboBox()
        self.lbs_filter.setMinimumHeight(34)
        self.active_only = QCheckBox("Somente vínculos ativos")
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setMinimumHeight(34)
        self.refresh_button.clicked.connect(self.refresh)
        self.spreader_filter.currentIndexChanged.connect(self.refresh)
        self.lbs_filter.currentIndexChanged.connect(self.refresh)
        self.active_only.stateChanged.connect(self.refresh)

        filters.addWidget(QLabel("Spreader"))
        filters.addWidget(self.spreader_filter, 1)
        filters.addWidget(QLabel("LBS"))
        filters.addWidget(self.lbs_filter, 1)
        filters.addWidget(self.active_only)
        filters.addWidget(self.refresh_button)
        layout.addWidget(filter_card)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_top = QHBoxLayout()
        table_title = QLabel("Sequência de vínculos")
        table_title.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Carregando histórico")
        self.summary_badge.setObjectName("TopBarPill")
        table_top.addWidget(table_title)
        table_top.addStretch()
        table_top.addWidget(self.summary_badge)

        caption = QLabel(
            "Cada linha representa um período: o início mostra a entrada na LBS ou reserva; o término mostra quando o vínculo foi substituído ou encerrado."
        )
        caption.setObjectName("SectionCaption")
        caption.setWordWrap(True)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Início", "Fim / situação", "Spreader", "LBS", "Tipo", "Local da LBS", "Observação"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(460)

        table_layout.addLayout(table_top)
        table_layout.addWidget(caption)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self._load_filters()
        self.refresh()

    @staticmethod
    def _format_datetime(value) -> str:
        if not value:
            return "-"
        return str(value).replace("T", " ")[:16]

    @staticmethod
    def _restore_selection(combo: QComboBox, items: list[dict], label_key: str):
        selected = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todos", None)
        for item in items:
            combo.addItem(item.get(label_key) or "-", item.get("id"))
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _load_filters(self):
        equipment = self.api_client.get_equipment(ativos=None) or []
        spreaders = sorted(
            (item for item in equipment if str(item.get("tipo") or "").lower() == "spreader"),
            key=lambda item: str(item.get("frota") or ""),
        )
        lbs_rows = sorted(
            (item for item in equipment if str(item.get("tipo") or "").lower() == "lbs"),
            key=lambda item: str(item.get("frota") or ""),
        )
        self._restore_selection(self.spreader_filter, spreaders, "frota")
        self._restore_selection(self.lbs_filter, lbs_rows, "frota")
        self._locations_by_lbs_id = {
            item.get("id"): ((item.get("operational_location") or {}).get("full_name") or item.get("local") or "-")
            for item in lbs_rows
        }

    def refresh(self, *_args):
        try:
            child_id = self.spreader_filter.currentData()
            parent_id = self.lbs_filter.currentData()
            rows = self.api_client.get_equipment_links(
                active=True if self.active_only.isChecked() else None,
                parent_id=parent_id,
                child_id=child_id,
            ) or []
            rows = [
                row for row in rows
                if str((row.get("child_equipment") or {}).get("tipo") or "").lower() == "spreader"
            ]
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                child = row.get("child_equipment") or {}
                parent = row.get("parent_equipment") or {}
                active = bool(row.get("active"))
                end_label = "EM USO" if active else self._format_datetime(row.get("ended_at"))
                self.table.setItem(index, 0, make_table_item(self._format_datetime(row.get("started_at")), payload=row))
                self.table.setItem(index, 1, make_table_item(end_label))
                self.table.setItem(index, 2, make_table_item(child.get("frota") or "-"))
                self.table.setItem(index, 3, make_table_item(parent.get("frota") or "-"))
                self.table.setItem(index, 4, make_table_item(str(row.get("link_type") or "-").replace("_", " ")))
                self.table.setItem(index, 5, make_table_item(self._locations_by_lbs_id.get(row.get("parent_vehicle_id"), "-")))
                self.table.setItem(index, 6, make_table_item(row.get("notes") or "-"))
            self.table.setSortingEnabled(True)
            self.summary_badge.setText(f"{len(rows)} evento(s)")
        except Exception as exc:
            from components import show_notice
            show_notice(self, "Falha ao carregar linha do tempo", str(exc), icon_name="warning")


class EquipmentPage(QFrame):
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
        title = QLabel("Equipamentos")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Base central de ativos com foco em consulta rápida, abertura de ficha externa e manutenção do cadastro."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.add_button = QPushButton("Adicionar")
        self.add_button.setProperty("variant", "primary")
        self.add_button.setMinimumHeight(34)
        self.add_button.clicked.connect(self.add_equipment)

        self.structure_button = QPushButton("Novo local")
        self.structure_button.setMinimumHeight(34)
        self.structure_button.clicked.connect(self.add_operational_location)

        self.edit_button = QPushButton("Editar")
        self.edit_button.setMinimumHeight(34)
        self.edit_button.clicked.connect(self.edit_selected)

        self.open_button = QPushButton("Abrir ficha")
        self.open_button.setMinimumHeight(34)
        self.open_button.clicked.connect(self.open_selected)

        self.timeline_button = QPushButton("Linha do tempo")
        self.timeline_button.setMinimumHeight(34)
        self.timeline_button.clicked.connect(self.open_spreader_timeline)

        self.retire_button = QPushButton("Retirar")
        self.retire_button.setProperty("variant", "danger")
        self.retire_button.setMinimumHeight(34)
        self.retire_button.clicked.connect(self.retire_selected)

        buttons.addWidget(self.structure_button)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.timeline_button)
        buttons.addWidget(self.retire_button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(buttons)

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filters = QHBoxLayout(self.filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por frota, placa, modelo, chassi ou atividade")
        self.search_input.setMinimumHeight(34)
        self.search_input.returnPressed.connect(self.refresh)
        self.search_input.textChanged.connect(self._schedule_live_refresh)

        self.type_filter = QComboBox()
        self.type_filter.addItem("Todos", "")
        self.type_filter.addItem("Cavalos", "cavalo")
        self.type_filter.addItem("Carretas", "carreta")
        self.type_filter.addItem("Carros simples", "carro_simples")
        self.type_filter.addItem("Cavalos auxiliares", "cavalo_auxiliar")
        self.type_filter.addItem("Ambulancias", "ambulancia")
        self.type_filter.addItem("Caminhao pipa", "caminhao_pipa")
        self.type_filter.addItem("Caminhao brigada", "caminhao_brigada")
        self.type_filter.addItem("Onibus", "onibus")
        self.type_filter.addItem("Vans", "van")
        self.type_filter.addItem("Auxiliares legados", "auxiliar")
        self.type_filter.addItem("RTGs", "rtg")
        self.type_filter.addItem("LBSs", "lbs")
        self.type_filter.addItem("Spreaders", "spreader")
        self.type_filter.setMinimumHeight(34)
        self.type_filter.currentIndexChanged.connect(self.refresh)

        filter_button = QPushButton("Aplicar filtros")
        filter_button.setMinimumHeight(34)
        filter_button.clicked.connect(self.refresh)

        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.type_filter)
        active_badge = QLabel("Exibe apenas ativos")
        active_badge.setObjectName("TopBarPill")
        filters.addWidget(active_badge)
        filters.addWidget(filter_button)

        table_card = QFrame()
        style_table_card(table_card)
        self.table_skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        table_top = QHBoxLayout()
        table_top.setContentsMargins(0, 0, 0, 0)
        table_top.setSpacing(12)

        table_title = QLabel("Base de equipamentos")
        table_title.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Nenhum registro carregado")
        self.summary_badge.setObjectName("TopBarPill")

        table_top.addWidget(table_title)
        table_top.addStretch()
        table_top.addWidget(self.summary_badge)

        table_caption = QLabel(
            "A tabela e o foco principal desta tela. Clique duas vezes em qualquer linha para abrir a ficha completa."
        )
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Identificação", "Família", "Tipo", "Série", "Modelo", "Status", "Criticidade", "Local", "Foto"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(540)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())
        self.table.itemDoubleClicked.connect(self.open_item_details)

        table_layout.addLayout(table_top)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table)

        layout.addLayout(header)
        layout.addWidget(self.filter_card)
        layout.addWidget(table_card, 1)

        self._set_action_state(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(220)

    def _set_action_state(self, enabled: bool):
        self.edit_button.setEnabled(enabled)
        self.retire_button.setEnabled(enabled)
        self.open_button.setEnabled(enabled)

    def _filtered_rows(self, rows: list[dict]) -> list[dict]:
        term = self.search_input.text().strip().lower()
        if not term:
            return rows

        filtered = []
        for item in rows:
            haystack = " ".join(
                str(item.get(field) or "")
                for field in (
                    "frota",
                    "placa",
                    "modelo",
                    "chassi",
                    "descricao",
                    "atividade",
                    "local",
                    "serial_number",
                    "manufacturer",
                )
            ).lower()
            if term in haystack:
                filtered.append(item)
        return filtered

    def refresh(self, preferred_item_id: int | None = None):
        rows = self.api_client.get_equipment(self.type_filter.currentData() or None, True)
        self.items = self._filtered_rows(rows)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))

            for row, item in enumerate(self.items):
                first_cell = make_table_item(item["frota"], payload=item)
                self.table.setItem(row, 0, first_cell)
                family = item.get("family") or {}
                location = item.get("operational_location") or {}
                self.table.setItem(row, 1, make_table_item(family.get("name") or item["tipo"].title()))
                self.table.setItem(row, 2, make_table_item(item["tipo"].upper()))
                self.table.setItem(row, 3, make_table_item(item.get("serial_number") or ""))
                self.table.setItem(row, 4, make_table_item(item["modelo"]))
                self.table.setItem(row, 5, make_table_item(item.get("status") or ""))
                self.table.setItem(row, 6, make_table_item(item.get("criticality") or "MEDIA"))
                self.table.setItem(row, 7, make_table_item(location.get("full_name") or item.get("local") or ""))
                self.table.setItem(row, 8, make_table_item("Sim" if item.get("foto_path") else "Não"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.summary_badge.setText(f"{len(self.items)} registros")
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

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando base de equipamentos")
        else:
            self.table_skeleton.hide_skeleton()

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_item = None
            self._set_action_state(False)
            return
        self.current_item = self._item_for_row(selected[0].topRow())
        self._set_action_state(True)

    def _item_for_row(self, row: int | None):
        if row is None or row < 0 or row >= len(self.items):
            return None
        first_cell = self.table.item(row, 0)
        if first_cell:
            payload = first_cell.data(Qt.UserRole)
            if payload:
                return payload
        return self.items[row]

    def _selected_item(self):
        selected = self.table.selectedRanges()
        if selected:
            return self._item_for_row(selected[0].topRow())
        return self.current_item

    def open_item_details(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self._selected_item()
        if not row_item:
            return
        self.current_item = row_item
        dialog = VehicleDetailDialog(self.api_client, row_item, self)
        dialog.exec()

    def open_selected(self, *_args):
        self.open_item_details()

    def open_spreader_timeline(self):
        SpreaderTimelineDialog(self.api_client, self).exec()

    def add_equipment(self):
        dialog = EquipmentDialog(self.api_client, parent=self)
        if dialog.exec():
            try:
                created = self.api_client.create_vehicle(dialog.result_payload)
                from components import show_notice
                show_notice(self, "Equipamento salvo", "Cadastro realizado com sucesso.", icon_name="dashboard")
                self.refresh((created or {}).get("id") if isinstance(created, dict) else None)
                self.data_changed.emit()
            except Exception as exc:
                from components import show_notice
                show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")

    def add_operational_location(self):
        dialog = OperationalLocationDialog(self.api_client, self)
        if dialog.exec():
            from components import show_notice
            show_notice(
                self,
                "Local salvo",
                "O local operacional já está disponível nos cadastros de equipamento.",
                icon_name="dashboard",
            )

    def edit_selected(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        dialog = EquipmentDialog(self.api_client, target_item, self)
        if dialog.exec():
            try:
                updated_payload = dialog.result_payload
                old_frota = target_item.get("frota")
                new_frota = updated_payload.get("frota")
                
                self.api_client.update_vehicle(target_item["id"], updated_payload)
                
                # Se frota foi alterada, avisar sistema para atualizar referencias em todos os lugares
                if old_frota and new_frota and old_frota.upper() != new_frota.upper():
                    from components import show_notice
                    show_notice(
                        self,
                        "Equipamento atualizado",
                        f"Frota alterada de '{old_frota}' para '{new_frota}'.\n\nAtualizando sistema...",
                        icon_name="dashboard"
                    )
                else:
                    from components import show_notice
                    show_notice(self, "Equipamento atualizado", "Cadastro atualizado com sucesso.", icon_name="dashboard")
                
                self.refresh(target_item.get("id"))
                self.data_changed.emit()
            except Exception as exc:
                from components import show_notice
                show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def retire_selected(self):
        target_item = self._selected_item()
        if not target_item:
            return
        self.current_item = target_item
        confirm = ask_confirmation(
            self,
            "Retirar equipamento",
            f"Deseja retirar {target_item['frota']} da frota ativa?",
            confirm_text="Sim",
            cancel_text="Não",
            icon_name="warning",
        )
        if confirm:
            try:
                self.api_client.retire_vehicle(target_item["id"])
                from components import show_notice
                show_notice(self, "Equipamento retirado", "Equipamento removido da lista ativa.", icon_name="dashboard")
                self.refresh()
                self.data_changed.emit()
            except Exception as exc:
                from components import show_notice
                show_notice(self, "Falha ao retirar", str(exc), icon_name="warning")
