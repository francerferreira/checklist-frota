from __future__ import annotations

from PySide6.QtCore import QDate, QDateTime, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout

from components import StatCard, show_notice
from theme import configure_table, style_filter_bar, style_table_card

STATUS_LABELS = {"PENDENTE": "Pendente", "PROGRAMADO": "Programado", "AGUARDANDO_MATERIAL": "Aguardando material", "INSTALADO": "Conclu\u00eddo", "NAO_EXECUTADO": "N\u00e3o executado", "REPROGRAMADO": "Reprogramado", "CANCELADO": "Cancelado"}
PENDING_STATUSES = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}


def _text(value) -> str:
    return str(value or "").strip()


def _is_family(item: dict, family: str) -> bool:
    vehicle = item.get("vehicle") or {}
    family_data = vehicle.get("family") or {}
    return any(family in _text(value).upper() for value in (vehicle.get("tipo"), vehicle.get("frota"), family_data.get("code"), family_data.get("name")))


class CorrectiveEmergencyDialog(QDialog):
    def __init__(self, api_client, family: str, vehicles: list[dict], parent=None):
        super().__init__(parent)
        self.api_client, self.family, self.vehicles = api_client, family, list(vehicles or [])
        self.setWindowTitle(f"Corretiva emergencial - {family}")
        self.setMinimumWidth(610)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        title = QLabel(f"CORRETIVA EMERGENCIAL - {family}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Informe o problema, a causa e a a\u00e7\u00e3o imediata. Ao salvar, o sistema cria a ocorr\u00eancia e a OS da fam\u00edlia.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        form = QFormLayout()
        form.setSpacing(10)
        self.vehicle = QComboBox()
        self.vehicle.addItem("Selecione o equipamento", None)
        for row in self.vehicles:
            label = _text(row.get("frota") or row.get("placa") or row.get("modelo")) or "Equipamento"
            local = _text((row.get("operational_location") or {}).get("full_name"))
            self.vehicle.addItem(f"{label}{f' | {local}' if local else ''}", row.get("id"))
        self.problem = QLineEdit()
        self.problem.setPlaceholderText("Ex.: falha no sistema hidr\u00e1ulico")
        self.cause, self.action = QTextEdit(), QTextEdit()
        self.cause.setPlaceholderText("Descreva a causa identificada.")
        self.action.setPlaceholderText("Descreva a a\u00e7\u00e3o imediata realizada ou planejada.")
        self.cause.setMaximumHeight(70)
        self.action.setMaximumHeight(70)
        self.severity = QComboBox()
        self.severity.addItem("Alta", "ALTA")
        self.mechanic = QComboBox()
        self.mechanic.addItem("Selecione o respons\u00e1vel", None)
        try:
            for user in self.api_client.get_mechanics() or []:
                self.mechanic.addItem(_text(user.get("nome") or user.get("login")), user.get("id"))
        except Exception:
            pass
        self.severity.addItem("Cr\u00edtica", "CRITICA")
        self.severity.addItem("M\u00e9dia", "MEDIA")
        self.opened_at = QDateTimeEdit(QDateTime.currentDateTime())
        self.opened_at.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.opened_at.setCalendarPopup(True)
        self.stopped = QCheckBox("Equipamento parado")
        self.stopped.setChecked(True)
        for label, field in (("Equipamento *", self.vehicle), ("Problema *", self.problem), ("Causa *", self.cause), ("A\u00e7\u00e3o *", self.action), ("Respons\u00e1vel *", self.mechanic), ("Criticidade", self.severity), ("Data e hora", self.opened_at), ("Situa\u00e7\u00e3o", self.stopped)):
            form.addRow(label, field)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.Save).setText("Criar OS corretiva")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)

    def _save(self):
        vehicle_id, problem = self.vehicle.currentData(), self.problem.text().strip()
        cause, action = self.cause.toPlainText().strip(), self.action.toPlainText().strip()
        mechanic_id = self.mechanic.currentData()
        if not vehicle_id or not mechanic_id or not problem or not cause or not action:
            show_notice(self, "Campos obrigat\u00f3rios", "Para a corretiva emergencial, informe equipamento, respons\u00e1vel, problema, causa e a\u00e7\u00e3o.", icon_name="warning")
            return
        try:
            emergency = self.api_client.create_emergency({"vehicle_id": int(vehicle_id), "severity": self.severity.currentData(), "equipment_stopped": self.stopped.isChecked(), "title": problem, "description": f"Problema: {problem}\nCausa: {cause}\nA\u00e7\u00e3o: {action}", "opened_at": self.opened_at.dateTime().toPython().isoformat(timespec="minutes")})
            emergency_id = int(emergency["id"])
            self.api_client.triage_emergency(emergency_id, {"assigned_mechanic_user_id": int(mechanic_id)})
            self.api_client.convert_emergency_to_work_order(emergency_id, {"assigned_mechanic_user_id": int(mechanic_id), "scheduled_date": self.opened_at.date().toString("yyyy-MM-dd")})
        except Exception as exc:
            show_notice(self, "Corretiva n\u00e3o registrada", str(exc), icon_name="warning")
            return
        self.accept()


