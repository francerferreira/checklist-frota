from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
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

from components import show_notice
from theme import configure_table, make_table_item, style_card, style_table_card


class SpecialSchedulePage(QFrame):
    """Escala nativa do Desktop, com as mesmas regras do Web Mobile."""

    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.employees: list[dict] = []
        self.filtered_employees: list[dict] = []
        self.row_checks: dict[int, QCheckBox] = {}
        self._initializing = True
        self.setObjectName("ContentSurface")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        title = QLabel("Escala de Domingo e Feriado")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Selecione quem trabalhara e registre a DSR prevista para cada colaborador.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.counter = QLabel("Carregando colaboradores ativos...")
        self.counter.setObjectName("SectionTitle")
        summary = QFrame()
        summary.setObjectName("HeaderCard")
        summary.setAttribute(Qt.WA_StyledBackground, True)
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.addWidget(self.counter)
        summary_layout.addStretch()
        hint = QLabel("A DSR e criada apos a confirmacao da presenca no domingo.")
        hint.setObjectName("MutedText")
        summary_layout.addWidget(hint)
        root.addWidget(summary)

        form = QFrame()
        style_card(form)
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(8)

        self.schedule_date = QDateEdit()
        self.schedule_date.setCalendarPopup(True)
        self.schedule_date.setDisplayFormat("dd/MM/yyyy")
        self.schedule_date.setDate(self._next_sunday_qdate())
        self.schedule_type = QComboBox()
        self.schedule_type.addItems(["DOMINGO", "FERIADO"])
        self.holiday_name = QLineEdit()
        self.holiday_name.setPlaceholderText("Nome do feriado")
        self.dsr_date = QDateEdit()
        self.dsr_date.setCalendarPopup(True)
        self.dsr_date.setDisplayFormat("dd/MM/yyyy")
        self.dsr_date.setDate(self.schedule_date.date().addDays(1))
        self.load_button = QPushButton("CARREGAR")
        self.load_button.clicked.connect(self.refresh_employees)
        self.schedule_type.currentTextChanged.connect(self._toggle_holiday)
        self.schedule_date.dateChanged.connect(self._sync_dsr_date)

        self._field(form_layout, 0, 0, "DATA DA ESCALA", self.schedule_date)
        self._field(form_layout, 0, 1, "TIPO", self.schedule_type)
        self._field(form_layout, 1, 0, "NOME DO FERIADO", self.holiday_name)
        dsr_box = QHBoxLayout()
        dsr_box.setContentsMargins(0, 0, 0, 0)
        dsr_box.addWidget(self.dsr_date, 1)
        dsr_box.addWidget(self.load_button)
        dsr_field = QFrame()
        dsr_field_layout = QVBoxLayout(dsr_field)
        dsr_field_layout.setContentsMargins(0, 0, 0, 0)
        dsr_field_layout.addWidget(QLabel("DATA PREVISTA DA DSR"))
        dsr_field_layout.addLayout(dsr_box)
        form_layout.addWidget(dsr_field, 1, 1)
        root.addWidget(form)

        filters = QFrame()
        filters_layout = QGridLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setHorizontalSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar colaborador ou matricula")
        self.area_filter = self._combo("TODAS AS AREAS")
        self.team_filter = self._combo("TODOS OS TIMES")
        self.shift_filter = self._combo("TODOS OS TURNOS")
        self.function_filter = self._combo("TODAS AS FUNCOES")
        for widget in (self.search, self.area_filter, self.team_filter, self.shift_filter, self.function_filter):
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.render_table)
            else:
                widget.currentTextChanged.connect(self.render_table)
        filters_layout.addWidget(self.search, 0, 0)
        filters_layout.addWidget(self.area_filter, 0, 1)
        filters_layout.addWidget(self.team_filter, 0, 2)
        filters_layout.addWidget(self.shift_filter, 0, 3)
        filters_layout.addWidget(self.function_filter, 0, 4)
        root.addWidget(filters)

        actions = QHBoxLayout()
        self.select_all = QCheckBox("SELECIONAR TODOS")
        self.select_all.stateChanged.connect(self._toggle_all)
        history_button = QPushButton("HISTORICO")
        history_button.clicked.connect(self.open_history)
        pdf_button = QPushButton("EXPORTAR PDF")
        pdf_button.clicked.connect(self.export_pdf)
        actions.addWidget(self.select_all)
        actions.addStretch()
        actions.addWidget(history_button)
        actions.addWidget(pdf_button)
        root.addLayout(actions)

        self.table_card = QFrame()
        style_table_card(self.table_card)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["AREA", "COLABORADOR", "MATRICULA", "FUNCAO / TURNO", "SITUACAO", "DSR PREVISTA", "ACAO"])
        configure_table(self.table)
        self.table.setMinimumHeight(420)
        table_layout.addWidget(self.table)
        root.addWidget(self.table_card, 1)

        save_button = QPushButton("SALVAR ESCALA E DSR")
        save_button.setProperty("variant", "primary")
        save_button.setMinimumHeight(48)
        save_button.clicked.connect(self.save_schedule)
        root.addWidget(save_button)
        self._toggle_holiday(self.schedule_type.currentText())
        self.refresh_employees()
        self._initializing = False

    @staticmethod
    def _field(layout, row, column, label_text, widget):
        box = QFrame()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setObjectName("SectionCaption")
        box_layout.addWidget(label)
        box_layout.addWidget(widget)
        layout.addWidget(box, row, column)

    @staticmethod
    def _combo(default: str):
        combo = QComboBox()
        combo.addItem(default, "")
        return combo

    @staticmethod
    def _next_sunday_qdate():
        today = date.today()
        days = (6 - today.weekday()) % 7 or 7
        target = today + timedelta(days=days)
        return QDate(target.year, target.month, target.day)

    def _sync_dsr_date(self, selected: QDate):
        if self.schedule_type.currentText() == "DOMINGO":
            self.dsr_date.setDate(selected.addDays(1))

    def _toggle_holiday(self, value: str):
        is_holiday = value == "FERIADO"
        self.holiday_name.setEnabled(is_holiday)
        self.dsr_date.setEnabled(not is_holiday)

    def refresh(self, *_args):
        self.refresh_employees()

    def refresh_employees(self):
        try:
            self.employees = list(self.api_client.get_employees(status="ATIVO") or [])
        except Exception as exc:
            if not self._initializing:
                show_notice(self, "Falha ao carregar colaboradores", str(exc), icon_name="warning")
            self.employees = []
        self._populate_filters()
        self.render_table()

    def _populate_filters(self):
        values = {
            self.area_filter: sorted({str(row.get("team_name") or "").strip() for row in self.employees if row.get("team_name")}),
            self.team_filter: sorted({str(row.get("team_name") or "").strip() for row in self.employees if row.get("team_name")}),
            self.shift_filter: sorted({str(row.get("shift_name") or "").strip() for row in self.employees if row.get("shift_name")}),
            self.function_filter: sorted({str(row.get("function_name") or "").strip() for row in self.employees if row.get("function_name")}),
        }
        for combo, options in values.items():
            current = combo.currentData() or ""
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(combo.property("default_label") or "TODAS AS OPCOES", "")
            combo.addItems(options)
            if current:
                combo.setCurrentText(current)
            combo.blockSignals(False)
        self.area_filter.setItemText(0, "TODAS AS AREAS")
        self.team_filter.setItemText(0, "TODOS OS TIMES")
        self.shift_filter.setItemText(0, "TODOS OS TURNOS")
        self.function_filter.setItemText(0, "TODAS AS FUNCOES")

    def _matches(self, employee: dict) -> bool:
        term = self.search.text().strip().casefold()
        haystack = f"{employee.get('full_name', '')} {employee.get('registration', '')}".casefold()
        return (
            (not term or term in haystack)
            and (not self.area_filter.currentData() or self.area_filter.currentText() == employee.get("team_name"))
            and (not self.team_filter.currentData() or self.team_filter.currentText() == employee.get("team_name"))
            and (not self.shift_filter.currentData() or self.shift_filter.currentText() == employee.get("shift_name"))
            and (not self.function_filter.currentData() or self.function_filter.currentText() == employee.get("function_name"))
        )

    def render_table(self, *_args):
        self.filtered_employees = [row for row in self.employees if self._matches(row)]
        self.row_checks = {}
        self.table.setRowCount(len(self.filtered_employees))
        for row_index, employee in enumerate(self.filtered_employees):
            self.table.setItem(row_index, 0, make_table_item(employee.get("team_name") or "-"))
            self.table.setItem(row_index, 1, make_table_item(employee.get("full_name") or "-"))
            self.table.setItem(row_index, 2, make_table_item(employee.get("registration") or "-"))
            function_shift = " / ".join(value for value in [employee.get("function_name"), employee.get("shift_name")] if value)
            self.table.setItem(row_index, 3, make_table_item(function_shift or "-"))
            self.table.setItem(row_index, 4, make_table_item("INCLUIR NA ESCALA"))
            self.table.setItem(row_index, 5, make_table_item(self.dsr_date.date().toString("dd/MM/yyyy") if self.schedule_type.currentText() == "DOMINGO" else "NAO SE APLICA"))
            check = QCheckBox()
            check.setProperty("employee_id", employee.get("id"))
            check.stateChanged.connect(lambda *_args: self._update_counter())
            self.table.setCellWidget(row_index, 6, check)
            self.row_checks[row_index] = check
        self.table.resizeColumnsToContents()
        self._update_counter()

    def _toggle_all(self, state: int):
        checked = state == Qt.Checked
        for check in self.row_checks.values():
            check.setChecked(checked)
        self._update_counter()

    def _update_counter(self):
        selected = sum(check.isChecked() for check in self.row_checks.values())
        self.counter.setText(f"{len(self.filtered_employees)} elegiveis | {selected} ja selecionados")

    def save_schedule(self):
        selected = [self.filtered_employees[index] for index, check in self.row_checks.items() if check.isChecked()]
        if not selected:
            show_notice(self, "Selecao obrigatoria", "Selecione ao menos um colaborador.", icon_name="warning")
            return
        schedule_type = self.schedule_type.currentText()
        if schedule_type == "FERIADO" and not self.holiday_name.text().strip():
            show_notice(self, "Feriado sem nome", "Informe o nome do feriado.", icon_name="warning")
            return
        payload = {
            "schedule_date": self.schedule_date.date().toString("yyyy-MM-dd"),
            "schedule_type": schedule_type,
            "holiday_name": self.holiday_name.text().strip() or None,
            "entries": [
                {
                    "employee_id": employee.get("id"),
                    "dsr_date": self.dsr_date.date().toString("yyyy-MM-dd") if schedule_type == "DOMINGO" else None,
                }
                for employee in selected
            ],
        }
        try:
            result = self.api_client.create_special_schedule(payload)
            show_notice(self, "Escala salva", f"{len(result or [])} colaborador(es) incluido(s) na escala.", icon_name="dashboard")
            self.data_changed.emit()
            self.refresh_employees()
        except Exception as exc:
            show_notice(self, "Falha ao salvar escala", str(exc), icon_name="warning")

    def open_history(self):
        try:
            rows = self.api_client.get_special_schedules()
        except Exception as exc:
            show_notice(self, "Historico indisponivel", str(exc), icon_name="warning")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Historico de escala")
        dialog.resize(980, 560)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(rows or []), 6)
        table.setHorizontalHeaderLabels(["DATA", "TIPO", "COLABORADOR", "AREA", "SITUACAO", "DSR"])
        configure_table(table)
        for row_index, row in enumerate(rows or []):
            employee = row.get("employee") or {}
            values = [row.get("schedule_date"), row.get("schedule_type"), employee.get("full_name"), employee.get("team_name"), row.get("status"), row.get("dsr_date") or "NAO SE APLICA"]
            for column, value in enumerate(values):
                table.setItem(row_index, column, make_table_item(value or "-"))
        layout.addWidget(table)
        close_button = QPushButton("FECHAR")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignRight)
        dialog.exec()

    def export_pdf(self):
        try:
            content = self.api_client.get_special_schedule_pdf(
                self.schedule_date.date().toString("yyyy-MM-dd"), self.schedule_type.currentText()
            )
        except Exception as exc:
            show_notice(self, "Exportacao indisponivel", str(exc), icon_name="warning")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar escala em PDF", "escala_domingo_feriado.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            with open(path, "wb") as handle:
                handle.write(content)
            show_notice(self, "PDF exportado", f"Arquivo salvo em {path}.", icon_name="dashboard")
        except OSError as exc:
            show_notice(self, "Falha ao salvar PDF", str(exc), icon_name="warning")
