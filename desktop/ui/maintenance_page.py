from __future__ import annotations

from collections import defaultdict
from math import ceil

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from components import StatCard, TableSkeletonOverlay, choose_pdf_save_path, show_notice, start_export_task_with_preset
from services.export_service import make_default_export_path
from theme import (
    build_dialog_layout,
    configure_dialog_window,
    configure_table,
    make_table_item,
    style_card,
    style_filter_bar,
    style_table_card,
)


SOURCE_LABELS = {
    "CHECKLIST_NC": "Não conformidade legada",
    "PACOTE_RESOLUCAO": "Pacote de resolução",
    "ATIVIDADE": "Inspeção legada",
    "PREVENTIVA": "Preventiva",
}

SCHEDULE_STATUS_LABELS = {
    "ABERTA": "Aberta",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "PROGRAMADA": "Programada",
    "EM_EXECUCAO": "Em execução",
    "CONCLUIDA": "Concluída",
    "CANCELADA": "Cancelada",
}

ITEM_STATUS_LABELS = {
    "PENDENTE": "Pendente",
    "PROGRAMADO": "Programado",
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "INSTALADO": "Concluído",
    "NAO_EXECUTADO": "Não executado",
    "REPROGRAMADO": "Reprogramado",
    "CANCELADO": "Cancelado",
}

MATERIAL_STATUS_LABELS = {
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "EM_COMPRAS": "Em compras",
    "DISPONIVEL_EM_ESTOQUE": "Disponível em estoque",
    "RESERVADO": "Reservado",
    "UTILIZADO": "Utilizado",
}

REPORT_TYPE_LABELS = {
    "mensal": "Manutenção mensal",
    "preventiva": "Preventiva",
    "mecanico": "Por mecânico",
    "veiculo": "Por veículo",
    "material": "Materiais utilizados",
    "pendencias": "Pendências",
}

WEEKDAY_HEADERS = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SAB"]


def _schedule_source_code(schedule: dict) -> str:
    return str(schedule.get("source_origin_type") or schedule.get("source_type") or "").upper()


class MaintenanceScheduleCreateDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.packages: list[dict] = []
        self.vehicles: list[dict] = []
        self.mechanics: list[dict] = []
        self.result_payload: dict | None = None
        self.suggested_mechanic_user_id: int | None = None
        self.suggested_start_date_iso: str | None = None

        self.setWindowTitle("Nova programação de manutenção")
        configure_dialog_window(self, width=1060, height=760, min_width=900, min_height=640)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=1120)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(4)
        title = QLabel("Criar programação de manutenção")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            "Fluxo atual: resoluções corretivas entram por Pacotes de Resolução; preventiva continua por veículos, com distribuição diária."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Pacotes de resolução", "PACOTE_RESOLUCAO")
        self.source_combo.addItem("Preventiva por veículos", "PREVENTIVA")
        self.source_combo.currentIndexChanged.connect(self._render_source_rows)

        self.title_input = QLineEdit("Programação de manutenção")
        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDate(QDate.currentDate())
        self.start_date_input.setDisplayFormat("dd/MM/yyyy")
        self.start_date_input.dateChanged.connect(self._apply_schedule_suggestion)

        self.daily_capacity_input = QSpinBox()
        self.daily_capacity_input.setMinimum(1)
        self.daily_capacity_input.setMaximum(999)
        self.daily_capacity_input.setValue(1)
        self.daily_capacity_input.valueChanged.connect(self._update_selection_summary)

        self.observation_input = QTextEdit()
        self.observation_input.setPlaceholderText("Contexto da programação, prioridade e observações.")

        self.selection_badge = QLabel("0 selecionados | estimativa 0 dia(s)")
        self.selection_badge.setObjectName("TopBarPill")
        self.suggestion_badge = QLabel("Sugestão de responsável: selecione registros para o sistema analisar o histórico.")
        self.suggestion_badge.setObjectName("TopBarPill")
        self.mechanic_load_badge = QLabel("Carga do mecânico: selecione um responsável para ver a fila atual.")
        self.mechanic_load_badge.setObjectName("TopBarPill")
        self.schedule_suggestion_badge = QLabel("Sugestão de agenda: selecione registros para o sistema encontrar a melhor janela.")
        self.schedule_suggestion_badge.setObjectName("TopBarPill")

        self.mechanic_combo = QComboBox()
        self.mechanic_combo.setMinimumHeight(34)
        self.mechanic_combo.currentIndexChanged.connect(self._apply_schedule_suggestion)
        self.apply_suggested_date_button = QPushButton("Usar data sugerida")
        self.apply_suggested_date_button.setMinimumHeight(34)
        self.apply_suggested_date_button.clicked.connect(self._apply_suggested_start_date)
        self.apply_suggested_date_button.setEnabled(False)

        form.addWidget(QLabel("Origem"), 0, 0)
        form.addWidget(self.source_combo, 1, 0)
        form.addWidget(QLabel("Título"), 0, 1)
        form.addWidget(self.title_input, 1, 1)
        form.addWidget(QLabel("Data inicial"), 0, 2)
        form.addWidget(self.start_date_input, 1, 2)
        form.addWidget(QLabel("Capacidade diária"), 0, 3)
        form.addWidget(self.daily_capacity_input, 1, 3)
        form.addWidget(QLabel("Responsável sugerido"), 2, 0)
        form.addWidget(self.mechanic_combo, 3, 0, 1, 2)
        form.addWidget(self.suggestion_badge, 3, 2, 1, 2)
        form.addWidget(self.mechanic_load_badge, 4, 0, 1, 4)
        form.addWidget(self.schedule_suggestion_badge, 5, 0, 1, 3)
        form.addWidget(self.apply_suggested_date_button, 5, 3)
        form.addWidget(QLabel("Observação"), 6, 0, 1, 4)
        form.addWidget(self.observation_input, 7, 0, 1, 4)
        form.addWidget(self.selection_badge, 8, 0, 1, 4)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        actions = QHBoxLayout()
        self.source_title = QLabel("Base de seleção")
        self.source_title.setObjectName("SectionTitle")
        select_all_button = QPushButton("Selecionar todos")
        select_all_button.clicked.connect(self._select_all_rows)
        clear_button = QPushButton("Limpar seleção")
        clear_button.clicked.connect(self._clear_selection)
        actions.addWidget(self.source_title)
        actions.addStretch()
        actions.addWidget(select_all_button)
        actions.addWidget(clear_button)

        self.source_table = QTableWidget(0, 5)
        configure_table(self.source_table, stretch_last=True)
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_table.itemSelectionChanged.connect(self._update_selection_summary)
        self.source_table.setMinimumHeight(300)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()
        close_button = QPushButton("Cancelar")
        close_button.clicked.connect(self.reject)
        create_button = QPushButton("Criar programação")
        create_button.setProperty("variant", "primary")
        create_button.clicked.connect(self._submit)
        footer_layout.addWidget(close_button)
        footer_layout.addWidget(create_button)

        table_layout.addLayout(actions)
        table_layout.addWidget(self.source_table)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(table_card, 1)
        layout.addWidget(footer)

        self._load_sources()
        self._populate_mechanic_combo()
        self._render_source_rows()

    def _load_sources(self):
        self.packages = self.api_client.get_resolution_packages(status="ABERTO") or []
        self.vehicles = self.api_client.get_equipment(ativos=True) or []
        self.mechanics = self.api_client.get_mechanics() or []

    def _populate_mechanic_combo(self):
        current_value = self.mechanic_combo.currentData()
        self.mechanic_combo.blockSignals(True)
        try:
            self.mechanic_combo.clear()
            self.mechanic_combo.addItem("Sem responsável fixo", None)
            for mechanic in sorted(self.mechanics, key=lambda row: (row.get("nome") or row.get("login") or "").upper()):
                name = mechanic.get("nome") or mechanic.get("login") or f"Mecânico {mechanic.get('id')}"
                self.mechanic_combo.addItem(name, int(mechanic.get("id")))
            index = self.mechanic_combo.findData(current_value)
            self.mechanic_combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.mechanic_combo.blockSignals(False)

    def _render_source_rows(self):
        source_type = self.source_combo.currentData()
        if source_type == "PACOTE_RESOLUCAO":
            self.source_title.setText("Pacotes prontos para entrar em manutenção")
            self.source_table.setColumnCount(6)
            self.source_table.setHorizontalHeaderLabels(["ID", "Pacote", "Agrupamento", "Referência", "Score", "Abertas"])
            rows = self.packages
            self.source_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                resumo = row.get("resumo") or {}
                values = [
                    row.get("id"),
                    row.get("title") or "-",
                    "Por item" if row.get("grouping_mode") == "POR_ITEM" else "Por equipamento",
                    row.get("reference_label") or "-",
                    row.get("priority_score") or 0,
                    resumo.get("abertas", 0),
                ]
                for column, value in enumerate(values):
                    payload = row if column == 0 else None
                    self.source_table.setItem(row_index, column, make_table_item(value, payload=payload))
        else:
            self.source_title.setText("Veiculos para preventiva")
            self.source_table.setColumnCount(5)
            self.source_table.setHorizontalHeaderLabels(["ID", "Frota", "Placa", "Modelo", "Tipo"])
            rows = self.vehicles
            self.source_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [
                    row.get("id"),
                    row.get("frota") or "-",
                    row.get("placa") or "-",
                    row.get("modelo") or "-",
                    row.get("tipo") or "-",
                ]
                for column, value in enumerate(values):
                    payload = row if column == 0 else None
                    self.source_table.setItem(row_index, column, make_table_item(value, payload=payload))

        self._clear_selection()

    def _selected_payloads(self) -> list[dict]:
        model = self.source_table.selectionModel()
        if not model:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        selected: list[dict] = []
        for row in rows:
            cell = self.source_table.item(row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                selected.append(payload)
        return selected

    def _select_all_rows(self):
        self.source_table.selectAll()
        self._update_selection_summary()

    def _clear_selection(self):
        self.source_table.clearSelection()
        self._update_selection_summary()

    def _update_selection_summary(self):
        total = len(self._selected_payloads())
        capacity = max(1, int(self.daily_capacity_input.value()))
        days = ceil(total / capacity) if total else 0
        self.selection_badge.setText(f"{total} selecionados | estimativa {days} dia(s)")
        self._apply_mechanic_suggestion()
        self._apply_schedule_suggestion()

    def _suggestion_payload(self) -> dict:
        source_type = self.source_combo.currentData()
        selected = self._selected_payloads()
        selected_total = 0
        if source_type == "PACOTE_RESOLUCAO":
            for row in selected:
                resumo = row.get("resumo") or {}
                selected_total += int(resumo.get("abertas") or resumo.get("total") or 0)
        else:
            selected_total = len(selected)
        payload: dict = {
            "source_type": source_type,
            "item_name": (self.title_input.text() or "").strip(),
            "start_date": self.start_date_input.date().toString("yyyy-MM-dd"),
            "daily_capacity": int(self.daily_capacity_input.value()),
            "assigned_mechanic_user_id": self.mechanic_combo.currentData(),
            "selected_total": selected_total,
        }
        if source_type == "PACOTE_RESOLUCAO":
            payload["package_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
        else:
            payload["vehicle_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
        return payload

    def _apply_mechanic_suggestion(self):
        selected = self._selected_payloads()
        if not selected:
            self.suggested_mechanic_user_id = None
            self.suggestion_badge.setText("Sugestão de responsável: selecione registros para o sistema analisar o histórico.")
            return
        try:
            suggestion = self.api_client.get_maintenance_mechanic_suggestion(self._suggestion_payload())
        except Exception:
            suggestion = None
        if not suggestion:
            self.suggested_mechanic_user_id = None
            self.suggestion_badge.setText("Sugestão de responsável: sem histórico suficiente. Você ainda pode definir manualmente.")
            return
        user = suggestion.get("user") or {}
        self.suggested_mechanic_user_id = suggestion.get("user_id")
        index = self.mechanic_combo.findData(self.suggested_mechanic_user_id)
        if index >= 0:
            self.mechanic_combo.setCurrentIndex(index)
        mechanic_name = user.get("nome") or user.get("login") or f"Mecânico {self.suggested_mechanic_user_id}"
        reason = suggestion.get("reason") or "Histórico parecido encontrado"
        self.suggestion_badge.setText(f"Sugestão de responsável: {mechanic_name} | {reason}")

    def _apply_schedule_suggestion(self):
        selected = self._selected_payloads()
        if not selected:
            self.suggested_start_date_iso = None
            self.schedule_suggestion_badge.setText("Sugestão de agenda: selecione registros para o sistema encontrar a melhor janela.")
            self.mechanic_load_badge.setText("Carga do mecânico: selecione um responsável para ver a fila atual.")
            self.apply_suggested_date_button.setEnabled(False)
            return
        try:
            suggestion = self.api_client.get_maintenance_schedule_suggestion(self._suggestion_payload())
        except Exception:
            suggestion = None
        if not suggestion:
            self.suggested_start_date_iso = None
            self.schedule_suggestion_badge.setText("Sugestão de agenda: não foi possível calcular a janela agora.")
            self.mechanic_load_badge.setText("Carga do mecânico: histórico indisponível no momento.")
            self.apply_suggested_date_button.setEnabled(False)
            return

        self.suggested_start_date_iso = suggestion.get("suggested_start_date")
        suggested_end_date = suggestion.get("suggested_end_date")
        total_items = int(suggestion.get("total_items") or 0)
        reason = suggestion.get("reason") or "Janela calculada pela capacidade da agenda."
        self.schedule_suggestion_badge.setText(
            f"Sugestão de agenda: {self._format_date(self.suggested_start_date_iso)} até {self._format_date(suggested_end_date)} | "
            f"{total_items} serviço(s) | {reason}"
        )
        self.apply_suggested_date_button.setEnabled(bool(self.suggested_start_date_iso))

        mechanic_load = suggestion.get("mechanic_load") or {}
        if not mechanic_load:
            self.mechanic_load_badge.setText("Carga do mecânico: sem responsável fixo selecionado.")
            return
        user = mechanic_load.get("user") or {}
        mechanic_name = user.get("nome") or user.get("login") or f"Mecânico {mechanic_load.get('user_id')}"
        self.mechanic_load_badge.setText(
            f"Carga do mecânico: {mechanic_name} | "
            f"{int(mechanic_load.get('open_work_orders') or 0)} OS abertas | "
            f"{int(mechanic_load.get('overdue_work_orders') or 0)} atrasadas | "
            f"{int(mechanic_load.get('scheduled_in_window') or 0)} já na janela"
        )

    def _apply_suggested_start_date(self):
        if not self.suggested_start_date_iso:
            return
        target = QDate.fromString(str(self.suggested_start_date_iso), "yyyy-MM-dd")
        if target.isValid():
            self.start_date_input.setDate(target)

    def _submit(self):
        source_type = self.source_combo.currentData()
        selected = self._selected_payloads()
        if not selected:
            show_notice(self, "Seleção obrigatória", "Selecione pelo menos um registro para criar a programação.", icon_name="warning")
            return

        title = (self.title_input.text() or "").strip() or "Programação de manutenção"
        start_date = self.start_date_input.date().toString("yyyy-MM-dd")
        daily_capacity = int(self.daily_capacity_input.value())
        observation = (self.observation_input.toPlainText() or "").strip()

        payload: dict = {
            "source_type": source_type,
            "title": title,
            "start_date": start_date,
            "daily_capacity": daily_capacity,
            "observation": observation,
            "assigned_mechanic_user_id": self.mechanic_combo.currentData(),
        }
        if source_type == "PACOTE_RESOLUCAO":
            payload["package_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
            payload["item_name"] = "Pacotes de resolução selecionados"
        else:
            payload["vehicle_ids"] = sorted({int(row.get("id")) for row in selected if row.get("id")})
            payload["item_name"] = "Preventiva de frota"

        self.result_payload = payload
        self.accept()


class QuickMaintenanceDialog(QDialog):
    """Entrada curta para programar uma manutenção de RTG ou LBS."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.equipment: list[dict] = []
        self.mechanics: list[dict] = []

        self.setWindowTitle("Agendar manutenção")
        configure_dialog_window(self, width=620, height=520, min_width=560, min_height=460)
        style_card(self)
        layout = build_dialog_layout(self, max_content_width=700)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("Agendar manutenção")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Escolha o equipamento e a data. O sistema cria a programação e a OS automaticamente.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("HeaderCard")
        form_card.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(form_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.equipment_combo = QComboBox()
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.title_input = QLineEdit("Manutenção preventiva")
        self.mechanic_combo = QComboBox()
        self.mechanic_combo.addItem("Sem responsável definido", None)
        self.observation_input = QTextEdit()
        self.observation_input.setPlaceholderText("Observação opcional para a programação")

        form.addWidget(QLabel("Equipamento RTG/LBS"), 0, 0)
        form.addWidget(self.equipment_combo, 1, 0, 1, 2)
        form.addWidget(QLabel("Data"), 0, 2)
        form.addWidget(self.date_input, 1, 2)
        form.addWidget(QLabel("Serviço"), 2, 0)
        form.addWidget(self.title_input, 3, 0, 1, 3)
        form.addWidget(QLabel("Responsável"), 4, 0)
        form.addWidget(self.mechanic_combo, 5, 0, 1, 3)
        form.addWidget(QLabel("Observação"), 6, 0, 1, 3)
        form.addWidget(self.observation_input, 7, 0, 1, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Agendar manutenção")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(buttons)

        self._load_options()

    def _load_options(self):
        try:
            self.equipment = [
                row for row in (self.api_client.get_equipment(ativos=True) or [])
                if str(row.get("tipo") or "").lower() in {"rtg", "lbs"}
            ]
            self.mechanics = self.api_client.get_mechanics() or []
        except Exception as exc:
            show_notice(self, "Falha ao carregar equipamentos", str(exc), icon_name="warning")
            self.equipment = []
            self.mechanics = []

        ordered_equipment = sorted(self.equipment, key=lambda item: str(item.get("frota") or "").upper())
        for row in ordered_equipment:
            label = row.get("frota") or row.get("modelo") or f"Equipamento {row.get('id')}"
            self.equipment_combo.addItem(label, row)

        preferred = next(
            (index for index, row in enumerate(ordered_equipment) if str(row.get("frota") or "").upper() == "RTG 03"),
            -1,
        )
        if preferred >= 0:
            self.equipment_combo.setCurrentIndex(preferred)

        for row in sorted(self.mechanics, key=lambda item: str(item.get("nome") or item.get("login") or "").upper()):
            self.mechanic_combo.addItem(row.get("nome") or row.get("login") or "Responsável", row.get("id"))

    def _submit(self):
        equipment = self.equipment_combo.currentData() or {}
        vehicle_id = equipment.get("id")
        if not vehicle_id:
            show_notice(self, "Equipamento obrigatório", "Selecione um RTG ou LBS.", icon_name="warning")
            return

        payload = {
            "source_type": "PREVENTIVA",
            "title": (self.title_input.text() or "").strip() or "Manutenção preventiva",
            "item_name": "Manutenção preventiva",
            "start_date": self.date_input.date().toString("yyyy-MM-dd"),
            "daily_capacity": 1,
            "vehicle_ids": [int(vehicle_id)],
            "assigned_mechanic_user_id": self.mechanic_combo.currentData(),
            "observation": (self.observation_input.toPlainText() or "").strip(),
        }
        try:
            self.api_client.create_maintenance_schedule(payload)
        except Exception as exc:
            show_notice(self, "Falha ao agendar manutenção", str(exc), icon_name="warning")
            return
        self.accept()


class MaintenancePage(QFrame):
    data_changed = Signal()
    open_page_requested = Signal(str)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.overview: dict = {"resumo": {}, "cronograma": {"days": []}, "programacoes": []}
        self.filtered_schedules: list[dict] = []
        self.selected_schedule_id: int | None = None
        self.selected_calendar_day_iso: str | None = None
        self.calendar_day_index: dict[str, dict] = {}
        self.material_catalog: list[dict] = []
        self.mechanics: list[dict] = []
        self.report_vehicles: list[dict] = []
        self.setObjectName("ContentSurface")

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        scroll = QScrollArea()
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content = QWidget()
        content.setAttribute(Qt.WA_StyledBackground, False)
        scroll.setWidget(content)
        shell.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header_frame = QFrame()
        style_filter_bar(header_frame)
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(12, 10, 12, 10)
        header.setSpacing(10)
        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)
        title = QLabel("Home da manutenção")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Veja os indicadores da oficina, use os filtros do período, acompanhe o cronograma e abra a tela certa para trabalhar."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)
        context_hint = QLabel(
            "Fluxo oficial: Central de Resolução -> Pacote de Resolução -> Manutenção -> OS -> Relatório"
        )
        context_hint.setObjectName("ContextHint")
        text_wrap.addWidget(context_hint)

        self.quick_schedule_button = QPushButton("Agendar equipamento")
        self.quick_schedule_button.setProperty("variant", "primary")
        self.quick_schedule_button.setMinimumHeight(34)
        self.quick_schedule_button.clicked.connect(self.create_quick_schedule)

        self.new_schedule_button = QPushButton("Programação avançada")
        self.new_schedule_button.setMinimumHeight(34)
        self.new_schedule_button.clicked.connect(self.create_schedule)

        self.open_os_button = QPushButton("Ver OS")
        self.open_os_button.setMinimumHeight(34)
        self.open_os_button.clicked.connect(lambda: self._open_maintenance_screen("OS"))

        self.open_pcm_button = QPushButton("Abrir PCM")
        self.open_pcm_button.setMinimumHeight(34)
        self.open_pcm_button.clicked.connect(lambda: self.open_page_requested.emit("pcm"))

        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "success")
        refresh_button.setMinimumHeight(34)
        refresh_button.clicked.connect(self.refresh)

        header.addLayout(text_wrap, 1)
        header.addWidget(self.quick_schedule_button)
        header.addWidget(self.new_schedule_button)
        header.addWidget(self.open_os_button)
        header.addWidget(self.open_pcm_button)
        header.addWidget(refresh_button)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(8)
        self.schedules_card = StatCard("Programações abertas", "0", "Clique para abrir o planejamento do período", icon_name="activities")
        self.items_card = StatCard("Serviços do mês", "0", "Clique para abrir os serviços do período selecionado", icon_name="reports")
        self.pending_card = StatCard("Serviços pendentes", "0", "Clique para focar o que ainda precisa de ação", icon_name="warning")
        self.installed_card = StatCard("Serviços concluídos", "0", "Clique para revisar as conclusões do período", icon_name="ok")
        self.overdue_os_card = StatCard("OS atrasadas", "0", "Clique para abrir a área das ordens em atraso", icon_name="warning")
        self.waiting_parts_card = StatCard("Aguardando peça", "0", "Clique para abrir a área das peças que estão travando", icon_name="warning")
        self.no_responsible_card = StatCard("Sem responsável", "0", "Clique para abrir a área dos serviços sem dono", icon_name="activities")
        self.blockers_card = StatCard("Bloqueios ativos", "0", "Clique para abrir a área dos travamentos atuais", icon_name="dashboard")
        cards_layout.addWidget(self.schedules_card, 0, 0)
        cards_layout.addWidget(self.items_card, 0, 1)
        cards_layout.addWidget(self.pending_card, 0, 2)
        cards_layout.addWidget(self.installed_card, 0, 3)
        cards_layout.addWidget(self.overdue_os_card, 1, 0)
        cards_layout.addWidget(self.waiting_parts_card, 1, 1)
        cards_layout.addWidget(self.no_responsible_card, 1, 2)
        cards_layout.addWidget(self.blockers_card, 1, 3)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filter_layout = QGridLayout(filter_card)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setHorizontalSpacing(8)
        filter_layout.setVerticalSpacing(6)

        self.month_input = QDateEdit()
        self.month_input.setCalendarPopup(True)
        self.month_input.setDisplayFormat("MM/yyyy")
        self.month_input.setDate(QDate.currentDate())

        self.source_filter = QComboBox()
        self.source_filter.addItem("Todas as origens", "ALL")
        self.source_filter.addItem("Não conformidade legada", "CHECKLIST_NC")
        self.source_filter.addItem("Pacote de resolução", "PACOTE_RESOLUCAO")
        self.source_filter.addItem("Inspeção legada", "ATIVIDADE")
        self.source_filter.addItem("Preventiva", "PREVENTIVA")

        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "ALL")
        self.status_filter.addItem("Aberta", "ABERTA")
        self.status_filter.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.status_filter.addItem("Programada", "PROGRAMADA")
        self.status_filter.addItem("Em execução", "EM_EXECUCAO")
        self.status_filter.addItem("Concluída", "CONCLUIDA")
        self.status_filter.addItem("Cancelada", "CANCELADA")

        apply_button = QPushButton("Aplicar")
        apply_button.setProperty("variant", "primary")
        apply_button.setMinimumHeight(34)
        apply_button.clicked.connect(self.apply_filters)

        clear_button = QPushButton("Limpar filtros")
        clear_button.setMinimumHeight(34)
        clear_button.clicked.connect(self.clear_filters)

        filter_layout.addWidget(QLabel("Mes"), 0, 0)
        filter_layout.addWidget(self.month_input, 1, 0)
        filter_layout.addWidget(QLabel("Origem"), 0, 1)
        filter_layout.addWidget(self.source_filter, 1, 1)
        filter_layout.addWidget(QLabel("Status"), 0, 2)
        filter_layout.addWidget(self.status_filter, 1, 2)
        filter_layout.addWidget(apply_button, 1, 3)
        filter_layout.addWidget(clear_button, 1, 4)
        filter_layout.setColumnStretch(5, 1)

        screens_card = QFrame()
        style_filter_bar(screens_card)
        screens_layout = QVBoxLayout(screens_card)
        screens_layout.setContentsMargins(12, 10, 12, 10)
        screens_layout.setSpacing(8)

        screens_top = QHBoxLayout()
        screens_title = QLabel("Telas da manutenção")
        screens_title.setObjectName("SectionTitle")
        self.current_screen_badge = QLabel("Tela atual: Home da manutenção")
        self.current_screen_badge.setObjectName("TopBarPill")
        screens_top.addWidget(screens_title)
        screens_top.addStretch()
        screens_top.addWidget(self.current_screen_badge)

        screens_hint = QLabel(
            "Use os botões abaixo para abrir a tela certa. A ideia aqui é igual oficina organizada: um assunto por vez, sem misturar tudo no mesmo lugar."
        )
        screens_hint.setObjectName("PageSubtitle")
        screens_hint.setWordWrap(True)

        screens_buttons = QHBoxLayout()
        screens_buttons.setSpacing(8)
        self.programacoes_screen_button = QPushButton("Programações")
        self.programacoes_screen_button.clicked.connect(lambda: self._open_maintenance_screen("PROGRAMACOES"))
        self.agenda_screen_button = QPushButton("Agenda")
        self.agenda_screen_button.clicked.connect(lambda: self._open_maintenance_screen("AGENDA"))
        self.servicos_screen_button = QPushButton("Serviços")
        self.servicos_screen_button.clicked.connect(lambda: self._open_maintenance_screen("SERVICOS"))
        self.responsaveis_screen_button = QPushButton("Responsáveis")
        self.responsaveis_screen_button.clicked.connect(lambda: self._open_maintenance_screen("RESPONSAVEIS"))
        self.pecas_screen_button = QPushButton("Peças")
        self.pecas_screen_button.clicked.connect(lambda: self._open_maintenance_screen("PECAS"))
        self.os_screen_button = QPushButton("OS")
        self.os_screen_button.clicked.connect(lambda: self._open_maintenance_screen("OS"))
        self.bloqueios_screen_button = QPushButton("Bloqueios")
        self.bloqueios_screen_button.clicked.connect(lambda: self._open_maintenance_screen("BLOQUEIOS"))
        for button in (
            self.programacoes_screen_button,
            self.agenda_screen_button,
            self.servicos_screen_button,
            self.responsaveis_screen_button,
            self.pecas_screen_button,
            self.os_screen_button,
            self.bloqueios_screen_button,
        ):
            button.setMinimumHeight(34)
            screens_buttons.addWidget(button)
        screens_buttons.addStretch(1)

        screens_layout.addLayout(screens_top)
        screens_layout.addWidget(screens_hint)
        screens_layout.addLayout(screens_buttons)

        reports_card = QFrame()
        style_filter_bar(reports_card)
        reports_layout = QGridLayout(reports_card)
        reports_layout.setContentsMargins(12, 10, 12, 10)
        reports_layout.setHorizontalSpacing(8)
        reports_layout.setVerticalSpacing(6)

        self.report_badge = QLabel("Exporte uma visão gerencial do período selecionado")
        self.report_badge.setObjectName("TopBarPill")

        self.report_type_combo = QComboBox()
        for key, label in REPORT_TYPE_LABELS.items():
            self.report_type_combo.addItem(label, key)
        self.report_type_combo.currentIndexChanged.connect(self._update_report_filter_visibility)

        self.report_mechanic_combo = QComboBox()
        self.report_vehicle_combo = QComboBox()

        self.export_report_button = QPushButton("Exportar PDF")
        self.export_report_button.setProperty("variant", "primary")
        self.export_report_button.setMinimumHeight(34)
        self.export_report_button.clicked.connect(self.export_maintenance_report_pdf)

        reports_layout.addWidget(self.report_badge, 0, 0, 1, 5)
        reports_layout.addWidget(QLabel("Tipo de relatorio"), 1, 0)
        reports_layout.addWidget(self.report_type_combo, 1, 1)
        reports_layout.addWidget(QLabel("Mecânico"), 1, 2)
        reports_layout.addWidget(self.report_mechanic_combo, 1, 3)
        reports_layout.addWidget(self.export_report_button, 1, 4)
        reports_layout.addWidget(QLabel("Veiculo"), 2, 0)
        reports_layout.addWidget(self.report_vehicle_combo, 2, 1, 1, 3)
        reports_layout.setColumnStretch(3, 1)

        schedules_card = QFrame()
        style_table_card(schedules_card)
        self.schedules_skeleton = TableSkeletonOverlay(schedules_card, rows=7)
        schedules_layout = QVBoxLayout(schedules_card)
        schedules_layout.setContentsMargins(12, 10, 12, 10)
        schedules_layout.setSpacing(8)

        planning_screen_card = QFrame()
        self.planning_screen_card = planning_screen_card
        style_filter_bar(planning_screen_card)
        planning_screen_layout = QVBoxLayout(planning_screen_card)
        planning_screen_layout.setContentsMargins(12, 10, 12, 10)
        planning_screen_layout.setSpacing(8)

        planning_screen_top = QHBoxLayout()
        planning_screen_title = QLabel("Tela de programações")
        planning_screen_title.setObjectName("SectionTitle")
        self.planning_screen_badge = QLabel("Nenhum planejamento selecionado")
        self.planning_screen_badge.setObjectName("TopBarPill")
        planning_screen_top.addWidget(planning_screen_title)
        planning_screen_top.addStretch()
        planning_screen_top.addWidget(self.planning_screen_badge)

        planning_screen_hint = QLabel(
            "Aqui fica a mesa do planejamento. Primeiro você cria ou escolhe a programação, depois abre agenda, serviços ou responsáveis conforme a necessidade."
        )
        planning_screen_hint.setObjectName("PageSubtitle")
        planning_screen_hint.setWordWrap(True)

        planning_summary_layout = QGridLayout()
        planning_summary_layout.setHorizontalSpacing(8)
        planning_summary_layout.setVerticalSpacing(6)
        self.planning_origin_badge = QLabel("Origem: -")
        self.planning_origin_badge.setObjectName("TopBarPill")
        self.planning_status_badge = QLabel("Situação: -")
        self.planning_status_badge.setObjectName("TopBarPill")
        self.planning_period_badge = QLabel("Período: -")
        self.planning_period_badge.setObjectName("TopBarPill")
        self.planning_volume_badge = QLabel("Itens: 0 | Pendentes: 0 | Concluídos: 0")
        self.planning_volume_badge.setObjectName("TopBarPill")
        self.planning_capacity_badge = QLabel("Capacidade diária: -")
        self.planning_capacity_badge.setObjectName("TopBarPill")
        self.planning_package_badge = QLabel("Pacote: sem pacote")
        self.planning_package_badge.setObjectName("TopBarPill")
        planning_summary_layout.addWidget(self.planning_origin_badge, 0, 0)
        planning_summary_layout.addWidget(self.planning_status_badge, 0, 1)
        planning_summary_layout.addWidget(self.planning_period_badge, 0, 2)
        planning_summary_layout.addWidget(self.planning_volume_badge, 1, 0, 1, 2)
        planning_summary_layout.addWidget(self.planning_capacity_badge, 1, 2)
        planning_summary_layout.addWidget(self.planning_package_badge, 2, 0, 1, 3)

        planning_actions = QHBoxLayout()
        planning_actions.setSpacing(8)
        self.planning_new_button = QPushButton("Nova programação")
        self.planning_new_button.setProperty("variant", "primary")
        self.planning_new_button.setMinimumHeight(34)
        self.planning_new_button.clicked.connect(self.create_schedule)
        self.planning_open_agenda_button = QPushButton("Abrir agenda")
        self.planning_open_agenda_button.setMinimumHeight(34)
        self.planning_open_agenda_button.clicked.connect(lambda: self._open_maintenance_screen("AGENDA"))
        self.planning_open_services_button = QPushButton("Abrir serviços")
        self.planning_open_services_button.setMinimumHeight(34)
        self.planning_open_services_button.clicked.connect(lambda: self._open_maintenance_screen("SERVICOS"))
        self.planning_open_governance_button = QPushButton("Abrir responsáveis e peças")
        self.planning_open_governance_button.setMinimumHeight(34)
        self.planning_open_governance_button.clicked.connect(lambda: self._open_maintenance_screen("RESPONSAVEIS"))
        self.planning_back_home_button = QPushButton("Voltar para home")
        self.planning_back_home_button.setMinimumHeight(34)
        self.planning_back_home_button.clicked.connect(self._go_to_maintenance_home)
        planning_actions.addWidget(self.planning_new_button)
        planning_actions.addWidget(self.planning_open_agenda_button)
        planning_actions.addWidget(self.planning_open_services_button)
        planning_actions.addWidget(self.planning_open_governance_button)
        planning_actions.addWidget(self.planning_back_home_button)
        planning_actions.addStretch(1)

        planning_screen_layout.addLayout(planning_screen_top)
        planning_screen_layout.addWidget(planning_screen_hint)
        planning_screen_layout.addLayout(planning_summary_layout)
        planning_screen_layout.addLayout(planning_actions)

        schedules_title_row = QHBoxLayout()
        schedules_title = QLabel("Planejamento da manutenção")
        schedules_title.setObjectName("SectionTitle")
        self.schedules_badge = QLabel("0 registros")
        self.schedules_badge.setObjectName("TopBarPill")
        self.schedule_flow_badge = QLabel("1. Selecione o planejamento | 2. Confira a agenda acima | 3. Atue nos serviços")
        self.schedule_flow_badge.setObjectName("TopBarPill")
        schedules_title_row.addWidget(schedules_title)
        schedules_title_row.addStretch()
        schedules_title_row.addWidget(self.schedules_badge)
        schedules_title_row.addWidget(self.schedule_flow_badge)

        self.schedules_table = QTableWidget(0, 9)
        self.schedules_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Planejamento",
                "Origem",
                "Situação",
                "Período",
                "Itens",
                "Pendentes",
                "Concluídos",
                "Cap./dia",
            ]
        )
        configure_table(self.schedules_table, stretch_last=False)
        self.schedules_table.setMinimumHeight(300)
        self.schedules_table.setColumnHidden(0, True)
        self.schedules_table.itemSelectionChanged.connect(self._on_schedule_selection_changed)
        self.schedules_table.itemDoubleClicked.connect(lambda _item: self._open_maintenance_screen("SERVICOS"))

        schedules_hint = QLabel("Crie e selecione a programação base que será distribuída na agenda.")
        schedules_hint.setObjectName("PageSubtitle")
        schedules_hint.setWordWrap(True)
        schedules_layout.addLayout(schedules_title_row)
        schedules_layout.addWidget(schedules_hint)
        schedules_layout.addWidget(self.schedules_table)

        action_card = QFrame()
        style_filter_bar(action_card)
        action_layout = QGridLayout(action_card)
        action_layout.setContentsMargins(12, 10, 12, 10)
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(6)

        self.selected_schedule_badge = QLabel("Nenhum planejamento selecionado")
        self.selected_schedule_badge.setObjectName("TopBarPill")

        self.item_status_filter = QComboBox()
        self.item_status_filter.addItem("Itens: todos", "ALL")
        self.item_status_filter.addItem("Pendentes (todos)", "PENDENTES")
        self.item_status_filter.addItem("Pendente", "PENDENTE")
        self.item_status_filter.addItem("Programado", "PROGRAMADO")
        self.item_status_filter.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.item_status_filter.addItem("Concluído", "INSTALADO")
        self.item_status_filter.addItem("Não executado", "NAO_EXECUTADO")
        self.item_status_filter.addItem("Reprogramado", "REPROGRAMADO")
        self.item_status_filter.addItem("Cancelado", "CANCELADO")
        self.item_status_filter.currentIndexChanged.connect(self.render_selected_schedule_items)

        self.move_date_input = QDateEdit()
        self.move_date_input.setCalendarPopup(True)
        self.move_date_input.setDisplayFormat("dd/MM/yyyy")
        self.move_date_input.setDate(QDate.currentDate())
        self.move_reason_input = QLineEdit()
        self.move_reason_input.setPlaceholderText("Obrigatório: explique por que o serviço foi movido")

        self.move_button = QPushButton("Reprogramar itens")
        self.move_button.setProperty("variant", "primary")
        self.move_button.setMinimumHeight(34)
        self.move_button.clicked.connect(self.move_selected_items)

        self.remove_button = QPushButton("Retirar do cronograma")
        self.remove_button.setProperty("variant", "danger")
        self.remove_button.setMinimumHeight(34)
        self.remove_button.clicked.connect(self.remove_selected_items)
        self.export_work_order_button = QPushButton("Exportar OS")
        self.export_work_order_button.setMinimumHeight(34)
        self.export_work_order_button.clicked.connect(self.export_selected_work_order_pdf)

        self.redistribute_start_input = QDateEdit()
        self.redistribute_start_input.setCalendarPopup(True)
        self.redistribute_start_input.setDisplayFormat("dd/MM/yyyy")
        self.redistribute_start_input.setDate(QDate.currentDate())

        self.redistribute_capacity_input = QSpinBox()
        self.redistribute_capacity_input.setMinimum(1)
        self.redistribute_capacity_input.setMaximum(999)
        self.redistribute_capacity_input.setValue(1)

        self.redistribute_button = QPushButton("Recalcular agenda")
        self.redistribute_button.setProperty("variant", "primary")
        self.redistribute_button.setMinimumHeight(34)
        self.redistribute_button.clicked.connect(self.redistribute_selected_schedule)
        self.action_help_label = QLabel(
            "Selecione um planejamento e depois escolha os itens do serviço para liberar reprogramação e retirada."
        )
        self.action_help_label.setObjectName("PageSubtitle")
        self.action_help_label.setWordWrap(True)

        action_layout.addWidget(self.selected_schedule_badge, 0, 0, 1, 5)
        action_layout.addWidget(self.action_help_label, 1, 0, 1, 5)
        action_layout.addWidget(QLabel("Filtro de itens"), 2, 0)
        action_layout.addWidget(self.item_status_filter, 2, 1)
        action_layout.addWidget(QLabel("Nova data"), 2, 2)
        action_layout.addWidget(self.move_date_input, 2, 3)
        action_layout.addWidget(self.move_button, 2, 4)
        action_layout.addWidget(QLabel("Motivo da reprogramação"), 3, 0)
        action_layout.addWidget(self.move_reason_input, 3, 1, 1, 3)
        action_layout.addWidget(self.export_work_order_button, 3, 4)
        action_layout.addWidget(self.remove_button, 4, 4)
        action_layout.addWidget(QLabel("Início da redistribuição"), 4, 0)
        action_layout.addWidget(self.redistribute_start_input, 4, 1)
        action_layout.addWidget(QLabel("Cap./dia"), 4, 2)
        action_layout.addWidget(self.redistribute_capacity_input, 4, 3)
        action_layout.addWidget(self.redistribute_button, 5, 3, 1, 2)
        action_layout.setColumnStretch(1, 1)
        action_layout.setColumnStretch(4, 1)

        services_screen_card = QFrame()
        self.services_screen_card = services_screen_card
        style_filter_bar(services_screen_card)
        services_screen_layout = QVBoxLayout(services_screen_card)
        services_screen_layout.setContentsMargins(12, 10, 12, 10)
        services_screen_layout.setSpacing(8)

        services_screen_top = QHBoxLayout()
        services_screen_title = QLabel("Tela dos serviços")
        services_screen_title.setObjectName("SectionTitle")
        self.services_screen_badge = QLabel("Nenhum planejamento selecionado")
        self.services_screen_badge.setObjectName("TopBarPill")
        services_screen_top.addWidget(services_screen_title)
        services_screen_top.addStretch()
        services_screen_top.addWidget(self.services_screen_badge)

        services_screen_hint = QLabel(
            "Aqui fica a execução do serviço. Pense como a bancada do mecânico: você filtra, escolhe o que vai agir e usa os botões para reprogramar, retirar ou exportar a OS."
        )
        services_screen_hint.setObjectName("PageSubtitle")
        services_screen_hint.setWordWrap(True)

        services_summary_layout = QGridLayout()
        services_summary_layout.setHorizontalSpacing(8)
        services_summary_layout.setVerticalSpacing(6)
        self.services_scope_badge = QLabel("Escopo: -")
        self.services_scope_badge.setObjectName("TopBarPill")
        self.services_filter_badge = QLabel("Filtro: todos os serviços")
        self.services_filter_badge.setObjectName("TopBarPill")
        self.services_volume_badge = QLabel("Serviços: 0 | Selecionados: 0")
        self.services_volume_badge.setObjectName("TopBarPill")
        self.services_blockers_badge = QLabel("Aguardando peça: 0 | Sem execução: 0")
        self.services_blockers_badge.setObjectName("TopBarPill")
        self.services_context_badge = QLabel("Contexto: sem pacote")
        self.services_context_badge.setObjectName("TopBarPill")
        services_summary_layout.addWidget(self.services_scope_badge, 0, 0)
        services_summary_layout.addWidget(self.services_filter_badge, 0, 1)
        services_summary_layout.addWidget(self.services_volume_badge, 1, 0)
        services_summary_layout.addWidget(self.services_blockers_badge, 1, 1)
        services_summary_layout.addWidget(self.services_context_badge, 2, 0, 1, 2)

        services_actions = QHBoxLayout()
        services_actions.setSpacing(8)
        self.services_open_agenda_button = QPushButton("Abrir agenda")
        self.services_open_agenda_button.setMinimumHeight(34)
        self.services_open_agenda_button.clicked.connect(lambda: self._open_maintenance_screen("AGENDA"))
        self.services_open_governance_button = QPushButton("Abrir responsáveis e peças")
        self.services_open_governance_button.setMinimumHeight(34)
        self.services_open_governance_button.clicked.connect(lambda: self._open_maintenance_screen("RESPONSAVEIS"))
        self.services_back_home_button = QPushButton("Voltar para home")
        self.services_back_home_button.setMinimumHeight(34)
        self.services_back_home_button.clicked.connect(self._go_to_maintenance_home)
        services_actions.addWidget(self.services_open_agenda_button)
        services_actions.addWidget(self.services_open_governance_button)
        services_actions.addWidget(self.services_back_home_button)
        services_actions.addStretch(1)

        services_screen_layout.addLayout(services_screen_top)
        services_screen_layout.addWidget(services_screen_hint)
        services_screen_layout.addLayout(services_summary_layout)
        services_screen_layout.addLayout(services_actions)

        os_screen_card = QFrame()
        style_filter_bar(os_screen_card)
        self.os_screen_card = os_screen_card
        os_screen_layout = QVBoxLayout(os_screen_card)
        os_screen_layout.setContentsMargins(12, 10, 12, 10)
        os_screen_layout.setSpacing(8)

        os_screen_top = QHBoxLayout()
        os_screen_title = QLabel("Tela de OS")
        os_screen_title.setObjectName("SectionTitle")
        self.os_screen_badge = QLabel("Nenhum planejamento selecionado")
        self.os_screen_badge.setObjectName("TopBarPill")
        os_screen_top.addWidget(os_screen_title)
        os_screen_top.addStretch()
        os_screen_top.addWidget(self.os_screen_badge)

        os_screen_hint = QLabel(
            "Aqui fica o balcão das ordens de serviço. Pense como a comanda oficial da oficina: você enxerga quais OS estão abertas, atrasadas, bloqueadas ou concluídas."
        )
        os_screen_hint.setObjectName("PageSubtitle")
        os_screen_hint.setWordWrap(True)

        os_summary_layout = QGridLayout()
        os_summary_layout.setHorizontalSpacing(8)
        os_summary_layout.setVerticalSpacing(6)
        self.os_scope_badge = QLabel("Escopo: todos os dias")
        self.os_scope_badge.setObjectName("TopBarPill")
        self.os_filter_badge = QLabel("Filtro: todas as OS")
        self.os_filter_badge.setObjectName("TopBarPill")
        self.os_volume_badge = QLabel("OS: 0 | Selecionadas: 0")
        self.os_volume_badge.setObjectName("TopBarPill")
        self.os_blockers_badge = QLabel("Atrasadas: 0 | Bloqueadas: 0 | Concluídas: 0")
        self.os_blockers_badge.setObjectName("TopBarPill")
        os_summary_layout.addWidget(self.os_scope_badge, 0, 0)
        os_summary_layout.addWidget(self.os_filter_badge, 0, 1)
        os_summary_layout.addWidget(self.os_volume_badge, 1, 0)
        os_summary_layout.addWidget(self.os_blockers_badge, 1, 1)

        os_actions = QHBoxLayout()
        os_actions.setSpacing(8)
        self.os_filter_combo = QComboBox()
        self.os_filter_combo.addItem("Todas as OS", "ALL")
        self.os_filter_combo.addItem("OS abertas", "ABERTAS")
        self.os_filter_combo.addItem("OS atrasadas", "ATRASADAS")
        self.os_filter_combo.addItem("OS bloqueadas", "BLOQUEADAS")
        self.os_filter_combo.addItem("OS concluídas", "CONCLUIDAS")
        self.os_filter_combo.currentIndexChanged.connect(self._render_os_table)
        self.os_export_button = QPushButton("Exportar OS selecionada")
        self.os_export_button.setMinimumHeight(34)
        self.os_export_button.clicked.connect(self.export_selected_os_from_screen)
        self.os_open_services_button = QPushButton("Abrir serviços")
        self.os_open_services_button.setMinimumHeight(34)
        self.os_open_services_button.clicked.connect(lambda: self._open_maintenance_screen("SERVICOS"))
        self.os_back_home_button = QPushButton("Voltar para home")
        self.os_back_home_button.setMinimumHeight(34)
        self.os_back_home_button.clicked.connect(self._go_to_maintenance_home)
        os_actions.addWidget(QLabel("Filtro"))
        os_actions.addWidget(self.os_filter_combo)
        os_actions.addWidget(self.os_export_button)
        os_actions.addWidget(self.os_open_services_button)
        os_actions.addWidget(self.os_back_home_button)
        os_actions.addStretch(1)

        os_table_card = QFrame()
        style_table_card(os_table_card)
        os_table_layout = QVBoxLayout(os_table_card)
        os_table_layout.setContentsMargins(12, 10, 12, 10)
        os_table_layout.setSpacing(8)

        os_table_hint = QLabel(
            "Clique em uma OS para conferir a comanda. Dê duplo clique para exportar o PDF rico daquela ordem."
        )
        os_table_hint.setObjectName("PageSubtitle")
        os_table_hint.setWordWrap(True)

        self.os_table = QTableWidget(0, 8)
        self.os_table.setHorizontalHeaderLabels(
            [
                "ID item",
                "OS",
                "Veículo",
                "Serviço",
                "Data",
                "Situação",
                "Execução",
                "Material",
            ]
        )
        configure_table(self.os_table, stretch_last=True)
        self.os_table.setColumnHidden(0, True)
        self.os_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.os_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.os_table.itemSelectionChanged.connect(self._update_os_selection_badge)
        self.os_table.itemDoubleClicked.connect(self.export_selected_os_from_screen)
        self.os_table.setMinimumHeight(280)

        os_table_layout.addWidget(os_table_hint)
        os_table_layout.addWidget(self.os_table)

        os_screen_layout.addLayout(os_screen_top)
        os_screen_layout.addWidget(os_screen_hint)
        os_screen_layout.addLayout(os_summary_layout)
        os_screen_layout.addLayout(os_actions)
        os_screen_layout.addWidget(os_table_card)

        blockers_screen_card = QFrame()
        style_filter_bar(blockers_screen_card)
        self.blockers_screen_card = blockers_screen_card
        blockers_screen_layout = QVBoxLayout(blockers_screen_card)
        blockers_screen_layout.setContentsMargins(12, 10, 12, 10)
        blockers_screen_layout.setSpacing(8)

        blockers_screen_top = QHBoxLayout()
        blockers_screen_title = QLabel("Tela de bloqueios")
        blockers_screen_title.setObjectName("SectionTitle")
        self.blockers_screen_badge = QLabel("Nenhum travamento selecionado")
        self.blockers_screen_badge.setObjectName("TopBarPill")
        blockers_screen_top.addWidget(blockers_screen_title)
        blockers_screen_top.addStretch()
        blockers_screen_top.addWidget(self.blockers_screen_badge)

        blockers_screen_hint = QLabel(
            "Aqui fica o painel dos travamentos. Pense como o quadro de pendências da oficina: tudo que impede o serviço de andar aparece reunido aqui."
        )
        blockers_screen_hint.setObjectName("PageSubtitle")
        blockers_screen_hint.setWordWrap(True)

        blockers_summary_layout = QGridLayout()
        blockers_summary_layout.setHorizontalSpacing(8)
        blockers_summary_layout.setVerticalSpacing(6)
        self.blockers_scope_badge = QLabel("Escopo: todos os planejamentos")
        self.blockers_scope_badge.setObjectName("TopBarPill")
        self.blockers_filter_badge = QLabel("Filtro: todos os bloqueios")
        self.blockers_filter_badge.setObjectName("TopBarPill")
        self.blockers_volume_badge = QLabel("Bloqueios: 0 | Planejamentos travados: 0")
        self.blockers_volume_badge.setObjectName("TopBarPill")
        self.blockers_types_badge = QLabel("Sem responsável: 0 | Peça: 0 | OS bloqueada: 0")
        self.blockers_types_badge.setObjectName("TopBarPill")
        blockers_summary_layout.addWidget(self.blockers_scope_badge, 0, 0)
        blockers_summary_layout.addWidget(self.blockers_filter_badge, 0, 1)
        blockers_summary_layout.addWidget(self.blockers_volume_badge, 1, 0)
        blockers_summary_layout.addWidget(self.blockers_types_badge, 1, 1)

        blockers_actions = QHBoxLayout()
        blockers_actions.setSpacing(8)
        self.blockers_filter_combo = QComboBox()
        self.blockers_filter_combo.addItem("Todos os bloqueios", "ALL")
        self.blockers_filter_combo.addItem("Sem responsável", "SEM_RESPONSAVEL")
        self.blockers_filter_combo.addItem("Aguardando peça", "AGUARDANDO_PECA")
        self.blockers_filter_combo.addItem("OS bloqueadas", "OS_BLOQUEADAS")
        self.blockers_filter_combo.addItem("Com travamento", "COM_TRAVAMENTO")
        self.blockers_filter_combo.currentIndexChanged.connect(self._render_blockers_table)
        self.blockers_open_services_button = QPushButton("Abrir serviços")
        self.blockers_open_services_button.setMinimumHeight(34)
        self.blockers_open_services_button.clicked.connect(lambda: self._open_maintenance_screen("SERVICOS"))
        self.blockers_open_parts_button = QPushButton("Abrir peças")
        self.blockers_open_parts_button.setMinimumHeight(34)
        self.blockers_open_parts_button.clicked.connect(lambda: self._open_maintenance_screen("PECAS"))
        self.blockers_open_responsible_button = QPushButton("Abrir responsáveis")
        self.blockers_open_responsible_button.setMinimumHeight(34)
        self.blockers_open_responsible_button.clicked.connect(lambda: self._open_maintenance_screen("RESPONSAVEIS"))
        self.blockers_back_home_button = QPushButton("Voltar para home")
        self.blockers_back_home_button.setMinimumHeight(34)
        self.blockers_back_home_button.clicked.connect(self._go_to_maintenance_home)
        blockers_actions.addWidget(QLabel("Filtro"))
        blockers_actions.addWidget(self.blockers_filter_combo)
        blockers_actions.addWidget(self.blockers_open_services_button)
        blockers_actions.addWidget(self.blockers_open_parts_button)
        blockers_actions.addWidget(self.blockers_open_responsible_button)
        blockers_actions.addWidget(self.blockers_back_home_button)
        blockers_actions.addStretch(1)

        blockers_table_card = QFrame()
        style_table_card(blockers_table_card)
        blockers_table_layout = QVBoxLayout(blockers_table_card)
        blockers_table_layout.setContentsMargins(12, 10, 12, 10)
        blockers_table_layout.setSpacing(8)

        blockers_table_hint = QLabel(
            "Clique em um travamento para carregar o planejamento relacionado. Dê duplo clique para abrir os serviços daquele ponto."
        )
        blockers_table_hint.setObjectName("PageSubtitle")
        blockers_table_hint.setWordWrap(True)

        self.blockers_table = QTableWidget(0, 8)
        self.blockers_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Planejamento",
                "Tipo principal",
                "Detalhes",
                "Responsável",
                "Peças travando",
                "OS bloqueadas",
                "Pacote",
            ]
        )
        configure_table(self.blockers_table, stretch_last=True)
        self.blockers_table.setColumnHidden(0, True)
        self.blockers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.blockers_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.blockers_table.itemSelectionChanged.connect(self._on_blocker_selection_changed)
        self.blockers_table.itemDoubleClicked.connect(lambda _item: self._open_maintenance_screen("SERVICOS"))
        self.blockers_table.setMinimumHeight(280)

        blockers_table_layout.addWidget(blockers_table_hint)
        blockers_table_layout.addWidget(self.blockers_table)

        blockers_screen_layout.addLayout(blockers_screen_top)
        blockers_screen_layout.addWidget(blockers_screen_hint)
        blockers_screen_layout.addLayout(blockers_summary_layout)
        blockers_screen_layout.addLayout(blockers_actions)
        blockers_screen_layout.addWidget(blockers_table_card)

        responsible_screen_card = QFrame()
        style_filter_bar(responsible_screen_card)
        self.responsible_screen_card = responsible_screen_card
        responsible_screen_layout = QVBoxLayout(responsible_screen_card)
        responsible_screen_layout.setContentsMargins(12, 10, 12, 10)
        responsible_screen_layout.setSpacing(8)

        responsible_screen_top = QHBoxLayout()
        responsible_screen_title = QLabel("Tela de responsáveis")
        responsible_screen_title.setObjectName("SectionTitle")
        self.responsible_screen_badge = QLabel("Nenhum planejamento selecionado")
        self.responsible_screen_badge.setObjectName("TopBarPill")
        responsible_screen_top.addWidget(responsible_screen_title)
        responsible_screen_top.addStretch()
        responsible_screen_top.addWidget(self.responsible_screen_badge)

        responsible_screen_hint = QLabel(
            "Aqui fica a distribuição dos donos do serviço. Pense como a prancheta do encarregado: quem já recebeu tarefa, quem ainda está sem dono e quem está mais carregado."
        )
        responsible_screen_hint.setObjectName("PageSubtitle")
        responsible_screen_hint.setWordWrap(True)

        responsible_summary_layout = QGridLayout()
        responsible_summary_layout.setHorizontalSpacing(8)
        responsible_summary_layout.setVerticalSpacing(6)
        self.responsible_scope_badge = QLabel("Escopo: todos os planejamentos")
        self.responsible_scope_badge.setObjectName("TopBarPill")
        self.responsible_filter_badge = QLabel("Filtro: todos")
        self.responsible_filter_badge.setObjectName("TopBarPill")
        self.responsible_load_badge = QLabel("Sem responsável: 0 | Com responsável: 0")
        self.responsible_load_badge.setObjectName("TopBarPill")
        self.responsible_queue_badge = QLabel("OS abertas: 0 | OS atrasadas: 0")
        self.responsible_queue_badge.setObjectName("TopBarPill")
        responsible_summary_layout.addWidget(self.responsible_scope_badge, 0, 0)
        responsible_summary_layout.addWidget(self.responsible_filter_badge, 0, 1)
        responsible_summary_layout.addWidget(self.responsible_load_badge, 1, 0)
        responsible_summary_layout.addWidget(self.responsible_queue_badge, 1, 1)

        responsible_actions = QHBoxLayout()
        responsible_actions.setSpacing(8)
        self.responsible_filter_combo = QComboBox()
        self.responsible_filter_combo.addItem("Todos os planejamentos", "ALL")
        self.responsible_filter_combo.addItem("Sem responsável", "SEM_RESPONSAVEL")
        self.responsible_filter_combo.addItem("Com responsável", "COM_RESPONSAVEL")
        self.responsible_filter_combo.currentIndexChanged.connect(self._render_responsible_table)
        self.responsible_open_parts_button = QPushButton("Abrir peças")
        self.responsible_open_parts_button.setMinimumHeight(34)
        self.responsible_open_parts_button.clicked.connect(lambda: self._open_maintenance_screen("PECAS"))
        self.responsible_back_home_button = QPushButton("Voltar para home")
        self.responsible_back_home_button.setMinimumHeight(34)
        self.responsible_back_home_button.clicked.connect(self._go_to_maintenance_home)
        responsible_actions.addWidget(QLabel("Filtro"))
        responsible_actions.addWidget(self.responsible_filter_combo)
        responsible_actions.addWidget(self.responsible_open_parts_button)
        responsible_actions.addWidget(self.responsible_back_home_button)
        responsible_actions.addStretch(1)

        responsible_table_card = QFrame()
        style_table_card(responsible_table_card)
        responsible_table_layout = QVBoxLayout(responsible_table_card)
        responsible_table_layout.setContentsMargins(12, 10, 12, 10)
        responsible_table_layout.setSpacing(8)

        responsible_table_hint = QLabel(
            "Clique em um planejamento para carregar o responsável abaixo. Dê duplo clique para abrir os serviços daquele planejamento."
        )
        responsible_table_hint.setObjectName("PageSubtitle")
        responsible_table_hint.setWordWrap(True)

        self.responsible_table = QTableWidget(0, 7)
        self.responsible_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Planejamento",
                "Responsável atual",
                "Situação",
                "OS abertas",
                "OS atrasadas",
                "Carga",
            ]
        )
        configure_table(self.responsible_table, stretch_last=False)
        self.responsible_table.setColumnHidden(0, True)
        self.responsible_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.responsible_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.responsible_table.itemSelectionChanged.connect(self._on_responsible_schedule_selection_changed)
        self.responsible_table.itemDoubleClicked.connect(lambda _item: self._open_maintenance_screen("SERVICOS"))
        self.responsible_table.setMinimumHeight(260)

        responsible_table_layout.addWidget(responsible_table_hint)
        responsible_table_layout.addWidget(self.responsible_table)

        responsible_screen_layout.addLayout(responsible_screen_top)
        responsible_screen_layout.addWidget(responsible_screen_hint)
        responsible_screen_layout.addLayout(responsible_summary_layout)
        responsible_screen_layout.addLayout(responsible_actions)
        responsible_screen_layout.addWidget(responsible_table_card)

        governance_header_card = QFrame()
        style_filter_bar(governance_header_card)
        governance_header_layout = QVBoxLayout(governance_header_card)
        governance_header_layout.setContentsMargins(12, 10, 12, 10)
        governance_header_layout.setSpacing(6)

        self.governance_badge = QLabel("Responsável e peças: selecione um planejamento")
        self.governance_badge.setObjectName("TopBarPill")

        self.mechanic_combo = QComboBox()
        self.assign_mechanic_button = QPushButton("Definir responsável")
        self.assign_mechanic_button.setProperty("variant", "primary")
        self.assign_mechanic_button.setMinimumHeight(34)
        self.assign_mechanic_button.clicked.connect(self.assign_schedule_mechanic)

        self.material_combo = QComboBox()
        self.material_combo.currentIndexChanged.connect(self._sync_material_form_with_link)
        self.material_suggestion_badge = QLabel("Sugestão de peça: selecione um planejamento para o sistema analisar o histórico.")
        self.material_suggestion_badge.setObjectName("TopBarPill")
        self.material_suggest_button = QPushButton("Aplicar sugestão")
        self.material_suggest_button.setMinimumHeight(34)
        self.material_suggest_button.clicked.connect(self.apply_material_suggestion_for_selected_schedule)
        self.material_suggest_button.setEnabled(False)
        self.material_qty_input = QSpinBox()
        self.material_qty_input.setMinimum(1)
        self.material_qty_input.setMaximum(999)
        self.material_qty_input.setValue(1)
        self.material_status_combo = QComboBox()
        self.material_status_combo.addItem("Aguardando material", "AGUARDANDO_MATERIAL")
        self.material_status_combo.addItem("Em compras", "EM_COMPRAS")
        self.material_status_combo.addItem("Disponível em estoque", "DISPONIVEL_EM_ESTOQUE")
        self.material_status_combo.addItem("Reservado", "RESERVADO")
        self.material_status_combo.addItem("Utilizado", "UTILIZADO")
        self.material_observation_input = QLineEdit()
        self.material_observation_input.setPlaceholderText("Observação da peça para esta programação.")
        self.link_material_button = QPushButton("Salvar peça")
        self.link_material_button.setProperty("variant", "primary")
        self.link_material_button.setMinimumHeight(34)
        self.link_material_button.clicked.connect(self.link_material_for_selected_schedule)
        self.management_help_label = QLabel(
            "As definições de responsável e peça só são liberadas depois que um planejamento é selecionado."
        )
        self.management_help_label.setObjectName("PageSubtitle")
        self.management_help_label.setWordWrap(True)

        governance_hint = QLabel("Defina quem atende a programação e registre a peça que libera ou bloqueia a execução.")
        governance_hint.setObjectName("PageSubtitle")
        governance_hint.setWordWrap(True)
        governance_header_layout.addWidget(self.governance_badge)
        governance_header_layout.addWidget(governance_hint)
        governance_header_layout.addWidget(self.management_help_label)

        responsible_card = QFrame()
        style_table_card(responsible_card)
        responsible_layout = QGridLayout(responsible_card)
        responsible_layout.setContentsMargins(12, 10, 12, 10)
        responsible_layout.setHorizontalSpacing(8)
        responsible_layout.setVerticalSpacing(6)
        responsible_title = QLabel("Responsável da programação")
        responsible_title.setObjectName("SectionTitle")
        responsible_hint = QLabel("Escolha quem atende este pacote antes de distribuir a execução.")
        responsible_hint.setObjectName("PageSubtitle")
        responsible_hint.setWordWrap(True)
        responsible_layout.addWidget(responsible_title, 0, 0, 1, 3)
        responsible_layout.addWidget(responsible_hint, 1, 0, 1, 3)
        responsible_layout.addWidget(QLabel("Mecânico responsável"), 2, 0)
        responsible_layout.addWidget(self.mechanic_combo, 3, 0, 1, 2)
        responsible_layout.addWidget(self.assign_mechanic_button, 3, 2)
        responsible_layout.setColumnStretch(1, 1)

        pieces_screen_card = QFrame()
        style_filter_bar(pieces_screen_card)
        self.pieces_screen_card = pieces_screen_card
        pieces_screen_layout = QVBoxLayout(pieces_screen_card)
        pieces_screen_layout.setContentsMargins(12, 10, 12, 10)
        pieces_screen_layout.setSpacing(8)

        pieces_screen_top = QHBoxLayout()
        pieces_screen_title = QLabel("Tela de peças")
        pieces_screen_title.setObjectName("SectionTitle")
        self.pieces_screen_badge = QLabel("Nenhum planejamento selecionado")
        self.pieces_screen_badge.setObjectName("TopBarPill")
        pieces_screen_top.addWidget(pieces_screen_title)
        pieces_screen_top.addStretch()
        pieces_screen_top.addWidget(self.pieces_screen_badge)

        pieces_screen_hint = QLabel(
            "Aqui fica o balcão das peças. Você enxerga o que está faltando, o que já está reservado e o que já liberou a execução."
        )
        pieces_screen_hint.setObjectName("PageSubtitle")
        pieces_screen_hint.setWordWrap(True)

        pieces_summary_layout = QGridLayout()
        pieces_summary_layout.setHorizontalSpacing(8)
        pieces_summary_layout.setVerticalSpacing(6)
        self.pieces_scope_badge = QLabel("Escopo: todos os planejamentos")
        self.pieces_scope_badge.setObjectName("TopBarPill")
        self.pieces_filter_badge = QLabel("Filtro: todas as peças")
        self.pieces_filter_badge.setObjectName("TopBarPill")
        self.pieces_volume_badge = QLabel("Peças: 0 | Reservadas: 0 | Utilizadas: 0")
        self.pieces_volume_badge.setObjectName("TopBarPill")
        self.pieces_blockers_badge = QLabel("Aguardando peça: 0 | Em compras: 0")
        self.pieces_blockers_badge.setObjectName("TopBarPill")
        pieces_summary_layout.addWidget(self.pieces_scope_badge, 0, 0)
        pieces_summary_layout.addWidget(self.pieces_filter_badge, 0, 1)
        pieces_summary_layout.addWidget(self.pieces_volume_badge, 1, 0)
        pieces_summary_layout.addWidget(self.pieces_blockers_badge, 1, 1)

        pieces_actions = QHBoxLayout()
        pieces_actions.setSpacing(8)
        self.pieces_filter_combo = QComboBox()
        self.pieces_filter_combo.addItem("Todas as peças", "ALL")
        self.pieces_filter_combo.addItem("Aguardando peça", "AGUARDANDO_MATERIAL")
        self.pieces_filter_combo.addItem("Em compras", "EM_COMPRAS")
        self.pieces_filter_combo.addItem("Disponível em estoque", "DISPONIVEL_EM_ESTOQUE")
        self.pieces_filter_combo.addItem("Reservadas", "RESERVADO")
        self.pieces_filter_combo.addItem("Utilizadas", "UTILIZADO")
        self.pieces_filter_combo.currentIndexChanged.connect(self.render_selected_schedule_materials)
        self.pieces_open_services_button = QPushButton("Abrir serviços")
        self.pieces_open_services_button.setMinimumHeight(34)
        self.pieces_open_services_button.clicked.connect(lambda: self._open_maintenance_screen("SERVICOS"))
        self.pieces_open_responsible_button = QPushButton("Abrir responsáveis")
        self.pieces_open_responsible_button.setMinimumHeight(34)
        self.pieces_open_responsible_button.clicked.connect(lambda: self._open_maintenance_screen("RESPONSAVEIS"))
        self.pieces_back_home_button = QPushButton("Voltar para home")
        self.pieces_back_home_button.setMinimumHeight(34)
        self.pieces_back_home_button.clicked.connect(self._go_to_maintenance_home)
        pieces_actions.addWidget(QLabel("Filtro"))
        pieces_actions.addWidget(self.pieces_filter_combo)
        pieces_actions.addWidget(self.pieces_open_services_button)
        pieces_actions.addWidget(self.pieces_open_responsible_button)
        pieces_actions.addWidget(self.pieces_back_home_button)
        pieces_actions.addStretch(1)

        pieces_screen_layout.addLayout(pieces_screen_top)
        pieces_screen_layout.addWidget(pieces_screen_hint)
        pieces_screen_layout.addLayout(pieces_summary_layout)
        pieces_screen_layout.addLayout(pieces_actions)

        material_form_card = QFrame()
        style_table_card(material_form_card)
        material_form_layout = QGridLayout(material_form_card)
        material_form_layout.setContentsMargins(12, 10, 12, 10)
        material_form_layout.setHorizontalSpacing(8)
        material_form_layout.setVerticalSpacing(6)
        material_form_title = QLabel("Peça para liberar execução")
        material_form_title.setObjectName("SectionTitle")
        material_form_hint = QLabel("Registre a peça do serviço para liberar, reservar ou bloquear a execução no mobile.")
        material_form_hint.setObjectName("PageSubtitle")
        material_form_hint.setWordWrap(True)
        material_form_layout.addWidget(material_form_title, 0, 0, 1, 4)
        material_form_layout.addWidget(material_form_hint, 1, 0, 1, 4)
        material_form_layout.addWidget(self.material_suggestion_badge, 2, 0, 1, 3)
        material_form_layout.addWidget(self.material_suggest_button, 2, 3)
        material_form_layout.addWidget(QLabel("Peça / material"), 3, 0)
        material_form_layout.addWidget(self.material_combo, 4, 0, 1, 2)
        material_form_layout.addWidget(QLabel("Quantidade por veículo"), 3, 2)
        material_form_layout.addWidget(self.material_qty_input, 4, 2)
        material_form_layout.addWidget(QLabel("Situação da peça"), 5, 0)
        material_form_layout.addWidget(self.material_status_combo, 6, 0, 1, 2)
        material_form_layout.addWidget(self.material_observation_input, 6, 2)
        material_form_layout.addWidget(self.link_material_button, 4, 3, 3, 1)
        material_form_layout.setColumnStretch(1, 1)
        material_form_layout.setColumnStretch(2, 1)

        materials_card = QFrame()
        style_table_card(materials_card)
        self.materials_skeleton = TableSkeletonOverlay(materials_card, rows=5)
        materials_layout = QVBoxLayout(materials_card)
        materials_layout.setContentsMargins(12, 10, 12, 10)
        materials_layout.setSpacing(8)

        materials_top = QHBoxLayout()
        materials_title = QLabel("Peças da programação")
        materials_title.setObjectName("SectionTitle")
        self.materials_badge = QLabel("0 peças")
        self.materials_badge.setObjectName("TopBarPill")
        materials_top.addWidget(materials_title)
        materials_top.addStretch()
        materials_top.addWidget(self.materials_badge)
        materials_hint = QLabel("Acompanhe o material necessário para liberar a execução no mobile.")
        materials_hint.setObjectName("PageSubtitle")
        materials_hint.setWordWrap(True)

        self.materials_table = QTableWidget(0, 9)
        self.materials_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Referencia",
                "Descricao",
                "Saldo estoque",
                "Qtd/veiculo",
                "Qtd necessaria",
                "Qtd reservada",
                "Status",
                "Observação",
            ]
        )
        configure_table(self.materials_table, stretch_last=True)
        self.materials_table.setMinimumHeight(260)

        materials_layout.addLayout(materials_top)
        materials_layout.addWidget(materials_hint)
        materials_layout.addWidget(self.materials_table)

        details_card = QFrame()
        style_table_card(details_card)
        self.details_skeleton = TableSkeletonOverlay(details_card, rows=8)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setSpacing(8)

        detail_top = QHBoxLayout()
        detail_title = QLabel("Serviços da programação")
        detail_title.setObjectName("SectionTitle")
        self.items_badge = QLabel("0 itens")
        self.items_badge.setObjectName("TopBarPill")
        detail_top.addWidget(detail_title)
        detail_top.addStretch()
        detail_top.addWidget(self.items_badge)
        self.details_hint_label = QLabel("Aqui estão os itens executáveis do contexto selecionado.")
        self.details_hint_label.setObjectName("PageSubtitle")
        self.details_hint_label.setWordWrap(True)

        self.items_table = QTableWidget(0, 10)
        self.items_table.setHorizontalHeaderLabels(
            [
                "ID item",
                "OS",
                "Veículo",
                "Origem",
                "Serviço",
                "Data",
                "Situação",
                "Material",
                "Execução",
                "Observação",
            ]
        )
        configure_table(self.items_table, stretch_last=True)
        self.items_table.setColumnHidden(0, True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.items_table.itemSelectionChanged.connect(self._update_items_badge)
        self.items_table.itemDoubleClicked.connect(self.export_selected_work_order_pdf)
        self.items_table.setMinimumHeight(360)

        details_layout.addLayout(detail_top)
        details_layout.addWidget(self.details_hint_label)
        details_layout.addWidget(self.items_table)

        calendar_card = QFrame()
        style_table_card(calendar_card)
        self.calendar_skeleton = TableSkeletonOverlay(calendar_card, rows=6)
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(10, 10, 10, 10)
        calendar_layout.setSpacing(8)

        calendar_title_row = QHBoxLayout()
        calendar_title = QLabel("Calendário da manutenção")
        calendar_title.setObjectName("SectionTitle")
        self.calendar_badge = QLabel("0 dias")
        self.calendar_badge.setObjectName("TopBarPill")
        self.calendar_selected_badge = QLabel("Clique em um dia para abrir a agenda daquele dia")
        self.calendar_selected_badge.setObjectName("TopBarPill")
        self.calendar_day_resume_badge = QLabel("Selecione um dia para acompanhar carga, pendência e bloqueios")
        self.calendar_day_resume_badge.setObjectName("TopBarPill")
        self.clear_calendar_filter_button = QPushButton("Limpar dia")
        self.clear_calendar_filter_button.setMinimumHeight(34)
        self.clear_calendar_filter_button.clicked.connect(self._clear_calendar_day_filter)
        calendar_title_row.addWidget(calendar_title)
        calendar_title_row.addStretch()
        calendar_title_row.addWidget(self.calendar_badge)
        calendar_title_row.addWidget(self.calendar_selected_badge)
        calendar_title_row.addWidget(self.calendar_day_resume_badge)
        calendar_title_row.addWidget(self.clear_calendar_filter_button)

        self.calendar_table = QTableWidget(6, 7)
        self.calendar_table.setObjectName("CalendarGrid")
        self.calendar_table.setHorizontalHeaderLabels(WEEKDAY_HEADERS)
        configure_table(self.calendar_table, stretch_last=False, auto_fit=False)
        self.calendar_table.setSortingEnabled(False)
        self.calendar_table.horizontalHeader().setSectionsClickable(False)
        self.calendar_table.horizontalHeader().setSortIndicatorShown(False)
        self.calendar_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.calendar_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.calendar_table.itemSelectionChanged.connect(self._on_calendar_day_selection_changed)
        self.calendar_table.verticalHeader().setVisible(False)
        self.calendar_table.setMinimumHeight(520)
        calendar_hint = QLabel("Clique em um dia para trazer os serviços do dia e conferir pendências, conclusões e bloqueios.")
        calendar_hint.setObjectName("PageSubtitle")
        calendar_hint.setWordWrap(True)
        calendar_layout.addLayout(calendar_title_row)
        calendar_layout.addWidget(calendar_hint)
        calendar_layout.addWidget(self.calendar_table)

        agenda_screen_card = QFrame()
        self.agenda_screen_card = agenda_screen_card
        style_filter_bar(agenda_screen_card)
        agenda_screen_layout = QVBoxLayout(agenda_screen_card)
        agenda_screen_layout.setContentsMargins(12, 10, 12, 10)
        agenda_screen_layout.setSpacing(8)

        agenda_screen_top = QHBoxLayout()
        agenda_screen_title = QLabel("Tela da agenda")
        agenda_screen_title.setObjectName("SectionTitle")
        self.agenda_screen_badge = QLabel("Nenhum dia selecionado")
        self.agenda_screen_badge.setObjectName("TopBarPill")
        agenda_screen_top.addWidget(agenda_screen_title)
        agenda_screen_top.addStretch()
        agenda_screen_top.addWidget(self.agenda_screen_badge)

        agenda_screen_hint = QLabel(
            "Aqui fica a agenda operacional. Pense como a mesa que distribui o dia: você escolhe o dia, enxerga a carga e abre os serviços daquele ponto."
        )
        agenda_screen_hint.setObjectName("PageSubtitle")
        agenda_screen_hint.setWordWrap(True)

        agenda_summary_layout = QGridLayout()
        agenda_summary_layout.setHorizontalSpacing(8)
        agenda_summary_layout.setVerticalSpacing(6)
        self.agenda_period_badge = QLabel("Período: -")
        self.agenda_period_badge.setObjectName("TopBarPill")
        self.agenda_day_volume_badge = QLabel("Programados: 0 | Pendentes: 0 | Concluídos: 0")
        self.agenda_day_volume_badge.setObjectName("TopBarPill")
        self.agenda_day_blockers_badge = QLabel("Aguardando peça: 0 | Não executados: 0")
        self.agenda_day_blockers_badge.setObjectName("TopBarPill")
        self.agenda_schedule_scope_badge = QLabel("Planejamento: todos os planejamentos")
        self.agenda_schedule_scope_badge.setObjectName("TopBarPill")
        agenda_summary_layout.addWidget(self.agenda_period_badge, 0, 0)
        agenda_summary_layout.addWidget(self.agenda_schedule_scope_badge, 0, 1)
        agenda_summary_layout.addWidget(self.agenda_day_volume_badge, 1, 0)
        agenda_summary_layout.addWidget(self.agenda_day_blockers_badge, 1, 1)

        agenda_actions = QHBoxLayout()
        agenda_actions.setSpacing(8)
        self.agenda_open_services_button = QPushButton("Abrir serviços do dia")
        self.agenda_open_services_button.setMinimumHeight(34)
        self.agenda_open_services_button.clicked.connect(self._open_services_for_selected_day)
        self.agenda_clear_day_button = QPushButton("Limpar dia")
        self.agenda_clear_day_button.setMinimumHeight(34)
        self.agenda_clear_day_button.clicked.connect(self._clear_calendar_day_filter)
        self.agenda_back_home_button = QPushButton("Voltar para home")
        self.agenda_back_home_button.setMinimumHeight(34)
        self.agenda_back_home_button.clicked.connect(self._go_to_maintenance_home)
        agenda_actions.addWidget(self.agenda_open_services_button)
        agenda_actions.addWidget(self.agenda_clear_day_button)
        agenda_actions.addWidget(self.agenda_back_home_button)
        agenda_actions.addStretch(1)

        agenda_days_card = QFrame()
        style_table_card(agenda_days_card)
        agenda_days_layout = QVBoxLayout(agenda_days_card)
        agenda_days_layout.setContentsMargins(12, 10, 12, 10)
        agenda_days_layout.setSpacing(8)

        agenda_days_top = QHBoxLayout()
        agenda_days_title = QLabel("Dias programados")
        agenda_days_title.setObjectName("SectionTitle")
        self.agenda_days_badge = QLabel("0 dias")
        self.agenda_days_badge.setObjectName("TopBarPill")
        agenda_days_top.addWidget(agenda_days_title)
        agenda_days_top.addStretch()
        agenda_days_top.addWidget(self.agenda_days_badge)

        agenda_days_hint = QLabel(
            "Clique em um dia para focar o trabalho. Dê duplo clique para abrir direto os serviços daquele dia."
        )
        agenda_days_hint.setObjectName("PageSubtitle")
        agenda_days_hint.setWordWrap(True)

        self.agenda_days_table = QTableWidget(0, 6)
        self.agenda_days_table.setHorizontalHeaderLabels(
            [
                "Data",
                "Programados",
                "Pendentes",
                "Concluídos",
                "Aguardando peça",
                "Não executados",
            ]
        )
        configure_table(self.agenda_days_table, stretch_last=False)
        self.agenda_days_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.agenda_days_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.agenda_days_table.itemSelectionChanged.connect(self._on_agenda_day_selection_changed)
        self.agenda_days_table.itemDoubleClicked.connect(lambda _item: self._open_services_for_selected_day())
        self.agenda_days_table.setMinimumHeight(360)

        agenda_days_layout.addLayout(agenda_days_top)
        agenda_days_layout.addWidget(agenda_days_hint)
        agenda_days_layout.addWidget(self.agenda_days_table)

        agenda_screen_layout.addLayout(agenda_screen_top)
        agenda_screen_layout.addWidget(agenda_screen_hint)
        agenda_screen_layout.addLayout(agenda_summary_layout)
        agenda_screen_layout.addLayout(agenda_actions)
        agenda_screen_layout.addWidget(agenda_days_card)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(760)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        programacoes_tab = QWidget()
        programacoes_layout = QVBoxLayout(programacoes_tab)
        programacoes_layout.setContentsMargins(0, 0, 0, 0)
        programacoes_layout.setSpacing(10)
        programacoes_layout.addWidget(planning_screen_card)
        programacoes_layout.addWidget(schedules_card)

        agenda_tab = QWidget()
        agenda_layout = QVBoxLayout(agenda_tab)
        agenda_layout.setContentsMargins(0, 0, 0, 0)
        agenda_layout.setSpacing(10)
        agenda_layout.addWidget(agenda_screen_card)

        execucao_tab = QWidget()
        execucao_layout = QVBoxLayout(execucao_tab)
        execucao_layout.setContentsMargins(0, 0, 0, 0)
        execucao_layout.setSpacing(10)
        execucao_layout.addWidget(services_screen_card)
        execucao_layout.addWidget(os_screen_card)
        execucao_layout.addWidget(blockers_screen_card)
        execucao_layout.addWidget(action_card)
        execucao_layout.addWidget(details_card, 1)

        governanca_tab = QWidget()
        governanca_layout = QVBoxLayout(governanca_tab)
        governanca_layout.setContentsMargins(0, 0, 0, 0)
        governanca_layout.setSpacing(10)
        governanca_layout.addWidget(responsible_screen_card)
        governanca_layout.addWidget(pieces_screen_card)
        governanca_layout.addWidget(governance_header_card)
        governance_split_layout = QHBoxLayout()
        governance_split_layout.setSpacing(10)
        governance_split_layout.addWidget(responsible_card, 1)
        governance_split_layout.addWidget(material_form_card, 1)
        governanca_layout.addLayout(governance_split_layout)
        governanca_layout.addWidget(materials_card, 1)

        relatorios_tab = QWidget()
        relatorios_layout = QVBoxLayout(relatorios_tab)
        relatorios_layout.setContentsMargins(0, 0, 0, 0)
        relatorios_layout.setSpacing(10)
        relatorios_hint = QLabel("Exporte uma visão gerencial da manutenção filtrando por período, mecânico ou veículo.")
        relatorios_hint.setObjectName("PageSubtitle")
        relatorios_hint.setWordWrap(True)
        relatorios_layout.addWidget(relatorios_hint)
        relatorios_layout.addWidget(reports_card)
        relatorios_layout.addStretch(1)

        self.tab_programacoes_index = self.tabs.addTab(programacoes_tab, "Planejamento")
        self.tab_agenda_index = self.tabs.addTab(agenda_tab, "Agenda")
        self.tab_execucao_index = self.tabs.addTab(execucao_tab, "Serviços")
        self.tab_governanca_index = self.tabs.addTab(governanca_tab, "Responsável e Peças")
        self.tab_relatorios_index = self.tabs.addTab(relatorios_tab, "Relatório")
        self.tabs.tabBar().hide()

        layout.addWidget(header_frame)
        layout.addLayout(cards_layout)
        layout.addWidget(filter_card)
        layout.addWidget(screens_card)
        layout.addWidget(calendar_card)
        layout.addWidget(self.tabs, 1)

        self._set_action_controls_enabled(False)
        self._set_management_controls_enabled(False)
        self._populate_material_combo()
        self._populate_mechanic_combo()
        self._populate_report_filters()
        self._update_report_filter_visibility()
        self._bind_summary_cards_to_actions()
        self._refresh_calendar_selection_badge()

    def set_loading_state(self, loading: bool):
        # Nesta tela o skeleton animado atrapalha leitura operacional.
        # Mantemos sempre oculto para priorizar visibilidade das tabelas.
        _ = loading
        self.schedules_skeleton.hide_skeleton()
        self.materials_skeleton.hide_skeleton()
        self.details_skeleton.hide_skeleton()
        self.calendar_skeleton.hide_skeleton()

    def refresh(self):
        month = self.month_input.date()
        year = month.year()
        month_number = month.month()
        self._load_reference_data()
        self.overview = self.api_client.get_maintenance_overview(year=year, month=month_number) or {}
        self.apply_filters()

    def create_quick_schedule(self):
        dialog = QuickMaintenanceDialog(self.api_client, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.refresh()
        self.data_changed.emit()
        show_notice(self, "Manutenção agendada", "A programação foi criada e a ordem de serviço já está disponível na tela de OS.", icon_name="ok")

    def clear_filters(self):
        self.source_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.apply_filters()

    def _bind_summary_cards_to_actions(self):
        self.schedules_card.setToolTip("Abrir tela de Programações")
        self.items_card.setToolTip("Abrir tela de Serviços com todos os itens")
        self.pending_card.setToolTip("Abrir tela de Serviços focando pendências")
        self.installed_card.setToolTip("Abrir tela de Serviços focando conclusões")
        self.overdue_os_card.setToolTip("Abrir área de OS em atraso")
        self.waiting_parts_card.setToolTip("Abrir área de Peças aguardando liberação")
        self.no_responsible_card.setToolTip("Abrir área de Responsáveis sem definição")
        self.blockers_card.setToolTip("Abrir área de Bloqueios")

        self.schedules_card.mousePressEvent = lambda event: self._handle_summary_card_click("PROGRAMACOES")
        self.items_card.mousePressEvent = lambda event: self._handle_summary_card_click("ITENS")
        self.pending_card.mousePressEvent = lambda event: self._handle_summary_card_click("PENDENTES")
        self.installed_card.mousePressEvent = lambda event: self._handle_summary_card_click("INSTALADOS")
        self.overdue_os_card.mousePressEvent = lambda event: self._handle_summary_card_click("OS_ATRASADAS")
        self.waiting_parts_card.mousePressEvent = lambda event: self._handle_summary_card_click("AGUARDANDO_PECA")
        self.no_responsible_card.mousePressEvent = lambda event: self._handle_summary_card_click("SEM_RESPONSAVEL")
        self.blockers_card.mousePressEvent = lambda event: self._handle_summary_card_click("BLOQUEIOS")

    def _handle_summary_card_click(self, key: str):
        self._clear_calendar_day_scope()
        if key == "PROGRAMACOES":
            self._open_maintenance_screen("PROGRAMACOES")
            self._refresh_planning_screen_summary()
            return
        if key == "ITENS":
            self._open_maintenance_screen("SERVICOS")
            self._set_item_status_filter("ALL")
            self.render_selected_schedule_items()
            return
        if key == "PENDENTES":
            self._open_maintenance_screen("SERVICOS")
            self._set_item_status_filter("PENDENTES")
        elif key == "INSTALADOS":
            self._open_maintenance_screen("SERVICOS")
            self._set_item_status_filter("INSTALADO")
        elif key == "OS_ATRASADAS":
            self._set_os_filter("ATRASADAS")
            self._open_maintenance_screen("OS")
        elif key == "AGUARDANDO_PECA":
            self._set_pieces_filter("AGUARDANDO_MATERIAL")
            self._open_maintenance_screen("PECAS")
        elif key == "SEM_RESPONSAVEL":
            self._set_responsible_filter("SEM_RESPONSAVEL")
            self._open_maintenance_screen("RESPONSAVEIS")
        elif key == "BLOQUEIOS":
            self._set_blockers_filter("COM_TRAVAMENTO")
            self._open_maintenance_screen("BLOQUEIOS")
        else:
            self._open_maintenance_screen("SERVICOS")
            self._set_item_status_filter("ALL")
        self.render_selected_schedule_items()

    def _clear_calendar_day_scope(self):
        self.selected_calendar_day_iso = None
        self.calendar_table.clearSelection()
        self._refresh_calendar_selection_badge()
        self._render_agenda_days_table()
        self.render_selected_schedule_items()
        self._render_os_table()

    def _open_maintenance_screen(self, screen_key: str):
        labels = {
            "PROGRAMACOES": "Programações",
            "AGENDA": "Agenda",
            "SERVICOS": "Serviços",
            "RESPONSAVEIS": "Responsáveis",
            "PECAS": "Peças",
            "OS": "OS",
            "BLOQUEIOS": "Bloqueios",
        }
        label = labels.get(screen_key, "Home da manutenção")
        self.current_screen_badge.setText(f"Tela atual: {label}")
        if screen_key == "PROGRAMACOES":
            self.tabs.setCurrentIndex(self.tab_programacoes_index)
            self.scroll_area.ensureWidgetVisible(self.planning_screen_card, 24, 24)
            return
        if screen_key == "AGENDA":
            self.tabs.setCurrentIndex(self.tab_agenda_index)
            self.scroll_area.ensureWidgetVisible(self.agenda_screen_card, 24, 24)
            return
        if screen_key == "SERVICOS":
            self.tabs.setCurrentIndex(self.tab_execucao_index)
            self.scroll_area.ensureWidgetVisible(self.services_screen_card, 24, 24)
            return
        if screen_key == "BLOQUEIOS":
            self.tabs.setCurrentIndex(self.tab_execucao_index)
            self.scroll_area.ensureWidgetVisible(self.blockers_screen_card, 24, 24)
            return
        if screen_key == "OS":
            self.tabs.setCurrentIndex(self.tab_execucao_index)
            self.scroll_area.ensureWidgetVisible(self.os_screen_card, 24, 24)
            return
        if screen_key == "RESPONSAVEIS":
            self.tabs.setCurrentIndex(self.tab_governanca_index)
            self.scroll_area.ensureWidgetVisible(self.responsible_screen_card, 24, 24)
            return
        if screen_key == "PECAS":
            self.tabs.setCurrentIndex(self.tab_governanca_index)
            self.scroll_area.ensureWidgetVisible(self.pieces_screen_card, 24, 24)
            return

    def _go_to_maintenance_home(self):
        self.current_screen_badge.setText("Tela atual: Home da manutenção")
        self.scroll_area.verticalScrollBar().setValue(0)

    def _set_responsible_filter(self, filter_code: str):
        index = self.responsible_filter_combo.findData(filter_code)
        if index < 0:
            index = 0
        self.responsible_filter_combo.setCurrentIndex(index)

    def _set_pieces_filter(self, filter_code: str):
        index = self.pieces_filter_combo.findData(filter_code)
        if index < 0:
            index = 0
        self.pieces_filter_combo.setCurrentIndex(index)

    def _set_os_filter(self, filter_code: str):
        index = self.os_filter_combo.findData(filter_code)
        if index < 0:
            index = 0
        self.os_filter_combo.setCurrentIndex(index)

    def _set_blockers_filter(self, filter_code: str):
        index = self.blockers_filter_combo.findData(filter_code)
        if index < 0:
            index = 0
        self.blockers_filter_combo.setCurrentIndex(index)

    def _open_services_for_selected_day(self):
        if not self.selected_calendar_day_iso:
            show_notice(self, "Dia obrigatório", "Selecione um dia da agenda para abrir os serviços.", icon_name="warning")
            return
        self._open_maintenance_screen("SERVICOS")
        self.render_selected_schedule_items()

    def _set_item_status_filter(self, status_code: str):
        index = self.item_status_filter.findData(status_code)
        if index < 0:
            index = 0
        self.item_status_filter.setCurrentIndex(index)

    def _load_reference_data(self):
        try:
            self.mechanics = list(self.api_client.get_mechanics() or [])
        except Exception:
            self.mechanics = []
        try:
            self.report_vehicles = list(self.api_client.get_equipment(ativos=True) or [])
        except Exception:
            self.report_vehicles = []
        try:
            self.material_catalog = list(self.api_client.get_materials(ativos="true") or [])
        except Exception:
            self.material_catalog = []
        self._populate_mechanic_combo()
        self._populate_material_combo()
        self._populate_report_filters()

    def _populate_mechanic_combo(self):
        current_value = self.mechanic_combo.currentData() if hasattr(self, "mechanic_combo") else None
        if not hasattr(self, "mechanic_combo"):
            return
        self.mechanic_combo.blockSignals(True)
        try:
            self.mechanic_combo.clear()
            self.mechanic_combo.addItem("Sem mecânico fixo", None)
            for mechanic in sorted(self.mechanics, key=lambda row: (row.get("nome") or row.get("login") or "").upper()):
                name = mechanic.get("nome") or mechanic.get("login") or f"Mecânico {mechanic.get('id')}"
                self.mechanic_combo.addItem(name, int(mechanic.get("id")))
            index = self.mechanic_combo.findData(current_value)
            if index < 0:
                index = 0
            self.mechanic_combo.setCurrentIndex(index)
        finally:
            self.mechanic_combo.blockSignals(False)

    def _populate_material_combo(self):
        current_value = self.material_combo.currentData() if hasattr(self, "material_combo") else None
        if not hasattr(self, "material_combo"):
            return
        self.material_combo.blockSignals(True)
        try:
            self.material_combo.clear()
            self.material_combo.addItem("Selecione um material", None)
            for material in sorted(self.material_catalog, key=lambda row: (row.get("referencia") or "").upper()):
                reference = material.get("referencia") or f"ID {material.get('id')}"
                description = material.get("descricao") or "-"
                stock = int(material.get("quantidade_estoque") or 0)
                label = f"{reference} | {description} | saldo {stock}"
                self.material_combo.addItem(label, material)
            index = self.material_combo.findData(current_value)
            if index < 0:
                index = 0
            self.material_combo.setCurrentIndex(index)
        finally:
            self.material_combo.blockSignals(False)
        self._sync_material_form_with_link()

    def _populate_report_filters(self):
        if not hasattr(self, "report_mechanic_combo") or not hasattr(self, "report_vehicle_combo"):
            return
        current_mechanic = self.report_mechanic_combo.currentData()
        current_vehicle = self.report_vehicle_combo.currentData()

        self.report_mechanic_combo.blockSignals(True)
        self.report_vehicle_combo.blockSignals(True)
        try:
            self.report_mechanic_combo.clear()
            self.report_mechanic_combo.addItem("Todos os mecânicos", None)
            for mechanic in sorted(self.mechanics, key=lambda row: (row.get("nome") or row.get("login") or "").upper()):
                name = mechanic.get("nome") or mechanic.get("login") or f"Mecânico {mechanic.get('id')}"
                self.report_mechanic_combo.addItem(name, int(mechanic.get("id")))

            self.report_vehicle_combo.clear()
            self.report_vehicle_combo.addItem("Todos os veículos", None)
            for vehicle in sorted(self.report_vehicles, key=lambda row: (row.get("frota") or "").upper()):
                label = f"{vehicle.get('frota') or '-'} | {vehicle.get('placa') or '-'} | {vehicle.get('modelo') or '-'}"
                self.report_vehicle_combo.addItem(label, int(vehicle.get("id")))

            mechanic_index = self.report_mechanic_combo.findData(current_mechanic)
            vehicle_index = self.report_vehicle_combo.findData(current_vehicle)
            self.report_mechanic_combo.setCurrentIndex(mechanic_index if mechanic_index >= 0 else 0)
            self.report_vehicle_combo.setCurrentIndex(vehicle_index if vehicle_index >= 0 else 0)
        finally:
            self.report_mechanic_combo.blockSignals(False)
            self.report_vehicle_combo.blockSignals(False)

    def _mechanic_name_by_id(self, mechanic_id) -> str:
        if not mechanic_id:
            return "Sem responsável"
        for mechanic in self.mechanics:
            if int(mechanic.get("id") or 0) == int(mechanic_id):
                return mechanic.get("nome") or mechanic.get("login") or f"Mecânico {mechanic_id}"
        return f"Mecânico {mechanic_id}"

    def _responsible_metrics_map(self) -> dict[int, dict]:
        metrics: dict[int, dict] = defaultdict(
            lambda: {
                "open_orders": 0,
                "overdue_orders": 0,
                "schedules": 0,
            }
        )
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")
        for schedule in (self.overview or {}).get("programacoes") or []:
            mechanic_id = int(schedule.get("assigned_mechanic_user_id") or 0)
            if not mechanic_id:
                continue
            row = metrics[mechanic_id]
            row["schedules"] += 1
            for item in schedule.get("itens") or []:
                status = str(item.get("status") or "").upper()
                if status not in {"INSTALADO", "CANCELADO"}:
                    row["open_orders"] += 1
                scheduled_date = str(item.get("scheduled_date") or "")[:10]
                work_order = item.get("work_order") or {}
                if (
                    int(work_order.get("id") or 0)
                    and scheduled_date
                    and scheduled_date < today_iso
                    and status not in {"INSTALADO", "CANCELADO"}
                ):
                    row["overdue_orders"] += 1
        return metrics

    def _render_responsible_table(self):
        schedules = list(self.filtered_schedules)
        filter_code = self.responsible_filter_combo.currentData() if hasattr(self, "responsible_filter_combo") else "ALL"
        if filter_code == "SEM_RESPONSAVEL":
            schedules = [row for row in schedules if not row.get("assigned_mechanic_user_id")]
        elif filter_code == "COM_RESPONSAVEL":
            schedules = [row for row in schedules if row.get("assigned_mechanic_user_id")]

        metrics_map = self._responsible_metrics_map()
        self.responsible_table.setSortingEnabled(False)
        self.responsible_table.setUpdatesEnabled(False)
        self.responsible_table.blockSignals(True)
        selected_row = -1
        try:
            self.responsible_table.setRowCount(len(schedules))
            for row_index, schedule in enumerate(schedules):
                schedule_id = int(schedule.get("id") or 0)
                if self.selected_schedule_id and schedule_id == self.selected_schedule_id:
                    selected_row = row_index
                mechanic_id = int(schedule.get("assigned_mechanic_user_id") or 0)
                metrics = metrics_map.get(mechanic_id) or {"open_orders": 0, "overdue_orders": 0, "schedules": 0}
                has_responsible = mechanic_id > 0
                values = [
                    schedule_id,
                    schedule.get("title") or "-",
                    self._mechanic_name_by_id(mechanic_id),
                    "Com responsável" if has_responsible else "Sem responsável",
                    int(metrics.get("open_orders") or 0),
                    int(metrics.get("overdue_orders") or 0),
                    int(metrics.get("schedules") or 0),
                ]
                for column, value in enumerate(values):
                    payload = schedule if column == 0 else None
                    self.responsible_table.setItem(row_index, column, make_table_item(value, payload=payload))
            if selected_row >= 0:
                self.responsible_table.selectRow(selected_row)
        finally:
            self.responsible_table.blockSignals(False)
            self.responsible_table.setUpdatesEnabled(True)
            self.responsible_table.setSortingEnabled(True)
        self._refresh_responsible_screen_summary(schedules, metrics_map)

    def _refresh_responsible_screen_summary(self, schedules: list[dict], metrics_map: dict[int, dict]):
        total_without = sum(1 for row in self.filtered_schedules if not row.get("assigned_mechanic_user_id"))
        total_with = sum(1 for row in self.filtered_schedules if row.get("assigned_mechanic_user_id"))
        total_open = sum(int(values.get("open_orders") or 0) for values in metrics_map.values())
        total_overdue = sum(int(values.get("overdue_orders") or 0) for values in metrics_map.values())
        filter_label = str(self.responsible_filter_combo.currentText() or "Todos os planejamentos")
        self.responsible_filter_badge.setText(f"Filtro: {filter_label}")
        self.responsible_load_badge.setText(f"Sem responsável: {total_without} | Com responsável: {total_with}")
        self.responsible_queue_badge.setText(f"OS abertas: {total_open} | OS atrasadas: {total_overdue}")

        selected_schedule = self._selected_schedule()
        if selected_schedule:
            title = str(selected_schedule.get("title") or f"#{selected_schedule.get('id')}")
            self.responsible_screen_badge.setText(f"Planejamento: {title}")
            self.responsible_scope_badge.setText("Escopo: planejamento selecionado")
        else:
            self.responsible_screen_badge.setText(f"{len(schedules)} planejamento(s) na tela")
            self.responsible_scope_badge.setText("Escopo: todos os planejamentos filtrados")

    def _update_report_filter_visibility(self):
        report_type = str(self.report_type_combo.currentData() or "mensal")
        needs_mechanic = report_type == "mecanico"
        needs_vehicle = report_type == "veiculo"
        self.report_mechanic_combo.setEnabled(needs_mechanic)
        self.report_vehicle_combo.setEnabled(needs_vehicle)
        if not needs_mechanic:
            self.report_mechanic_combo.setCurrentIndex(0)
        if not needs_vehicle:
            self.report_vehicle_combo.setCurrentIndex(0)

    def export_maintenance_report_pdf(self):
        month = self.month_input.date()
        report_type = str(self.report_type_combo.currentData() or "mensal")
        mechanic_id = self.report_mechanic_combo.currentData()
        vehicle_id = self.report_vehicle_combo.currentData()
        report_label = REPORT_TYPE_LABELS.get(report_type, "manutencao")
        safe_label = report_label.lower().replace(" ", "_")
        default_name = make_default_export_path(f"relatorio_{safe_label}", "pdf")

        filename = choose_pdf_save_path(self, "Exportar relatório de manutenção", default_name)
        if not filename:
            return

        year = month.year()
        month_number = month.month()

        def task(progress):
            progress(8, "Preparando parametros do relatorio")
            progress(28, "Solicitando PDF ao backend")
            self.api_client.download_maintenance_pdf(
                filename,
                report_type=report_type,
                year=year,
                month=month_number,
                mechanic_id=int(mechanic_id) if mechanic_id else None,
                vehicle_id=int(vehicle_id) if vehicle_id else None,
            )
            progress(88, "Finalizando arquivo PDF")
            return filename

        start_export_task_with_preset(
            self,
            "maintenance_pdf",
            task,
        )

    def apply_filters(self):
        schedules = list((self.overview or {}).get("programacoes") or [])
        source_filter = self.source_filter.currentData()
        status_filter = self.status_filter.currentData()

        if source_filter and source_filter != "ALL":
            schedules = [row for row in schedules if _schedule_source_code(row) == source_filter]
        if status_filter and status_filter != "ALL":
            schedules = [row for row in schedules if str(row.get("status") or "").upper() == status_filter]

        self.filtered_schedules = schedules
        self.selected_calendar_day_iso = None
        if self.selected_schedule_id and not any(int(row.get("id") or 0) == self.selected_schedule_id for row in schedules):
            self.selected_schedule_id = None
        if self.selected_schedule_id is None and schedules:
            self.selected_schedule_id = int(schedules[0].get("id"))

        self._render_summary()
        self._render_schedules_table()
        self._render_os_table()
        self._render_blockers_table()
        self._render_responsible_table()
        self.render_selected_schedule_items()
        self.render_selected_schedule_materials()
        self._render_calendar_table()
        self._render_agenda_days_table()

    def create_schedule(self):
        try:
            dialog = MaintenanceScheduleCreateDialog(self.api_client, self)
        except Exception as exc:
            show_notice(self, "Falha ao abrir criação", str(exc), icon_name="warning")
            return
        if not dialog.exec() or not dialog.result_payload:
            return

        button = self.new_schedule_button
        button.setEnabled(False)
        button.setText("Criando...")
        try:
            created = self.api_client.create_maintenance_schedule(dialog.result_payload)
            created_id = int((created or {}).get("id") or 0)
            if created_id:
                self.selected_schedule_id = created_id
            start_date = str(dialog.result_payload.get("start_date") or "")
            if start_date:
                date_value = QDate.fromString(start_date, "yyyy-MM-dd")
                if date_value.isValid():
                    self.month_input.setDate(date_value)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Planejamento criado", "Planejamento registrado e pronto para distribuição na agenda.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao criar programação", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Nova programação")

    def redistribute_selected_schedule(self):
        schedule = self._selected_schedule()
        if not schedule:
            show_notice(self, "Seleção obrigatória", "Selecione uma programação para redistribuir.", icon_name="warning")
            return

        start_date = self.redistribute_start_input.date().toString("yyyy-MM-dd")
        daily_capacity = int(self.redistribute_capacity_input.value())
        button = self.redistribute_button
        button.setEnabled(False)
        button.setText("Aplicando...")
        try:
            self.api_client.program_maintenance_schedule(
                int(schedule.get("id")),
                {"start_date": start_date, "daily_capacity": daily_capacity},
            )
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Agenda recalculada", "Distribuição atualizada pela nova data inicial e capacidade diária.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha na redistribuicao", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Recalcular agenda")

    def move_selected_items(self):
        selected_items = self._selected_item_payloads()
        if not selected_items:
            show_notice(self, "Seleção obrigatória", "Selecione um ou mais itens para mover.", icon_name="warning")
            return

        target_date = self.move_date_input.date().toString("yyyy-MM-dd")
        reason = self.move_reason_input.text().strip()
        if not reason:
            show_notice(self, "Motivo obrigatório", "Explique o motivo antes de reprogramar os itens.", icon_name="warning")
            return
        moved = 0
        skipped = 0
        errors: list[str] = []
        for item in selected_items:
            status = str(item.get("status") or "").upper()
            if status in {"INSTALADO", "CANCELADO"}:
                skipped += 1
                continue
            try:
                self.api_client.reprogram_maintenance_item(
                    int(item.get("id")),
                    {"scheduled_date": target_date, "reason": reason},
                )
                moved += 1
            except Exception as exc:
                errors.append(str(exc))

        if moved:
            self.move_reason_input.clear()
            self.refresh()
            self.data_changed.emit()
        summary = f"Itens reprogramados: {moved} | ignorados: {skipped}"
        if errors:
            summary += f" | falhas: {len(errors)}"
        icon = "dashboard" if moved else "warning"
        show_notice(self, "Reprogramação em lote", summary, icon_name=icon)

    def remove_selected_items(self):
        selected_items = self._selected_item_payloads()
        if not selected_items:
            show_notice(self, "Seleção obrigatória", "Selecione um ou mais itens para retirar.", icon_name="warning")
            return

        removed = 0
        skipped = 0
        errors: list[str] = []
        for item in selected_items:
            status = str(item.get("status") or "").upper()
            if status == "INSTALADO":
                skipped += 1
                continue
            try:
                self.api_client.update_maintenance_item(
                    int(item.get("id")),
                    {
                        "status": "CANCELADO",
                        "observation": "Retirado do cronograma no desktop.",
                    },
                )
                removed += 1
            except Exception as exc:
                errors.append(str(exc))

        if removed:
            self.refresh()
            self.data_changed.emit()
        summary = f"Itens retirados: {removed} | ignorados: {skipped}"
        if errors:
            summary += f" | falhas: {len(errors)}"
        icon = "dashboard" if removed else "warning"
        show_notice(self, "Retirada do cronograma", summary, icon_name=icon)

    def export_selected_work_order_pdf(self):
        selected_items = self._selected_item_payloads()
        if not selected_items:
            show_notice(self, "Seleção obrigatória", "Selecione um item com OS para exportar.", icon_name="warning")
            return
        self._export_item_work_order_pdf(selected_items[0])

    def _export_item_work_order_pdf(self, item: dict):
        work_order = (item.get("work_order") or {})
        work_order_id = int(work_order.get("id") or 0)
        order_number = str(work_order.get("order_number") or "os")
        if not work_order_id:
            show_notice(self, "OS indisponível", "Este item ainda não possui ordem de serviço formal.", icon_name="warning")
            return

        default_name = make_default_export_path(f"ordem_servico_{order_number.lower().replace('-', '_')}", "pdf")
        filename = choose_pdf_save_path(self, "Exportar ordem de serviço", default_name)
        if not filename:
            return

        def task(progress):
            progress(12, "Preparando ordem de serviço")
            progress(38, "Solicitando PDF rico da OS")
            self.api_client.download_maintenance_work_order_pdf(work_order_id, filename)
            progress(92, "Finalizando arquivo PDF")
            return filename

        start_export_task_with_preset(self, "maintenance_pdf", task)

    def export_selected_os_from_screen(self):
        item = self._selected_os_payload()
        if not item:
            show_notice(self, "Seleção obrigatória", "Selecione uma OS da tabela para exportar.", icon_name="warning")
            return
        self._export_item_work_order_pdf(item)

    def assign_schedule_mechanic(self):
        schedule = self._selected_schedule()
        if not schedule:
            show_notice(self, "Seleção obrigatória", "Selecione um planejamento para definir o responsável.", icon_name="warning")
            return

        start_date = str(schedule.get("start_date") or QDate.currentDate().toString("yyyy-MM-dd"))
        daily_capacity = int(schedule.get("daily_capacity") or 1)
        mechanic_id = self.mechanic_combo.currentData()
        payload = {
            "start_date": start_date,
            "daily_capacity": max(1, daily_capacity),
            "assigned_mechanic_user_id": mechanic_id if mechanic_id is not None else "",
        }
        button = self.assign_mechanic_button
        button.setEnabled(False)
        button.setText("Aplicando...")
        try:
            self.api_client.program_maintenance_schedule(int(schedule.get("id")), payload)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Responsável definido", "Responsável atualizado no planejamento selecionado.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao aplicar mecânico", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Definir responsável")

    def link_material_for_selected_schedule(self):
        schedule = self._selected_schedule()
        if not schedule:
            show_notice(self, "Seleção obrigatória", "Selecione um planejamento para salvar a peça.", icon_name="warning")
            return

        material = self.material_combo.currentData()
        if not isinstance(material, dict) or not material.get("id"):
            show_notice(self, "Peça obrigatória", "Selecione uma peça/material válida.", icon_name="warning")
            return

        payload = {
            "material_id": int(material.get("id")),
            "quantity_per_vehicle": int(self.material_qty_input.value()),
            "status": self.material_status_combo.currentData(),
            "observation": (self.material_observation_input.text() or "").strip() or None,
        }
        button = self.link_material_button
        button.setEnabled(False)
        button.setText("Salvando...")
        try:
            self.api_client.link_maintenance_schedule_material(int(schedule.get("id")), payload)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Peça salva", "Controle de peças atualizado no planejamento.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao salvar peça", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Salvar peça")

    def apply_material_suggestion_for_selected_schedule(self):
        schedule = self._selected_schedule()
        if not schedule:
            show_notice(self, "Seleção obrigatória", "Selecione um planejamento para sugerir a peça.", icon_name="warning")
            return
        button = self.material_suggest_button
        button.setEnabled(False)
        button.setText("Sugerindo...")
        try:
            suggestion = self.api_client.get_maintenance_material_suggestion(int(schedule.get("id"))) or {}
            material = suggestion.get("material") or {}
            material_id = int(material.get("id") or 0)
            if not material_id:
                show_notice(self, "Sem sugestão", "O sistema não encontrou peça compatível para este planejamento.", icon_name="warning")
                return
            combo_index = -1
            for index in range(self.material_combo.count()):
                payload = self.material_combo.itemData(index)
                if isinstance(payload, dict) and int(payload.get("id") or 0) == material_id:
                    combo_index = index
                    break
            if combo_index >= 0:
                self.material_combo.setCurrentIndex(combo_index)
            self.material_qty_input.setValue(max(1, int(suggestion.get("quantity_per_vehicle") or 1)))
            status_index = self.material_status_combo.findData(str(suggestion.get("status") or "").upper())
            self.material_status_combo.setCurrentIndex(status_index if status_index >= 0 else 0)
            self.material_observation_input.setText(str(suggestion.get("reason") or "Sugestão automática aplicada."))
            self.material_suggestion_badge.setText(
                f"Sugestão de peça: {(material.get('referencia') or 'Peça')} | {suggestion.get('reason') or 'Histórico analisado'}"
            )
            show_notice(self, "Sugestão aplicada", "A peça sugerida foi carregada no formulário para conferência.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha na sugestão de peça", str(exc), icon_name="warning")
        finally:
            button.setEnabled(True)
            button.setText("Aplicar sugestão")

    def render_selected_schedule_materials(self):
        schedule = self._selected_schedule()
        if not schedule:
            self.materials_table.setRowCount(0)
            self.materials_badge.setText("0 peças")
            self.governance_badge.setText("Responsável e peças: selecione um planejamento")
            self.material_suggestion_badge.setText("Sugestão de peça: selecione um planejamento para o sistema analisar o histórico.")
            self.management_help_label.setText(
                "As definições de responsável e peça só são liberadas depois que um planejamento é selecionado."
            )
            self._set_management_controls_enabled(False)
            self._refresh_pieces_screen_summary(None, [])
            return

        self._set_management_controls_enabled(True)
        title = str(schedule.get("title") or f"Programação #{schedule.get('id')}")
        package_label = str(schedule.get("package_reference_label") or "Sem pacote")
        self.governance_badge.setText(f"#{schedule.get('id')} | {title} | {package_label}")
        self.management_help_label.setText(self._management_context_text(schedule))

        assigned_id = schedule.get("assigned_mechanic_user_id")
        current_mechanic_index = self.mechanic_combo.findData(assigned_id)
        self.mechanic_combo.setCurrentIndex(current_mechanic_index if current_mechanic_index >= 0 else 0)

        materials = self._visible_material_links_for_current_context(schedule)
        self.materials_table.setSortingEnabled(False)
        self.materials_table.setUpdatesEnabled(False)
        self.materials_table.blockSignals(True)
        try:
            self.materials_table.setRowCount(len(materials))
            for row_index, link in enumerate(materials):
                material = link.get("material") or {}
                values = [
                    link.get("id"),
                    material.get("referencia") or "-",
                    material.get("descricao") or "-",
                    material.get("quantidade_estoque") if material.get("quantidade_estoque") is not None else "-",
                    link.get("quantity_per_vehicle") or 0,
                    link.get("quantity_required") or 0,
                    link.get("quantity_reserved") or 0,
                    MATERIAL_STATUS_LABELS.get(str(link.get("status") or "").upper(), link.get("status") or "-"),
                    link.get("observation") or "-",
                ]
                for column, value in enumerate(values):
                    self.materials_table.setItem(row_index, column, make_table_item(value))
        finally:
            self.materials_table.blockSignals(False)
            self.materials_table.setUpdatesEnabled(True)
            self.materials_table.setSortingEnabled(True)

        summary = self._material_summary_for_schedule(schedule)
        self.materials_badge.setText(f"{len(materials)} peças | {summary}")
        self.material_suggestion_badge.setText("Sugestão de peça: use o botão para buscar a peça mais provável para este planejamento.")
        self._sync_material_form_with_link()
        self._refresh_pieces_screen_summary(schedule, materials)

    def _visible_os_items_for_current_context(self, schedule: dict) -> list[dict]:
        items = list(schedule.get("itens") or [])
        if self.selected_calendar_day_iso:
            items = [item for item in items if str(item.get("scheduled_date") or "")[:10] == self.selected_calendar_day_iso]
        items = [item for item in items if int(((item.get("work_order") or {}).get("id") or 0)) > 0]
        filter_code = self.os_filter_combo.currentData() if hasattr(self, "os_filter_combo") else "ALL"
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")

        def is_open(row: dict) -> bool:
            status = str(row.get("status") or "").upper()
            return status not in {"INSTALADO", "CANCELADO"}

        if filter_code == "ABERTAS":
            items = [item for item in items if is_open(item)]
        elif filter_code == "ATRASADAS":
            items = [
                item
                for item in items
                if is_open(item) and str(item.get("scheduled_date") or "")[:10] and str(item.get("scheduled_date") or "")[:10] < today_iso
            ]
        elif filter_code == "BLOQUEADAS":
            items = [item for item in items if str(item.get("status") or "").upper() == "AGUARDANDO_MATERIAL"]
        elif filter_code == "CONCLUIDAS":
            items = [item for item in items if str(item.get("status") or "").upper() == "INSTALADO"]
        return items

    def _render_os_table(self):
        schedule = self._selected_schedule()
        if not schedule:
            self.os_table.setRowCount(0)
            self._refresh_os_screen_summary(None, [])
            return

        items = self._visible_os_items_for_current_context(schedule)
        material_text = self._material_summary_for_schedule(schedule)
        self.os_table.setSortingEnabled(False)
        self.os_table.setUpdatesEnabled(False)
        self.os_table.blockSignals(True)
        try:
            self.os_table.setRowCount(len(items))
            for row_index, item in enumerate(items):
                work_order = item.get("work_order") or {}
                vehicle = item.get("vehicle") or {}
                values = [
                    item.get("id"),
                    work_order.get("order_number") or "-",
                    self._vehicle_table_label(vehicle),
                    self._item_label(item, schedule),
                    self._format_date(item.get("scheduled_date")),
                    ITEM_STATUS_LABELS.get(str(item.get("status") or "").upper(), item.get("status") or "-"),
                    self._execution_label(item),
                    material_text,
                ]
                for column, value in enumerate(values):
                    payload = item if column == 0 else None
                    self.os_table.setItem(row_index, column, make_table_item(value, payload=payload))
        finally:
            self.os_table.blockSignals(False)
            self.os_table.setUpdatesEnabled(True)
            self.os_table.setSortingEnabled(True)
        self._refresh_os_screen_summary(schedule, items)

    def _selected_os_payload(self) -> dict | None:
        model = self.os_table.selectionModel()
        if not model:
            return None
        selected_rows = model.selectedRows()
        if not selected_rows:
            current_row = self.os_table.currentRow()
            if current_row < 0:
                return None
            cell = self.os_table.item(current_row, 0)
            return cell.data(Qt.UserRole) if cell else None
        cell = self.os_table.item(selected_rows[0].row(), 0)
        return cell.data(Qt.UserRole) if cell else None

    def _update_os_selection_badge(self):
        schedule = self._selected_schedule()
        if schedule:
            items = self._visible_os_items_for_current_context(schedule)
            self._refresh_os_screen_summary(schedule, items)

    def _refresh_os_screen_summary(self, schedule: dict | None, items: list[dict]):
        if not schedule:
            self.os_screen_badge.setText("Nenhum planejamento selecionado")
            self.os_scope_badge.setText("Escopo: selecione um planejamento")
            self.os_filter_badge.setText("Filtro: todas as OS")
            self.os_volume_badge.setText("OS: 0 | Selecionadas: 0")
            self.os_blockers_badge.setText("Atrasadas: 0 | Bloqueadas: 0 | Concluídas: 0")
            self.os_export_button.setEnabled(False)
            return

        selected_count = 1 if self._selected_os_payload() else 0
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")
        overdue = sum(
            1
            for item in items
            if str(item.get("status") or "").upper() not in {"INSTALADO", "CANCELADO"}
            and str(item.get("scheduled_date") or "")[:10]
            and str(item.get("scheduled_date") or "")[:10] < today_iso
        )
        blocked = sum(1 for item in items if str(item.get("status") or "").upper() == "AGUARDANDO_MATERIAL")
        completed = sum(1 for item in items if str(item.get("status") or "").upper() == "INSTALADO")
        title = str(schedule.get("title") or f"#{schedule.get('id')}")
        self.os_screen_badge.setText(f"Planejamento: {title}")
        if self.selected_calendar_day_iso:
            self.os_scope_badge.setText(f"Escopo: dia {self._format_date(self.selected_calendar_day_iso)}")
        else:
            self.os_scope_badge.setText("Escopo: todos os dias do planejamento")
        self.os_filter_badge.setText(f"Filtro: {str(self.os_filter_combo.currentText() or 'Todas as OS')}")
        self.os_volume_badge.setText(f"OS: {len(items)} | Selecionadas: {selected_count}")
        self.os_blockers_badge.setText(f"Atrasadas: {overdue} | Bloqueadas: {blocked} | Concluídas: {completed}")
        self.os_export_button.setEnabled(selected_count > 0)

    def _build_blocker_rows(self) -> list[dict]:
        rows: list[dict] = []
        for schedule in self.filtered_schedules:
            blockers = schedule.get("bloqueios_resumo") or {}
            mechanic_name = self._mechanic_name_by_id(schedule.get("assigned_mechanic_user_id"))
            package_label = str(schedule.get("package_reference_label") or "sem pacote")
            details: list[str] = []
            if blockers.get("sem_responsavel") or not schedule.get("assigned_mechanic_user_id"):
                details.append("sem responsável definido")
            if int(blockers.get("materiais_bloqueados") or 0):
                details.append(f"{int(blockers.get('materiais_bloqueados') or 0)} peça(s) travando")
            if int(blockers.get("ordens_bloqueadas") or 0):
                details.append(f"{int(blockers.get('ordens_bloqueadas') or 0)} OS bloqueada(s)")
            if not details:
                continue
            primary_type = "Com travamento"
            if blockers.get("sem_responsavel") or not schedule.get("assigned_mechanic_user_id"):
                primary_type = "Sem responsável"
            elif int(blockers.get("materiais_bloqueados") or 0):
                primary_type = "Aguardando peça"
            elif int(blockers.get("ordens_bloqueadas") or 0):
                primary_type = "OS bloqueada"
            rows.append(
                {
                    "schedule": schedule,
                    "primary_type": primary_type,
                    "details": " | ".join(details),
                    "responsible": mechanic_name,
                    "blocked_materials": int(blockers.get("materiais_bloqueados") or 0),
                    "blocked_orders": int(blockers.get("ordens_bloqueadas") or 0),
                    "package_label": package_label,
                    "has_no_responsible": bool(blockers.get("sem_responsavel") or not schedule.get("assigned_mechanic_user_id")),
                }
            )
        return rows

    def _visible_blocker_rows(self) -> list[dict]:
        rows = self._build_blocker_rows()
        filter_code = self.blockers_filter_combo.currentData() if hasattr(self, "blockers_filter_combo") else "ALL"
        if filter_code == "SEM_RESPONSAVEL":
            rows = [row for row in rows if row.get("has_no_responsible")]
        elif filter_code == "AGUARDANDO_PECA":
            rows = [row for row in rows if int(row.get("blocked_materials") or 0) > 0]
        elif filter_code == "OS_BLOQUEADAS":
            rows = [row for row in rows if int(row.get("blocked_orders") or 0) > 0]
        elif filter_code == "COM_TRAVAMENTO":
            rows = [row for row in rows if row.get("details")]
        return rows

    def _render_blockers_table(self):
        rows = self._visible_blocker_rows()
        self.blockers_table.setSortingEnabled(False)
        self.blockers_table.setUpdatesEnabled(False)
        self.blockers_table.blockSignals(True)
        selected_row = -1
        try:
            self.blockers_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                schedule = row.get("schedule") or {}
                schedule_id = int(schedule.get("id") or 0)
                if self.selected_schedule_id and schedule_id == self.selected_schedule_id:
                    selected_row = row_index
                values = [
                    schedule_id,
                    schedule.get("title") or "-",
                    row.get("primary_type") or "-",
                    row.get("details") or "-",
                    row.get("responsible") or "-",
                    int(row.get("blocked_materials") or 0),
                    int(row.get("blocked_orders") or 0),
                    row.get("package_label") or "-",
                ]
                for column, value in enumerate(values):
                    payload = schedule if column == 0 else None
                    self.blockers_table.setItem(row_index, column, make_table_item(value, payload=payload))
            if selected_row >= 0:
                self.blockers_table.selectRow(selected_row)
        finally:
            self.blockers_table.blockSignals(False)
            self.blockers_table.setUpdatesEnabled(True)
            self.blockers_table.setSortingEnabled(True)
        self._refresh_blockers_screen_summary(rows)

    def _refresh_blockers_screen_summary(self, rows: list[dict]):
        total_schedules = len({int((row.get("schedule") or {}).get("id") or 0) for row in rows if (row.get("schedule") or {}).get("id")})
        no_responsible = sum(1 for row in rows if row.get("has_no_responsible"))
        blocked_materials = sum(1 for row in rows if int(row.get("blocked_materials") or 0) > 0)
        blocked_orders = sum(1 for row in rows if int(row.get("blocked_orders") or 0) > 0)
        self.blockers_filter_badge.setText(f"Filtro: {str(self.blockers_filter_combo.currentText() or 'Todos os bloqueios')}")
        self.blockers_volume_badge.setText(f"Bloqueios: {len(rows)} | Planejamentos travados: {total_schedules}")
        self.blockers_types_badge.setText(
            f"Sem responsável: {no_responsible} | Peça: {blocked_materials} | OS bloqueada: {blocked_orders}"
        )
        selected_schedule = self._selected_schedule()
        if selected_schedule:
            self.blockers_screen_badge.setText(f"Planejamento: {str(selected_schedule.get('title') or f'#{selected_schedule.get('id')}')}")
            self.blockers_scope_badge.setText("Escopo: planejamento selecionado")
        else:
            self.blockers_screen_badge.setText(f"{len(rows)} travamento(s) na tela")
            self.blockers_scope_badge.setText("Escopo: todos os planejamentos filtrados")

    def _visible_material_links_for_current_context(self, schedule: dict) -> list[dict]:
        materials = list(schedule.get("materiais") or [])
        filter_code = self.pieces_filter_combo.currentData() if hasattr(self, "pieces_filter_combo") else "ALL"
        if filter_code and filter_code != "ALL":
            materials = [row for row in materials if str(row.get("status") or "").upper() == filter_code]
        return materials

    def _refresh_pieces_screen_summary(self, schedule: dict | None, materials: list[dict]):
        if not schedule:
            self.pieces_screen_badge.setText("Nenhum planejamento selecionado")
            self.pieces_scope_badge.setText("Escopo: selecione um planejamento")
            self.pieces_filter_badge.setText("Filtro: todas as peças")
            self.pieces_volume_badge.setText("Peças: 0 | Reservadas: 0 | Utilizadas: 0")
            self.pieces_blockers_badge.setText("Aguardando peça: 0 | Em compras: 0")
            return

        reserved = sum(1 for row in materials if str(row.get("status") or "").upper() == "RESERVADO")
        used = sum(1 for row in materials if str(row.get("status") or "").upper() == "UTILIZADO")
        waiting = sum(1 for row in materials if str(row.get("status") or "").upper() == "AGUARDANDO_MATERIAL")
        buying = sum(1 for row in materials if str(row.get("status") or "").upper() == "EM_COMPRAS")
        title = str(schedule.get("title") or f"#{schedule.get('id')}")
        filter_label = str(self.pieces_filter_combo.currentText() or "Todas as peças")
        self.pieces_screen_badge.setText(f"Planejamento: {title}")
        self.pieces_scope_badge.setText(
            f"Escopo: {str(schedule.get('package_reference_label') or 'sem pacote')}"
        )
        self.pieces_filter_badge.setText(f"Filtro: {filter_label}")
        self.pieces_volume_badge.setText(f"Peças: {len(materials)} | Reservadas: {reserved} | Utilizadas: {used}")
        self.pieces_blockers_badge.setText(f"Aguardando peça: {waiting} | Em compras: {buying}")

    def _sync_material_form_with_link(self):
        schedule = self._selected_schedule()
        material = self.material_combo.currentData() if hasattr(self, "material_combo") else None
        if not schedule or not isinstance(material, dict):
            self.material_qty_input.setValue(1)
            self.material_status_combo.setCurrentIndex(0)
            self.material_observation_input.clear()
            return

        selected_material_id = int(material.get("id") or 0)
        link = next(
            (
                row
                for row in (schedule.get("materiais") or [])
                if int(row.get("material_id") or 0) == selected_material_id
            ),
            None,
        )
        if not link:
            self.material_qty_input.setValue(1)
            default_status = "DISPONIVEL_EM_ESTOQUE" if int(material.get("quantidade_estoque") or 0) > 0 else "AGUARDANDO_MATERIAL"
            status_index = self.material_status_combo.findData(default_status)
            self.material_status_combo.setCurrentIndex(status_index if status_index >= 0 else 0)
            self.material_observation_input.clear()
            return

        self.material_qty_input.setValue(max(1, int(link.get("quantity_per_vehicle") or 1)))
        status_index = self.material_status_combo.findData(str(link.get("status") or "").upper())
        self.material_status_combo.setCurrentIndex(status_index if status_index >= 0 else 0)
        self.material_observation_input.setText(str(link.get("observation") or ""))

    def _render_summary(self):
        summary = (self.overview or {}).get("resumo") or {}
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")
        overdue_orders = 0
        no_responsible = 0
        active_blockers = 0
        for schedule in self.filtered_schedules:
            blockers = schedule.get("bloqueios_resumo") or {}
            has_blocker = False
            if blockers.get("sem_responsavel") or not schedule.get("assigned_mechanic_user_id"):
                no_responsible += 1
                has_blocker = True
            if int(blockers.get("materiais_bloqueados") or 0) > 0:
                has_blocker = True
            if int(blockers.get("ordens_bloqueadas") or 0) > 0:
                has_blocker = True
            if has_blocker:
                active_blockers += 1
            for item in schedule.get("itens") or []:
                work_order = item.get("work_order") or {}
                item_status = str(item.get("status") or "").upper()
                scheduled_date = str(item.get("scheduled_date") or "")[:10]
                if (
                    int(work_order.get("id") or 0)
                    and scheduled_date
                    and scheduled_date < today_iso
                    and item_status not in {"INSTALADO", "CANCELADO"}
                ):
                    overdue_orders += 1
        self.schedules_card.set_content("Programações abertas", str(summary.get("programacoes", 0)), "Clique para abrir o planejamento do período")
        self.items_card.set_content("Serviços do mês", str(summary.get("itens", 0)), "Clique para abrir os serviços do período selecionado")
        self.pending_card.set_content(
            "Serviços pendentes",
            str(summary.get("pendentes", 0)),
            f"Aguardando material: {summary.get('aguardando_material', 0)} | OS bloqueadas: {summary.get('os_bloqueadas', 0)}",
        )
        self.installed_card.set_content(
            "Serviços concluídos",
            str(summary.get("instalados", 0)),
            f"Não executados: {summary.get('nao_executados', 0)}",
        )
        self.overdue_os_card.set_content(
            "OS atrasadas",
            str(overdue_orders),
            "Ordens com data passada e pendência de execução.",
        )
        self.waiting_parts_card.set_content(
            "Aguardando peça",
            str(summary.get("aguardando_material", 0)),
            "Serviços travados esperando peça para liberar.",
        )
        self.no_responsible_card.set_content(
            "Sem responsável",
            str(no_responsible),
            "Programações que ainda estão sem mecânico definido.",
        )
        self.blockers_card.set_content(
            "Bloqueios ativos",
            str(active_blockers),
            f"OS bloqueadas: {summary.get('os_bloqueadas', 0)} | veja os travamentos do período.",
        )
        self.schedules_badge.setText(f"{len(self.filtered_schedules)} registros")
        self._refresh_planning_screen_summary()

    def _render_schedules_table(self):
        rows = self.filtered_schedules
        selected_row = -1
        self.schedules_table.setSortingEnabled(False)
        self.schedules_table.setUpdatesEnabled(False)
        self.schedules_table.blockSignals(True)
        try:
            self.schedules_table.setRowCount(len(rows))
            for row_index, schedule in enumerate(rows):
                schedule_id = int(schedule.get("id") or 0)
                if self.selected_schedule_id and schedule_id == self.selected_schedule_id:
                    selected_row = row_index
                resumo = schedule.get("resumo") or {}
                values = [
                    schedule_id,
                    schedule.get("title") or "-",
                    SOURCE_LABELS.get(_schedule_source_code(schedule), schedule.get("source_type") or "-"),
                    SCHEDULE_STATUS_LABELS.get(str(schedule.get("status") or "").upper(), schedule.get("status") or "-"),
                    self._schedule_period_label(schedule),
                    resumo.get("total", 0),
                    resumo.get("pendentes", 0),
                    resumo.get("instalados", 0),
                    schedule.get("daily_capacity") or 1,
                ]
                for column, value in enumerate(values):
                    payload = schedule if column == 0 else None
                    self.schedules_table.setItem(row_index, column, make_table_item(value, payload=payload))
            if selected_row >= 0:
                self.schedules_table.selectRow(selected_row)
            elif rows:
                self.schedules_table.selectRow(0)
        finally:
            self.schedules_table.blockSignals(False)
            self.schedules_table.setUpdatesEnabled(True)
            self.schedules_table.setSortingEnabled(True)
        self._apply_schedule_table_layout()

    def _render_calendar_table(self):
        rows = self._calendar_rows_for_selected_schedule()
        self.calendar_day_index = {
            str(row.get("date")): row
            for row in rows
            if row.get("date")
        }
        total_services = sum(int(row.get("total") or 0) for row in rows)
        total_pending = sum(int(row.get("pendentes") or 0) for row in rows)
        self.calendar_badge.setText(f"{len(rows)} dias com agenda | {total_services} serviços | {total_pending} pendentes")

        current_month = self.month_input.date()
        year = current_month.year()
        month = current_month.month()
        if year <= 0 or month <= 0:
            year = QDate.currentDate().year()
            month = QDate.currentDate().month()
        first_day = QDate(year, month, 1)
        if not first_day.isValid():
            first_day = QDate.currentDate()
            year = first_day.year()
            month = first_day.month()
        days_in_month = first_day.daysInMonth()
        first_column = first_day.dayOfWeek() % 7  # DOM=0 ... SAB=6
        today_iso = QDate.currentDate().toString("yyyy-MM-dd")

        self.calendar_table.setSortingEnabled(False)
        self.calendar_table.setUpdatesEnabled(False)
        self.calendar_table.blockSignals(True)
        try:
            self.calendar_table.clearContents()
            self.calendar_table.setRowCount(6)
            for row in range(6):
                self.calendar_table.setRowHeight(row, 82)
            for column in range(7):
                self.calendar_table.setColumnWidth(column, 154)

            table_row = 0
            table_column = first_column
            for day in range(1, days_in_month + 1):
                day_iso = f"{year:04d}-{month:02d}-{day:02d}"
                payload = self.calendar_day_index.get(day_iso) or {
                    "date": day_iso,
                    "total": 0,
                    "pendentes": 0,
                    "instalados": 0,
                    "nao_executados": 0,
                    "aguardando_material": 0,
                }
                text = self._build_calendar_day_text(day, payload, day_iso == today_iso)
                day_item = make_table_item(text, payload=day_iso, sort_value=day)
                day_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                day_item.setBackground(self._calendar_cell_background(payload, day_iso == today_iso))
                day_item.setToolTip(self._calendar_cell_tooltip(payload, day_iso == today_iso))
                self.calendar_table.setItem(table_row, table_column, day_item)

                table_column += 1
                if table_column >= 7:
                    table_column = 0
                    table_row += 1
                    if table_row >= 6:
                        break
        finally:
            self.calendar_table.blockSignals(False)
            self.calendar_table.setUpdatesEnabled(True)
            self.calendar_table.setSortingEnabled(False)
        self._sync_calendar_selected_day()
        self._refresh_calendar_selection_badge()

    def _render_agenda_days_table(self):
        rows = self._calendar_rows_for_selected_schedule()
        self.agenda_days_table.setSortingEnabled(False)
        self.agenda_days_table.setUpdatesEnabled(False)
        self.agenda_days_table.blockSignals(True)
        selected_row = -1
        try:
            self.agenda_days_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                day_iso = str(row.get("date") or "")
                if self.selected_calendar_day_iso and day_iso == self.selected_calendar_day_iso:
                    selected_row = row_index
                values = [
                    self._format_date(day_iso),
                    int(row.get("total") or 0),
                    int(row.get("pendentes") or 0),
                    int(row.get("instalados") or 0),
                    int(row.get("aguardando_material") or 0),
                    int(row.get("nao_executados") or 0),
                ]
                for column, value in enumerate(values):
                    payload = day_iso if column == 0 else None
                    self.agenda_days_table.setItem(row_index, column, make_table_item(value, payload=payload))
            if selected_row >= 0:
                self.agenda_days_table.selectRow(selected_row)
        finally:
            self.agenda_days_table.blockSignals(False)
            self.agenda_days_table.setUpdatesEnabled(True)
            self.agenda_days_table.setSortingEnabled(True)
        self.agenda_days_badge.setText(f"{len(rows)} dias na agenda")
        self._refresh_agenda_screen_summary()

    def _sync_calendar_selected_day(self):
        if not self.selected_calendar_day_iso:
            self.calendar_table.clearSelection()
            return
        self.calendar_table.blockSignals(True)
        try:
            for row in range(self.calendar_table.rowCount()):
                for column in range(self.calendar_table.columnCount()):
                    item = self.calendar_table.item(row, column)
                    if item and item.data(Qt.UserRole) == self.selected_calendar_day_iso:
                        self.calendar_table.setCurrentCell(row, column)
                        self.calendar_table.selectRow(row)
                        return
        finally:
            self.calendar_table.blockSignals(False)

    def _refresh_agenda_screen_summary(self):
        rows = self._calendar_rows_for_selected_schedule()
        schedule = self._selected_schedule()
        if schedule:
            self.agenda_schedule_scope_badge.setText(
                f"Planejamento: {str(schedule.get('title') or f'#{schedule.get('id')}')}"
            )
        else:
            self.agenda_schedule_scope_badge.setText("Planejamento: todos os planejamentos")
        if not self.selected_calendar_day_iso:
            self.agenda_screen_badge.setText("Nenhum dia selecionado")
            self.agenda_period_badge.setText(f"Período: {len(rows)} dia(s) na agenda")
            total_programados = sum(int(row.get("total") or 0) for row in rows)
            total_pendentes = sum(int(row.get("pendentes") or 0) for row in rows)
            total_concluidos = sum(int(row.get("instalados") or 0) for row in rows)
            total_aguardando = sum(int(row.get("aguardando_material") or 0) for row in rows)
            total_nao_exec = sum(int(row.get("nao_executados") or 0) for row in rows)
            self.agenda_day_volume_badge.setText(
                f"Programados: {total_programados} | Pendentes: {total_pendentes} | Concluídos: {total_concluidos}"
            )
            self.agenda_day_blockers_badge.setText(
                f"Aguardando peça: {total_aguardando} | Não executados: {total_nao_exec}"
            )
            self.agenda_open_services_button.setEnabled(False)
            self.agenda_clear_day_button.setEnabled(False)
            return

        payload = self.calendar_day_index.get(self.selected_calendar_day_iso) or {}
        self.agenda_screen_badge.setText(f"Dia escolhido: {self._format_date(self.selected_calendar_day_iso)}")
        self.agenda_period_badge.setText(f"Período: {self._format_date(self.selected_calendar_day_iso)}")
        self.agenda_day_volume_badge.setText(
            f"Programados: {int(payload.get('total') or 0)} | Pendentes: {int(payload.get('pendentes') or 0)} | Concluídos: {int(payload.get('instalados') or 0)}"
        )
        self.agenda_day_blockers_badge.setText(
            f"Aguardando peça: {int(payload.get('aguardando_material') or 0)} | Não executados: {int(payload.get('nao_executados') or 0)}"
        )
        self.agenda_open_services_button.setEnabled(True)
        self.agenda_clear_day_button.setEnabled(True)
        self._refresh_calendar_selection_badge()

    def _build_calendar_day_text(self, day: int, payload: dict, is_today: bool) -> str:
        prefix = f"{day:02d} HOJE" if is_today else f"{day:02d}"
        total = int(payload.get("total") or 0)
        pendentes = int(payload.get("pendentes") or 0)
        instalados = int(payload.get("instalados") or 0)
        aguardando = int(payload.get("aguardando_material") or 0)
        nao_exec = int(payload.get("nao_executados") or 0)
        if total <= 0:
            return f"{prefix}\nSem agenda"
        return (
            f"{prefix}\n"
            f"Prog {total} | Pend {pendentes}\n"
            f"Concl {instalados} | Aguar {aguardando}\n"
            f"Não exec {nao_exec}"
        )

    @staticmethod
    def _calendar_cell_background(payload: dict, is_today: bool = False) -> QColor:
        total = int(payload.get("total") or 0)
        pendentes = int(payload.get("pendentes") or 0)
        instalados = int(payload.get("instalados") or 0)
        aguardando = int(payload.get("aguardando_material") or 0)

        if total <= 0:
            return QColor("#D3D8DE") if is_today else QColor("#ECEFF2")
        if aguardando > 0 and instalados == 0:
            return QColor("#CFC8B2") if is_today else QColor("#E5DFCD")
        if pendentes == 0 and instalados > 0:
            return QColor("#C8D4C8") if is_today else QColor("#E3EAE3")
        if instalados > 0 and pendentes > 0:
            return QColor("#CDD3C4") if is_today else QColor("#E7EBDD")
        return QColor("#D2CCB8") if is_today else QColor("#ECE6D6")

    @staticmethod
    def _calendar_cell_tooltip(payload: dict, is_today: bool) -> str:
        total = int(payload.get("total") or 0)
        pendentes = int(payload.get("pendentes") or 0)
        instalados = int(payload.get("instalados") or 0)
        aguardando = int(payload.get("aguardando_material") or 0)
        nao_exec = int(payload.get("nao_executados") or 0)

        lines = []
        if is_today:
            lines.append("HOJE")
        lines.append(f"Programados: {total}")
        lines.append(f"Pendentes: {pendentes}")
        lines.append(f"Concluídos: {instalados}")
        lines.append(f"Aguardando material: {aguardando}")
        if nao_exec:
            lines.append(f"Não executados: {nao_exec}")
        return "\n".join(lines)

    def _calendar_rows_for_selected_schedule(self) -> list[dict]:
        schedule = self._selected_schedule()
        if not schedule:
            days = list(((self.overview or {}).get("cronograma") or {}).get("days") or [])
            return [day for day in days if int(day.get("total") or 0) > 0]

        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "date": "",
                "total": 0,
                "pendentes": 0,
                "instalados": 0,
                "nao_executados": 0,
                "aguardando_material": 0,
            }
        )
        for item in schedule.get("itens") or []:
            date_key = item.get("scheduled_date")
            if not date_key:
                continue
            row = grouped[date_key]
            row["date"] = date_key
            row["total"] += 1
            status = str(item.get("status") or "").upper()
            if status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}:
                row["pendentes"] += 1
            if status == "INSTALADO":
                row["instalados"] += 1
            if status == "NAO_EXECUTADO":
                row["nao_executados"] += 1
            if status == "AGUARDANDO_MATERIAL":
                row["aguardando_material"] += 1
        rows = list(grouped.values())
        rows.sort(key=lambda row: row.get("date") or "")
        return rows

    def _on_schedule_selection_changed(self):
        row = self.schedules_table.currentRow()
        if row < 0:
            self.selected_schedule_id = None
            self.selected_calendar_day_iso = None
            self._refresh_planning_screen_summary()
            self._render_os_table()
            self._render_responsible_table()
            self.render_selected_schedule_items()
            self.render_selected_schedule_materials()
            self._render_calendar_table()
            return
        first_cell = self.schedules_table.item(row, 0)
        payload = first_cell.data(Qt.UserRole) if first_cell else None
        if not payload:
            return
        self.selected_schedule_id = int(payload.get("id"))
        self.selected_calendar_day_iso = None
        self._refresh_planning_screen_summary()
        self._render_os_table()
        self._render_responsible_table()
        self.render_selected_schedule_items()
        self.render_selected_schedule_materials()
        self._render_calendar_table()

    def _on_calendar_day_selection_changed(self):
        selected_items = self.calendar_table.selectedItems()
        if not selected_items:
            self.selected_calendar_day_iso = None
        else:
            day_iso = selected_items[0].data(Qt.UserRole)
            self.selected_calendar_day_iso = day_iso if day_iso else None
        self._refresh_calendar_selection_badge()
        self._render_agenda_days_table()
        self.render_selected_schedule_items()
        self._render_os_table()
        if self.selected_calendar_day_iso:
            self._open_maintenance_screen("AGENDA")

    def _on_agenda_day_selection_changed(self):
        selected_rows = self.agenda_days_table.selectionModel().selectedRows() if self.agenda_days_table.selectionModel() else []
        if not selected_rows:
            self.selected_calendar_day_iso = None
        else:
            item = self.agenda_days_table.item(selected_rows[0].row(), 0)
            day_iso = item.data(Qt.UserRole) if item else None
            self.selected_calendar_day_iso = day_iso if day_iso else None
        self._sync_calendar_selected_day()
        self._refresh_calendar_selection_badge()
        self._refresh_agenda_screen_summary()
        self.render_selected_schedule_items()
        self._render_os_table()

    def _on_responsible_schedule_selection_changed(self):
        selected_rows = self.responsible_table.selectionModel().selectedRows() if self.responsible_table.selectionModel() else []
        if not selected_rows:
            return
        item = self.responsible_table.item(selected_rows[0].row(), 0)
        payload = item.data(Qt.UserRole) if item else None
        if not payload:
            return
        self.selected_schedule_id = int(payload.get("id") or 0)
        self._refresh_planning_screen_summary()
        self._refresh_responsible_screen_summary(
            [row for row in self.filtered_schedules if int(row.get("id") or 0) == self.selected_schedule_id] or self.filtered_schedules,
            self._responsible_metrics_map(),
        )
        self._render_os_table()
        self.render_selected_schedule_items()
        self.render_selected_schedule_materials()
        self._render_calendar_table()
        self._render_agenda_days_table()

    def _on_blocker_selection_changed(self):
        selected_rows = self.blockers_table.selectionModel().selectedRows() if self.blockers_table.selectionModel() else []
        if not selected_rows:
            return
        item = self.blockers_table.item(selected_rows[0].row(), 0)
        payload = item.data(Qt.UserRole) if item else None
        if not payload:
            return
        self.selected_schedule_id = int(payload.get("id") or 0)
        self._refresh_planning_screen_summary()
        self._render_os_table()
        self._render_blockers_table()
        self._render_responsible_table()
        self.render_selected_schedule_items()
        self.render_selected_schedule_materials()
        self._render_calendar_table()
        self._render_agenda_days_table()

    def _clear_calendar_day_filter(self):
        self._clear_calendar_day_scope()

    def _refresh_calendar_selection_badge(self):
        if not self.selected_calendar_day_iso:
            self.calendar_selected_badge.setText("Clique em um dia para abrir a agenda daquele dia")
            self.calendar_day_resume_badge.setText("Escolha um dia para ver carga, pendência e bloqueios da oficina")
            self.clear_calendar_filter_button.setEnabled(False)
            self._refresh_agenda_screen_summary()
            return
        payload = self.calendar_day_index.get(self.selected_calendar_day_iso) or {}
        self.calendar_selected_badge.setText(
            f"Dia {self._format_date(self.selected_calendar_day_iso)} | "
            f"Prog {int(payload.get('total') or 0)} | "
            f"Pend {int(payload.get('pendentes') or 0)} | "
            f"Concl {int(payload.get('instalados') or 0)}"
        )
        self.calendar_day_resume_badge.setText(
            f"Aguardando material {int(payload.get('aguardando_material') or 0)} | "
            f"Não executados {int(payload.get('nao_executados') or 0)} | "
            "Tela aberta: Agenda do dia"
        )
        self.clear_calendar_filter_button.setEnabled(True)
        self._refresh_agenda_screen_summary()

    def _selected_schedule(self) -> dict | None:
        schedule_id = self.selected_schedule_id
        if not schedule_id:
            return None
        for row in (self.overview or {}).get("programacoes") or []:
            if int(row.get("id") or 0) == schedule_id:
                return row
        return None

    def _refresh_planning_screen_summary(self):
        schedule = self._selected_schedule()
        if not schedule:
            self.planning_screen_badge.setText("Nenhum planejamento selecionado")
            self.planning_origin_badge.setText("Origem: -")
            self.planning_status_badge.setText("Situação: -")
            self.planning_period_badge.setText("Período: -")
            self.planning_volume_badge.setText("Itens: 0 | Pendentes: 0 | Concluídos: 0")
            self.planning_capacity_badge.setText("Capacidade diária: -")
            self.planning_package_badge.setText("Pacote: sem pacote")
            return

        resumo = schedule.get("resumo") or {}
        title = str(schedule.get("title") or f"Programação #{schedule.get('id')}")
        self.planning_screen_badge.setText(f"Selecionado: {title}")
        self.planning_origin_badge.setText(
            f"Origem: {SOURCE_LABELS.get(_schedule_source_code(schedule), schedule.get('source_type') or '-')}"
        )
        self.planning_status_badge.setText(
            f"Situação: {SCHEDULE_STATUS_LABELS.get(str(schedule.get('status') or '').upper(), schedule.get('status') or '-')}"
        )
        self.planning_period_badge.setText(f"Período: {self._schedule_period_label(schedule)}")
        self.planning_volume_badge.setText(
            f"Itens: {int(resumo.get('total', 0) or 0)} | Pendentes: {int(resumo.get('pendentes', 0) or 0)} | Concluídos: {int(resumo.get('instalados', 0) or 0)}"
        )
        self.planning_capacity_badge.setText(f"Capacidade diária: {int(schedule.get('daily_capacity') or 1)}")
        self.planning_package_badge.setText(
            f"Pacote: {str(schedule.get('package_reference_label') or 'sem pacote')}"
        )

    def render_selected_schedule_items(self):
        schedule = self._selected_schedule()
        if not schedule:
            self.selected_schedule_badge.setText("Nenhum planejamento selecionado")
            self.items_table.setRowCount(0)
            if hasattr(self, "details_hint_label"):
                self.details_hint_label.setText("Selecione um planejamento e, se quiser, um dia no calendário para ver os serviços.")
            self._set_action_controls_enabled(False)
            self._update_items_badge()
            self._refresh_services_screen_summary(None, [])
            return

        self._set_action_controls_enabled(True)
        title = str(schedule.get("title") or f"Programação #{schedule.get('id')}")
        day_suffix = f" | Dia {self._format_date(self.selected_calendar_day_iso)}" if self.selected_calendar_day_iso else ""
        self.selected_schedule_badge.setText(f"#{schedule.get('id')} | {title}{day_suffix}")
        if hasattr(self, "details_hint_label"):
            if self.selected_calendar_day_iso:
                self.details_hint_label.setText(
                    f"Serviços filtrados para {self._format_date(self.selected_calendar_day_iso)} dentro do planejamento selecionado. {self._execution_context_text(schedule)}"
                )
            else:
                self.details_hint_label.setText(
                    f"Aqui estão os serviços do planejamento selecionado. Use o calendário para focar um dia. {self._execution_context_text(schedule)}"
                )

        start_date = str(schedule.get("start_date") or "")
        start_qdate = QDate.fromString(start_date, "yyyy-MM-dd")
        if start_qdate.isValid():
            self.redistribute_start_input.setDate(start_qdate)
            self.move_date_input.setDate(start_qdate)
        self.redistribute_capacity_input.setValue(max(1, int(schedule.get("daily_capacity") or 1)))

        status_filter = self.item_status_filter.currentData()
        items = list(schedule.get("itens") or [])
        if status_filter == "PENDENTES":
            pending_statuses = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}
            items = [item for item in items if str(item.get("status") or "").upper() in pending_statuses]
        elif status_filter and status_filter != "ALL":
            items = [item for item in items if str(item.get("status") or "").upper() == status_filter]
        if self.selected_calendar_day_iso:
            items = [
                item
                for item in items
                if str(item.get("scheduled_date") or "")[:10] == self.selected_calendar_day_iso
            ]

        material_text = self._material_summary_for_schedule(schedule)
        self.items_table.setSortingEnabled(False)
        self.items_table.setUpdatesEnabled(False)
        self.items_table.blockSignals(True)
        try:
            self.items_table.setRowCount(len(items))
            for row_index, item in enumerate(items):
                vehicle = item.get("vehicle") or {}
                source_label = self._item_source_label(item, schedule)
                item_label = self._item_label(item, schedule)
                values = [
                    item.get("id"),
                    ((item.get("work_order") or {}).get("order_number") or "-"),
                    self._vehicle_table_label(vehicle),
                    source_label,
                    item_label,
                    self._format_date(item.get("scheduled_date")),
                    ITEM_STATUS_LABELS.get(str(item.get("status") or "").upper(), item.get("status") or "-"),
                    material_text,
                    self._execution_label(item),
                    item.get("observation") or "-",
                ]
                for column, value in enumerate(values):
                    payload = item if column == 0 else None
                    self.items_table.setItem(row_index, column, make_table_item(value, payload=payload))
        finally:
            self.items_table.blockSignals(False)
            self.items_table.setUpdatesEnabled(True)
            self.items_table.setSortingEnabled(True)
        self._apply_items_table_layout()

        self._update_items_badge()
        self._refresh_services_screen_summary(schedule, items)

    def _selected_item_payloads(self) -> list[dict]:
        model = self.items_table.selectionModel()
        if not model:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        selected: list[dict] = []
        for row in rows:
            cell = self.items_table.item(row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                selected.append(payload)
        if selected:
            return selected
        current_row = self.items_table.currentRow()
        if current_row >= 0:
            cell = self.items_table.item(current_row, 0)
            payload = cell.data(Qt.UserRole) if cell else None
            if payload:
                return [payload]
        return []

    def _update_items_badge(self):
        total = self.items_table.rowCount()
        selected = len(self._selected_item_payloads())
        if self.selected_calendar_day_iso:
            self.items_badge.setText(
                f"{total} itens no dia | {selected} selecionados | {self._format_date(self.selected_calendar_day_iso)}"
            )
        else:
            self.items_badge.setText(f"{total} itens | {selected} selecionados")
        self._refresh_contextual_actions()
        schedule = self._selected_schedule()
        if schedule:
            items = self._visible_items_for_current_context(schedule)
            self._refresh_services_screen_summary(schedule, items)

    def _visible_items_for_current_context(self, schedule: dict) -> list[dict]:
        status_filter = self.item_status_filter.currentData()
        items = list(schedule.get("itens") or [])
        if status_filter == "PENDENTES":
            pending_statuses = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}
            items = [item for item in items if str(item.get("status") or "").upper() in pending_statuses]
        elif status_filter and status_filter != "ALL":
            items = [item for item in items if str(item.get("status") or "").upper() == status_filter]
        if self.selected_calendar_day_iso:
            items = [item for item in items if str(item.get("scheduled_date") or "")[:10] == self.selected_calendar_day_iso]
        return items

    def _refresh_services_screen_summary(self, schedule: dict | None, items: list[dict]):
        if not schedule:
            self.services_screen_badge.setText("Nenhum planejamento selecionado")
            self.services_scope_badge.setText("Escopo: selecione um planejamento")
            self.services_filter_badge.setText("Filtro: todos os serviços")
            self.services_volume_badge.setText("Serviços: 0 | Selecionados: 0")
            self.services_blockers_badge.setText("Aguardando peça: 0 | Sem execução: 0")
            self.services_context_badge.setText("Contexto: sem pacote")
            return

        selected_count = len(self._selected_item_payloads())
        waiting_parts = sum(1 for item in items if str(item.get("status") or "").upper() == "AGUARDANDO_MATERIAL")
        not_executed = sum(1 for item in items if str(item.get("status") or "").upper() == "NAO_EXECUTADO")
        schedule_title = str(schedule.get("title") or f"#{schedule.get('id')}")
        self.services_screen_badge.setText(f"Planejamento: {schedule_title}")
        if self.selected_calendar_day_iso:
            self.services_scope_badge.setText(f"Escopo: dia {self._format_date(self.selected_calendar_day_iso)}")
        else:
            self.services_scope_badge.setText("Escopo: todos os dias do planejamento")
        filter_label = str(self.item_status_filter.currentText() or "Itens: todos")
        self.services_filter_badge.setText(f"Filtro: {filter_label}")
        self.services_volume_badge.setText(f"Serviços: {len(items)} | Selecionados: {selected_count}")
        self.services_blockers_badge.setText(
            f"Aguardando peça: {waiting_parts} | Sem execução: {not_executed}"
        )
        self.services_context_badge.setText(f"Contexto: {self._execution_context_text(schedule)}")

    def _refresh_contextual_actions(self):
        schedule_selected = self._selected_schedule() is not None
        item_selected = len(self._selected_item_payloads()) > 0
        material_selected = isinstance(self.material_combo.currentData(), dict) if hasattr(self, "material_combo") else False

        self.item_status_filter.setEnabled(schedule_selected)
        self.redistribute_start_input.setEnabled(schedule_selected)
        self.redistribute_capacity_input.setEnabled(schedule_selected)
        self.redistribute_button.setEnabled(schedule_selected)
        self.move_date_input.setEnabled(schedule_selected and item_selected)
        self.move_button.setEnabled(schedule_selected and item_selected)
        self.export_work_order_button.setEnabled(schedule_selected and item_selected)
        self.remove_button.setEnabled(schedule_selected and item_selected)
        self.clear_calendar_filter_button.setEnabled(schedule_selected and bool(self.selected_calendar_day_iso))
        if hasattr(self, "link_material_button"):
            self.link_material_button.setEnabled(schedule_selected and material_selected)

        if hasattr(self, "action_help_label"):
            self.action_help_label.setVisible(not schedule_selected or not item_selected)
            if not schedule_selected:
                self.action_help_label.setText(
                    "Selecione um planejamento para liberar o filtro de serviços e as ações da agenda."
                )
            elif not item_selected:
                self.action_help_label.setText(
                    "Selecione um ou mais itens da tabela para liberar reprogramação e retirada."
                )
            else:
                self.action_help_label.setText(
                    "Selecione um planejamento e depois escolha os itens do serviço para liberar reprogramação e retirada."
                )

        if hasattr(self, "management_help_label"):
            self.management_help_label.setVisible(True)

    def _set_action_controls_enabled(self, enabled: bool):
        self.item_status_filter.setEnabled(enabled)
        self.move_date_input.setEnabled(False)
        self.move_button.setEnabled(False)
        self.export_work_order_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.redistribute_start_input.setEnabled(enabled)
        self.redistribute_capacity_input.setEnabled(enabled)
        self.redistribute_button.setEnabled(enabled)
        self.clear_calendar_filter_button.setEnabled(enabled and bool(self.selected_calendar_day_iso))
        self._refresh_contextual_actions()

    def _set_management_controls_enabled(self, enabled: bool):
        self.mechanic_combo.setEnabled(enabled)
        self.assign_mechanic_button.setEnabled(enabled)
        self.material_combo.setEnabled(enabled)
        self.material_qty_input.setEnabled(enabled)
        self.material_status_combo.setEnabled(enabled)
        self.material_observation_input.setEnabled(enabled)
        self.link_material_button.setEnabled(enabled)
        self.material_suggest_button.setEnabled(enabled)
        self._refresh_contextual_actions()

    def _item_source_label(self, item: dict, schedule: dict) -> str:
        schedule_source = _schedule_source_code(schedule)
        if schedule_source == "PACOTE_RESOLUCAO":
            return "Pacote"
        if item.get("checklist_item_id"):
            return "NC legada"
        if item.get("activity_id"):
            return "Inspeção legada"
        return SOURCE_LABELS.get(schedule_source, "-")

    def _item_label(self, item: dict, schedule: dict) -> str:
        checklist_item = item.get("checklist_item") or {}
        if checklist_item.get("item_nome"):
            return checklist_item.get("item_nome")
        activity = item.get("activity") or {}
        if activity.get("item_nome"):
            return activity.get("item_nome")
        return schedule.get("item_name") or schedule.get("title") or "-"

    def _schedule_period_label(self, schedule: dict) -> str:
        start = self._format_date(schedule.get("start_date"))
        end = self._format_date(schedule.get("end_date"))
        if start == "-" and end == "-":
            return "-"
        if end == "-" or start == end:
            return start
        if start == "-":
            return end
        return f"{start} a {end}"

    @staticmethod
    def _vehicle_table_label(vehicle: dict) -> str:
        frota = str(vehicle.get("frota") or "-")
        placa = str(vehicle.get("placa") or "-")
        modelo = str(vehicle.get("modelo") or "").strip()
        label = f"{frota} | {placa}"
        return f"{label} | {modelo}" if modelo else label

    def _execution_label(self, item: dict) -> str:
        executed_at = self._format_datetime(item.get("executed_at"))
        if executed_at != "-":
            return executed_at
        if item.get("executed_by_user_id"):
            return "Com apontamento"
        return "Pendente"

    def _apply_schedule_table_layout(self):
        widths = {
            1: 260,
            2: 110,
            3: 120,
            4: 150,
            5: 70,
            6: 90,
            7: 95,
            8: 80,
        }
        for column, width in widths.items():
            self.schedules_table.setColumnWidth(column, width)

    def _apply_items_table_layout(self):
        widths = {
            1: 120,
            2: 230,
            3: 90,
            4: 220,
            5: 90,
            6: 115,
            7: 170,
            8: 150,
        }
        for column, width in widths.items():
            self.items_table.setColumnWidth(column, width)

    def _material_summary_for_schedule(self, schedule: dict) -> str:
        materials = list(schedule.get("materiais") or [])
        if not materials:
            return "Sem material"
        counters: dict[str, int] = defaultdict(int)
        for link in materials:
            counters[str(link.get("status") or "").upper()] += 1
        parts = []
        if counters.get("DISPONIVEL_EM_ESTOQUE"):
            parts.append(f"Disponível {counters['DISPONIVEL_EM_ESTOQUE']}")
        if counters.get("AGUARDANDO_MATERIAL"):
            parts.append(f"Aguardando {counters['AGUARDANDO_MATERIAL']}")
        if counters.get("EM_COMPRAS"):
            parts.append(f"Compras {counters['EM_COMPRAS']}")
        if counters.get("RESERVADO"):
            parts.append(f"Reservado {counters['RESERVADO']}")
        if counters.get("UTILIZADO"):
            parts.append(f"Utilizado {counters['UTILIZADO']}")
        return " | ".join(parts) if parts else "Com material"

    def _management_context_text(self, schedule: dict) -> str:
        blockers = schedule.get("bloqueios_resumo") or {}
        materials = schedule.get("materiais_resumo") or {}
        family = str(materials.get("familia_veiculo") or schedule.get("vehicle_family") or "ambos").replace("_", " ")
        parts = [f"Módulo {family}"]
        if blockers.get("sem_responsavel"):
            parts.append("sem responsável")
        if int(blockers.get("materiais_bloqueados") or 0):
            parts.append(f"{int(blockers.get('materiais_bloqueados') or 0)} peça(s) bloqueando")
        if int(blockers.get("ordens_bloqueadas") or 0):
            parts.append(f"{int(blockers.get('ordens_bloqueadas') or 0)} OS bloqueada(s)")
        if int(materials.get("quantidade_reservada") or 0):
            parts.append(f"reservado {int(materials.get('quantidade_reservada') or 0)}")
        if int(materials.get("quantidade_prevista") or 0):
            parts.append(f"previsto {int(materials.get('quantidade_prevista') or 0)}")
        return "Leitura rápida: " + " | ".join(parts)

    def _execution_context_text(self, schedule: dict) -> str:
        blockers = schedule.get("bloqueios_resumo") or {}
        package_label = str(schedule.get("package_reference_label") or "Sem pacote")
        parts = [package_label]
        if int(blockers.get("materiais_bloqueados") or 0):
            parts.append(f"{int(blockers.get('materiais_bloqueados') or 0)} bloqueio(s) de peça")
        if int(blockers.get("ordens_bloqueadas") or 0):
            parts.append(f"{int(blockers.get('ordens_bloqueadas') or 0)} OS travada(s)")
        if blockers.get("sem_responsavel"):
            parts.append("sem responsável definido")
        return " | ".join(parts)

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        text = str(value)[:10]
        parts = text.split("-")
        if len(parts) != 3:
            return text
        return f"{parts[2]}/{parts[1]}/{parts[0]}"

    @staticmethod
    def _format_datetime(value: str | None) -> str:
        if not value:
            return "-"
        text = str(value).replace("T", " ")
        if len(text) >= 16:
            date_part = text[:10]
            time_part = text[11:16]
            parts = date_part.split("-")
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]} {time_part}"
        return text