class CorrectiveScheduledDialog(QDialog):
    """Programa uma corretiva e cria a OS sem abrir uma ocorrência emergencial."""

    def __init__(self, api_client, family: str, vehicles: list[dict], parent=None):
        super().__init__(parent)
        self.api_client, self.family, self.vehicles = api_client, family, list(vehicles or [])
        self.setWindowTitle(f"Corretiva programada - {family}")
        self.setMinimumWidth(610)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        title = QLabel(f"CORRETIVA PROGRAMADA - {family}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Planeje uma correção sem caracterizar emergência. Ao salvar, será criada uma programação e a OS da família.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        form = QFormLayout()
        form.setSpacing(10)
        self.vehicle = QComboBox()
        self.vehicle.addItem("Selecione o equipamento", None)
        for row in self.vehicles:
            label = _text(row.get("frota") or row.get("placa") or row.get("modelo")) or "Equipamento"
            local = _text((row.get("operational_location") or {}).get("full_name"))
            self.vehicle.addItem(f"{label}{f' | {local}' if local else ''}", row.get("id"))
        self.problem = QLineEdit()
        self.problem.setPlaceholderText("Ex.: troca programada de mangueira hidráulica")
        self.cause, self.action = QTextEdit(), QTextEdit()
        self.cause.setPlaceholderText("Descreva a causa identificada.")
        self.action.setPlaceholderText("Descreva a ação planejada.")
        self.cause.setMaximumHeight(70)
        self.action.setMaximumHeight(70)
        self.mechanic = QComboBox()
        self.mechanic.addItem("Selecione o responsável", None)
        try:
            for user in self.api_client.get_mechanics() or []:
                self.mechanic.addItem(_text(user.get("nome") or user.get("login")), user.get("id"))
        except Exception:
            pass
        self.scheduled_date = QDateEdit(QDate.currentDate())
        self.scheduled_date.setDisplayFormat("dd/MM/yyyy")
        self.scheduled_date.setCalendarPopup(True)
        for label, field in (
            ("Equipamento *", self.vehicle),
            ("Problema *", self.problem),
            ("Causa *", self.cause),
            ("Ação planejada *", self.action),
            ("Responsável *", self.mechanic),
            ("Data programada *", self.scheduled_date),
        ):
            form.addRow(label, field)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.Save).setText("Programar corretiva e criar OS")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)

    def _save(self):
        vehicle_id, problem = self.vehicle.currentData(), self.problem.text().strip()
        cause, action = self.cause.toPlainText().strip(), self.action.toPlainText().strip()
        mechanic_id = self.mechanic.currentData()
        if not vehicle_id or not mechanic_id or not problem or not cause or not action:
            show_notice(self, "Campos obrigatórios", "Informe equipamento, responsável, problema, causa e ação planejada.", icon_name="warning")
            return
        payload = {
            "source_type": "CORRETIVA_PROGRAMADA",
            "title": f"Corretiva programada - {problem}",
            "item_name": problem,
            "vehicle_ids": [int(vehicle_id)],
            "assigned_mechanic_user_id": int(mechanic_id),
            "start_date": self.scheduled_date.date().toString("yyyy-MM-dd"),
            "daily_capacity": 1,
            "status": "PROGRAMADA",
            "observation": f"Problema: {problem}\nCausa: {cause}\nAção planejada: {action}",
        }
        try:
            self.api_client.create_maintenance_schedule(payload)
        except Exception as exc:
            show_notice(self, "Corretiva não programada", str(exc), icon_name="warning")
            return
        self.accept()


