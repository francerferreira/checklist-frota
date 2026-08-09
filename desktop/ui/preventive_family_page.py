from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import (
    StatCard,
    finalize_saved_file,
    run_export_by_type,
    show_notice,
    start_export_task_with_preset,
)
from services.export_service import (
    export_rows_to_csv,
    export_rows_to_pdf,
    export_rows_to_xlsx,
    make_default_export_path,
)
from theme import configure_table, make_table_item, style_filter_bar, style_table_card


STATUS_LABELS = {
    "NO_PRAZO": "No prazo",
    "ATENCAO": "Atenção",
    "PROXIMA": "Próxima",
    "CRITICA": "Crítica",
    "VENCIDA": "Vencida",
    "LEITURA_DESATUALIZADA": "Leitura desatualizada",
    "SEM_DADOS": "Sem dados",
}
STATUS_COLORS = {
    "NO_PRAZO": ("#DCFCE7", "#166534"),
    "ATENCAO": ("#FEF3C7", "#92400E"),
    "PROXIMA": ("#FFEDD5", "#9A3412"),
    "CRITICA": ("#FEE2E2", "#B91C1C"),
    "VENCIDA": ("#FECACA", "#991B1B"),
    "LEITURA_DESATUALIZADA": ("#E2E8F0", "#475569"),
    "SEM_DADOS": ("#F1F5F9", "#64748B"),
}


