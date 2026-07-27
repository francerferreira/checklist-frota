from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QDateTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, style_card, style_filter_bar, style_table_card


STOP_STATUSES = {"INDISPONIVEL", "MANUTENCAO"}
STATUS_LABELS = {
    "SEM_APONTAMENTO": "Sem apontamento",
    "DISPONIVEL": "Disponivel",
    "INDISPONIVEL": "Indisponivel",
    "RESTRICAO": "Restricao",
    "MANUTENCAO": "Manutencao",
}
STATUS_COLORS = {
    "SEM_APONTAMENTO": ("#F1F5F9", "#64748B"),
    "DISPONIVEL": ("#DCFCE7", "#166534"),
    "INDISPONIVEL": ("#FEE2E2", "#991B1B"),
    "RESTRICAO": ("#FEF3C7", "#92400E"),
    "MANUTENCAO": ("#E2E8F0", "#334155"),
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _format_datetime(value: str | None) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%d/%m/%Y %H:%M") if parsed else "-"


def _hours_for_events(events: list[dict], start: datetime, end: datetime) -> float:
    now = datetime.now()
    total = timedelta()
    for event in events:
        if str(event.get("status") or "").upper() not in STOP_STATUSES:
            continue
        event_start = _parse_datetime(event.get("started_at"))
        if not event_start:
            continue
        event_end = _parse_datetime(event.get("ended_at")) or now
        overlap_start = max(event_start, start)
        overlap_end = min(event_end, end, now)
        if overlap_end > overlap_start:
            total += overlap_end - overlap_start
    return round(total.total_seconds() / 3600, 2)


class EquipmentStatusDialog(QDialog):
    def __init__(self, api_client, vehicle: dict, user: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.vehicle = vehicle
        self.user = user or {}
        self.evidence_file: str | None = None
        self.setWindowTitle(f"Atualizar situacao - {vehicle.get('frota') or 'equipamento'}")
        self.setMinimumWidth(560)

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self.status = QComboBox()
        for value in ("DISPONIVEL", "INDISPONIVEL", "RESTRICAO", "MANUTENCAO"):
            self.status.addItem(STATUS_LABELS[value], value)
        self.status.currentIndexChanged.connect(self._update_reason_hint)

        self.started_at = QDateTimeEdit(QDateTime.currentDateTime())
        self.started_at.setCalendarPopup(True)
        self.started_at.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.reason = QLineEdit()
        self.observation = QLineEdit()
        self.observation.setPlaceholderText("Detalhe operacional opcional")

        evidence_row = QHBoxLayout()
        self.evidence_label = QLabel("Nenhuma foto selecionada")
        self.evidence_label.setObjectName("SectionCaption")
        evidence_button = QPushButton("Selecionar foto")
        evidence_button.clicked.connect(self._select_evidence)
        evidence_row.addWidget(self.evidence_label, 1)
        evidence_row.addWidget(evidence_button)

        form.addRow("Nova situacao", self.status)
        form.addRow("Inicio da situacao", self.started_at)
        form.addRow("Motivo", self.reason)
        form.addRow("Observacao", self.observation)
        form.addRow("Evidencia", evidence_row)

        footer = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salvar situacao")
        save.setProperty("variant", "primary")
        save.clicked.connect(self._save)
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(save)
        form.addRow(footer)
        self._update_reason_hint()

    def _update_reason_hint(self):
        requires_reason = self.status.currentData() in STOP_STATUSES | {"RESTRICAO"}
        self.reason.setPlaceholderText("Obrigatorio para indisponivel, restricao ou manutencao" if requires_reason else "Opcional")

    def _select_evidence(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar evidencia",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp);;Todos os arquivos (*)",
        )
        if path:
            self.evidence_file = path
            self.evidence_label.setText(Path(path).name)

    def _save(self):
        status = str(self.status.currentData() or "")
        reason = self.reason.text().strip()
        if status in STOP_STATUSES | {"RESTRICAO"} and not reason:
            show_notice(self, "Motivo obrigatorio", "Informe o motivo da situacao escolhida.", icon_name="warning")
            return
        evidence_path = None
        try:
            if self.evidence_file:
                result = self.api_client.upload_file(
                    self.evidence_file,
                    str(self.vehicle.get("frota") or self.vehicle.get("placa") or "equipamento"),
                    "parada",
                    str(self.user.get("login") or "desktop"),
                )
                evidence_path = result.get("path") or result.get("url")
            self.api_client.set_equipment_operational_status(
                int(self.vehicle["id"]),
                {
                    "status": status,
                    "started_at": self.started_at.dateTime().toPython().isoformat(timespec="minutes"),
                    "reason": reason or None,
                    "observation": self.observation.text().strip() or None,
                    "evidence_path": evidence_path,
                },
            )
        except Exception as exc:
            show_notice(self, "Situacao nao salva", str(exc), icon_name="warning")
            return
        self.accept()


class FamilyDowntimePage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, family: str, user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = str(family or "").strip().upper()
        self.user = user or {}
        self.rows: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel(f"CONTROLE DE PARADAS - {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"Registre e acompanhe paradas da familia {self.family}. "
            "O encerramento da parada ocorre ao registrar uma nova situacao operacional."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.total_card = StatCard("Equipamentos", "0", f"Ativos {self.family}", icon_name="equipment")
        self.stopped_card = StatCard("Em parada", "0", "Indisponivel ou manutencao", icon_name="warning")
        self.hours_card = StatCard("Horas no periodo", "0,00 h", "Paradas acumuladas", icon_name="reports")
        for index, card in enumerate((self.total_card, self.stopped_card, self.hours_card)):
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        layout.addLayout(cards)

        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(8)
        self.date_from = QDateEdit(QDate.currentDate())
        self.date_to = QDateEdit(QDate.currentDate())
        for field in (self.date_from, self.date_to):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd/MM/yyyy")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar equipamento, local ou serie")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for value in ("DISPONIVEL", "INDISPONIVEL", "RESTRICAO", "MANUTENCAO", "SEM_APONTAMENTO"):
            self.status_filter.addItem(STATUS_LABELS[value], value)
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        filter_layout.addWidget(QLabel("Inicio"), 0, 0)
        filter_layout.addWidget(self.date_from, 1, 0)
        filter_layout.addWidget(QLabel("Fim"), 0, 1)
        filter_layout.addWidget(self.date_to, 1, 1)
        filter_layout.addWidget(QLabel("Equipamento"), 0, 2)
        filter_layout.addWidget(self.search, 1, 2)
        filter_layout.addWidget(QLabel("Status"), 0, 3)
        filter_layout.addWidget(self.status_filter, 1, 3)
        filter_layout.addWidget(refresh_button, 1, 4)
        for column in (0, 1, 2, 3):
            filter_layout.setColumnStretch(column, 1)
        layout.addWidget(filters)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Equipamento", "Local", "Situacao", "Inicio da parada", "Horas no periodo", "Motivo", "Acao"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(420)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

    def set_loading_state(self, loading: bool):
        self.setEnabled(not loading)

    def _belongs_to_family(self, row: dict) -> bool:
        family = row.get("family") or {}
        vehicle = row.get("vehicle") or {}
        values = (
            family.get("code"), family.get("name"),
            vehicle.get("tipo"), vehicle.get("frota"),
        )
        return any(self.family in str(value or "").upper() for value in values)

    def _matches_filters(self, row: dict) -> bool:
        vehicle = row.get("vehicle") or {}
        location = row.get("location") or {}
        state = vehicle.get("operational_state") or {}
        status = str(state.get("operational_status") or "SEM_APONTAMENTO").upper()
        selected_status = str(self.status_filter.currentData() or "")
        if selected_status and status != selected_status:
            return False
        query = self.search.text().strip().casefold()
        if query:
            searchable = " ".join(
                str(value or "")
                for value in (vehicle.get("frota"), vehicle.get("placa"), vehicle.get("modelo"), vehicle.get("serial_number"), location.get("full_name"))
            ).casefold()
            if query not in searchable:
                return False
        return True

    def refresh(self):
        try:
            date_from = self.date_from.date().toString("yyyy-MM-dd")
            date_to = self.date_to.date().toString("yyyy-MM-dd")
            overview = self.api_client.get_availability_overview(date_from=date_from, date_to=date_to)
            start = datetime.combine(self.date_from.date().toPython(), datetime.min.time())
            end = datetime.combine(self.date_to.date().toPython(), datetime.max.time())
            rows = []
            for row in overview.get("rows", []):
                if not self._belongs_to_family(row):
                    continue
                vehicle = row.get("vehicle") or {}
                history = self.api_client.get_equipment_status_history(int(vehicle["id"]))
                row = {**row, "status_history": history or []}
                if self._matches_filters(row):
                    rows.append(row)
            self.rows = rows
            self._render_rows(start, end)
        except Exception as exc:
            show_notice(self, "Falha ao carregar paradas", str(exc), icon_name="warning")

    def _render_rows(self, start: datetime, end: datetime):
        total_hours = 0.0
        stopped = 0
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            vehicle = row.get("vehicle") or {}
            state = vehicle.get("operational_state") or {}
            status = str(state.get("operational_status") or "SEM_APONTAMENTO").upper()
            history = row.get("status_history") or []
            hours = _hours_for_events(history, start, end)
            total_hours += hours
            if status in STOP_STATUSES:
                stopped += 1
            location = row.get("location") or {}
            current_event = next((event for event in history if not event.get("ended_at")), None)
            values = [
                vehicle.get("frota") or vehicle.get("placa") or f"ID {vehicle.get('id')}",
                location.get("full_name") or "Sem local",
                STATUS_LABELS.get(status, status),
                _format_datetime(current_event.get("started_at") if current_event else None),
                f"{hours:.2f} h",
                (current_event or {}).get("reason") or state.get("status_reason") or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 2:
                    background, foreground = STATUS_COLORS.get(status, STATUS_COLORS["SEM_APONTAMENTO"])
                    item.setBackground(QColor(background))
                    item.setForeground(QColor(foreground))
                    item.setToolTip(f"Situacao atual: {STATUS_LABELS.get(status, status)}")
                self.table.setItem(index, column, item)
            action = QPushButton("Atualizar situacao")
            action.clicked.connect(lambda _checked=False, v=vehicle: self._open_status_dialog(v))
            self.table.setCellWidget(index, 6, action)
        self.total_card.set_content("Equipamentos", str(len(self.rows)), f"Ativos {self.family}")
        self.stopped_card.set_content("Em parada", str(stopped), "Indisponivel ou manutencao")
        self.hours_card.set_content("Horas no periodo", f"{total_hours:.2f} h", "Paradas acumuladas")

    def _open_status_dialog(self, vehicle: dict):
        dialog = EquipmentStatusDialog(self.api_client, vehicle, self.user, self)
        if dialog.exec() == QDialog.Accepted:
            self.data_changed.emit()
            self.refresh()
