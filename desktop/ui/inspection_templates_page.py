from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTextEdit, QVBoxLayout,
)

from components import TableSkeletonOverlay, show_notice
from theme import configure_table, make_table_item, style_table_card


class InspectionTemplateDialog(QDialog):
    def __init__(self, families: list[dict], template: dict | None = None, parent=None):
        super().__init__(parent)
        self.template = template or {}
        self.setWindowTitle("Template técnico")
        self.setMinimumSize(680, 620)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Informe um item por linha: Categoria | Item | STATUS/TEXTO/NUMERO | Unidade | Mínimo | Máximo"
        )
        intro.setWordWrap(True)
        intro.setObjectName("SectionCaption")
        form = QFormLayout()
        self.family = QComboBox()
        for family in families:
            self.family.addItem(family["name"], family["id"])
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.instructions = QTextEdit()
        self.instructions.setMaximumHeight(90)
        self.items = QTextEdit()
        self.items.setPlaceholderText("Segurança | Freio de serviço | STATUS\nMotor | Pressão | NUMERO | bar | 5 | 10")
        form.addRow("Família", self.family)
        form.addRow("Código", self.code)
        form.addRow("Nome", self.name)
        form.addRow("Instruções", self.instructions)
        form.addRow("Itens", self.items)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if template:
            index = self.family.findData(template.get("family_id"))
            self.family.setCurrentIndex(max(0, index))
            self.family.setEnabled(False)
            self.code.setText(template.get("code") or "")
            self.code.setEnabled(False)
            self.name.setText(template.get("name") or "")
            self.instructions.setPlainText(template.get("instructions") or "")
            lines = []
            for item in template.get("items") or []:
                lines.append(" | ".join(str(value or "") for value in (
                    item.get("category"), item.get("label"), item.get("response_type"),
                    item.get("unit"), item.get("minimum_value"), item.get("maximum_value"),
                )).rstrip(" |"))
            self.items.setPlainText("\n".join(lines))

    def payload(self) -> dict:
        items = []
        for line in self.items.toPlainText().splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split("|")]
            parts += [""] * (6 - len(parts))
            items.append({
                "category": parts[0] or None, "label": parts[1],
                "response_type": (parts[2] or "STATUS").upper(), "unit": parts[3] or None,
                "minimum_value": parts[4] or None, "maximum_value": parts[5] or None,
                "required": True, "evidence_on_nc": True,
            })
        return {
            "family_id": self.family.currentData(), "code": self.code.text().strip().upper(),
            "name": self.name.text().strip(), "instructions": self.instructions.toPlainText().strip(),
            "items": items,
        }


class InspectionTemplatesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.templates = []
        self.families = []
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Templates de Inspeção Técnica")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Crie modelos por família. Versões publicadas ficam congeladas para preservar o histórico.")
        subtitle.setObjectName("PageSubtitle")
        actions = QHBoxLayout()
        self.add_button = QPushButton("Novo template")
        self.edit_button = QPushButton("Editar rascunho")
        self.publish_button = QPushButton("Publicar")
        self.version_button = QPushButton("Nova versão")
        self.add_button.setProperty("variant", "primary")
        for button in (self.add_button, self.edit_button, self.publish_button, self.version_button):
            actions.addWidget(button)
        actions.addStretch()
        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Família", "Código", "Nome", "Versão", "Situação", "Itens", "Publicada em"])
        configure_table(self.table, stretch_last=False)
        self.skeleton = TableSkeletonOverlay(table_card, rows=7)
        table_layout.addWidget(self.table)
        history_card = QFrame()
        style_table_card(history_card)
        history_layout = QVBoxLayout(history_card)
        history_title = QLabel("Últimas execuções")
        history_title.setObjectName("SectionTitle")
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(
            ["Equipamento", "Template", "Versão", "Resultado", "Executada em", "Executor"]
        )
        configure_table(self.history_table, stretch_last=False)
        history_layout.addWidget(history_title)
        history_layout.addWidget(self.history_table)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(actions)
        layout.addWidget(table_card, 1)
        layout.addWidget(history_card, 1)
        self.add_button.clicked.connect(self.add_template)
        self.edit_button.clicked.connect(self.edit_template)
        self.publish_button.clicked.connect(self.publish_template)
        self.version_button.clicked.connect(self.new_version)

    def set_loading_state(self, loading: bool):
        self.skeleton.show_skeleton("Carregando templates") if loading else self.skeleton.hide_skeleton()

    def refresh(self):
        structure = self.api_client.get_equipment_structure()
        self.families = structure.get("families") or []
        self.templates = self.api_client.get_inspection_templates(include_all=True)
        executions = self.api_client.get_technical_inspection_executions()
        self.table.setRowCount(len(self.templates))
        for row, template in enumerate(self.templates):
            values = [
                (template.get("family") or {}).get("name") or "-", template.get("code"),
                template.get("name"), template.get("version"), template.get("status"),
                len(template.get("items") or []), (template.get("published_at") or "-").replace("T", " ")[:16],
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, make_table_item(str(value)))
        self.history_table.setRowCount(len(executions))
        for row, execution in enumerate(executions):
            values = [
                (execution.get("vehicle") or {}).get("frota") or "-",
                (execution.get("template") or {}).get("name") or "-",
                execution.get("template_version") or "-", execution.get("result") or "-",
                (execution.get("completed_at") or "-").replace("T", " ")[:16],
                (execution.get("user") or {}).get("nome") or "-",
            ]
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, make_table_item(str(value)))

    def selected(self) -> dict | None:
        row = self.table.currentRow()
        return self.templates[row] if 0 <= row < len(self.templates) else None

    def add_template(self):
        dialog = InspectionTemplateDialog(self.families, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.api_client.create_inspection_template(dialog.payload())
                self.refresh(); self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao criar template", str(exc), icon_name="warning")

    def edit_template(self):
        template = self.selected()
        if not template:
            show_notice(self, "Seleção necessária", "Selecione um template.", icon_name="warning"); return
        dialog = InspectionTemplateDialog(self.families, template, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.api_client.update_inspection_template(template["id"], dialog.payload())
                self.refresh(); self.data_changed.emit()
            except Exception as exc:
                show_notice(self, "Falha ao editar template", str(exc), icon_name="warning")

    def publish_template(self):
        template = self.selected()
        if not template:
            show_notice(self, "Seleção necessária", "Selecione um template.", icon_name="warning"); return
        try:
            self.api_client.publish_inspection_template(template["id"])
            self.refresh(); self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao publicar", str(exc), icon_name="warning")

    def new_version(self):
        template = self.selected()
        if not template:
            show_notice(self, "Seleção necessária", "Selecione um template.", icon_name="warning"); return
        try:
            self.api_client.create_inspection_template_version(template["id"])
            self.refresh(); self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao versionar", str(exc), icon_name="warning")