class PreventiveScheduleDialog(QDialog):
    """Programa uma execução preventiva sem criar regras diferentes por família."""

    def __init__(self, api_client, family: str, plans: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = family.upper()
        self.plans = list(plans or [])
        self.setWindowTitle(f"Programar preventiva {self.family}")
        self.setMinimumWidth(560)
        form = QGridLayout(self)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        title = QLabel(f"PROGRAMAR PREVENTIVA — {self.family}")
        title.setObjectName("PageTitle")
        form.addWidget(title, 0, 0, 1, 2)
        form.addWidget(QLabel("Plano / equipamento"), 1, 0, 1, 2)
        self.plan_combo = QComboBox()
        for plan in self.plans:
            vehicle = plan.get("vehicle") or {}
            label = f"{vehicle.get('frota') or vehicle.get('placa') or 'Equipamento'} — {plan.get('title') or plan.get('code') or 'Plano'}"
            self.plan_combo.addItem(label, plan)
        form.addWidget(self.plan_combo, 2, 0, 1, 2)
        form.addWidget(QLabel("Data programada"), 3, 0)
        self.scheduled_date = QDateEdit()
        self.scheduled_date.setCalendarPopup(True)
        self.scheduled_date.setDate(date.today())
        form.addWidget(self.scheduled_date, 4, 0)
        form.addWidget(QLabel("Horímetro inicial (opcional)"), 3, 1)
        self.hourmeter_start = QDoubleSpinBox()
        self.hourmeter_start.setRange(0, 10_000_000)
        self.hourmeter_start.setDecimals(2)
        self.hourmeter_start.setSpecialValueText("Não informado")
        form.addWidget(self.hourmeter_start, 4, 1)
        form.addWidget(QLabel("Responsável"), 5, 0)
        self.responsible = QComboBox()
        self.responsible.addItem("Usuário atual", (self.api_client.user or {}).get("id"))
        try:
            for row in self.api_client.get_mechanics() or []:
                self.responsible.addItem(row.get("nome") or row.get("login"), row.get("id"))
        except Exception:
            pass
        form.addWidget(self.responsible, 6, 0)
        form.addWidget(QLabel("Janela / local de execução"), 5, 1)
        self.window = QLineEdit()
        self.window.setPlaceholderText("Ex.: 07:00–11:00 | Pátio 03")
        form.addWidget(self.window, 6, 1)
        form.addWidget(QLabel("Observação"), 7, 0, 1, 2)
        self.observation = QTextEdit()
        self.observation.setPlaceholderText("Orientação para a equipe de execução")
        self.observation.setMaximumHeight(90)
        form.addWidget(self.observation, 8, 0, 1, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Programar preventiva")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons, 9, 0, 1, 2)

    def _save(self):
        plan = self.plan_combo.currentData() or {}
        if not plan.get("id"):
            show_notice(self, "Plano obrigatório", "Selecione um plano preventivo.", icon_name="warning")
            return
        vehicle = plan.get("vehicle") or {}
        observation = self.observation.toPlainText().strip()
        if self.window.text().strip():
            observation = f"Janela/local: {self.window.text().strip()}\n{observation}".strip()
        payload = {
            "preventive_plan_id": plan["id"],
            "vehicle_id": plan.get("vehicle_id") or vehicle.get("id"),
            "status": "PROGRAMADA",
            "scheduled_date": self.scheduled_date.date().toString("yyyy-MM-dd"),
            "hourmeter_start": self.hourmeter_start.value() or None,
            "responsible_user_id": self.responsible.currentData(),
            "observation": observation or None,
        }
        try:
            self.api_client.create_preventive_execution(payload)
        except Exception as exc:
            show_notice(self, "Programação não salva", str(exc), icon_name="warning")
            return
        self.accept()


class PreventivePlanDialog(QDialog):
    """Cria o plano mínimo necessário antes de agendar uma preventiva."""

    def __init__(self, api_client, family: str, rows: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = family.upper()
        self.rows = list(rows or [])
        self.setWindowTitle(f"Criar plano preventivo {self.family}")
        self.setMinimumWidth(560)

        form = QGridLayout(self)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        title = QLabel(f"CRIAR PLANO PREVENTIVO — {self.family}")
        title.setObjectName("PageTitle")
        form.addWidget(title, 0, 0, 1, 2)
        instruction = QLabel(
            "Informe o ciclo de horas. O sistema calcula automaticamente o próximo horímetro e, em seguida, abre o agendamento."
        )
        instruction.setWordWrap(True)
        instruction.setObjectName("PageSubtitle")
        form.addWidget(instruction, 1, 0, 1, 2)

        form.addWidget(QLabel("Equipamento"), 2, 0, 1, 2)
        self.vehicle_combo = QComboBox()
        for row in self.rows:
            vehicle = row.get("vehicle") or {}
            current = row.get("current")
            label = vehicle.get("frota") or vehicle.get("placa") or "Equipamento"
            if current is not None:
                label = f"{label} | horímetro atual: {float(current):.2f} h"
            else:
                label = f"{label} | sem leitura"
            self.vehicle_combo.addItem(label, row)
        self.vehicle_combo.currentIndexChanged.connect(self._update_preview)
        form.addWidget(self.vehicle_combo, 3, 0, 1, 2)

        form.addWidget(QLabel("Ciclo entre preventivas (horas)"), 4, 0)
        self.interval_hourmeter = QLineEdit()
        self.interval_hourmeter.setPlaceholderText("Ex.: 250")
        self.interval_hourmeter.textChanged.connect(self._update_preview)
        form.addWidget(self.interval_hourmeter, 5, 0)
        form.addWidget(QLabel("Prioridade"), 4, 1)
        self.priority = QComboBox()
        for value, label in (("BAIXA", "Baixa"), ("MEDIA", "Média"), ("ALTA", "Alta"), ("CRITICA", "Crítica")):
            self.priority.addItem(label, value)
        self.priority.setCurrentIndex(self.priority.findData("MEDIA"))
        form.addWidget(self.priority, 5, 1)

        self.preview = QLabel("Próximo horímetro: informe o ciclo de horas.")
        self.preview.setObjectName("SectionCaption")
        self.preview.setWordWrap(True)
        form.addWidget(self.preview, 6, 0, 1, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Criar plano e programar")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons, 7, 0, 1, 2)
        self._update_preview()

    def _selected_row(self) -> dict:
        return self.vehicle_combo.currentData() or {}

    def _update_preview(self):
        row = self._selected_row()
        current = row.get("current")
        try:
            interval = float(self.interval_hourmeter.text().strip().replace(",", "."))
        except ValueError:
            interval = 0
        if current is None:
            self.preview.setText("Antes de criar o plano, registre o horímetro atual deste equipamento.")
        elif interval > 0:
            self.preview.setText(f"Próximo horímetro calculado: {float(current) + interval:.2f} h.")
        else:
            self.preview.setText("Próximo horímetro: informe o ciclo de horas.")

    def _save(self):
        row = self._selected_row()
        vehicle = row.get("vehicle") or {}
        current = row.get("current")
        if not vehicle.get("id"):
            show_notice(self, "Equipamento obrigatório", "Selecione o equipamento da preventiva.", icon_name="warning")
            return
        if current is None:
            show_notice(
                self,
                "Horímetro obrigatório",
                "Registre primeiro o horímetro atual deste equipamento. Depois volte para programar a preventiva.",
                icon_name="warning",
            )
            return
        try:
            interval = float(self.interval_hourmeter.text().strip().replace(",", "."))
        except ValueError:
            interval = 0
        if interval <= 0:
            show_notice(self, "Ciclo obrigatório", "Informe um ciclo em horas maior que zero.", icon_name="warning")
            return
        equipment_name = vehicle.get("frota") or vehicle.get("placa") or "Equipamento"
        payload = {
            "vehicle_id": vehicle["id"],
            "title": f"Preventiva por horímetro — {equipment_name}",
            "trigger_type": "HORIMETRO",
            "interval_hourmeter": interval,
            "priority": self.priority.currentData(),
        }
        try:
            self.api_client.create_preventive_plan(payload)
        except Exception as exc:
            show_notice(self, "Plano não salvo", str(exc), icon_name="warning")
            return
        self.accept()


class PreventiveExecutionDialog(QDialog):
    """Atualiza o início, etapas e conclusão de uma execução preventiva."""

    def __init__(self, api_client, execution: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.execution = execution or {}
        self.setWindowTitle("Executar preventiva")
        self.setMinimumSize(680, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        vehicle = self.execution.get("vehicle") or {}
        plan = self.execution.get("preventive_plan") or {}
        title = QLabel(f"EXECUÇÃO — {vehicle.get('frota') or 'Equipamento'}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(plan.get("title") or "Preventiva programada"))
        form = QGridLayout()
        form.addWidget(QLabel("Status"), 0, 0)
        self.status = QComboBox()
        for value, label in (("EM_EXECUCAO", "Em execução"), ("CONCLUIDA", "Concluída"), ("NAO_EXECUTADA", "Não executada"), ("PROGRAMADA", "Programada")):
            self.status.addItem(label, value)
        current_status = str(self.execution.get("status") or "PROGRAMADA").upper()
        index = self.status.findData(current_status)
        if index >= 0:
            self.status.setCurrentIndex(index)
        form.addWidget(self.status, 1, 0)
        form.addWidget(QLabel("Horímetro inicial"), 0, 1)
        self.hourmeter_start = QDoubleSpinBox(); self.hourmeter_start.setRange(0, 10_000_000); self.hourmeter_start.setDecimals(2)
        if self.execution.get("hourmeter_start") is not None: self.hourmeter_start.setValue(float(self.execution["hourmeter_start"]))
        form.addWidget(self.hourmeter_start, 1, 1)
        form.addWidget(QLabel("Horímetro da execução"), 0, 2)
        self.hourmeter_execution = QDoubleSpinBox(); self.hourmeter_execution.setRange(0, 10_000_000); self.hourmeter_execution.setDecimals(2)
        if self.execution.get("hourmeter_execution") is not None: self.hourmeter_execution.setValue(float(self.execution["hourmeter_execution"]))
        form.addWidget(self.hourmeter_execution, 1, 2)
        layout.addLayout(form)
        layout.addWidget(QLabel("Etapas da preventiva"))
        self.stage_table = QTableWidget(0, 3)
        self.stage_table.setHorizontalHeaderLabels(["Etapa", "Situação", "% concluído"])
        configure_table(self.stage_table, stretch_last=False)
        stages = self.execution.get("etapas") or []
        self.stage_widgets: list[tuple[dict, QComboBox, QSpinBox]] = []
        self.stage_table.setRowCount(len(stages))
        for row_index, stage in enumerate(stages):
            self.stage_table.setItem(row_index, 0, make_table_item(str(stage.get("stage_type") or "").replace("_", " ")))
            combo = QComboBox()
            for value, label in (("PENDENTE", "Pendente"), ("EM_EXECUCAO", "Em execução"), ("CONCLUIDA", "Concluída"), ("BLOQUEADA", "Bloqueada"), ("NAO_EXECUTADA", "Não executada")):
                combo.addItem(label, value)
            stage_index = combo.findData(stage.get("status") or "PENDENTE")
            if stage_index >= 0: combo.setCurrentIndex(stage_index)
            percent = QSpinBox(); percent.setRange(0, 100); percent.setSuffix(" %"); percent.setValue(int(stage.get("percent_complete") or 0))
            self.stage_table.setCellWidget(row_index, 1, combo)
            self.stage_table.setCellWidget(row_index, 2, percent)
            self.stage_widgets.append((stage, combo, percent))
        layout.addWidget(self.stage_table, 1)
        layout.addWidget(QLabel("Observação"))
        self.observation = QTextEdit(); self.observation.setMaximumHeight(75); self.observation.setPlainText(self.execution.get("observation") or "")
        layout.addWidget(self.observation)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Salvar execução")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        try:
            for stage, combo, percent in self.stage_widgets:
                self.api_client.update_preventive_stage(
                    int(self.execution["id"]), int(stage["id"]),
                    {"status": combo.currentData(), "percent_complete": percent.value()},
                )
            self.api_client.update_preventive_execution(
                int(self.execution["id"]),
                {
                    "status": self.status.currentData(),
                    "hourmeter_start": self.hourmeter_start.value() or None,
                    "hourmeter_execution": self.hourmeter_execution.value() or None,
                    "observation": self.observation.toPlainText().strip() or None,
                },
            )
        except Exception as exc:
            show_notice(self, "Execução não salva", str(exc), icon_name="warning")
            return
        self.accept()


class PreventiveIntegrationDialog(QDialog):
    """Integra a execucao ao fluxo oficial de OS e reserva de materiais."""

    def __init__(self, api_client, execution: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.execution = execution or {}
        self.materials: list[dict] = []
        self.setWindowTitle("Integrar OS e materiais")
        self.setMinimumSize(720, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        vehicle = self.execution.get("vehicle") or {}
        plan = self.execution.get("preventive_plan") or {}
        title = QLabel(f"INTEGRACAO — {vehicle.get('frota') or 'Equipamento'}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"{plan.get('code') or 'Preventiva'} | {plan.get('title') or '-'}"))

        options = QGridLayout()
        self.create_work_order = QCheckBox("Criar OS automaticamente quando nao houver OS vinculada")
        self.create_work_order.setChecked(True)
        options.addWidget(self.create_work_order, 0, 0, 1, 2)
        options.addWidget(QLabel("OS existente (numero opcional)"), 1, 0)
        self.work_order = QLineEdit()
        self.work_order.setPlaceholderText("Ex.: OS-000123")
        options.addWidget(self.work_order, 2, 0)
        self.close_work_order = QCheckBox("Encerrar OS ao concluir a preventiva")
        self.close_work_order.setEnabled(str(self.execution.get("status") or "").upper() == "CONCLUIDA")
        options.addWidget(self.close_work_order, 2, 1)
        layout.addLayout(options)

        material_header = QHBoxLayout()
        material_header.addWidget(QLabel("Kit de materiais da preventiva"), 1)
        add_button = QPushButton("Adicionar material")
        add_button.clicked.connect(self._add_material_row)
        remove_button = QPushButton("Remover selecionado")
        remove_button.clicked.connect(self._remove_material_row)
        material_header.addWidget(add_button)
        material_header.addWidget(remove_button)
        layout.addLayout(material_header)

        self.material_table = QTableWidget(0, 3)
        self.material_table.setHorizontalHeaderLabels(["Material", "Quantidade", "Observacao"])
        configure_table(self.material_table, stretch_last=True)
        self.material_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.material_table, 1)

        try:
            self.materials = self.api_client.get_materials() or []
        except Exception:
            self.materials = []
        for row in self.execution.get("materiais") or []:
            self._add_material_row(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Salvar integracao")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_material_row(self, existing: dict | None = None):
        row_index = self.material_table.rowCount()
        self.material_table.insertRow(row_index)
        combo = QComboBox()
        combo.addItem("Selecione um material", None)
        for material in self.materials:
            label = f"{material.get('referencia') or '-'} — {material.get('descricao') or 'Material'}"
            combo.addItem(label, material.get("id"))
        selected_id = (existing or {}).get("material_id")
        if selected_id:
            index = combo.findData(selected_id)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.material_table.setCellWidget(row_index, 0, combo)
        quantity = QSpinBox()
        quantity.setRange(1, 9999)
        quantity.setValue(int((existing or {}).get("quantity_planned") or 1))
        self.material_table.setCellWidget(row_index, 1, quantity)
        observation = QLineEdit()
        observation.setPlaceholderText("Opcional")
        observation.setText((existing or {}).get("observation") or "")
        self.material_table.setCellWidget(row_index, 2, observation)

    def _remove_material_row(self):
        row = self.material_table.currentRow()
        if row >= 0:
            self.material_table.removeRow(row)

    def _save(self):
        material_rows = []
        for row in range(self.material_table.rowCount()):
            combo = self.material_table.cellWidget(row, 0)
            quantity = self.material_table.cellWidget(row, 1)
            observation = self.material_table.cellWidget(row, 2)
            material_id = combo.currentData() if combo else None
            if not material_id:
                show_notice(self, "Material incompleto", "Selecione o material em todas as linhas ou remova a linha vazia.", icon_name="warning")
                return
            material_rows.append({
                "material_id": int(material_id),
                "quantity_planned": int(quantity.value()),
                "observation": observation.text().strip() or None,
            })
        payload = {
            "create_work_order": self.create_work_order.isChecked(),
            "close_work_order": self.close_work_order.isChecked(),
            "materials": material_rows,
        }
        if self.work_order.text().strip():
            payload["order_number"] = self.work_order.text().strip()
            payload["create_work_order"] = False
        try:
            self.api_client.integrate_preventive_execution(int(self.execution["id"]), payload)
        except Exception as exc:
            show_notice(self, "Integracao nao salva", str(exc), icon_name="warning")
            return
        self.accept()


class HourmeterEntryDialog(QDialog):
    """Lançamento auditável de horímetro para uma família de equipamentos."""

    def __init__(self, api_client, family: str, rows: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = family.upper()
        self.rows = list(rows or [])
        self.selected_row: dict | None = None
        self.current_reading: float | None = None
        self.photo_path: str | None = None
        self.setWindowTitle(f"Registrar horímetro {self.family}")
        self.setMinimumSize(620, 610)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(f"REGISTRAR HORÍMETRO — {self.family}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Registre uma nova leitura sem apagar o histórico anterior.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Pesquisar equipamento"))
        self.search = QLineEdit()
        self.search.setPlaceholderText(f"Buscar equipamento {self.family}")
        self.search.textChanged.connect(self._render_equipment_list)
        layout.addWidget(self.search)

        layout.addWidget(QLabel("Equipamento"))
        self.equipment_list = QListWidget()
        self.equipment_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.equipment_list.setMinimumHeight(100)
        self.equipment_list.setMaximumHeight(145)
        self.equipment_list.itemSelectionChanged.connect(self._select_equipment)
        layout.addWidget(self.equipment_list)

        self.last_reading_label = QLabel("Último horímetro: Sem leitura")
        self.last_reading_label.setObjectName("SectionCaption")
        layout.addWidget(self.last_reading_label)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Novo horímetro"), 0, 0)
        self.meter_type = QComboBox()
        self.meter_type.addItem("Diesel", "DIESEL")
        self.meter_type.addItem("Elétrico", "ELETRICO")
        self.meter_type.currentIndexChanged.connect(self._load_selected_meter_history)
        layout.addWidget(QLabel("Tipo de horímetro"))
        layout.addWidget(self.meter_type)
        self.reading_spin = QDoubleSpinBox()
        self.reading_spin.setRange(0, 10_000_000)
        self.reading_spin.setDecimals(2)
        self.reading_spin.setSingleStep(1)
        self.reading_spin.valueChanged.connect(self._update_difference)
        form.addWidget(self.reading_spin, 1, 0)
        form.addWidget(QLabel("Diferença da leitura anterior"), 0, 1)
        self.difference_label = QLabel("-")
        form.addWidget(self.difference_label, 1, 1)

        form.addWidget(QLabel("Data e hora da leitura"), 2, 0)
        self.recorded_at = QDateTimeEdit()
        self.recorded_at.setDateTime(QDateTime.currentDateTime())
        self.recorded_at.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.recorded_at.setCalendarPopup(True)
        can_edit_date = str((self.api_client.user or {}).get("tipo") or "").lower() in {"admin", "gestor"}
        self.recorded_at.setEnabled(can_edit_date)
        self.recorded_at.setToolTip("Somente ADMIN e GESTOR podem alterar a data e hora.")
        form.addWidget(self.recorded_at, 3, 0)
        form.addWidget(QLabel("Origem"), 2, 1)
        form.addWidget(QLabel("Desktop"), 3, 1)
        layout.addLayout(form)

        user = self.api_client.user or {}
        layout.addWidget(QLabel(f"Usuário responsável: {user.get('nome') or user.get('login') or 'Usuário autenticado'}"))
        layout.addWidget(QLabel("Observação (opcional)"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Informe uma observação sobre a leitura, se necessário.")
        self.notes.setMaximumHeight(70)
        layout.addWidget(self.notes)

        photo_row = QHBoxLayout()
        self.photo_label = QLabel("Nenhuma foto selecionada")
        photo_button = QPushButton("Anexar foto do painel")
        photo_button.clicked.connect(self._select_photo)
        photo_row.addWidget(photo_button)
        photo_row.addWidget(self.photo_label, 1)
        layout.addLayout(photo_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.Save).setText("Salvar leitura")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)

        self._render_equipment_list()

    def _render_equipment_list(self):
        query = self.search.text().strip().casefold()
        self.equipment_list.clear()
        for row in self.rows:
            vehicle = row.get("vehicle") or {}
            label = str(vehicle.get("frota") or vehicle.get("placa") or vehicle.get("modelo") or "Equipamento")
            local = (vehicle.get("operational_location") or {}).get("full_name") or "Sem local"
            if query and query not in f"{label} {local}".casefold():
                continue
            item = QListWidgetItem(f"{label}  |  {local}")
            item.setData(Qt.UserRole, row)
            self.equipment_list.addItem(item)
        if self.equipment_list.count() and not self.equipment_list.currentItem():
            self.equipment_list.setCurrentRow(0)

    def _select_equipment(self):
        item = self.equipment_list.currentItem()
        self.selected_row = item.data(Qt.UserRole) if item else None
        self._load_selected_meter_history()

    def _load_selected_meter_history(self):
        vehicle = ((self.selected_row or {}).get("vehicle") or {})
        meter_type = self.meter_type.currentData() if hasattr(self, "meter_type") else "DIESEL"
        current = None
        latest_reading = None
        try:
            history = self.api_client.get_equipment_hourmeters(int(vehicle["id"])) if vehicle.get("id") else []
            readings = [row for row in history if str(row.get("meter_type") or "DIESEL").upper() == meter_type]
            if readings:
                readings.sort(key=lambda row: str(row.get("recorded_at") or ""), reverse=True)
                latest_reading = readings[0]
                current = latest_reading.get("reading")
        except Exception:
            current = None
        if current is None and meter_type == "DIESEL":
            current = (self.selected_row or {}).get("current") or ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        self.current_reading = float(current) if current is not None else None
        if self.current_reading is None:
            self.last_reading_label.setText(f"Leitura anterior ({self.meter_type.currentText()}): Sem leitura")
            self.reading_spin.setValue(0)
        else:
            recorded_at = str((latest_reading or {}).get("recorded_at") or "")
            when = ""
            if recorded_at:
                try:
                    when = f" | {datetime.fromisoformat(recorded_at.replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M')}"
                except ValueError:
                    when = f" | {recorded_at[:16].replace('T', ' ')}"
            self.last_reading_label.setText(
                f"Leitura anterior ({self.meter_type.currentText()}): {self.current_reading:.2f} h{when}"
            )
            self.reading_spin.setValue(self.current_reading)
        self._update_difference()
        return

    def _legacy_select_equipment(self):
        item = self.equipment_list.currentItem()
        self.selected_row = item.data(Qt.UserRole) if item else None
        current = (self.selected_row or {}).get("current")
        if current is None:
            current = ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        if current is None:
            self.last_reading_label.setText("Último horímetro: Sem leitura")
            self.reading_spin.setValue(0)
        else:
            current_value = float(current)
            self.last_reading_label.setText(f"Último horímetro: {current_value:.2f} h")
            self.reading_spin.setValue(current_value)
        self._update_difference()

    def _update_difference(self):
        if self.current_reading is not None:
            self.difference_label.setText(f"{self.reading_spin.value() - self.current_reading:.2f} h")
            return
        current = (self.selected_row or {}).get("current")
        if current is None:
            current = ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        self.difference_label.setText(f"{self.reading_spin.value() - float(current):.2f} h" if current is not None else "Primeira leitura")

    def _select_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar foto do painel", "", "Imagens (*.png *.jpg *.jpeg *.webp);;Todos os arquivos (*)")
        if path:
            self.photo_path = path
            self.photo_label.setText(Path(path).name)

    def _save(self):
        if not self.selected_row:
            show_notice(self, "Equipamento obrigatório", f"Selecione um equipamento {self.family}.", icon_name="warning")
            return
        if self.recorded_at.dateTime() > QDateTime.currentDateTime():
            show_notice(self, "Data inválida", "A data da leitura não pode estar no futuro.", icon_name="warning")
            return
        current = self.current_reading
        reading = self.reading_spin.value()
        if current is not None and reading < float(current):
            show_notice(
                self,
                "Leitura menor que a anterior",
                f"A leitura informada é menor que a última leitura registrada ({float(current):.2f} h).",
                icon_name="warning",
            )
            return
        if current is not None and reading - float(current) > 400:
            answer = QMessageBox.question(
                self,
                "Variação elevada",
                f"A diferença informada é de {reading - float(current):.2f} h. Confirma a leitura?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        vehicle = self.selected_row.get("vehicle") or {}
        evidence_path = None
        try:
            if self.photo_path:
                upload = self.api_client.upload_file(
                    self.photo_path,
                    str(vehicle.get("frota") or vehicle.get("placa") or "equipamento"),
                    "horimetro",
                    str((self.api_client.user or {}).get("login") or "desktop"),
                )
                evidence_path = upload.get("path") or upload.get("url")
            self.api_client.record_equipment_hourmeter(
                int(vehicle["id"]),
                {
                    "reading": reading,
                    "meter_type": self.meter_type.currentData(),
                    "recorded_at": self.recorded_at.dateTime().toPython().isoformat(timespec="minutes"),
                    "notes": self.notes.toPlainText().strip() or None,
                    "evidence_path": evidence_path,
                },
            )
        except Exception as exc:
            show_notice(self, "Leitura não salva", str(exc), icon_name="warning")
            return
        self.accept()


def _text(value) -> str:
    return str(value or "").strip()


def _date_text(value) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)[:10]


def _family_match(vehicle: dict, family: str) -> bool:
    family_data = vehicle.get("family") or {}
    expected = family.casefold()
    return any(
        expected == _text(value).casefold()
        for value in (vehicle.get("tipo"), family_data.get("code"), family_data.get("name"))
    )


def _status_for_plan(plan: dict | None) -> str:
    if not plan:
        return "SEM_DADOS"
    due = plan.get("due") or {}
    status = _text(due.get("calculation_status")).upper()
    if status in STATUS_LABELS:
        return status
    return {"VENCENDO": "ATENCAO", "EM_DIA": "NO_PRAZO", "VENCIDA": "VENCIDA"}.get(
        _text(due.get("status")).upper(), "SEM_DADOS"
    )


class PreventiveFamilyPage(QFrame):
    """Tela compartilhada de preventiva por família.

    A Etapa 6 habilita RTG. A mesma classe será reutilizada pela tela LBS na
    Etapa 7, mantendo as fontes de dados filtradas por família.
    """

    data_changed = Signal()
    open_page_requested = Signal(str)

    def __init__(self, api_client, family: str, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = _text(family).upper()
        self.rows: list[dict] = []
        self.visible_rows: list[dict] = []
        self.executions: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(f"PREVENTIVA {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Fluxo simples: registre o horímetro, programe a preventiva e execute o serviço.")
        subtitle.setObjectName("PageSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        self.last_update = QLabel("Última atualização: -")
        self.last_update.setObjectName("SectionCaption")
        header.addWidget(self.last_update, 0, Qt.AlignTop)
        register_button = QPushButton("Registrar horímetro")
        register_button.setProperty("variant", "primary")
        register_button.clicked.connect(self._open_hourmeter_dialog)
        schedule_button = QPushButton("Programar preventiva")
        schedule_button.clicked.connect(self._open_schedule_dialog)
        execute_button = QPushButton("Executar preventiva")
        execute_button.clicked.connect(self._open_execution_dialog)
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        csv_button = QPushButton("CSV")
        csv_button.clicked.connect(lambda: self.export_preventives("csv"))
        xlsx_button = QPushButton("Excel")
        xlsx_button.clicked.connect(lambda: self.export_preventives("xlsx"))
        pdf_button = QPushButton("PDF")
        pdf_button.setProperty("variant", "primary")
        pdf_button.clicked.connect(lambda: self.export_preventives("pdf"))
        header.addWidget(register_button)
        header.addWidget(schedule_button)
        header.addWidget(execute_button)
        header.addWidget(refresh_button)
        header.addWidget(csv_button)
        header.addWidget(xlsx_button)
        header.addWidget(pdf_button)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)
        self.cards = {
            "total": StatCard("Equipamentos", "0", f"Ativos {self.family}", icon_name="equipment"),
            "NO_PRAZO": StatCard("No prazo", "0", "Ciclo acima de 200 h", icon_name="ok"),
            "ATENCAO": StatCard("Atenção", "0", "Entre 101 e 200 h", icon_name="warning"),
            "PROXIMA": StatCard("Próximas", "0", "Entre 21 e 100 h", icon_name="warning"),
            "CRITICA": StatCard("Críticas", "0", "Até 20 h restantes", icon_name="warning"),
            "VENCIDA": StatCard("Vencidas", "0", "Ciclo atingido", icon_name="warning"),
            "SEM_DADOS": StatCard("Sem leitura", "0", "Sem plano ou horímetro", icon_name="dashboard"),
        }
        for index, card in enumerate(self.cards.values()):
            cards.addWidget(card, index // 4, index % 4)
        for column in range(4):
            cards.setColumnStretch(column, 1)
        layout.addLayout(cards)

        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setHorizontalSpacing(10)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for key, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, key)
        self.search = QLineEdit()
        self.search.setPlaceholderText(f"Buscar equipamento, local ou plano {self.family}")
        filter_layout.addWidget(QLabel("Situação"), 0, 0)
        filter_layout.addWidget(self.status_filter, 1, 0)
        filter_layout.addWidget(QLabel("Pesquisa"), 0, 1)
        filter_layout.addWidget(self.search, 1, 1)
        filter_layout.setColumnStretch(0, 1)
        filter_layout.setColumnStretch(1, 2)
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        self.search.textChanged.connect(self._render_rows)
        layout.addWidget(filters)

        content = QHBoxLayout()
        content.setSpacing(12)
        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.addWidget(QLabel("Equipamentos RTG" if self.family == "RTG" else f"Equipamentos {self.family}"))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Equipamento", "Local", "Horímetro", "Última leitura", "Próx. h", "Restantes", "Progresso", "Situação"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(420)
        self.table.itemSelectionChanged.connect(self._show_selected_row)
        table_layout.addWidget(self.table)
        content.addWidget(table_card, 3)

        self.detail_card = QFrame()
        style_table_card(self.detail_card)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Detalhes do equipamento")
        detail_title.setObjectName("SectionTitle")
        detail_layout.addWidget(detail_title)
        self.detail_labels: dict[str, QLabel] = {}
        for key, label in (
            ("equipment", "Equipamento"),
            ("location", "Local"),
            ("model", "Modelo / motor"),
            ("current", "Horímetro atual"),
            ("last", "Última leitura"),
            ("last_preventive", "Última preventiva"),
            ("next", "Próxima preventiva"),
            ("remaining", "Horas restantes"),
            ("status", "Situação"),
        ):
            line = QLabel(f"{label}: -")
            line.setWordWrap(True)
            detail_layout.addWidget(line)
            self.detail_labels[key] = line
        detail_layout.addWidget(QLabel("Execução preventiva selecionada"))
        self.execution_selector = QComboBox()
        self.execution_selector.currentIndexChanged.connect(self._execution_selection_changed)
        detail_layout.addWidget(self.execution_selector)
        self.execution_status_label = QLabel("Status da execução: -")
        self.execution_status_label.setObjectName("SectionCaption")
        detail_layout.addWidget(self.execution_status_label)
        self.integration_button = QPushButton("Integrar OS e materiais", self)
        self.integration_button.setProperty("variant", "primary")
        self.integration_button.clicked.connect(self._open_integration_dialog)
        self.integration_button.setEnabled(False)
        detail_layout.addWidget(self.integration_button)
        self.execution_selector.currentIndexChanged.connect(self._sync_integration_button)
        detail_layout.addStretch(1)
        content.addWidget(self.detail_card, 1)
        layout.addLayout(content, 1)

    def set_loading_state(self, loading: bool):
        self.setEnabled(not loading)

    def _open_hourmeter_dialog(self):
        if not self.rows:
            show_notice(self, "Equipamentos indisponíveis", f"Nenhum equipamento ativo do módulo {self.family} foi carregado.", icon_name="warning")
            return
        dialog = HourmeterEntryDialog(self.api_client, self.family, self.rows, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
            self.data_changed.emit()

    def _plan_rows_for_family(self) -> list[dict]:
        return [row.get("plan") for row in self.rows if row.get("plan")]

    def _open_schedule_dialog(self):
        plans = self._plan_rows_for_family()
        if not plans:
            dialog = PreventivePlanDialog(self.api_client, self.family, self.rows, self)
            if dialog.exec() != QDialog.Accepted:
                return
            self.refresh()
            self.data_changed.emit()
            plans = self._plan_rows_for_family()
            if not plans:
                show_notice(self, "Plano indisponível", "O plano foi salvo, mas não foi possível carregá-lo para agendar. Clique em Atualizar e tente novamente.", icon_name="warning")
                return
        dialog = PreventiveScheduleDialog(self.api_client, self.family, plans, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
            self.data_changed.emit()

    def _open_execution_dialog(self):
        execution = self.execution_selector.currentData()
        if not execution:
            show_notice(self, "Execução indisponível", "Selecione uma execução preventiva programada.", icon_name="warning")
            return
        try:
            if hasattr(self.api_client, "get_preventive_execution"):
                execution = self.api_client.get_preventive_execution(int(execution["id"]))
            dialog = PreventiveExecutionDialog(self.api_client, execution, self)
            if dialog.exec() == QDialog.Accepted:
                self.refresh()
                self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao abrir execução", str(exc), icon_name="warning")

    def _execution_selection_changed(self):
        execution = self.execution_selector.currentData()
        self.execution_status_label.setText(f"Status da execução: {execution.get('status') if execution else '-'}")

    def _open_integration_dialog(self):
        execution = self.execution_selector.currentData()
        if not execution:
            show_notice(self, "Execucao indisponivel", "Selecione uma execucao preventiva para integrar.", icon_name="warning")
            return
        try:
            if hasattr(self.api_client, "get_preventive_execution"):
                execution = self.api_client.get_preventive_execution(int(execution["id"]))
            dialog = PreventiveIntegrationDialog(self.api_client, execution, self)
            if dialog.exec() == QDialog.Accepted:
                self.refresh()
                self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao integrar preventiva", str(exc), icon_name="warning")

    def _sync_integration_button(self):
        self.integration_button.setEnabled(bool(self.execution_selector.currentData()))

    def refresh(self):
        try:
            vehicles = self.api_client.get_equipment(tipo=self.family.lower(), ativos=True) or []
            plans = self.api_client.get_preventive_plans() or []
            self.executions = []
            if hasattr(self.api_client, "get_preventive_executions"):
                self.executions = self.api_client.get_preventive_executions() or []
            plans_by_vehicle: dict[int, dict] = {}
            for plan in plans:
                if _text(plan.get("status")).upper() != "ATIVO":
                    continue
                vehicle_id = plan.get("vehicle_id")
                if vehicle_id is not None and vehicle_id not in plans_by_vehicle:
                    plans_by_vehicle[vehicle_id] = plan
            self.rows = []
            for vehicle in vehicles:
                if not vehicle.get("ativo", True) or not _family_match(vehicle, self.family):
                    continue
                plan = plans_by_vehicle.get(vehicle.get("id"))
                due = (plan or {}).get("due") or {}
                state = vehicle.get("operational_state") or {}
                status = _status_for_plan(plan)
                self.rows.append({
                    "vehicle": vehicle,
                    "plan": plan,
                    "state": state,
                    "status": status,
                    "current": state.get("latest_hourmeter"),
                    "last_reading_at": state.get("latest_hourmeter_at"),
                    "next_due": due.get("next_due_hourmeter") or (plan or {}).get("next_due_hourmeter"),
                    "remaining": due.get("hours_remaining"),
                    "percent": due.get("percent_used"),
                })
            self.last_update.setText(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            self._render_executions()
            self._render_rows()
        except Exception as exc:
            show_notice(self, f"Falha ao carregar preventiva {self.family}", str(exc), icon_name="warning")

    def _matches(self, row: dict) -> bool:
        selected = _text(self.status_filter.currentData()).upper()
        if selected and row["status"] != selected:
            return False
        query = self.search.text().strip().casefold()
        if not query:
            return True
        vehicle = row.get("vehicle") or {}
        plan = row.get("plan") or {}
        location = vehicle.get("operational_location") or {}
        searchable = " ".join(
            _text(value)
            for value in (
                vehicle.get("frota"), vehicle.get("modelo"), vehicle.get("local"),
                location.get("name"), location.get("full_name"), plan.get("title"),
            )
        ).casefold()
        return query in searchable

    def _render_rows(self):
        self.visible_rows = [row for row in self.rows if self._matches(row)]
        counts = {key: 0 for key in self.cards if key != "total"}
        for row in self.visible_rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        self.cards["total"].set_content("Equipamentos", str(len(self.visible_rows)), f"Ativos {self.family}")
        for key in counts:
            self.cards[key].set_content(STATUS_LABELS.get(key, key), str(counts[key]), self.cards[key].subtitle_label.text())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.visible_rows))
        for index, row in enumerate(self.visible_rows):
            vehicle = row["vehicle"]
            location = vehicle.get("operational_location") or {}
            local = location.get("full_name") or location.get("name") or vehicle.get("local") or "Sem local"
            current = row.get("current")
            next_due = row.get("next_due")
            remaining = row.get("remaining")
            percent = row.get("percent")
            progress = f"{float(percent):.0f}%" if percent is not None else "-"
            values = [
                STATUS_LABELS.get(row["status"], row["status"]),
                vehicle.get("frota") or vehicle.get("placa") or "-",
                local,
                f"{float(current):.2f} h" if current is not None else "-",
                _date_text(row.get("last_reading_at")),
                f"{float(next_due):.2f} h" if next_due is not None else "-",
                f"{float(remaining):.0f} h" if remaining is not None else "-",
                progress,
                STATUS_LABELS.get(row["status"], row["status"]),
            ]
            for column, value in enumerate(values):
                item = make_table_item(value, payload=row if column == 1 else None)
                if column in (0, 8):
                    background, foreground = STATUS_COLORS.get(row["status"], STATUS_COLORS["SEM_DADOS"])
                    item.setBackground(QColor(background))
                    item.setForeground(QColor(foreground))
                self.table.setItem(index, column, item)
        self.table.resizeColumnsToContents()
        if self.visible_rows and self.table.currentRow() < 0:
            self.table.selectRow(0)
        elif not self.visible_rows:
            self._clear_details()

    def _render_executions(self):
        family_vehicle_ids = {
            int((row.get("vehicle") or {}).get("id"))
            for row in self.rows
            if (row.get("vehicle") or {}).get("id") is not None
        }
        self.execution_selector.blockSignals(True)
        self.execution_selector.clear()
        for execution in self.executions:
            if execution.get("vehicle_id") not in family_vehicle_ids:
                continue
            vehicle = execution.get("vehicle") or {}
            label = f"{vehicle.get('frota') or 'Equipamento'} | {execution.get('status') or '-'} | {_date_text(execution.get('scheduled_date'))}"
            self.execution_selector.addItem(label, execution)
        self.execution_selector.blockSignals(False)
        self._execution_selection_changed()

    def _show_selected_row(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.visible_rows):
            self._clear_details()
            return
        row = self.visible_rows[index]
        vehicle = row["vehicle"]
        plan = row.get("plan") or {}
        detail = {
            "equipment": vehicle.get("frota") or "-",
            "location": (vehicle.get("operational_location") or {}).get("full_name") or vehicle.get("local") or "Sem local",
            "model": " / ".join(value for value in (vehicle.get("modelo"), vehicle.get("configuracao")) if value) or "-",
            "current": f"{float(row['current']):.2f} h" if row.get("current") is not None else "Sem leitura",
            "last": _date_text(row.get("last_reading_at")),
            "last_preventive": plan.get("title") or "Sem plano preventivo",
            "next": f"{float(row['next_due']):.2f} h" if row.get("next_due") is not None else "Não calculada",
            "remaining": f"{float(row['remaining']):.0f} h" if row.get("remaining") is not None else "-",
            "status": STATUS_LABELS.get(row["status"], row["status"]),
        }
        for key, value in detail.items():
            label = self.detail_labels[key]
            caption = label.text().split(":", 1)[0]
            label.setText(f"{caption}: {value}")
        vehicle_id = vehicle.get("id")
        for option in range(self.execution_selector.count()):
            execution = self.execution_selector.itemData(option) or {}
            if execution.get("vehicle_id") == vehicle_id:
                self.execution_selector.setCurrentIndex(option)
                break

    def _clear_details(self):
        for label in self.detail_labels.values():
            caption = label.text().split(":", 1)[0]
            label.setText(f"{caption}: -")

    def _export_rows(self) -> tuple[list[tuple[str, str]], list[dict]]:
        """Converte a visão filtrada atual para o formato comum de exportação."""
        columns = [
            ("Módulo", "familia"),
            ("Equipamento", "equipamento"),
            ("Local", "local"),
            ("Horímetro", "horimetro"),
            ("Última leitura", "ultima_leitura"),
            ("Próxima preventiva", "proxima_preventiva"),
            ("Horas restantes", "horas_restantes"),
            ("Progresso", "progresso"),
            ("Situação", "situacao"),
        ]
        rows = []
        for row in self.visible_rows:
            vehicle = row.get("vehicle") or {}
            location = vehicle.get("operational_location") or {}
            current = row.get("current")
            next_due = row.get("next_due")
            remaining = row.get("remaining")
            percent = row.get("percent")
            rows.append(
                {
                    "familia": self.family,
                    "equipamento": vehicle.get("frota") or vehicle.get("placa") or "-",
                    "local": location.get("full_name") or location.get("name") or vehicle.get("local") or "Sem local",
                    "horimetro": f"{float(current):.2f} h" if current is not None else "-",
                    "ultima_leitura": _date_text(row.get("last_reading_at")),
                    "proxima_preventiva": f"{float(next_due):.2f} h" if next_due is not None else "-",
                    "horas_restantes": f"{float(remaining):.0f} h" if remaining is not None else "-",
                    "progresso": f"{float(percent):.0f}%" if percent is not None else "-",
                    "situacao": STATUS_LABELS.get(row.get("status"), row.get("status") or "-"),
                }
            )
        return columns, rows

    def export_preventives(self, file_type: str):
        """Exporta somente os equipamentos que passaram pelos filtros atuais."""
        columns, rows = self._export_rows()
        if not rows:
            show_notice(self, "Sem dados", "Nenhum equipamento da visão atual pode ser exportado.", icon_name="warning")
            return
        prefix = f"preventivas_{self.family.lower()}"
        default_path = make_default_export_path(prefix, file_type)
        filters = {"csv": "CSV (*.csv)", "xlsx": "Excel (*.xlsx)", "pdf": "PDF (*.pdf)"}
        if file_type == "pdf":
            filename = run_export_by_type(
                self,
                file_type="pdf",
                dialog_title=f"Exportar preventivas {self.family}",
                default_path=default_path,
                filters=filters,
                handlers={"pdf": lambda target: self._start_preventive_pdf_export(target, columns, rows)},
            )
            return filename
        run_export_by_type(
            self,
            file_type=file_type,
            dialog_title=f"Exportar preventivas {self.family}",
            default_path=default_path,
            filters=filters,
            handlers={
                "csv": lambda target: self._finish_preventive_export(export_rows_to_csv(columns, rows, target)),
                "xlsx": lambda target: self._finish_preventive_export(
                    export_rows_to_xlsx(f"Preventivas {self.family}", columns, rows, target)
                ),
            },
        )

    def _finish_preventive_export(self, path):
        finalize_saved_file(self, path, success_title="Exportação concluída")

    def _start_preventive_pdf_export(self, filename: str, columns: list[tuple[str, str]], rows: list[dict]):
        def task(progress):
            progress(25, "Preparando relatório de preventivas")
            result = export_rows_to_pdf(
                f"Preventivas {self.family}",
                "Visão filtrada de planos, horímetros e vencimentos",
                columns,
                rows,
                filename,
                generated_by=(self.api_client.user or {}).get("nome", ""),
                period_label=f"Módulo {self.family} | {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            )
            progress(100, "Relatório pronto")
            return result

        start_export_task_with_preset(
            self,
            "preventive_pdf",
            task,
            success_title="PDF de preventivas gerado",
            failure_title="Falha ao exportar preventivas",
        )


class PreventiveRTGPage(PreventiveFamilyPage):
    def __init__(self, api_client, parent=None):
        super().__init__(api_client, "RTG", parent)


class PreventiveLBSPage(PreventiveFamilyPage):
    def __init__(self, api_client, parent=None):
        super().__init__(api_client, "LBS", parent)
