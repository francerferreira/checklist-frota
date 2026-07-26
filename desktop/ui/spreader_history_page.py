from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from components import show_notice
from theme import configure_dialog_window, configure_table, make_table_item, style_filter_bar, style_table_card


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    return str(value).replace("T", " ")[:16]


def _date_edit(value: date) -> QDateEdit:
    editor = QDateEdit()
    editor.setCalendarPopup(True)
    editor.setDisplayFormat("dd/MM/yyyy")
    editor.setDate(QDate(value.year, value.month, value.day))
    editor.setMinimumHeight(34)
    return editor


class SpreaderHistoryDetailDialog(QDialog):
    def __init__(self, api_client, record: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.record = record
        self.setWindowTitle("Detalhe da conferência do Spreader")
        configure_dialog_window(self, width=760, height=620, min_width=620, min_height=500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        spreader = record.get("spreader") or {}
        lbs = record.get("lbs") or {}
        title = QLabel(f"{spreader.get('frota') or 'Spreader'} - conferência diária")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"Série: {spreader.get('serial_number') or '-'} | "
            f"Registro: {_format_datetime(record.get('started_at'))}"
        )
        subtitle.setObjectName("SectionCaption")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        detail_card = QFrame()
        style_table_card(detail_card)
        details = QVBoxLayout(detail_card)
        details.setContentsMargins(14, 14, 14, 14)
        details.setSpacing(7)
        author = record.get("created_by") or {}
        info_rows = [
            ("Situação", record.get("status") or "-"),
            ("LBS no momento", lbs.get("frota") or "Sem vínculo registrado"),
            ("Tipo de vínculo", record.get("link_type") or "-"),
            ("Local", lbs.get("location") or "-"),
            ("Motivo", record.get("reason") or "-"),
            ("Observação", record.get("observation") or "-"),
            ("Operador", author.get("nome") or author.get("login") or "-"),
        ]
        for label_text, value_text in info_rows:
            label = QLabel(f"<b>{label_text}:</b> {value_text}")
            label.setWordWrap(True)
            details.addWidget(label)
        layout.addWidget(detail_card)

        evidence_path = record.get("evidence_path")
        if evidence_path:
            evidence_title = QLabel("Foto informada pelo operador")
            evidence_title.setObjectName("SectionTitle")
            layout.addWidget(evidence_title)
            self.image_label = QLabel("Carregando foto...")
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setMinimumHeight(230)
            self.image_label.setStyleSheet("background: #F2F5F8; border: 1px solid #D5DCE5; border-radius: 6px;")
            layout.addWidget(self.image_label, 1)
            self._load_evidence(evidence_path)

        actions = QHBoxLayout()
        actions.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _load_evidence(self, evidence_path: str):
        try:
            image_data = self.api_client.fetch_image(evidence_path)
            image = QPixmap()
            if image_data and image.loadFromData(image_data):
                self.image_label.setPixmap(image.scaled(680, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
            self.image_label.setText("Não foi possível carregar a foto deste registro.")
        except Exception as exc:
            self.image_label.setText(f"Não foi possível carregar a foto: {exc}")


class SpreaderHistoryPage(QWidget):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.rows: list[dict] = []
        self.setObjectName("ContentSurface")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel("Histórico diário de Spreaders")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Conferências dos operadores com situação, LBS vinculada, motivo, responsável e foto."
        )
        subtitle.setObjectName("SectionCaption")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap)
        header.addStretch()
        root.addLayout(header)

        filter_card = QFrame()
        style_filter_bar(filter_card)
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(10, 8, 10, 8)
        filters.setSpacing(8)
        today = date.today()
        self.spreader_filter = QComboBox()
        self.lbs_filter = QComboBox()
        self.status_filter = QComboBox()
        self.status_filter.addItem("TODAS", "")
        for status in ("DISPONIVEL", "INDISPONIVEL", "RESTRICAO", "MANUTENCAO"):
            self.status_filter.addItem(status.replace("_", " "), status)
        self.start_date = _date_edit(today - timedelta(days=31))
        self.end_date = _date_edit(today)
        update_button = QPushButton("Atualizar")
        update_button.setProperty("variant", "primary")
        update_button.clicked.connect(self.refresh)
        filters.addWidget(self._field("SPREADER", self.spreader_filter), 2)
        filters.addWidget(self._field("LBS", self.lbs_filter), 2)
        filters.addWidget(self._field("SITUAÇÃO", self.status_filter), 1)
        filters.addWidget(self._field("DATA INICIAL", self.start_date), 1)
        filters.addWidget(self._field("DATA FINAL", self.end_date), 1)
        filters.addWidget(update_button, 0, Qt.AlignBottom)
        root.addWidget(filter_card)

        summary_card = QFrame()
        style_table_card(summary_card)
        summary = QHBoxLayout(summary_card)
        summary.setContentsMargins(10, 10, 10, 10)
        self.period_label = QLabel("PERÍODO\n-")
        self.records_label = QLabel("CONFERÊNCIAS\n0 REGISTROS")
        self.unavailable_label = QLabel("INDISPONÍVEIS\n0 REGISTROS")
        for label in (self.period_label, self.records_label, self.unavailable_label):
            label.setObjectName("TopBarPill")
            summary.addWidget(label, 1)
        root.addWidget(summary_card)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "DATA / HORA", "SPREADER", "SÉRIE", "SITUAÇÃO", "LBS / VÍNCULO", "LOCAL", "MOTIVO", "OPERADOR / FOTO",
        ])
        configure_table(self.table, stretch_last=False, auto_fit=False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.itemDoubleClicked.connect(self.open_detail)
        root.addWidget(self.table, 1)

    @staticmethod
    def _field(label_text: str, widget: QWidget) -> QWidget:
        box = QFrame()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("SectionCaption")
        layout.addWidget(label)
        layout.addWidget(widget)
        return box

    def _load_filter_options(self):
        selected_spreader = self.spreader_filter.currentData()
        selected_lbs = self.lbs_filter.currentData()
        self.spreader_filter.blockSignals(True)
        self.lbs_filter.blockSignals(True)
        self.spreader_filter.clear()
        self.lbs_filter.clear()
        self.spreader_filter.addItem("TODOS OS SPREADERS", None)
        self.lbs_filter.addItem("TODAS AS LBS", None)
        for equipment in self.api_client.get_equipment("spreader", ativos=True) or []:
            label = equipment.get("frota") or "Spreader sem identificação"
            serial = equipment.get("serial_number") or ""
            self.spreader_filter.addItem(f"{label} {f'| Série {serial}' if serial else ''}", equipment.get("id"))
        for equipment in self.api_client.get_equipment("lbs", ativos=True) or []:
            self.lbs_filter.addItem(equipment.get("frota") or "LBS sem identificação", equipment.get("id"))
        self._restore_combo_value(self.spreader_filter, selected_spreader)
        self._restore_combo_value(self.lbs_filter, selected_lbs)
        self.spreader_filter.blockSignals(False)
        self.lbs_filter.blockSignals(False)

    @staticmethod
    def _restore_combo_value(combo: QComboBox, value):
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def refresh(self):
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        if end < start:
            show_notice(self, "Filtro inválido", "A data final deve ser maior ou igual à data inicial.", icon_name="warning")
            return
        try:
            self._load_filter_options()
            self.rows = self.api_client.get_spreader_daily_history(
                date_from=start,
                date_to=end,
                spreader_id=self.spreader_filter.currentData(),
                lbs_id=self.lbs_filter.currentData(),
                status=self.status_filter.currentData() or None,
            ) or []
            self._render_table()
        except Exception as exc:
            show_notice(self, "Falha ao carregar histórico", str(exc), icon_name="warning")

    def _render_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        unavailable = 0
        for row_index, record in enumerate(self.rows):
            spreader = record.get("spreader") or {}
            lbs = record.get("lbs") or {}
            author = record.get("created_by") or {}
            status = record.get("status") or "-"
            unavailable += 1 if status == "INDISPONIVEL" else 0
            link_label = lbs.get("frota") or "Sem vínculo"
            if record.get("link_type"):
                link_label = f"{link_label}\n{record['link_type']}"
            operator = author.get("nome") or author.get("login") or "-"
            evidence = "Com foto" if record.get("evidence_path") else "Sem foto"
            values = [
                _format_datetime(record.get("started_at")),
                spreader.get("frota") or "-",
                spreader.get("serial_number") or "-",
                status.replace("_", " "),
                link_label,
                lbs.get("location") or "-",
                record.get("reason") or "-",
                f"{operator}\n{evidence}",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, make_table_item(value, payload=record))
            self.table.setRowHeight(row_index, 54)
        self.table.setColumnWidth(0, 126)
        self.table.setColumnWidth(1, 145)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 118)
        self.table.setColumnWidth(4, 135)
        self.table.setColumnWidth(5, 190)
        self.table.setColumnWidth(6, 220)
        self.table.setColumnWidth(7, 175)
        self.table.setSortingEnabled(True)
        self.period_label.setText(
            f"PERÍODO\n{self.start_date.date().toString('dd/MM/yyyy')} A {self.end_date.date().toString('dd/MM/yyyy')}"
        )
        self.records_label.setText(f"CONFERÊNCIAS\n{len(self.rows)} REGISTROS")
        self.unavailable_label.setText(f"INDISPONÍVEIS\n{unavailable} REGISTROS")

    def open_detail(self, item: QTableWidgetItem):
        record = item.data(Qt.UserRole) or {}
        if record:
            SpreaderHistoryDetailDialog(self.api_client, record, self).exec()