class FamilyMaintenancePage(QFrame):
    """Manuten\u00e7\u00e3o simples por fam\u00edlia, sem Central de A\u00e7\u00f5es ou PCM."""
    open_page_requested = Signal(str)
    data_changed = Signal()

    def __init__(self, api_client, family: str, parent=None):
        super().__init__(parent)
        self.api_client, self.family = api_client, _text(family).upper()
        self.items, self.vehicles, self.highlighted_dates = [], [], []
        self.selected_date = None
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(f"CORRETIVAS {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Rotina direta da área: corretivas programadas e emergenciais, OS, preventivas e horímetros.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        corrective = QPushButton("Nova corretiva emergencial")
        corrective.setProperty("variant", "danger")
        corrective.clicked.connect(self._open_corrective)
        scheduled_corrective = QPushButton("Nova corretiva programada")
        scheduled_corrective.setProperty("variant", "primary")
        scheduled_corrective.clicked.connect(self._open_scheduled_corrective)
        preventive = QPushButton("Preventivas e hor\u00edmetros")
        preventive.setProperty("variant", "primary")
        preventive.clicked.connect(self._open_preventive)
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self.refresh)
        header.addWidget(corrective)
        header.addWidget(scheduled_corrective)
        header.addWidget(preventive)
        header.addWidget(refresh)
        layout.addLayout(header)
        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.total_card = StatCard("Servi\u00e7os", "0", f"Itens {self.family}", icon_name="maintenance")
        self.corrective_card = StatCard("Corretivas", "0", "Programadas ou emergenciais", icon_name="warning")
        self.preventive_card = StatCard("Preventivas", "0", "Programa\u00e7\u00f5es da \u00e1rea", icon_name="activities")
        self.area_target_card = StatCard("Meta da \u00e1rea", "50 h", f"Meta operacional {self.family}", icon_name="dashboard")
        self.total_target_card = StatCard("Meta total", "100 h", "RTG e LBS somados", icon_name="dashboard")
        for index, card in enumerate((self.total_card, self.corrective_card, self.preventive_card, self.area_target_card, self.total_target_card)):
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        layout.addLayout(cards)
        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setHorizontalSpacing(12)
        self.month = QDateEdit(QDate.currentDate())
        self.month.setCalendarPopup(True)
        self.month.setDisplayFormat("MM/yyyy")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for key, label in STATUS_LABELS.items(): self.status_filter.addItem(label, key)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar equipamento, servi\u00e7o ou OS")
        clear_date = QPushButton("Mostrar todo o m\u00eas")
        self.month.dateChanged.connect(lambda _date: self.refresh())
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        self.search.textChanged.connect(self._render_rows)
        clear_date.clicked.connect(self._clear_date_filter)
        for col, label, field in ((0, "Per\u00edodo", self.month), (1, "Status", self.status_filter), (2, "Pesquisa", self.search)):
            filter_layout.addWidget(QLabel(label), 0, col)
            filter_layout.addWidget(field, 1, col)
            filter_layout.setColumnStretch(col, 1)
        filter_layout.addWidget(clear_date, 1, 3)
        layout.addWidget(filters)
        content = QGridLayout()
        content.setHorizontalSpacing(14)
        calendar_card = QFrame(); style_table_card(calendar_card)
        calendar_layout = QVBoxLayout(calendar_card); calendar_layout.setContentsMargins(14, 14, 14, 14)
        caption = QLabel("CALEND\u00c1RIO DE PROGRAMA\u00c7\u00d5ES"); caption.setObjectName("SectionCaption")
        self.calendar_info = QLabel("Clique em um dia para ver somente as programa\u00e7\u00f5es daquela data."); self.calendar_info.setWordWrap(True)
        self.calendar = QCalendarWidget(); self.calendar.setGridVisible(True); self.calendar.setSelectedDate(QDate.currentDate()); self.calendar.clicked.connect(self._select_calendar_date)
        calendar_layout.addWidget(caption); calendar_layout.addWidget(self.calendar_info); calendar_layout.addWidget(self.calendar)
        content.addWidget(calendar_card, 0, 0)
        table_card = QFrame(); style_table_card(table_card)
        table_layout = QVBoxLayout(table_card); table_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Data", "Equipamento", "Tipo", "Servi\u00e7o", "Situa\u00e7\u00e3o", "Problema, causa e a\u00e7\u00e3o", "OS"])
        configure_table(self.table, stretch_last=False); self.table.setMinimumHeight(430)
        table_layout.addWidget(self.table); content.addWidget(table_card, 0, 1)
        content.setColumnStretch(0, 1); content.setColumnStretch(1, 3)
        layout.addLayout(content, 1)

    def _open_preventive(self): self.open_page_requested.emit(f"{self.family.lower()}_preventive")
    def _open_corrective(self):
        dialog = CorrectiveEmergencyDialog(self.api_client, self.family, self.vehicles, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh(); self.data_changed.emit()
    def _open_scheduled_corrective(self):
        dialog = CorrectiveScheduledDialog(self.api_client, self.family, self.vehicles, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh(); self.data_changed.emit()
    def _clear_date_filter(self):
        self.selected_date = None; self.calendar_info.setText("Mostrando todas as programa\u00e7\u00f5es do per\u00edodo selecionado."); self._render_rows()
    def _select_calendar_date(self, selected: QDate):
        self.selected_date = selected; self.calendar_info.setText(f"Programa\u00e7\u00f5es de {selected.toString('dd/MM/yyyy')}."); self._render_rows()

    def refresh(self):
        try:
            selected = self.month.date()
            overview = self.api_client.get_maintenance_overview(selected.year(), selected.month()) or {}
            self.items = [item for item in overview.get("itens", []) if _is_family(item, self.family)]
            self.vehicles = self.api_client.get_equipment(tipo=self.family.lower(), ativos=True) or []
            self._refresh_calendar(); self._render_rows()
        except Exception as exc:
            show_notice(self, f"Falha ao carregar manuten\u00e7\u00e3o {self.family}", str(exc), icon_name="warning")

    def _refresh_calendar(self):
        for day in self.highlighted_dates: self.calendar.setDateTextFormat(day, QTextCharFormat())
        self.highlighted_dates = []
        preventive, corrective = QTextCharFormat(), QTextCharFormat()
        preventive.setBackground(QColor("#d9f7e8")); preventive.setForeground(QColor("#156c42"))
        corrective.setBackground(QColor("#ffe3d6")); corrective.setForeground(QColor("#a13d18"))
        for item in self.items:
            day = QDate.fromString(_text(item.get("scheduled_date"))[:10], "yyyy-MM-dd")
            if not day.isValid(): continue
            origin = _text((item.get("schedule") or {}).get("source_origin_type") or (item.get("schedule") or {}).get("source_type")).upper()
            self.calendar.setDateTextFormat(day, preventive if "PREVENT" in origin else corrective); self.highlighted_dates.append(day)

    def _matches(self, item: dict) -> bool:
        if self.status_filter.currentData() and _text(item.get("status")).upper() != _text(self.status_filter.currentData()): return False
        if self.selected_date and _text(item.get("scheduled_date"))[:10] != self.selected_date.toString("yyyy-MM-dd"): return False
        vehicle, order, schedule = item.get("vehicle") or {}, item.get("work_order") or {}, item.get("schedule") or {}
        query = self.search.text().strip().casefold()
        return not query or query in " ".join(_text(value) for value in (vehicle.get("frota"), vehicle.get("placa"), schedule.get("title"), order.get("order_number"), item.get("observation"))).casefold()

    def _render_rows(self):
        rows = [item for item in self.items if self._matches(item)]
        self.table.setSortingEnabled(False); self.table.setRowCount(len(rows))
        preventive = corrective = pending = 0
        for index, item in enumerate(rows):
            status, schedule = _text(item.get("status") or "PENDENTE").upper(), item.get("schedule") or {}
            origin = _text(schedule.get("source_origin_type") or schedule.get("source_type")).upper()
            service_type = "Preventiva" if "PREVENT" in origin else (
                "Corretiva programada" if "CORRETIVA_PROGRAMADA" in origin else (
                    "Corretiva emergencial" if "EMERGENC" in origin else "Corretiva"
                )
            )
            preventive += service_type == "Preventiva"; corrective += service_type != "Preventiva"; pending += status in PENDING_STATUSES
            vehicle, order, activity, checklist = item.get("vehicle") or {}, item.get("work_order") or {}, item.get("activity") or {}, item.get("checklist_item") or {}
            service = _text(schedule.get("title") or activity.get("titulo") or checklist.get("nome") or checklist.get("item_principal")) or "Servi\u00e7o de manuten\u00e7\u00e3o"
            values = [item.get("scheduled_date") or "-", vehicle.get("frota") or vehicle.get("placa") or "-", service_type, service, STATUS_LABELS.get(status, status), _text(item.get("observation") or item.get("not_executed_reason")) or "-", order.get("order_number") or "-"]
            for column, value in enumerate(values): self.table.setItem(index, column, QTableWidgetItem(str(value)))
        self.total_card.set_content("Servi\u00e7os", str(len(rows)), f"Itens {self.family}")
        self.corrective_card.set_content("Corretivas", str(corrective if corrective else pending), "Programadas ou emergenciais")
        self.preventive_card.set_content("Preventivas", str(preventive), "Programa\u00e7\u00f5es da \u00e1rea")
