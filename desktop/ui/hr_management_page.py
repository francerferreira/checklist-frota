from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QTabWidget, QVBoxLayout

from components import TableSkeletonOverlay, run_export_by_type, show_notice
from services.export_service import export_rows_to_csv, export_rows_to_xlsx, make_default_export_path
from theme import configure_table, make_table_item, style_table_card


class HRManagementPage(QFrame):
    data_changed = Signal()
    open_page_requested = Signal(str)

    def __init__(self, api_client, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.current_user = current_user or {}
        self.overview: dict = {}
        self.setObjectName("ContentSurface")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel("Central de RH")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Acesse colaboradores, frequência, férias e documentos em um único módulo de RH.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(subtitle)
        header.addLayout(text)
        header.addStretch()
        self.export_csv_button = QPushButton("Exportar CSV")
        self.export_csv_button.clicked.connect(lambda: self.export_alerts("csv"))
        self.export_xlsx_button = QPushButton("Exportar Excel")
        self.export_xlsx_button.setProperty("variant", "primary")
        self.export_xlsx_button.clicked.connect(lambda: self.export_alerts("xlsx"))
        header.addWidget(self.export_csv_button)
        header.addWidget(self.export_xlsx_button)
        layout.addLayout(header)

        shortcuts = QHBoxLayout()
        for caption, page_key in (
            ("Colaboradores", "employees"),
            ("Frequência", "attendance"),
            ("Férias", "vacations"),
            ("Documentos", "employee_records"),
        ):
            button = QPushButton(caption)
            button.clicked.connect(lambda checked=False, key=page_key: self.open_page_requested.emit(key))
            shortcuts.addWidget(button)
        shortcuts.addStretch()
        layout.addLayout(shortcuts)

        filters = QHBoxLayout()
        month_start = date.today().replace(day=1).isoformat()
        self.start_input = QLineEdit(month_start)
        self.end_input = QLineEdit(date.today().isoformat())
        self.alert_days = QSpinBox()
        self.alert_days.setRange(0, 180)
        self.alert_days.setValue(30)
        refresh = QPushButton("Atualizar painel")
        refresh.setProperty("variant", "primary")
        refresh.clicked.connect(self.refresh)
        filters.addWidget(QLabel("Inicio:"))
        filters.addWidget(self.start_input)
        filters.addWidget(QLabel("Fim:"))
        filters.addWidget(self.end_input)
        filters.addWidget(QLabel("Alerta em dias:"))
        filters.addWidget(self.alert_days)
        filters.addStretch()
        filters.addWidget(refresh)
        layout.addLayout(filters)

        cards = QFrame()
        cards.setObjectName("HeaderCard")
        cards.setAttribute(Qt.WA_StyledBackground, True)
        cards_layout = QGridLayout(cards)
        cards_layout.setContentsMargins(18, 18, 18, 18)
        cards_layout.setHorizontalSpacing(14)
        self.cards = {}
        for column, (key, label) in enumerate([
            ("active", "Colaboradores ativos"),
            ("absence", "Absenteismo do periodo"),
            ("expired", "Alertas vencidos"),
            ("expiring", "Vencendo em breve"),
        ]):
            card = QFrame()
            card.setObjectName("DialogInfoBlock")
            card.setAttribute(Qt.WA_StyledBackground, True)
            box = QVBoxLayout(card)
            box.setContentsMargins(14, 12, 14, 12)
            caption = QLabel(label)
            caption.setObjectName("SectionCaption")
            value = QLabel("-")
            value.setObjectName("PageTitle")
            box.addWidget(caption)
            box.addWidget(value)
            cards_layout.addWidget(card, 0, column)
            self.cards[key] = value
        layout.addWidget(cards)

        self.tabs = QTabWidget()
        self.alert_table = self._build_table(["Tipo", "Colaborador", "Registro", "Validade", "Situacao"])
        self.attendance_table = self._build_table(["Ocorrencia", "Quantidade"])
        self.team_table = self._build_table(["Atividade", "Ativos"])
        self.tabs.addTab(self.alert_table, "Alertas de vencimento")
        self.tabs.addTab(self.attendance_table, "Frequencia do periodo")
        self.tabs.addTab(self.team_table, "Efetivo por atividade")
        layout.addWidget(self.tabs, 1)
        self.info = QLabel("O absenteismo e um indicador gerencial; nao substitui a conferencia da folha de pagamento.")
        self.info.setObjectName("MutedText")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.skeleton = TableSkeletonOverlay(self, rows=6)

    @staticmethod
    def _build_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        configure_table(table)
        table.setMinimumHeight(420)
        return table

    def set_loading_state(self, loading: bool):
        self.skeleton.show_skeleton("Carregando painel de RH") if loading else self.skeleton.hide_skeleton()

    def refresh(self, *_):
        self.overview = self.api_client.get_hr_management(
            date_from=self.start_input.text().strip() or None,
            date_to=self.end_input.text().strip() or None,
            alert_days=self.alert_days.value(),
        )
        employees = self.overview.get("employees") or {}
        attendance = self.overview.get("attendance") or {}
        alert_summary = self.overview.get("alert_summary") or {}
        self.cards["active"].setText(str(employees.get("active", 0)))
        self.cards["absence"].setText(f"{attendance.get('absenteeism_percent', 0):.2f}%")
        self.cards["expired"].setText(str(alert_summary.get("expired", 0)))
        self.cards["expiring"].setText(str(alert_summary.get("expiring", 0)))
        self.info.setText(attendance.get("calculation") or "Indicador gerencial de frequencia.")
        self._fill(self.alert_table, self.overview.get("alerts") or [], lambda row: [row.get("kind"), (row.get("employee") or {}).get("full_name"), row.get("label"), row.get("expires_on"), row.get("status")])
        self._fill(self.attendance_table, attendance.get("by_type") or [], lambda row: [row.get("occurrence_type"), row.get("total")])
        self._fill(self.team_table, employees.get("by_team") or [], lambda row: [row.get("team_name"), row.get("total")])

    @staticmethod
    def _fill(table: QTableWidget, rows: list[dict], columns):
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate(columns(row)):
                table.setItem(index, column, make_table_item(str(value or ""), payload=row if column == 0 else None))
        table.resizeColumnsToContents()

    def export_alerts(self, file_type: str):
        alerts = self.overview.get("alerts") or []
        if not alerts:
            show_notice(self, "Sem alertas", "Atualize o painel e aguarde existir um alerta para exportar.", icon_name="warning")
            return
        rows = [{
            "tipo": row.get("kind"),
            "colaborador": (row.get("employee") or {}).get("full_name"),
            "matricula": (row.get("employee") or {}).get("registration"),
            "registro": row.get("label"),
            "validade": row.get("expires_on"),
            "situacao": row.get("status"),
        } for row in alerts]
        columns = [("Tipo", "tipo"), ("Colaborador", "colaborador"), ("Matricula", "matricula"), ("Registro", "registro"), ("Validade", "validade"), ("Situacao", "situacao")]
        default_path = make_default_export_path("alertas_rh", file_type)
        success = run_export_by_type(
            self,
            file_type=file_type,
            dialog_title="Exportar alertas de RH",
            default_path=default_path,
            filters={"csv": "CSV (*.csv)", "xlsx": "Excel (*.xlsx)"},
            handlers={
                "csv": lambda filename: export_rows_to_csv(columns, rows, filename),
                "xlsx": lambda filename: export_rows_to_xlsx("Alertas de RH", columns, rows, filename),
            },
        )
        if not success:
            return
        try:
            self.api_client.register_hr_export({
                "format": file_type.upper(),
                "data_inicial": self.start_input.text().strip() or None,
                "data_final": self.end_input.text().strip() or None,
                "dias_alerta": self.alert_days.value(),
            })
        except Exception as exc:
            show_notice(self, "Arquivo salvo", f"O arquivo foi salvo, mas o log de exportacao nao foi registrado: {exc}", icon_name="warning")
            return
        show_notice(self, "Exportacao concluida", "O arquivo e o log de exportacao foram registrados.", icon_name="reports")
