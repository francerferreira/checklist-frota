from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from components import StatCard, TableSkeletonOverlay, make_icon, show_notice
from services import severity_from_occurrence
from theme import build_dialog_layout, configure_dialog_window, configure_table, make_table_item, style_card, style_filter_bar, style_table_card
from ui.detail_dialogs import NonConformityDetailDialog


def _nc_label(item: dict) -> str:
    return item.get("item_label") or item.get("item_nome") or "-"


class ResolveDialog(QDialog):
    def __init__(self, api_client, nc_item: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.nc_item = nc_item
        self.selected_file = ""
        self.result_payload = None
        self.materials = self.api_client.get_materials(
            tipo=nc_item["veiculo"].get("tipo"),
            ativos="true",
        )
        self.setWindowTitle("Resolver não conformidade")
        configure_dialog_window(self, width=920, height=720, min_width=760, min_height=600)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=980)

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
        icon_label.setPixmap(make_icon("warning", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title = QLabel(f"{nc_item['veiculo']['frota']} - {_nc_label(nc_item)}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Informe peça, observação do reparo e foto depois em uma estrutura mais objetiva.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_row.addWidget(icon_badge, 0, Qt.AlignTop)
        header_row.addLayout(title_wrap, 1)
        header_layout.addLayout(header_row)

        self.codigo_input = QLineEdit(nc_item.get("codigo_peca") or "")
        self.descricao_input = QLineEdit(nc_item.get("descricao_peca") or "")
        self.material_combo = QComboBox()
        self.material_combo.addItem("Selecionar material do estoque", None)
        for material in self.materials:
            label = f"{material['referencia']} • {material['descricao']} • Saldo {material['quantidade_estoque']}"
            self.material_combo.addItem(label, material)
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)
        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(1)
        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Descreva o reparo executado.")

        self.file_label = QLabel("Nenhuma imagem selecionada.")
        self.file_label.setObjectName("MutedText")
        self.file_label.setWordWrap(True)
        select_button = QPushButton("Selecionar foto depois")
        select_button.setMinimumHeight(46)
        select_button.clicked.connect(self.select_file)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

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
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Código da peça", self.codigo_input, highlight=True)
        add_field(0, 1, "Descrição da peça", self.descricao_input)
        add_field(1, 0, "Material do estoque", self.material_combo, 2, True)
        add_field(2, 0, "Quantidade do material", self.quantidade_spin, highlight=True)
        add_field(2, 1, "Observação", self.observacao_input)

        media_field = QFrame()
        media_field.setObjectName("DialogInfoBlock")
        media_field.setAttribute(Qt.WA_StyledBackground, True)
        media_layout = QVBoxLayout(media_field)
        media_layout.setContentsMargins(12, 12, 12, 12)
        media_layout.setSpacing(8)
        media_label = QLabel("Foto depois")
        media_label.setObjectName("SectionCaption")
        media_actions = QHBoxLayout()
        media_actions.setContentsMargins(0, 0, 0, 0)
        media_actions.setSpacing(12)
        media_actions.addWidget(select_button, 0)
        media_actions.addWidget(self.file_label, 1)
        media_layout.addWidget(media_label)
        media_layout.addLayout(media_actions)
        form.addWidget(media_field, 3, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Marcar como resolvido")
        submit_button.setProperty("variant", "success")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        submit_button.setMinimumWidth(210)
        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(submit_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def select_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto depois",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if filename:
            self.selected_file = filename
            self.file_label.setText(filename)

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        self.codigo_input.setText(material.get("referencia") or "")
        self.descricao_input.setText(material.get("descricao") or "")

    def submit(self):
        try:
            foto_depois = None
            if self.selected_file:
                upload = self.api_client.upload_file(
                    self.selected_file,
                    self.nc_item["veiculo"]["frota"],
                    _nc_label(self.nc_item),
                    self.api_client.user["login"],
                )
                foto_depois = upload["path"]

            material = self.material_combo.currentData()
            self.result_payload = self.api_client.resolve_non_conformity(
                self.nc_item["id"],
                {
                    "codigo_peca": self.codigo_input.text().strip(),
                    "descricao_peca": self.descricao_input.text().strip(),
                    "observacao": self.observacao_input.toPlainText().strip(),
                    "foto_depois": foto_depois,
                    "material_id": material.get("id") if material else None,
                    "quantidade_material": int(self.quantidade_spin.value()),
                },
            )
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao resolver", str(exc), icon_name="warning")


class CreateActivityFromNCDialog(QDialog):
    def __init__(self, api_client, nc_item: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.nc_item = nc_item
        self.created_activity = None
        self.materials = self.api_client.get_materials(
            tipo=nc_item["veiculo"].get("tipo"),
            ativos="true",
        )
        self.mechanics = self.api_client.get_mechanics()

        self.setWindowTitle("Criar inspeção de apoio")
        configure_dialog_window(self, width=980, height=760, min_width=820, min_height=640)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=1040)

        vehicle = nc_item.get("veiculo") or {}
        user = nc_item.get("usuario") or {}

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)

        title = QLabel(f"Criar inspeção de apoio - NC #{nc_item.get('id')}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            f"{vehicle.get('frota') or '-'} • {_nc_label(nc_item)} • Motorista {user.get('nome') or '-'} • Uso auxiliar de conferência"
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.titulo_input = QLineEdit(f"Tratativa NC - {vehicle.get('frota') or '-'} - {_nc_label(nc_item)}")
        self.item_input = QLineEdit(nc_item.get("item_principal") or nc_item.get("item_nome") or "")
        self.item_input.setPlaceholderText("Módulo / componente")

        self.codigo_input = QLineEdit(nc_item.get("codigo_peca") or "")
        self.descricao_input = QLineEdit(nc_item.get("descricao_peca") or "")

        self.material_combo = QComboBox()
        self.material_combo.addItem("Selecionar material do estoque", None)
        for material in self.materials:
            label = f"{material['referencia']} • {material['descricao']} • Saldo {material['quantidade_estoque']}"
            self.material_combo.addItem(label, material)
        self.material_combo.currentIndexChanged.connect(self._sync_material_fields)

        self.quantidade_spin = QSpinBox()
        self.quantidade_spin.setMinimum(1)
        self.quantidade_spin.setMaximum(999)
        self.quantidade_spin.setValue(1)

        self.mechanic_combo = QComboBox()
        self.mechanic_combo.addItem("Sem direcionamento", None)
        for mechanic in self.mechanics:
            self.mechanic_combo.addItem(
                f"{mechanic.get('nome') or '-'} ({mechanic.get('login') or '-'})",
                mechanic,
            )

        self.allow_duplicate_check = QCheckBox("Permitir duplicidade se já existir inspeção aberta para esta NC")
        self.allow_duplicate_check.setChecked(False)

        self.observacao_input = QTextEdit()
        self.observacao_input.setPlaceholderText("Descreva o objetivo da conferência, critérios de auditoria e observações de apoio.")
        self.observacao_input.setPlainText(
            (
                f"NC #{nc_item.get('id')} - {_nc_label(nc_item)}\n"
                f"Equipamento: {vehicle.get('frota') or '-'} | Placa: {vehicle.get('placa') or '-'}\n"
                f"Abertura: {self._format(nc_item.get('created_at'))}\n"
                f"Motorista: {user.get('nome') or '-'}"
            )
        )

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

        add_field(0, 0, "Título da inspeção", self.titulo_input, 2, highlight=True)
        add_field(1, 0, "Módulo / componente", self.item_input, highlight=True)
        add_field(1, 1, "Material do estoque", self.material_combo, highlight=True)
        add_field(2, 0, "Código da peça", self.codigo_input)
        add_field(2, 1, "Descrição da peça", self.descricao_input)
        add_field(3, 0, "Mecânico direcionado", self.mechanic_combo, highlight=True)
        add_field(3, 1, "Quantidade por equipamento", self.quantidade_spin, highlight=True)
        add_field(4, 0, "Observação da conferência", self.observacao_input, 2)
        add_field(5, 0, "Regra de duplicidade", self.allow_duplicate_check, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Criar inspeção de apoio")
        submit_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.setMinimumWidth(132)
        submit_button.setMinimumWidth(184)
        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(submit_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)

    def _sync_material_fields(self):
        material = self.material_combo.currentData()
        if not material:
            return
        self.codigo_input.setText(material.get("referencia") or "")
        self.descricao_input.setText(material.get("descricao") or "")

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    def submit(self):
        item_nome = self.item_input.text().strip()
        if not item_nome:
            show_notice(self, "Módulo obrigatório", "Informe o módulo/componente da inspeção.", icon_name="warning")
            return

        try:
            material = self.material_combo.currentData() or {}
            mechanic = self.mechanic_combo.currentData() or {}
            payload = {
                "titulo": self.titulo_input.text().strip(),
                "item_nome": item_nome,
                "material_id": material.get("id"),
                "quantidade_por_equipamento": int(self.quantidade_spin.value()),
                "codigo_peca": self.codigo_input.text().strip(),
                "descricao_peca": self.descricao_input.text().strip(),
                "observacao": self.observacao_input.toPlainText().strip(),
                "assigned_mechanic_user_id": mechanic.get("id"),
                "permitir_duplicada": self.allow_duplicate_check.isChecked(),
            }
            self.created_activity = self.api_client.create_activity_from_non_conformity(self.nc_item["id"], payload)
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao criar inspeção", str(exc), icon_name="warning")


class CreateResolutionPackageDialog(QDialog):
    def __init__(self, api_client, selected_items: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.selected_items = selected_items
        self.created_package = None

        self.setWindowTitle("Criar pacote de resolução")
        configure_dialog_window(self, width=820, height=560, min_width=720, min_height=480)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=900)

        self.valid_modes = self._detect_modes()
        self.suggestions = self._load_suggestions()
        self.rule_defaults = self._load_rule_defaults()

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel(f"Criar pacote com {len(self.selected_items)} não conformidade(s)")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(self._build_hint())
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.grouping_mode_combo = QComboBox()
        for mode in self.valid_modes:
            if mode == "POR_ITEM":
                self.grouping_mode_combo.addItem("Por item distinto", mode)
            elif mode == "POR_EQUIPAMENTO":
                self.grouping_mode_combo.addItem("Por equipamento", mode)
        self.grouping_mode_combo.currentIndexChanged.connect(self._sync_title)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("Criar novo pacote", {"mode": "create"})
        for suggestion in self.suggestions:
            self.strategy_combo.addItem(
                f"Adicionar ao pacote #{suggestion.get('id')} - {suggestion.get('reason_label')}",
                {"mode": "append", "package_id": suggestion.get("id")},
            )
        for index in range(1, self.strategy_combo.count()):
            strategy = self.strategy_combo.itemData(index) or {}
            suggestion = next((row for row in self.suggestions if row.get("id") == strategy.get("package_id")), None)
            if suggestion and suggestion.get("reason") == "JA_CONTEM_REGISTRO":
                self.strategy_combo.setCurrentIndex(index)
                break

        self.title_input = QLineEdit()
        self.observation_input = QTextEdit()
        self.observation_input.setPlaceholderText("Observação opcional sobre o objetivo do pacote.")

        self.recurrence_days_spin = QSpinBox()
        self.recurrence_days_spin.setMinimum(1)
        self.recurrence_days_spin.setMaximum(120)
        self.recurrence_days_spin.setValue(int(self.rule_defaults.get("recurrence_window_days", 15)))

        self.recurrence_weight_spin = QSpinBox()
        self.recurrence_weight_spin.setMinimum(0)
        self.recurrence_weight_spin.setMaximum(50)
        self.recurrence_weight_spin.setValue(int(self.rule_defaults.get("recurrence_weight", 5)))

        def add_field(row: int, column: int, label_text: str, widget, col_span: int = 1, helper_text: str | None = None):
            field = QFrame()
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            field_layout.addWidget(label)
            field_layout.addWidget(widget)
            if helper_text:
                helper = QLabel(helper_text)
                helper.setObjectName("MutedText")
                helper.setWordWrap(True)
                field_layout.addWidget(helper)
            form.addWidget(field, row, column, 1, col_span)

        add_field(0, 0, "Destino sugerido", self.strategy_combo)
        add_field(0, 1, "Agrupamento sugerido", self.grouping_mode_combo)
        add_field(
            1,
            0,
            "Período para repetir o mesmo problema (dias)",
            self.recurrence_days_spin,
            helper_text="Serve para dizer por quantos dias o sistema olha para trás e verifica se esse mesmo problema voltou a acontecer.",
        )
        add_field(
            1,
            1,
            "Força da repetição na prioridade",
            self.recurrence_weight_spin,
            helper_text="Serve para dizer o quanto a repetição empurra esse pacote para cima na fila de atenção.",
        )
        add_field(2, 0, "Título do pacote", self.title_input, 2)
        add_field(3, 0, "Observação", self.observation_input, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(16, 14, 16, 14)
        actions.setSpacing(12)
        actions.addStretch()
        cancel_button = QPushButton("Cancelar")
        submit_button = QPushButton("Criar pacote")
        submit_button.setProperty("variant", "primary")
        cancel_button.setMinimumHeight(50)
        submit_button.setMinimumHeight(50)
        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self.submit)
        actions.addWidget(cancel_button)
        actions.addWidget(submit_button)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(footer)
        self._sync_title()

    def _normalized_item_name(self, item: dict) -> str:
        return str(item.get("item_principal") or item.get("item_nome") or "").strip().upper()

    def _vehicle_key(self, item: dict) -> int | None:
        vehicle = item.get("veiculo") or {}
        return vehicle.get("id")

    def _detect_modes(self) -> list[str]:
        modes: list[str] = []
        item_names = {self._normalized_item_name(item) for item in self.selected_items if self._normalized_item_name(item)}
        vehicle_ids = {self._vehicle_key(item) for item in self.selected_items if self._vehicle_key(item)}
        if len(item_names) == 1:
            modes.append("POR_ITEM")
        if len(vehicle_ids) == 1:
            modes.append("POR_EQUIPAMENTO")
        return modes

    def _build_hint(self) -> str:
        item_names = {self._normalized_item_name(item) for item in self.selected_items if self._normalized_item_name(item)}
        vehicle_labels = {
            (item.get("veiculo") or {}).get("frota") or (item.get("veiculo") or {}).get("placa") or "-"
            for item in self.selected_items
        }
        if self.suggestions:
            first = self.suggestions[0]
            return (
                f"Duplicidade inteligente: o sistema encontrou pacote compatível. "
                f"Sugestão principal: #{first.get('id')} - {first.get('reason_label')}."
            )
        if len(item_names) == 1:
            return "Sugestão inteligente: todos os registros têm o mesmo item. O sistema já pode abrir um pacote por item distinto."
        if len(vehicle_labels) == 1:
            return "Sugestão inteligente: todos os registros pertencem ao mesmo equipamento. O sistema já pode abrir um pacote por equipamento."
        return "Os registros misturam itens e equipamentos. Use este pacote para organizar a primeira triagem sem perder os vínculos."

    def _load_suggestions(self) -> list[dict]:
        try:
            payload = self.api_client.get_resolution_package_suggestions([int(item["id"]) for item in self.selected_items])
            return payload.get("suggestions") or []
        except Exception:
            return []

    def _load_rule_defaults(self) -> dict:
        try:
            payload = self.api_client.get_intelligent_rules() or {}
            return payload.get("rules") or {}
        except Exception:
            return {}

    def _sync_title(self):
        mode = self.grouping_mode_combo.currentData()
        if not mode:
            self.title_input.clear()
            return
        if mode == "POR_EQUIPAMENTO":
            vehicle = self.selected_items[0].get("veiculo") or {}
            label = vehicle.get("frota") or vehicle.get("placa") or "-"
            self.title_input.setText(f"Pacote por equipamento - {label}")
        else:
            label = self._normalized_item_name(self.selected_items[0]) or "-"
            self.title_input.setText(f"Pacote por item - {label}")

    def submit(self):
        try:
            strategy = self.strategy_combo.currentData() or {"mode": "create"}
            checklist_item_ids = [int(item["id"]) for item in self.selected_items]
            if strategy.get("mode") == "append" and strategy.get("package_id"):
                self.created_package = self.api_client.add_items_to_resolution_package(
                    int(strategy["package_id"]),
                    checklist_item_ids,
                    self.observation_input.toPlainText().strip(),
                )
            else:
                payload = {
                    "grouping_mode": self.grouping_mode_combo.currentData(),
                    "checklist_item_ids": checklist_item_ids,
                    "title": self.title_input.text().strip(),
                    "observation": self.observation_input.toPlainText().strip(),
                    "recurrence_window_days": int(self.recurrence_days_spin.value()),
                    "recurrence_weight": int(self.recurrence_weight_spin.value()),
                }
                self.created_package = self.api_client.create_resolution_package(payload)
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha ao criar pacote", str(exc), icon_name="warning")


class NonConformitiesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.items = []
        self.mechanic_items = []
        self.packages = []
        self.current_item = None
        self._live_filter_timer = QTimer(self)
        self._live_filter_timer.setSingleShot(True)
        self._live_filter_timer.timeout.connect(self.refresh)
        self.setObjectName("ContentSurface")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        header = QHBoxLayout()
        text_wrap = QVBoxLayout()
        title = QLabel("Central de Resolução")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Organize as não conformidades abertas, acompanhe a fila de tratativa e encaminhe os registros para resolução. A inspeção aqui é apenas apoio de conferência."
        )
        subtitle.setObjectName("SectionCaption")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = QPushButton("Abrir detalhes da linha")
        self.open_button.setMinimumHeight(34)
        self.open_button.setIcon(make_icon("reports", "#E7EBF0", "#2C5EA8", 18))
        self.open_button.setToolTip("Abre o detalhe completo da linha escolhida.")
        self.open_button.clicked.connect(self.open_selected_item)
        self.open_item_screen_button = QPushButton("Ver todos do mesmo item")
        self.open_item_screen_button.setMinimumHeight(34)
        self.open_item_screen_button.setIcon(make_icon("dashboard", "#E7EBF0", "#2C5EA8", 18))
        self.open_item_screen_button.setToolTip("Abre uma tela com todos os veículos que têm esse mesmo item.")
        self.open_item_screen_button.clicked.connect(self.open_selected_item_screen)
        self.open_equipment_screen_button = QPushButton("Ver todos do mesmo equipamento")
        self.open_equipment_screen_button.setMinimumHeight(34)
        self.open_equipment_screen_button.setIcon(make_icon("activities", "#E7EBF0", "#2C5EA8", 18))
        self.open_equipment_screen_button.setToolTip("Abre uma tela com todas as não conformidades desse equipamento.")
        self.open_equipment_screen_button.clicked.connect(self.open_selected_equipment_screen)
        self.create_activity_button = QPushButton("Abrir inspeção de apoio")
        self.create_activity_button.setMinimumHeight(34)
        self.create_activity_button.setProperty("variant", "primary")
        self.create_activity_button.setIcon(make_icon("activities", "#E7EBF0", "#2C5EA8", 18))
        self.create_activity_button.setToolTip("Cria uma inspeção auxiliar para conferir melhor a linha escolhida.")
        self.create_activity_button.clicked.connect(self.create_activity_from_current_item)
        self.create_package_button = QPushButton("Criar pacote")
        self.create_package_button.setMinimumHeight(34)
        self.create_package_button.setIcon(make_icon("dashboard", "#E7EBF0", "#2C5EA8", 18))
        self.create_package_button.clicked.connect(self.create_resolution_package_from_selection)
        self.resolve_button = QPushButton("Resolver agora")
        self.resolve_button.setMinimumHeight(34)
        self.resolve_button.setProperty("variant", "success")
        self.resolve_button.setIcon(make_icon("ok", "#E7EBF0", "#1E7A63", 18))
        self.resolve_button.setToolTip("Resolve imediatamente a linha escolhida.")
        self.resolve_button.clicked.connect(self.resolve_current_item)
        actions.addWidget(self.open_button)
        actions.addWidget(self.open_item_screen_button)
        actions.addWidget(self.open_equipment_screen_button)
        actions.addWidget(self.create_activity_button)
        actions.addWidget(self.create_package_button)
        actions.addWidget(self.resolve_button)

        header.addLayout(text_wrap)
        header.addStretch()
        header.addLayout(actions)

        self.actions_hint = QLabel(
            "Botões do topo: primeiro escolha a linha na tabela. Depois abra os detalhes da linha, todos do mesmo item, "
            "todos do mesmo equipamento ou trabalhe em lote com pacote."
        )
        self.actions_hint.setObjectName("SectionCaption")
        self.actions_hint.setWordWrap(True)

        self.selection_badge = QLabel("Nenhuma linha escolhida")
        self.selection_badge.setObjectName("TopBarPill")
        self.selection_help = QLabel(
            "1. Clique em uma linha da tabela principal. 2. Use 'Abrir detalhes da linha' para ver aquela NC. "
            "Use 'Ver todos do mesmo item' ou 'Ver todos do mesmo equipamento' para abrir uma tela agrupada."
        )
        self.selection_help.setObjectName("SectionCaption")
        self.selection_help.setWordWrap(True)

        summary_cards = QGridLayout()
        summary_cards.setSpacing(8)
        self.unpacked_card = StatCard("Sem pacote", "0", "Registros ainda soltos na triagem", icon_name="warning")
        self.packed_card = StatCard("Em pacote", "0", "Registros já agrupados para seguir", icon_name="dashboard")
        self.maintenance_card = StatCard("Em manutenção", "0", "Pacotes já enviados para execução", icon_name="activities")
        self.critical_card = StatCard("Críticos", "0", "Pacotes com reincidência crítica", icon_name="reports")
        summary_cards.addWidget(self.unpacked_card, 0, 0)
        summary_cards.addWidget(self.packed_card, 0, 1)
        summary_cards.addWidget(self.maintenance_card, 0, 2)
        summary_cards.addWidget(self.critical_card, 0, 3)

        self.filter_card = QFrame()
        style_filter_bar(self.filter_card)
        filters = QHBoxLayout(self.filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)

        self.vehicle_filter = QLineEdit()
        self.vehicle_filter.setPlaceholderText("Filtrar por veículo")
        self.vehicle_filter.setMinimumHeight(34)
        self.vehicle_filter.returnPressed.connect(self.refresh)
        self.vehicle_filter.textChanged.connect(self._schedule_live_refresh)

        self.item_filter = QLineEdit()
        self.item_filter.setPlaceholderText("Filtrar por item")
        self.item_filter.setMinimumHeight(34)
        self.item_filter.returnPressed.connect(self.refresh)
        self.item_filter.textChanged.connect(self._schedule_live_refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todas", "")
        self.status_filter.addItem("Abertas", "abertas")
        self.status_filter.addItem("Resolvidas", "resolvidas")
        self.status_filter.setMinimumHeight(34)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.setMinimumHeight(34)
        refresh_button.clicked.connect(self.refresh)

        filters.addWidget(self.vehicle_filter, 1)
        filters.addWidget(self.item_filter, 1)
        filters.addWidget(self.status_filter)
        filters.addWidget(refresh_button)

        screens_card = QFrame()
        style_filter_bar(screens_card)
        screens_layout = QHBoxLayout(screens_card)
        screens_layout.setContentsMargins(10, 8, 10, 8)
        screens_layout.setSpacing(8)
        screens_hint = QLabel("Abrir visões agrupadas da central")
        screens_hint.setObjectName("SectionCaption")
        screens_layout.addWidget(screens_hint)
        screens_layout.addStretch()

        self.open_item_summary_screen_button = QPushButton("Resumo por item")
        self.open_item_summary_screen_button.setToolTip("Mostra os itens que mais se repetem e quantos veículos estão ligados a cada um.")
        self.open_item_summary_screen_button.clicked.connect(self.open_item_summary_screen)
        self.open_equipment_summary_screen_button = QPushButton("Resumo por equipamento")
        self.open_equipment_summary_screen_button.setToolTip("Mostra os equipamentos com mais não conformidades abertas.")
        self.open_equipment_summary_screen_button.clicked.connect(self.open_equipment_summary_screen)
        self.open_queue_screen_button = QPushButton("Resumo da fila")
        self.open_queue_screen_button.setToolTip("Mostra o que está sem pacote, em pacote ou já em manutenção.")
        self.open_queue_screen_button.clicked.connect(self.open_queue_screen)
        self.open_blockers_screen_button = QPushButton("Resumo de bloqueios")
        self.open_blockers_screen_button.setToolTip("Mostra onde a resolução travou e o que está impedindo andamento.")
        self.open_blockers_screen_button.clicked.connect(self.open_blockers_screen)
        self.open_mechanic_screen_button = QPushButton("Registros dos mecânicos")
        self.open_mechanic_screen_button.setToolTip("Mostra registros internos abertos e resolvidos pelo módulo mecânico.")
        self.open_mechanic_screen_button.clicked.connect(self.open_mechanic_records_screen)
        self.open_packages_screen_button = QPushButton("Resumo dos pacotes")
        self.open_packages_screen_button.setToolTip("Mostra todos os pacotes de resolução já criados.")
        self.open_packages_screen_button.clicked.connect(self.open_packages_screen)
        for button in (
            self.open_item_summary_screen_button,
            self.open_equipment_summary_screen_button,
            self.open_queue_screen_button,
            self.open_blockers_screen_button,
            self.open_mechanic_screen_button,
            self.open_packages_screen_button,
        ):
            button.setMinimumHeight(34)
            screens_layout.addWidget(button)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)

        occurrences_tab = QFrame()
        occurrences_tab.setObjectName("TableCard")
        occurrences_tab.setAttribute(Qt.WA_StyledBackground, True)
        self.table_skeleton = TableSkeletonOverlay(occurrences_tab, rows=10)
        table_layout = QVBoxLayout(occurrences_tab)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)
        table_title = QLabel("Registros da central")
        table_title.setObjectName("SectionTitle")
        self.summary_badge = QLabel("Nenhum registro carregado")
        self.summary_badge.setObjectName("TopBarPill")
        top_row.addWidget(table_title)
        top_row.addStretch()
        top_row.addWidget(self.summary_badge)

        table_caption = QLabel(
            "Clique duas vezes em uma linha para abrir fotos, histórico, peça aplicada e exportação de PDF."
        )
        table_caption.setObjectName("SectionCaption")
        table_caption.setWordWrap(True)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["Veículo", "Item", "Pacote", "Status", "Prioridade", "Data", "Motorista", "Peça", "Foto antes", "Foto depois"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(620)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._selection_changed())
        self.table.itemDoubleClicked.connect(self.open_item_details)

        table_layout.addLayout(top_row)
        table_layout.addWidget(self.selection_badge)
        table_layout.addWidget(self.selection_help)
        table_layout.addWidget(table_caption)
        table_layout.addWidget(self.table, 1)

        item_tab = QFrame()
        item_tab.setObjectName("TableCard")
        item_tab.setAttribute(Qt.WA_StyledBackground, True)
        item_layout = QVBoxLayout(item_tab)
        item_layout.setContentsMargins(10, 10, 10, 10)
        item_layout.setSpacing(8)
        item_caption = QLabel("Visão por item distinto para enxergar repetição, volume e triagem em lote.")
        item_caption.setObjectName("SectionCaption")
        item_caption.setWordWrap(True)
        self.item_summary_table = QTableWidget(0, 5)
        self.item_summary_table.setHorizontalHeaderLabels(["Item", "Equipamentos", "NCs abertas", "Em pacote", "Ação sugerida"])
        configure_table(self.item_summary_table, stretch_last=False)
        self.item_summary_table.setMinimumHeight(620)
        self.item_summary_table.itemDoubleClicked.connect(self._open_item_screen_from_summary)
        item_layout.addWidget(item_caption)
        item_layout.addWidget(self.item_summary_table, 1)

        equipment_tab = QFrame()
        equipment_tab.setObjectName("TableCard")
        equipment_tab.setAttribute(Qt.WA_StyledBackground, True)
        equipment_layout = QVBoxLayout(equipment_tab)
        equipment_layout.setContentsMargins(10, 10, 10, 10)
        equipment_layout.setSpacing(8)
        equipment_caption = QLabel("Visão por equipamento para descobrir onde os problemas estão concentrados.")
        equipment_caption.setObjectName("SectionCaption")
        equipment_caption.setWordWrap(True)
        self.equipment_summary_table = QTableWidget(0, 5)
        self.equipment_summary_table.setHorizontalHeaderLabels(["Equipamento", "NCs abertas", "Itens distintos", "Em pacote", "Ação sugerida"])
        configure_table(self.equipment_summary_table, stretch_last=False)
        self.equipment_summary_table.setMinimumHeight(620)
        self.equipment_summary_table.itemDoubleClicked.connect(self._open_equipment_screen_from_summary)
        equipment_layout.addWidget(equipment_caption)
        equipment_layout.addWidget(self.equipment_summary_table, 1)

        queue_tab = QFrame()
        queue_tab.setObjectName("TableCard")
        queue_tab.setAttribute(Qt.WA_StyledBackground, True)
        queue_layout = QVBoxLayout(queue_tab)
        queue_layout.setContentsMargins(10, 10, 10, 10)
        queue_layout.setSpacing(8)
        queue_caption = QLabel("Fila operacional da central para saber o que ainda está solto e o que já entrou em pacote.")
        queue_caption.setObjectName("SectionCaption")
        queue_caption.setWordWrap(True)
        self.queue_table = QTableWidget(0, 4)
        self.queue_table.setHorizontalHeaderLabels(["Fase", "Quantidade", "Pacotes", "Leitura"])
        configure_table(self.queue_table, stretch_last=False)
        self.queue_table.setMinimumHeight(620)
        queue_layout.addWidget(queue_caption)
        queue_layout.addWidget(self.queue_table, 1)

        blockers_tab = QFrame()
        blockers_tab.setObjectName("TableCard")
        blockers_tab.setAttribute(Qt.WA_StyledBackground, True)
        blockers_layout = QVBoxLayout(blockers_tab)
        blockers_layout.setContentsMargins(10, 10, 10, 10)
        blockers_layout.setSpacing(8)
        blockers_caption = QLabel("Bloqueios e alertas da triagem e da execução oficial, para mostrar onde a resolução travou.")
        blockers_caption.setObjectName("SectionCaption")
        blockers_caption.setWordWrap(True)
        self.blockers_table = QTableWidget(0, 4)
        self.blockers_table.setHorizontalHeaderLabels(["Tipo", "Referência", "Quantidade", "Leitura"])
        configure_table(self.blockers_table, stretch_last=False)
        self.blockers_table.setMinimumHeight(620)
        blockers_layout.addWidget(blockers_caption)
        blockers_layout.addWidget(self.blockers_table, 1)

        mechanic_tab = QFrame()
        mechanic_tab.setObjectName("TableCard")
        mechanic_tab.setAttribute(Qt.WA_StyledBackground, True)
        mechanic_layout = QVBoxLayout(mechanic_tab)
        mechanic_layout.setContentsMargins(10, 10, 10, 10)
        mechanic_layout.setSpacing(8)

        mechanic_top = QHBoxLayout()
        mechanic_title = QLabel("Registros internos dos mecânicos")
        mechanic_title.setObjectName("SectionTitle")
        self.mechanic_badge = QLabel("0 registros")
        self.mechanic_badge.setObjectName("TopBarPill")
        mechanic_top.addWidget(mechanic_title)
        mechanic_top.addStretch()
        mechanic_top.addWidget(self.mechanic_badge)

        mechanic_caption = QLabel(
            "Registros internos abertos e resolvidos pelo módulo mecânico, separados das não conformidades do checklist."
        )
        mechanic_caption.setObjectName("SectionCaption")
        mechanic_caption.setWordWrap(True)

        self.mechanic_table = QTableWidget(0, 8)
        self.mechanic_table.setHorizontalHeaderLabels(
            ["Referência", "Item", "Status", "Aberta por", "Resolvida por", "Abertura", "Resolução", "Peça"]
        )
        configure_table(self.mechanic_table, stretch_last=False)
        self.mechanic_table.setMinimumHeight(620)

        mechanic_layout.addLayout(mechanic_top)
        mechanic_layout.addWidget(mechanic_caption)
        mechanic_layout.addWidget(self.mechanic_table, 1)

        self.tabs.addTab(occurrences_tab, "Registros da central")
        self.tabs.addTab(item_tab, "Por item")
        self.tabs.addTab(equipment_tab, "Por equipamento")
        self.tabs.addTab(queue_tab, "Fila")
        self.tabs.addTab(blockers_tab, "Bloqueios")
        self.tabs.addTab(mechanic_tab, "Registros internos dos mecânicos")

        packages_tab = QFrame()
        packages_tab.setObjectName("TableCard")
        packages_tab.setAttribute(Qt.WA_StyledBackground, True)
        packages_layout = QVBoxLayout(packages_tab)
        packages_layout.setContentsMargins(10, 10, 10, 10)
        packages_layout.setSpacing(8)

        packages_top = QHBoxLayout()
        packages_title = QLabel("Pacotes de resolução")
        packages_title.setObjectName("SectionTitle")
        self.packages_badge = QLabel("0 pacotes")
        self.packages_badge.setObjectName("TopBarPill")
        packages_top.addWidget(packages_title)
        packages_top.addStretch()
        packages_top.addWidget(self.packages_badge)

        packages_caption = QLabel(
            "Aqui nasce a caixa oficial da resolução. O pacote agrupa as não conformidades por item distinto ou por equipamento."
        )
        packages_caption.setObjectName("SectionCaption")
        packages_caption.setWordWrap(True)

        self.packages_table = QTableWidget(0, 8)
        self.packages_table.setHorizontalHeaderLabels(
            ["Título", "Agrupamento", "Referência", "Status", "Score", "Reincidência", "Crítico", "Resumo"]
        )
        configure_table(self.packages_table, stretch_last=False)
        self.packages_table.setMinimumHeight(620)
        self.packages_table.itemDoubleClicked.connect(self._open_package_screen_from_table)

        packages_layout.addLayout(packages_top)
        packages_layout.addWidget(packages_caption)
        packages_layout.addWidget(self.packages_table, 1)

        self.packages_tab_index = self.tabs.addTab(packages_tab, "Pacotes de resolução")

        outer.addLayout(header)
        outer.addWidget(self.actions_hint)
        outer.addLayout(summary_cards)
        outer.addWidget(self.filter_card)
        outer.addWidget(screens_card)
        outer.addWidget(self.tabs, 1)
        self.tabs.hide()
        self._set_action_state(False)

    def _schedule_live_refresh(self, *_args):
        self._live_filter_timer.start(240)

    def _user_has_management_access(self) -> bool:
        user = self.api_client.user or {}
        return user.get("tipo") in {"admin", "gestor"}

    def _set_action_state(self, enabled: bool):
        selected_count = len(self._selected_rows())
        has_single_selection = selected_count == 1 and enabled
        self.open_button.setEnabled(has_single_selection)
        self.open_item_screen_button.setEnabled(has_single_selection)
        self.open_equipment_screen_button.setEnabled(has_single_selection)
        self.create_activity_button.setEnabled(has_single_selection and not (self.current_item or {}).get("resolvido", False))
        self.create_package_button.setEnabled(
            self._user_has_management_access() and bool(self._package_modes_for_items(self._selected_items_for_package()))
        )
        self.resolve_button.setEnabled(has_single_selection and not (self.current_item or {}).get("resolvido", False))
        self._refresh_selection_badge()
        self._refresh_package_button_state()

    def _refresh_package_button_state(self):
        selected_items = self._selected_items_for_package()
        selected_count = len(selected_items)
        valid_modes = self._package_modes_for_items(selected_items)
        can_manage = self._user_has_management_access()

        if not can_manage:
            self.create_package_button.setText("Criar pacote")
            self.create_package_button.setToolTip("Somente admin ou gestor pode criar pacote.")
            return

        if selected_count <= 0:
            self.create_package_button.setText("Criar pacote")
            self.create_package_button.setToolTip(
                "Selecione uma ou mais linhas compatíveis. O pacote funciona em lote por item ou por equipamento."
            )
            return

        if not valid_modes:
            self.create_package_button.setText(f"Criar pacote ({selected_count} linhas)")
            self.create_package_button.setToolTip(
                "A seleção mistura itens e equipamentos diferentes. Para criar pacote, escolha o mesmo item ou o mesmo equipamento."
            )
            return

        if len(valid_modes) == 2:
            self.create_package_button.setText(f"Criar pacote guiado ({selected_count})")
            self.create_package_button.setToolTip(
                "A seleção permite pacote por item ou por equipamento. Ao abrir, o sistema vai sugerir o melhor agrupamento."
            )
            return

        mode_label = "por item" if valid_modes[0] == "POR_ITEM" else "por equipamento"
        self.create_package_button.setText(f"Criar pacote {mode_label} ({selected_count})")
        self.create_package_button.setToolTip(
            f"A seleção está pronta para abrir um pacote {mode_label}."
        )

    def _refresh_selection_badge(self):
        selected_rows = self._selected_rows()
        count = len(selected_rows)
        if count <= 0:
            self.selection_badge.setText("Nenhuma linha escolhida")
            return
        if count > 1:
            valid_modes = self._package_modes_for_items(self._selected_items_for_package())
            if not valid_modes:
                guidance = "Mistura inválida para pacote"
            elif len(valid_modes) == 2:
                guidance = "Lote pronto para item ou equipamento"
            elif valid_modes[0] == "POR_ITEM":
                guidance = "Lote pronto por item"
            else:
                guidance = "Lote pronto por equipamento"
            self.selection_badge.setText(f"{count} linhas escolhidas | {guidance}")
            return
        item = self._item_for_row(selected_rows[0]) or {}
        vehicle = item.get("veiculo") or {}
        vehicle_label = vehicle.get("frota") or vehicle.get("placa") or "-"
        item_label = _nc_label(item)
        self.selection_badge.setText(f"Linha escolhida: {vehicle_label} - {item_label}")

    def _selected_rows(self) -> list[int]:
        ranges = self.table.selectedRanges()
        if not ranges:
            return []
        rows: set[int] = set()
        for selected_range in ranges:
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                rows.add(row)
        return sorted(rows)

    def _selected_items_for_package(self) -> list[dict]:
        selected_items = []
        for row in self._selected_rows():
            item = self._item_for_row(row)
            if item and not item.get("resolvido"):
                selected_items.append(item)
        return selected_items

    def _package_modes_for_items(self, selected_items: list[dict]) -> list[str]:
        item_names = {
            str(item.get("item_principal") or item.get("item_nome") or "").strip().upper()
            for item in selected_items
            if str(item.get("item_principal") or item.get("item_nome") or "").strip()
        }
        vehicle_ids = {
            (item.get("veiculo") or {}).get("id")
            for item in selected_items
            if (item.get("veiculo") or {}).get("id")
        }
        modes: list[str] = []
        if len(item_names) == 1:
            modes.append("POR_ITEM")
        if len(vehicle_ids) == 1:
            modes.append("POR_EQUIPAMENTO")
        return modes

    def refresh(self):
        self.items = self.api_client.get_non_conformities(
            vehicle=self.vehicle_filter.text().strip() or None,
            item_type=self.item_filter.text().strip() or None,
            status=self.status_filter.currentData() or None,
        )
        self.mechanic_items = self.api_client.get_mechanic_non_conformities(
            status=self.status_filter.currentData() or None,
        )
        self.packages = self.api_client.get_resolution_packages() if self._user_has_management_access() else []
        self.maintenance_overview = self.api_client.get_maintenance_overview() if self._user_has_management_access() else {}
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))

            for row, item in enumerate(self.items):
                created_at = item["created_at"].replace("T", " ")[:19]
                status_label = "Resolvida" if item["resolvido"] else "Aberta"
                severity = severity_from_occurrence(item)
                package = item.get("resolution_package") or {}
                package_label = f"#{package.get('id')}" if package.get("id") else "-"
                values = [
                    item["veiculo"]["frota"],
                    _nc_label(item),
                    package_label,
                    status_label,
                    severity["label"],
                    created_at,
                    item["usuario"]["nome"],
                    item.get("codigo_peca") or "-",
                    "Sim" if item.get("foto_antes") else "Não",
                    "Sim" if item.get("foto_depois") else "Não",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value, payload=item if column == 0 else None)
                    if column == 4:
                        cell.setBackground(QBrush(QColor(severity["background"])))
                        cell.setForeground(QBrush(QColor(severity["color"])))
                    if column == 2 and package.get("critical_recurrence"):
                        cell.setBackground(QBrush(QColor("#F4D9D6")))
                        cell.setForeground(QBrush(QColor("#7A332B")))
                    self.table.setItem(row, column, cell)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.summary_badge.setText(f"{len(self.items)} registros")
        self._refresh_phase_cards()
        self._populate_item_summary_table()
        self._populate_equipment_summary_table()
        self._populate_queue_table()
        self._populate_blockers_table()
        self._populate_mechanic_table()
        self._populate_packages_table()
        self.table.clearSelection()
        self.current_item = None
        self._set_action_state(False)

    def _populate_mechanic_table(self):
        self.mechanic_table.setSortingEnabled(False)
        self.mechanic_table.setUpdatesEnabled(False)
        self.mechanic_table.blockSignals(True)
        try:
            self.mechanic_table.setRowCount(len(self.mechanic_items))
            for row, item in enumerate(self.mechanic_items):
                values = [
                    item.get("veiculo_referencia") or "-",
                    item.get("item_nome") or "-",
                    "Resolvida" if item.get("resolvido") else "Aberta",
                    (item.get("created_by") or {}).get("nome") or "-",
                    (item.get("resolved_by") or {}).get("nome") or "-",
                    self._format(item.get("created_at")),
                    self._format(item.get("data_resolucao")),
                    item.get("codigo_peca") or "-",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value)
                    if column == 2:
                        if item.get("resolvido"):
                            cell.setBackground(QBrush(QColor("#E5ECE5")))
                            cell.setForeground(QBrush(QColor("#3F5643")))
                        else:
                            cell.setBackground(QBrush(QColor("#ECE7D8")))
                            cell.setForeground(QBrush(QColor("#5F563F")))
                    self.mechanic_table.setItem(row, column, cell)
        finally:
            self.mechanic_table.blockSignals(False)
            self.mechanic_table.setUpdatesEnabled(True)
            self.mechanic_table.setSortingEnabled(True)
        self.mechanic_badge.setText(f"{len(self.mechanic_items)} registros")

    def _populate_packages_table(self):
        self.packages_table.setSortingEnabled(False)
        self.packages_table.setUpdatesEnabled(False)
        self.packages_table.blockSignals(True)
        try:
            self.packages_table.setRowCount(len(self.packages))
            for row, package in enumerate(self.packages):
                resumo = package.get("resumo") or {}
                values = [
                    package.get("title") or "-",
                    "Por item" if package.get("grouping_mode") == "POR_ITEM" else "Por equipamento",
                    package.get("reference_label") or "-",
                    package.get("status") or "-",
                    str(package.get("priority_score") or 0),
                    str(package.get("recurrence_hits") or 0),
                    "Sim" if package.get("critical_recurrence") else "Não",
                    f"{resumo.get('abertas', 0)} aberta(s) / {resumo.get('resolvidas', 0)} resolvida(s)",
                ]
                for column, value in enumerate(values):
                    cell = make_table_item(value, payload=package if column == 0 else None)
                    if column == 6 and package.get("critical_recurrence"):
                        cell.setBackground(QBrush(QColor("#F4D9D6")))
                        cell.setForeground(QBrush(QColor("#7A332B")))
                    self.packages_table.setItem(row, column, cell)
        finally:
            self.packages_table.blockSignals(False)
            self.packages_table.setUpdatesEnabled(True)
            self.packages_table.setSortingEnabled(True)
        self.packages_badge.setText(f"{len(self.packages)} pacotes")

    def _populate_item_summary_table(self):
        groups: dict[str, dict] = defaultdict(lambda: {"vehicles": set(), "open": 0, "packaged": 0, "package_ids": set()})
        for item in self.items:
            if item.get("resolvido"):
                continue
            key = str(item.get("item_principal") or item.get("item_nome") or "-").strip().upper() or "-"
            group = groups[key]
            vehicle = item.get("veiculo") or {}
            group["vehicles"].add(vehicle.get("id") or vehicle.get("frota") or "-")
            group["open"] += 1
            package = item.get("resolution_package") or {}
            if package.get("id"):
                group["packaged"] += 1
                group["package_ids"].add(package.get("id"))

        rows = sorted(groups.items(), key=lambda row: (-row[1]["open"], row[0]))
        self.item_summary_table.setRowCount(len(rows))
        for row, (item_name, group) in enumerate(rows):
            package_ids = sorted(group["package_ids"])
            action = f"Adicionar ao pacote #{package_ids[0]}" if package_ids else "Criar pacote por item"
            values = [item_name, str(len(group["vehicles"])), str(group["open"]), str(group["packaged"]), action]
            for column, value in enumerate(values):
                payload = {"item_name": item_name}
                self.item_summary_table.setItem(row, column, make_table_item(value, payload=payload if column == 0 else None))

    def _populate_equipment_summary_table(self):
        groups: dict[str, dict] = defaultdict(lambda: {"open": 0, "items": set(), "packaged": 0, "package_ids": set()})
        for item in self.items:
            if item.get("resolvido"):
                continue
            vehicle = item.get("veiculo") or {}
            label = vehicle.get("frota") or vehicle.get("placa") or "-"
            group = groups[label]
            group["open"] += 1
            group["items"].add(_nc_label(item))
            package = item.get("resolution_package") or {}
            if package.get("id"):
                group["packaged"] += 1
                group["package_ids"].add(package.get("id"))

        rows = sorted(groups.items(), key=lambda row: (-row[1]["open"], row[0]))
        self.equipment_summary_table.setRowCount(len(rows))
        for row, (vehicle_label, group) in enumerate(rows):
            package_ids = sorted(group["package_ids"])
            action = f"Adicionar ao pacote #{package_ids[0]}" if package_ids else "Criar pacote por equipamento"
            values = [vehicle_label, str(group["open"]), str(len(group["items"])), str(group["packaged"]), action]
            for column, value in enumerate(values):
                payload = {"vehicle_label": vehicle_label}
                self.equipment_summary_table.setItem(row, column, make_table_item(value, payload=payload if column == 0 else None))

    def _populate_queue_table(self):
        unresolved_items = [item for item in self.items if not item.get("resolvido")]
        unresolved_without_package = [item for item in unresolved_items if not (item.get("resolution_package") or {}).get("id")]
        unresolved_with_package = [item for item in unresolved_items if (item.get("resolution_package") or {}).get("id")]
        open_packages = [package for package in self.packages if package.get("status") == "ABERTO"]
        maintenance_packages = [package for package in self.packages if package.get("status") == "EM_MANUTENCAO"]
        critical_packages = [package for package in self.packages if package.get("critical_recurrence")]
        rows = [
            ("Sem pacote", len(unresolved_without_package), 0, "Registros ainda soltos na triagem."),
            ("Em pacote", len(unresolved_with_package), len(open_packages), "Registros já organizados em pacote aberto."),
            ("Em manutenção", 0, len(maintenance_packages), "Pacotes já despachados para execução oficial."),
            ("Recorrência crítica", 0, len(critical_packages), "Pacotes que já merecem atenção por repetição forte."),
        ]
        self.queue_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.queue_table.setItem(row, column, make_table_item(str(value)))

    def _refresh_phase_cards(self):
        unresolved_items = [item for item in self.items if not item.get("resolvido")]
        unresolved_without_package = [item for item in unresolved_items if not (item.get("resolution_package") or {}).get("id")]
        unresolved_with_package = [item for item in unresolved_items if (item.get("resolution_package") or {}).get("id")]
        maintenance_packages = [package for package in self.packages if package.get("status") == "EM_MANUTENCAO"]
        critical_packages = [package for package in self.packages if package.get("critical_recurrence")]
        self.unpacked_card.set_content("Sem pacote", str(len(unresolved_without_package)), "Registros aguardando triagem oficial")
        self.packed_card.set_content("Em pacote", str(len(unresolved_with_package)), "Registros já agrupados em pacote")
        self.maintenance_card.set_content("Em manutenção", str(len(maintenance_packages)), "Pacotes já carimbados para execução")
        self.critical_card.set_content("Críticos", str(len(critical_packages)), "Pacotes com repetição forte")

    def _populate_blockers_table(self):
        rows: list[tuple[str, str, str, str, bool]] = []
        unresolved_items = [item for item in self.items if not item.get("resolvido")]
        unresolved_without_package = [item for item in unresolved_items if not (item.get("resolution_package") or {}).get("id")]
        if unresolved_without_package:
            rows.append(
                (
                    "Sem pacote",
                    "Central de Resolução",
                    str(len(unresolved_without_package)),
                    "Existem não conformidades abertas esperando triagem oficial.",
                    False,
                )
            )
        for package in self.packages:
            if package.get("critical_recurrence"):
                resumo = package.get("resumo") or {}
                rows.append(
                    (
                        "Reincidência crítica",
                        f"Pacote #{package.get('id')} - {package.get('reference_label') or '-'}",
                        str(resumo.get("abertas", 0)),
                        "O mesmo problema está voltando demais e pede prioridade.",
                        True,
                    )
                )
        maintenance_blockers = list((self.maintenance_overview or {}).get("bloqueios") or [])
        for blocker in maintenance_blockers:
            rows.append(
                (
                    str(blocker.get("type") or "Bloqueio de manutenção"),
                    str(blocker.get("reference") or "Manutenção"),
                    str(blocker.get("quantity") or 0),
                    str(blocker.get("reading") or "A manutenção identificou um bloqueio operacional."),
                    bool(blocker.get("critical")),
                )
            )
        self.blockers_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values[:4]):
                cell = make_table_item(value)
                if values[4] and column == 0:
                    cell.setBackground(QBrush(QColor("#F4D9D6")))
                    cell.setForeground(QBrush(QColor("#7A332B")))
                self.blockers_table.setItem(row, column, cell)

    @staticmethod
    def _format(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ")[:19]

    def set_loading_state(self, loading: bool):
        if loading:
            self.table_skeleton.show_skeleton("Carregando não conformidades")
        else:
            self.table_skeleton.hide_skeleton()

    def _selection_changed(self):
        selected = self.table.selectedRanges()
        if not selected:
            self.current_item = None
            self._set_action_state(False)
            return

        row = selected[0].topRow()
        self.current_item = self._item_for_row(row)
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

    def _require_single_selected_item(self, action_label: str):
        selected_rows = self._selected_rows()
        if len(selected_rows) != 1:
            if not selected_rows:
                show_notice(
                    self,
                    "Escolha uma linha",
                    f"Para {action_label.lower()}, primeiro clique em uma linha da tabela principal.",
                    icon_name="warning",
                )
            else:
                show_notice(
                    self,
                    "Escolha só uma linha",
                    f"Para {action_label.lower()}, selecione apenas uma linha. Se a ideia for trabalhar em lote, use 'Criar pacote'.",
                    icon_name="warning",
                )
            return None
        return self._item_for_row(selected_rows[0])

    def open_item_details(self, item=None):
        row_item = self._item_for_row(item.row()) if item is not None else self._selected_item()
        if not row_item:
            return
        self.current_item = row_item
        dialog = NonConformityDetailDialog(self.api_client, row_item, self)
        dialog.exec()

    def open_selected_item(self, *_args):
        target_item = self._require_single_selected_item("abrir os detalhes da linha")
        if not target_item:
            return
        self.current_item = target_item
        dialog = NonConformityDetailDialog(self.api_client, target_item, self)
        dialog.exec()

    def resolve_current_item(self):
        target_item = self._require_single_selected_item("resolver agora")
        if not target_item:
            return
        self.current_item = target_item
        dialog = ResolveDialog(self.api_client, target_item, self)
        if dialog.exec():
            show_notice(
                self,
                "Resolvida",
                "Não conformidade atualizada com sucesso.",
                icon_name="dashboard",
            )
            self.refresh()
            self.data_changed.emit()

    def create_activity_from_current_item(self):
        target_item = self._require_single_selected_item("abrir a inspeção de apoio")
        if not target_item:
            return
        self.current_item = target_item
        dialog = CreateActivityFromNCDialog(self.api_client, target_item, self)
        if dialog.exec():
            created = dialog.created_activity or {}
            activity_id = created.get("id")
            message = "Inspeção de apoio criada com sucesso a partir da não conformidade."
            if activity_id:
                message = f"Inspeção de apoio #{activity_id} criada com sucesso a partir da não conformidade."
            show_notice(self, "Inspeção de apoio aberta", message, icon_name="activities")
            self.refresh()
            self.data_changed.emit()

            parent_window = self.window()
            if parent_window and hasattr(parent_window, "switch_page"):
                try:
                    parent_window.switch_page("activities")
                except Exception:
                    pass

    def create_resolution_package_from_selection(self):
        selected_items = self._selected_items_for_package()
        if not selected_items:
            show_notice(
                self,
                "Seleção insuficiente",
                "Selecione uma ou mais não conformidades abertas para criar o pacote de resolução.",
                icon_name="warning",
            )
            return
        valid_modes = self._package_modes_for_items(selected_items)
        if not valid_modes:
            show_notice(
                self,
                "Agrupamento inválido",
                "Os registros selecionados misturam itens e equipamentos diferentes. Para este start, o pacote só pode nascer por item distinto ou pelo mesmo equipamento.",
                icon_name="warning",
            )
            return
        dialog = CreateResolutionPackageDialog(self.api_client, selected_items, self)
        if dialog.exec():
            created = dialog.created_package or {}
            message = f"Pacote #{created.get('id')} atualizado com sucesso."
            if created.get("critical_recurrence"):
                message += " O sistema já marcou reincidência crítica para este item."
            show_notice(self, "Pacote criado", message, icon_name="dashboard")
            self.refresh()
            self.open_packages_screen()
            self.data_changed.emit()

    def _row_payload(self, table: QTableWidget, row: int):
        if row < 0:
            return None
        item = table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _build_occurrence_rows_for_item(self, item_name: str) -> list[dict]:
        normalized = str(item_name or "").strip().upper()
        return [
            item
            for item in self.items
            if str(item.get("item_principal") or item.get("item_nome") or "").strip().upper() == normalized
        ]

    def _build_occurrence_rows_for_vehicle(self, vehicle_label: str) -> list[dict]:
        normalized = str(vehicle_label or "").strip().upper()
        return [
            item
            for item in self.items
            if ((item.get("veiculo") or {}).get("frota") or (item.get("veiculo") or {}).get("placa") or "").strip().upper() == normalized
        ]

    def _open_table_screen(
        self,
        *,
        title: str,
        subtitle: str,
        headers: list[str],
        rows: list[list[str]],
        row_payloads: list[dict] | None = None,
        on_double_click=None,
        width: int = 1240,
        height: int = 760,
    ):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        configure_dialog_window(dialog, width=width, height=height, min_width=860, min_height=560)
        style_card(dialog)
        layout = build_dialog_layout(dialog, max_content_width=1280)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("DialogHeaderTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("DialogHeaderSubtitle")
        subtitle_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)

        table_card = QFrame()
        table_card.setObjectName("TableCard")
        table_card.setAttribute(Qt.WA_StyledBackground, True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)

        badge = QLabel(f"{len(rows)} registro(s)")
        badge.setObjectName("TopBarPill")
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge_row.addWidget(badge)

        dialog_selection_badge = QLabel("Nenhuma linha escolhida nesta tela")
        dialog_selection_badge.setObjectName("TopBarPill")
        dialog_selection_help = QLabel(
            "Clique em uma linha para destacar o registro. Dê duplo clique somente quando quiser abrir o detalhe daquela linha."
        )
        dialog_selection_help.setObjectName("SectionCaption")
        dialog_selection_help.setWordWrap(True)

        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        configure_table(table, stretch_last=False)
        table.setMinimumHeight(560)
        table.setSortingEnabled(False)
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setRowCount(len(rows))
            for row_index, row_values in enumerate(rows):
                payload = row_payloads[row_index] if row_payloads and row_index < len(row_payloads) else None
                for column, value in enumerate(row_values):
                    table.setItem(row_index, column, make_table_item(value, payload=payload if column == 0 else None))
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.setSortingEnabled(True)

        def _refresh_dialog_selection_badge():
            selected_rows = table.selectionModel().selectedRows() if table.selectionModel() else []
            if not selected_rows:
                dialog_selection_badge.setText("Nenhuma linha escolhida nesta tela")
                return
            payload = self._row_payload(table, selected_rows[0].row()) or {}
            label_parts = []
            if payload.get("item_name"):
                label_parts.append(str(payload.get("item_name")))
            if payload.get("vehicle_label"):
                label_parts.append(str(payload.get("vehicle_label")))
            if not label_parts:
                label_parts.append(str(table.item(selected_rows[0].row(), 0).text() if table.item(selected_rows[0].row(), 0) else "-"))
            dialog_selection_badge.setText(f"Linha escolhida nesta tela: {' - '.join(label_parts)}")

        table.itemSelectionChanged.connect(_refresh_dialog_selection_badge)

        if on_double_click:
            def _handle_double_click(cell):
                payload = self._row_payload(table, cell.row())
                if payload:
                    on_double_click(payload)

            table.itemDoubleClicked.connect(_handle_double_click)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(dialog.accept)
        footer_layout.addWidget(close_button)

        table_layout.addLayout(badge_row)
        table_layout.addWidget(dialog_selection_badge)
        table_layout.addWidget(dialog_selection_help)
        table_layout.addWidget(table)
        layout.addWidget(header)
        layout.addWidget(table_card, 1)
        layout.addWidget(footer)
        dialog.exec()

    def open_item_summary_screen(self):
        groups: dict[str, dict] = defaultdict(lambda: {"vehicles": set(), "open": 0, "packaged": 0, "package_ids": set()})
        for item in self.items:
            if item.get("resolvido"):
                continue
            key = str(item.get("item_principal") or item.get("item_nome") or "-").strip().upper() or "-"
            group = groups[key]
            vehicle = item.get("veiculo") or {}
            group["vehicles"].add(vehicle.get("id") or vehicle.get("frota") or "-")
            group["open"] += 1
            package = item.get("resolution_package") or {}
            if package.get("id"):
                group["packaged"] += 1
                group["package_ids"].add(package.get("id"))

        rows = []
        payloads = []
        for item_name, group in sorted(groups.items(), key=lambda row: (-row[1]["open"], row[0])):
            package_ids = sorted(group["package_ids"])
            action = f"Adicionar ao pacote #{package_ids[0]}" if package_ids else "Criar pacote por item"
            rows.append([item_name, str(len(group["vehicles"])), str(group["open"]), str(group["packaged"]), action])
            payloads.append({"item_name": item_name})
        self._open_table_screen(
            title="Tela por item",
            subtitle="Clique duas vezes em um item para abrir a tela com todos os veículos e registros ligados a essa não conformidade.",
            headers=["Item", "Equipamentos", "NCs abertas", "Em pacote", "Ação sugerida"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: self.open_item_occurrences_screen(payload.get("item_name")),
        )

    def open_equipment_summary_screen(self):
        groups: dict[str, dict] = defaultdict(lambda: {"open": 0, "items": set(), "packaged": 0, "package_ids": set()})
        for item in self.items:
            if item.get("resolvido"):
                continue
            vehicle = item.get("veiculo") or {}
            label = vehicle.get("frota") or vehicle.get("placa") or "-"
            group = groups[label]
            group["open"] += 1
            group["items"].add(_nc_label(item))
            package = item.get("resolution_package") or {}
            if package.get("id"):
                group["packaged"] += 1
                group["package_ids"].add(package.get("id"))

        rows = []
        payloads = []
        for vehicle_label, group in sorted(groups.items(), key=lambda row: (-row[1]["open"], row[0])):
            package_ids = sorted(group["package_ids"])
            action = f"Adicionar ao pacote #{package_ids[0]}" if package_ids else "Criar pacote por equipamento"
            rows.append([vehicle_label, str(group["open"]), str(len(group["items"])), str(group["packaged"]), action])
            payloads.append({"vehicle_label": vehicle_label})
        self._open_table_screen(
            title="Tela por equipamento",
            subtitle="Clique duas vezes em um equipamento para abrir a tela com todas as não conformidades daquele veículo.",
            headers=["Equipamento", "NCs abertas", "Itens distintos", "Em pacote", "Ação sugerida"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: self.open_equipment_occurrences_screen(payload.get("vehicle_label")),
        )

    def open_queue_screen(self):
        unresolved_items = [item for item in self.items if not item.get("resolvido")]
        unresolved_without_package = [item for item in unresolved_items if not (item.get("resolution_package") or {}).get("id")]
        unresolved_with_package = [item for item in unresolved_items if (item.get("resolution_package") or {}).get("id")]
        open_packages = [package for package in self.packages if package.get("status") == "ABERTO"]
        maintenance_packages = [package for package in self.packages if package.get("status") == "EM_MANUTENCAO"]
        critical_packages = [package for package in self.packages if package.get("critical_recurrence")]
        rows = [
            ["Sem pacote", str(len(unresolved_without_package)), "0", "Ainda aguardando decisão da central."],
            ["Em pacote", str(len(unresolved_with_package)), str(len(open_packages)), "Já agrupados para seguir."],
            ["Em manutenção", "0", str(len(maintenance_packages)), "Já enviados para execução oficial."],
            ["Problema repetindo muito", "0", str(len(critical_packages)), "Pacotes em que o mesmo problema voltou demais."],
        ]
        self._open_table_screen(
            title="Tela da fila da central",
            subtitle="Leitura simples para saber o que está solto, agrupado ou já enviado para execução.",
            headers=["Fase", "Quantidade", "Pacotes", "Leitura"],
            rows=rows,
        )

    def open_blockers_screen(self):
        rows = []
        unresolved_items = [item for item in self.items if not item.get("resolvido")]
        unresolved_without_package = [item for item in unresolved_items if not (item.get("resolution_package") or {}).get("id")]
        if unresolved_without_package:
            rows.append(["Sem pacote", "Central de Resolução", str(len(unresolved_without_package)), "Existem registros abertos esperando triagem oficial."])
        for package in self.packages:
            if package.get("critical_recurrence"):
                resumo = package.get("resumo") or {}
                rows.append([
                    "Problema repetindo muito",
                    f"Pacote #{package.get('id')} - {package.get('reference_label') or '-'}",
                    str(resumo.get("abertas", 0)),
                    "Esse mesmo problema está voltando demais e merece atenção.",
                ])
        for blocker in list((self.maintenance_overview or {}).get("bloqueios") or []):
            rows.append([
                str(blocker.get("type") or "Bloqueio de manutenção"),
                str(blocker.get("reference") or "Manutenção"),
                str(blocker.get("quantity") or 0),
                str(blocker.get("reading") or "Existe um bloqueio operacional na manutenção."),
            ])
        self._open_table_screen(
            title="Tela de bloqueios",
            subtitle="Mostra onde a resolução travou: sem pacote, problema repetindo muito ou bloqueio na execução.",
            headers=["Tipo", "Referência", "Quantidade", "Leitura"],
            rows=rows,
        )

    def open_mechanic_records_screen(self):
        rows = []
        payloads = []
        for item in self.mechanic_items:
            rows.append([
                item.get("veiculo_referencia") or "-",
                item.get("item_nome") or "-",
                "Resolvida" if item.get("resolvido") else "Aberta",
                (item.get("created_by") or {}).get("nome") or "-",
                (item.get("resolved_by") or {}).get("nome") or "-",
                self._format(item.get("created_at")),
                self._format(item.get("data_resolucao")),
                item.get("codigo_peca") or "-",
            ])
            payloads.append(item)
        self._open_table_screen(
            title="Tela dos registros internos dos mecânicos",
            subtitle="Mostra o que foi aberto e resolvido diretamente pelo mecânico, separado do checklist.",
            headers=["Referência", "Item", "Status", "Aberta por", "Resolvida por", "Abertura", "Resolução", "Peça"],
            rows=rows,
            row_payloads=payloads,
        )

    def open_packages_screen(self):
        rows = []
        payloads = []
        for package in self.packages:
            resumo = package.get("resumo") or {}
            rows.append([
                package.get("title") or "-",
                "Por item" if package.get("grouping_mode") == "POR_ITEM" else "Por equipamento",
                package.get("reference_label") or "-",
                package.get("status") or "-",
                str(package.get("priority_score") or 0),
                str(package.get("recurrence_hits") or 0),
                "Sim" if package.get("critical_recurrence") else "Não",
                f"{resumo.get('abertas', 0)} aberta(s) / {resumo.get('resolvidas', 0)} resolvida(s)",
            ])
            payloads.append(package)
        self._open_table_screen(
            title="Tela dos pacotes de resolução",
            subtitle="Clique duas vezes em um pacote para abrir a lista dos registros que estão dentro dele.",
            headers=["Título", "Agrupamento", "Referência", "Status", "Score", "Repetições", "Crítico", "Resumo"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: self.open_package_occurrences_screen(payload),
        )

    def open_item_occurrences_screen(self, item_name: str | None):
        if not item_name:
            return
        rows = []
        payloads = []
        for item in self._build_occurrence_rows_for_item(item_name):
            package = item.get("resolution_package") or {}
            rows.append([
                (item.get("veiculo") or {}).get("frota") or "-",
                _nc_label(item),
                "Resolvida" if item.get("resolvido") else "Aberta",
                self._format(item.get("created_at")),
                (item.get("usuario") or {}).get("nome") or "-",
                f"#{package.get('id')}" if package.get("id") else "-",
                "Sim" if item.get("foto_antes") else "Não",
                "Sim" if item.get("foto_depois") else "Não",
            ])
            payloads.append(item)
        self._open_table_screen(
            title=f"Tela do item - {item_name}",
            subtitle="Aqui aparecem todos os veículos e todos os registros ligados a esse item de não conformidade.",
            headers=["Veículo", "Item", "Status", "Abertura", "Motorista", "Pacote", "Foto antes", "Foto depois"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: NonConformityDetailDialog(self.api_client, payload, self).exec(),
        )

    def open_equipment_occurrences_screen(self, vehicle_label: str | None):
        if not vehicle_label:
            return
        rows = []
        payloads = []
        for item in self._build_occurrence_rows_for_vehicle(vehicle_label):
            package = item.get("resolution_package") or {}
            rows.append([
                (item.get("veiculo") or {}).get("frota") or "-",
                _nc_label(item),
                "Resolvida" if item.get("resolvido") else "Aberta",
                self._format(item.get("created_at")),
                (item.get("usuario") or {}).get("nome") or "-",
                f"#{package.get('id')}" if package.get("id") else "-",
                "Sim" if item.get("foto_antes") else "Não",
                "Sim" if item.get("foto_depois") else "Não",
            ])
            payloads.append(item)
        self._open_table_screen(
            title=f"Tela do equipamento - {vehicle_label}",
            subtitle="Aqui aparecem todas as não conformidades abertas ou resolvidas desse equipamento.",
            headers=["Veículo", "Item", "Status", "Abertura", "Motorista", "Pacote", "Foto antes", "Foto depois"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: NonConformityDetailDialog(self.api_client, payload, self).exec(),
        )

    def open_package_occurrences_screen(self, package: dict | None):
        if not package:
            return
        package_id = package.get("id")
        rows = []
        payloads = []
        for item in self.items:
            linked_package = item.get("resolution_package") or {}
            if linked_package.get("id") != package_id:
                continue
            rows.append([
                (item.get("veiculo") or {}).get("frota") or "-",
                _nc_label(item),
                "Resolvida" if item.get("resolvido") else "Aberta",
                self._format(item.get("created_at")),
                (item.get("usuario") or {}).get("nome") or "-",
                "Sim" if item.get("foto_antes") else "Não",
                "Sim" if item.get("foto_depois") else "Não",
            ])
            payloads.append(item)
        self._open_table_screen(
            title=f"Tela do pacote #{package_id}",
            subtitle="Aqui aparecem os registros que já estão dentro deste pacote de resolução.",
            headers=["Veículo", "Item", "Status", "Abertura", "Motorista", "Foto antes", "Foto depois"],
            rows=rows,
            row_payloads=payloads,
            on_double_click=lambda payload: NonConformityDetailDialog(self.api_client, payload, self).exec(),
        )

    def open_selected_item_screen(self):
        target_item = self._require_single_selected_item("ver todos do mesmo item")
        if not target_item:
            return
        self.open_item_occurrences_screen(str(target_item.get("item_principal") or target_item.get("item_nome") or ""))

    def open_selected_equipment_screen(self):
        target_item = self._require_single_selected_item("ver todos do mesmo equipamento")
        if not target_item:
            return
        vehicle = target_item.get("veiculo") or {}
        self.open_equipment_occurrences_screen(vehicle.get("frota") or vehicle.get("placa") or "")

    def _open_item_screen_from_summary(self, table_item):
        payload = self._row_payload(self.item_summary_table, table_item.row()) or {}
        self.open_item_occurrences_screen(payload.get("item_name"))

    def _open_equipment_screen_from_summary(self, table_item):
        payload = self._row_payload(self.equipment_summary_table, table_item.row()) or {}
        self.open_equipment_occurrences_screen(payload.get("vehicle_label"))

    def _open_package_screen_from_table(self, table_item):
        payload = self._row_payload(self.packages_table, table_item.row()) or {}
        self.open_package_occurrences_screen(payload)



