from __future__ import annotations

from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from components import show_notice
from theme import configure_dialog_window, configure_table, make_table_item, style_card, style_table_card


VACATION_STATUSES = ("PROGRAMADA", "APROVADA", "CANCELADA")


def _date_editor(value: date) -> QDateEdit:
    editor = QDateEdit()
    editor.setCalendarPopup(True)
    editor.setDisplayFormat("dd/MM/yyyy")
    editor.setDate(QDate(value.year, value.month, value.day))
    editor.setMinimumHeight(34)
    return editor


class VacationDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.payload: dict | None = None
        self.setWindowTitle("Programar férias")
        configure_dialog_window(self, width=620, height=430, min_width=520, min_height=360)
        style_card(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        title = QLabel("Programar férias")
        title.setObjectName("PageTitle")
        subtitle = QLabel("O sistema bloqueia períodos sobrepostos para o mesmo colaborador.")
        subtitle.setObjectName("SectionCaption")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.employee_combo = QComboBox()
        for employee in self.api_client.get_employees(status="ATIVO"):
            self.employee_combo.addItem(
                f"{employee.get('registration')} - {employee.get('full_name')}",
                employee.get("id"),
            )
        today = date.today()
        self.start_date = _date_editor(today)
        self.end_date = _date_editor(today)
        self.status_combo = QComboBox()
        self.status_combo.addItems(("PROGRAMADA", "APROVADA"))
        self.notes_input = QComboBox()
        self.notes_input.setEditable(True)
        self.notes_input.setInsertPolicy(QComboBox.NoInsert)
        self.notes_input.lineEdit().setPlaceholderText("Observação opcional")

        for label_text, widget in (
            ("Colaborador", self.employee_combo),
            ("Início", self.start_date),
            ("Fim", self.end_date),
            ("Situação", self.status_combo),
            ("Observação", self.notes_input),
        ):
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            root.addWidget(label)
            root.addWidget(widget)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        save = QPushButton("Salvar férias")
        save.setProperty("variant", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def _submit(self):
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        if end < start:
            show_notice(self, "Período inválido", "A data final não pode ser anterior à data inicial.", icon_name="warning")
            return
        if self.employee_combo.currentData() is None:
            show_notice(self, "Colaborador obrigatório", "Selecione o colaborador.", icon_name="warning")
            return
        self.payload = {
            "employee_id": self.employee_combo.currentData(),
            "starts_on": start,
            "ends_on": end,
            "status": self.status_combo.currentText(),
            "notes": self.notes_input.currentText().strip() or None,
        }
        self.accept()


class VacationsPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.rows: list[dict] = []
        self.marked_dates: list[QDate] = []
        self.setObjectName("ContentSurface")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel("Férias")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Calendário de férias programadas e aprovadas. O colaborador continua ativo; férias são uma ocorrência planejada.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(subtitle)
        add_button = QPushButton("Programar férias")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.add_vacation)
        cancel_button = QPushButton("Cancelar período")
        cancel_button.clicked.connect(self.cancel_selected)
        header.addLayout(text)
        header.addStretch()
        header.addWidget(cancel_button)
        header.addWidget(add_button)
        root.addLayout(header)

        rules = QFrame()
        style_table_card(rules)
        rules_layout = QVBoxLayout(rules)
        rules_layout.setContentsMargins(14, 12, 14, 12)
        rule_title = QLabel("Regras de férias")
        rule_title.setObjectName("SectionTitle")
        rule_text = QLabel(
            "1. Período de 1 a 90 dias.  2. Não é permitido sobrepor férias do mesmo colaborador.  "
            "3. Cancelamento exige motivo.  4. DSR não pode ser lançado no domingo coberto por férias."
        )
        rule_text.setWordWrap(True)
        rules_layout.addWidget(rule_title)
        rules_layout.addWidget(rule_text)
        root.addWidget(rules)

        content = QHBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setFirstDayOfWeek(Qt.Monday)
        self.calendar.currentPageChanged.connect(lambda *_: self.refresh())
        content.addWidget(self.calendar, 1)

        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_title = QLabel("Períodos do mês exibido")
        table_title.setObjectName("SectionTitle")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Colaborador", "Início", "Fim", "Situação", "Observação"])
        configure_table(self.table)
        self.table.setMinimumHeight(420)
        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table)
        content.addWidget(table_card, 2)
        root.addLayout(content, 1)

    def set_loading_state(self, loading: bool):
        self.setDisabled(loading)

    def refresh(self, *_):
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        starts_on = date(year, month, 1)
        ends_on = date(year, month, monthrange(year, month)[1])
        try:
            self.rows = self.api_client.get_employee_vacations(
                date_from=starts_on.isoformat(),
                date_to=ends_on.isoformat(),
            ) or []
            self._render()
        except Exception as exc:
            show_notice(self, "Falha ao carregar férias", str(exc), icon_name="warning")

    def _render(self):
        default_format = QTextCharFormat()
        for marked in self.marked_dates:
            self.calendar.setDateTextFormat(marked, default_format)
        self.marked_dates = []
        colors = {
            "PROGRAMADA": QColor("#D97706"),
            "APROVADA": QColor("#047857"),
            "CANCELADA": QColor("#6B7280"),
        }
        for vacation in self.rows:
            start = date.fromisoformat(vacation["starts_on"])
            end = date.fromisoformat(vacation["ends_on"])
            current = start
            date_format = QTextCharFormat()
            date_format.setBackground(colors.get(vacation.get("status"), QColor("#2563EB")))
            date_format.setForeground(QColor("white"))
            while current <= end:
                qdate = QDate(current.year, current.month, current.day)
                self.calendar.setDateTextFormat(qdate, date_format)
                self.marked_dates.append(qdate)
                current = date.fromordinal(current.toordinal() + 1)

        self.table.setRowCount(len(self.rows))
        for row_index, vacation in enumerate(self.rows):
            employee = vacation.get("employee") or {}
            values = [
                f"{employee.get('registration') or '-'}\n{employee.get('full_name') or '-'}",
                vacation.get("starts_on") or "-",
                vacation.get("ends_on") or "-",
                vacation.get("status") or "-",
                vacation.get("notes") or "-",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, make_table_item(value, payload=vacation))
            self.table.setRowHeight(row_index, 48)
        self.table.resizeColumnsToContents()

    def add_vacation(self):
        dialog = VacationDialog(self.api_client, self)
        if not dialog.exec() or not dialog.payload:
            return
        try:
            self.api_client.create_employee_vacation(dialog.payload)
            self.refresh()
            self.data_changed.emit()
            show_notice(self, "Férias programadas", "O período foi registrado no calendário.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao programar férias", str(exc), icon_name="warning")

    def cancel_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            show_notice(self, "Selecione um período", "Selecione uma linha da tabela para cancelar as férias.", icon_name="warning")
            return
        vacation = selected[0].data(Qt.UserRole) or {}
        if vacation.get("status") == "CANCELADA":
            show_notice(self, "Período cancelado", "Este período já está cancelado.", icon_name="warning")
            return
        reason, confirmed = QInputDialog.getText(self, "Cancelar férias", "Motivo do cancelamento:")
        if not confirmed or not reason.strip():
            return
        try:
            self.api_client.cancel_employee_vacation(int(vacation["id"]), reason.strip())
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao cancelar férias", str(exc), icon_name="warning")
