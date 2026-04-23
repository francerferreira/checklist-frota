from __future__ import annotations

import calendar
import re
import webbrowser
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from components import MessageComposerDialog, TableSkeletonOverlay, make_icon, show_notice, start_export_task
from runtime_paths import asset_path
from services.wash_reporting_service import (
    build_wash_tomorrow_message_package,
    export_wash_month_pdf,
    export_wash_schedule_pdf,
)
from theme import (
    build_dialog_layout,
    configure_dialog_window,
    configure_table,
    make_table_item,
    style_card,
    style_filter_bar,
    style_table_card,
)


WEEKDAY_OPTIONS = [
    ("Segunda-feira", 0),
    ("Terça-feira", 1),
    ("Quarta-feira", 2),
    ("Quinta-feira", 3),
    ("Sexta-feira", 4),
    ("Sábado", 5),
    ("Domingo", 6),
]
SHIFT_OPTIONS = [
    ("Dia todo", "ALL"),
    ("Manhã", "MANHA"),
    ("Tarde", "TARDE"),
]
WEEKDAY_HEADERS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]


def apply_date_popup_style(date_edit: QDateEdit):
    calendar_widget = date_edit.calendarWidget()
    if not calendar_widget:
        return
    calendar_widget.setStyleSheet(
        """
        QCalendarWidget QWidget {
            background: #E6E8EB;
            color: #1F2D3D;
        }
        QCalendarWidget QToolButton {
            background: #F3F3F3;
            color: #1F2D3D;
            border: 1px solid #B8BDC3;
            border-radius: 2px;
            padding: 4px 8px;
            font-weight: 700;
        }
        QCalendarWidget QMenu {
            background: #F3F3F3;
            color: #1F2D3D;
        }
        QCalendarWidget QSpinBox {
            background: #FFFFFF;
            color: #1F2D3D;
            border: 1px solid #B8BDC3;
            border-radius: 2px;
        }
        QCalendarWidget QAbstractItemView:enabled {
            selection-background-color: #6D7783;
            selection-color: #FFFFFF;
            background: #F3F3F3;
            color: #1F2D3D;
            outline: 0;
        }
        QCalendarWidget QAbstractItemView:disabled {
            color: #8F9DAA;
        }
        """
    )


class WashCalendarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()

        rect = option.rect.adjusted(1, 1, -1, -1)
        selected = bool(option.state & QStyle.State_Selected)

        background = index.data(Qt.BackgroundRole)
        base_color = background.color() if hasattr(background, "color") else QColor("#ECEFF2")
        if selected:
            base_color = QColor("#6D7783")

        painter.setPen(Qt.NoPen)
        painter.setBrush(base_color)
        painter.drawRect(rect)

        raw_text = (index.data(Qt.DisplayRole) or "").strip()
        if not raw_text:
            painter.restore()
            return

        lines = raw_text.splitlines()
        date_text = lines[0]
        detail_lines = lines[1:]

        pill_height = 22
        pill_width = min(max(58, len(date_text) * 8), max(58, rect.width() - 14))
        pill_x = rect.x() + (rect.width() - pill_width) // 2
        pill_y = rect.y() + 6
        pill_rect = rect.adjusted(pill_x - rect.x(), pill_y - rect.y(), -(rect.width() - (pill_x - rect.x()) - pill_width), -(rect.height() - (pill_y - rect.y()) - pill_height))

        painter.setBrush(QColor("#7A8591") if not selected else QColor("#626C77"))
        painter.drawRect(pill_rect)

        date_font = QFont(option.font)
        date_font.setBold(True)
        date_font.setPointSize(10)
        painter.setFont(date_font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pill_rect, Qt.AlignCenter, date_text)

        text_font = QFont(option.font)
        text_font.setBold(True)
        text_font.setPointSize(9)
        painter.setFont(text_font)
        painter.setPen(QColor("#FFFFFF") if selected else QColor("#1E293B"))

        text_rect = rect.adjusted(8, pill_height + 13, -8, -4)
        self._draw_detail_lines(painter, text_rect, detail_lines, selected)

        painter.restore()

    def _draw_detail_lines(self, painter: QPainter, rect, detail_lines: list[str], selected: bool) -> None:
        fm = painter.fontMetrics()
        line_height = max(18, fm.height() + 4)
        x = rect.x()
        y = rect.y()
        base_color = QColor("#FFFFFF") if selected else QColor("#1E293B")
        orange = QColor("#7A6A45")
        green = QColor("#4D6A55")
        red = QColor("#7A5555")

        summary_re = re.compile(r"●\s*OK\s*(\d+)\s+●\s*X\s*(\d+)\s+●\s*PEND\s*(\d+)")
        for line_index, line in enumerate(detail_lines):
            line_rect = rect.adjusted(0, line_index * line_height, 0, -max(0, rect.height() - ((line_index + 1) * line_height)))
            if line_rect.height() <= 0:
                break
            if match := summary_re.search(line):
                segments = [
                    (f"● OK {match.group(1)}", green),
                    (f"● X {match.group(2)}", red),
                    (f"● PEND {match.group(3)}", orange),
                ]
                current_x = x
                for segment, color in segments:
                    if current_x >= line_rect.right() - 8:
                        break
                    painter.setPen(color)
                    available = max(16, line_rect.right() - current_x - 4)
                    text = fm.elidedText(segment, Qt.ElideRight, available)
                    painter.drawText(current_x, line_rect.y(), available, line_rect.height(), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, text)
                    current_x += fm.horizontalAdvance(text) + 12
            else:
                painter.setPen(base_color)
                text = fm.elidedText(line, Qt.ElideRight, max(16, line_rect.width() - 2))
                painter.drawText(line_rect.adjusted(0, 0, -2, 0), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, text)


class WashRegisterDialog(QDialog):
    def __init__(self, queue_item: dict, trailers: list[dict], values: dict[str, float], parent=None, show_values: bool = True):
        super().__init__(parent)
        self.queue_item = queue_item
        self.trailers = trailers
        self.values = values
        self.show_values = show_values
        self.result_payload = None

        self.setWindowTitle("Registrar lavagem")
        configure_dialog_window(self, width=860, height=720, min_width=760, min_height=620)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=900)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon("activities", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        text_wrap = QVBoxLayout()
        title = QLabel(f"Lavagem de {queue_item.get('referencia')}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(
            "Escolha se a lavagem é do cavalo, do conjunto ou somente da carreta. O valor é sugerido automaticamente."
        )
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(text_wrap, 1)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        apply_date_popup_style(self.date_input)

        self.shift_combo = QComboBox()
        self.shift_combo.addItem("Manhã", "MANHA")
        self.shift_combo.addItem("Tarde", "TARDE")
        self.shift_combo.setCurrentIndex(0 if datetime.now().hour < 12 else 1)

        self.category_combo = QComboBox()
        for mode in queue_item.get("modos_lavagem", [queue_item.get("categoria_sugerida") or "CAVALO"]):
            self.category_combo.addItem(mode.title(), mode)

        suggested = queue_item.get("categoria_sugerida")
        if suggested:
            index = self.category_combo.findData(suggested)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

        self.trailer_combo = QComboBox()
        self.trailer_combo.addItem("Sem carreta", "")
        for trailer in trailers:
            label = f"{trailer.get('frota')} • {trailer.get('placa') or '-'}"
            self.trailer_combo.addItem(label, trailer.get("frota"))
        self._configure_trailer_search(self.trailer_combo)

        self.location_input = QLineEdit(queue_item.get("last_location") or "PATIO")
        self.location_input.setPlaceholderText("Local da lavagem")

        self.value_input = QDoubleSpinBox()
        self.value_input.setMaximum(99999.99)
        self.value_input.setDecimals(2)
        self.value_input.setPrefix("R$ ")

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Observações operacionais da lavagem.")

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("SectionCaption")
        self.hint_label.setWordWrap(True)

        self.category_combo.currentIndexChanged.connect(self._sync_category)
        self.trailer_combo.currentIndexChanged.connect(self._sync_category)

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(body)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        def add_field(row: int, column: int, label_text: str, widget, span: int = 1, highlight: bool = False):
            wrapper = QFrame()
            if highlight:
                wrapper.setObjectName("DialogInfoBlock")
                wrapper.setAttribute(Qt.WA_StyledBackground, True)
            wrapper_layout = QVBoxLayout(wrapper)
            margin = 12 if highlight else 0
            wrapper_layout.setContentsMargins(margin, margin, margin, margin)
            wrapper_layout.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            wrapper_layout.addWidget(label)
            wrapper_layout.addWidget(widget)
            form.addWidget(wrapper, row, column, 1, span)

        add_field(0, 0, "Data", self.date_input, highlight=True)
        add_field(0, 1, "Turno", self.shift_combo, highlight=True)
        add_field(1, 0, "Categoria da lavagem", self.category_combo, highlight=True)
        add_field(1, 1, "Carreta atrelada", self.trailer_combo, highlight=True)
        add_field(2, 0, "Local", self.location_input)
        if self.show_values:
            add_field(2, 1, "Valor sugerido", self.value_input)
        add_field(3, 0, "Observações", self.notes_input, 2)
        form.addWidget(self.hint_label, 4, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Registrar lavagem")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

        self._sync_category()

    def _sync_category(self):
        category = self.category_combo.currentData()
        requires_trailer = category in {"CONJUNTO", "CARRETA", "CARRETA PIPA"}
        self.trailer_combo.setEnabled(requires_trailer)
        if not requires_trailer:
            self.trailer_combo.setCurrentIndex(0)
        if self.show_values:
            self.value_input.setValue(float(self.values.get(category, 0.0)))
        if requires_trailer:
            self.hint_label.setText("Selecione qual carreta está atrelada. A referência continua sendo o cavalo.")
        elif category == "CAVALO":
            self.hint_label.setText("Lavagem apenas do cavalo. Se houver carreta junto, use CONJUNTO.")
        else:
            self.hint_label.setText("Categoria automática para veículo auxiliar.")

    def submit(self):
        category = self.category_combo.currentData()
        trailer = self._resolve_trailer_value(self.trailer_combo)
        if category in {"CONJUNTO", "CARRETA", "CARRETA PIPA"} and not trailer:
            show_notice(
                self,
                "Carreta obrigatória",
                "Informe qual carreta está atrelada quando a lavagem for de conjunto ou somente carreta.",
                icon_name="warning",
            )
            return

        wash_dt = self.date_input.date().toPython()
        self.result_payload = {
            "wash_date": datetime.combine(wash_dt, datetime.now().time().replace(second=0, microsecond=0)).isoformat(timespec="seconds"),
            "turno": self.shift_combo.currentData(),
            "local": self.location_input.text().strip(),
            "valor": round(self.value_input.value(), 2) if self.show_values else None,
            "carreta": trailer,
            "tipo_equipamento": category,
            "observacao": self.notes_input.toPlainText().strip(),
        }
        self.accept()

    @staticmethod
    def _configure_trailer_search(combo: QComboBox):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.lineEdit().setPlaceholderText("Digite para pesquisar carreta...")
        suggestions = [combo.itemText(index) for index in range(combo.count())]
        completer = QCompleter(suggestions, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(completer)

    @staticmethod
    def _resolve_trailer_value(combo: QComboBox) -> str:
        data = combo.currentData()
        if data:
            return str(data)
        typed = combo.currentText().strip()
        if not typed:
            return ""
        for index in range(combo.count()):
            label = combo.itemText(index)
            value = combo.itemData(index)
            if typed.lower() in label.lower():
                return str(value or "")
        return ""


class ScheduleQuickConfirmDialog(QDialog):
    def __init__(self, schedule_item: dict, queue_item: dict, trailers: list[dict], parent=None):
        super().__init__(parent)
        self.schedule_item = schedule_item
        self.queue_item = queue_item
        self.trailers = trailers
        self.photo_file_path = ""
        self.result_payload = None

        self.setWindowTitle("Confirmar lavagem do cronograma")
        configure_dialog_window(self, width=760, height=520, min_width=680, min_height=460)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=820)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel(f"Cumprimento de {queue_item.get('referencia') or '-'}")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Informe somente a carreta atrelada (se houver) e anexe a foto da lavagem.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QFrame()
        body.setObjectName("DialogInfoBlock")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)

        info = QLabel(
            f"Data: {self._format_date(schedule_item.get('scheduled_date'))} | "
            f"Turno: {'Manha' if schedule_item.get('scheduled_shift') == 'MANHA' else 'Tarde'} | "
            f"Referencia: {queue_item.get('referencia') or '-'}"
        )
        info.setObjectName("SectionCaption")

        self.trailer_combo = QComboBox()
        self.trailer_combo.addItem("Sem carreta (mantem cavalo/terberg)", "")
        for trailer in trailers:
            label = f"{trailer.get('frota')} • {trailer.get('placa') or '-'}"
            self.trailer_combo.addItem(label, trailer.get("frota"))
        WashRegisterDialog._configure_trailer_search(self.trailer_combo)

        if schedule_item.get("carreta"):
            trailer_index = self.trailer_combo.findData(schedule_item.get("carreta"))
            if trailer_index >= 0:
                self.trailer_combo.setCurrentIndex(trailer_index)

        trailer_field = self._build_field("Carreta atrelada", self.trailer_combo)

        self.photo_label = QLabel("Nenhuma foto selecionada.")
        self.photo_label.setObjectName("MicroText")
        self.photo_label.setWordWrap(True)
        select_photo_button = QPushButton("Selecionar foto")
        select_photo_button.clicked.connect(self.select_photo)
        clear_photo_button = QPushButton("Limpar foto")
        clear_photo_button.clicked.connect(self.clear_photo)
        photo_buttons = QHBoxLayout()
        photo_buttons.setSpacing(8)
        photo_buttons.addWidget(select_photo_button)
        photo_buttons.addWidget(clear_photo_button)
        photo_buttons.addStretch(1)

        photo_wrap = QFrame()
        photo_wrap.setObjectName("FieldCard")
        photo_wrap.setAttribute(Qt.WA_StyledBackground, True)
        photo_layout = QVBoxLayout(photo_wrap)
        photo_layout.setContentsMargins(0, 0, 0, 0)
        photo_layout.setSpacing(8)
        photo_title = QLabel("Foto da lavagem (opcional)")
        photo_title.setObjectName("SectionCaption")
        photo_layout.addWidget(photo_title)
        photo_layout.addWidget(self.photo_label)
        photo_layout.addLayout(photo_buttons)

        body_layout.addWidget(info)
        body_layout.addWidget(trailer_field)
        body_layout.addWidget(photo_wrap)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        confirm_button = QPushButton("Confirmar lavagem")
        confirm_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        confirm_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(confirm_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y")
        except ValueError:
            return value

    @staticmethod
    def _build_field(title_text: str, widget) -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("FieldCard")
        wrapper.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        title = QLabel(title_text)
        title.setObjectName("SectionCaption")
        layout.addWidget(title)
        layout.addWidget(widget)
        return wrapper

    def select_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar foto da lavagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        self.photo_file_path = path
        self.photo_label.setText(Path(path).name)

    def clear_photo(self):
        self.photo_file_path = ""
        self.photo_label.setText("Nenhuma foto selecionada.")

    def submit(self):
        trailer = WashRegisterDialog._resolve_trailer_value(self.trailer_combo)
        reference = str(self.queue_item.get("referencia") or "").upper()
        if trailer:
            category = "CONJUNTO"
        elif reference.startswith("TB"):
            category = "TERBERG"
        else:
            category = "CAVALO"

        self.result_payload = {
            "carreta": trailer,
            "tipo_equipamento": category,
            "photo_file_path": self.photo_file_path,
        }
        self.accept()


class WashUnavailableDialog(QDialog):
    def __init__(self, queue_item: dict, parent=None):
        super().__init__(parent)
        self.queue_item = queue_item
        self.result_payload = None

        self.setWindowTitle("Indisponibilidade para lavagem")
        configure_dialog_window(self, width=700, height=420, min_width=620, min_height=360)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=740)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel(f"{queue_item.get('referencia')} indisponível")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Use quando o veículo estiver em oficina, preventiva ou impossibilitado de lavar.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(10)
        label = QLabel("Motivo")
        label.setObjectName("SectionCaption")
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText("Ex.: Em oficina, aguardando manutenção, parado para preventiva.")
        body_layout.addWidget(label)
        body_layout.addWidget(self.reason_input)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        confirm_button = QPushButton("Pular da vez")
        confirm_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        confirm_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(confirm_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    def submit(self):
        self.result_payload = {"motivo": self.reason_input.toPlainText().strip()}
        self.accept()


class PreventiveScheduleDialog(QDialog):
    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self.result_payload = None

        self.setWindowTitle("Programar preventiva")
        configure_dialog_window(self, width=720, height=500, min_width=620, min_height=420)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=760)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Lavagem antes da preventiva")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(f"Defina a semana e o dia da semana para {count} veículo(s) na programação fixa.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        self.week_combo = QComboBox()
        for label, value in [("1ª semana", 1), ("2ª semana", 2), ("3ª semana", 3), ("4ª semana", 4), ("5ª semana", 5)]:
            self.week_combo.addItem(label, value)

        self.weekday_combo = QComboBox()
        for label, value in WEEKDAY_OPTIONS:
            self.weekday_combo.addItem(label, value)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Ex.: lavar na semana da preventiva da frota selecionada.")

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        form = QGridLayout(body)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        for column, (label_text, widget) in enumerate(
            [("Semana do mês", self.week_combo), ("Dia da semana", self.weekday_combo)]
        ):
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            form.addWidget(label, 0, column)
            form.addWidget(widget, 1, column)

        notes_label = QLabel("Observações")
        notes_label.setObjectName("SectionCaption")
        form.addWidget(notes_label, 2, 0, 1, 2)
        form.addWidget(self.notes_input, 3, 0, 1, 2)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar programação")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    def submit(self):
        self.result_payload = {
            "week_of_month": self.week_combo.currentData(),
            "weekday": self.weekday_combo.currentData(),
            "observacao": self.notes_input.toPlainText().strip(),
        }
        self.accept()


class WashDecisionDialog(QDialog):
    def __init__(self, reference: str, shift_label: str, parent=None):
        super().__init__(parent)
        self.result_payload = None
        self.setWindowTitle("Não lavado")
        configure_dialog_window(self, width=640, height=360, min_width=560, min_height=320)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=680)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel(f"{reference} não cumpriu a lavagem")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(f"Informe o motivo da não execução no turno {shift_label}.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(10)
        label = QLabel("Motivo")
        label.setObjectName("SectionCaption")
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText("Ex.: Em oficina, chuva forte, faltou operador, indisponivel no turno.")
        body_layout.addWidget(label)
        body_layout.addWidget(self.reason_input)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Marcar não lavado")
        save_button.setProperty("variant", "danger")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    def submit(self):
        self.result_payload = {"motivo": self.reason_input.toPlainText().strip()}
        self.accept()


class WashValuesDialog(QDialog):
    def __init__(self, api_client, rows: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowTitle("Configurar valores de lavagem")
        configure_dialog_window(self, width=620, height=560, min_width=560, min_height=480)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=660)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Valores por categoria")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Ajuste os preços das categorias de lavagem e salve para o módulo inteiro.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(10)

        self.table = QTableWidget(len(rows), 2)
        self.table.setHorizontalHeaderLabels(["Categoria", "Valor unitário"])
        configure_table(self.table, stretch_last=False)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionsClickable(False)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.editors: list[tuple[str, QDoubleSpinBox]] = []
        for row_index, item in enumerate(rows):
            category = item.get("categoria") or "-"
            self.table.setItem(row_index, 0, make_table_item(category))
            editor = QDoubleSpinBox()
            editor.setMaximum(99999.99)
            editor.setDecimals(2)
            editor.setPrefix("R$ ")
            editor.setValue(float(item.get("valor_unitario") or 0))
            self.table.setCellWidget(row_index, 1, editor)
            self.editors.append((category, editor))
        self.table.setMinimumHeight(320)
        body_layout.addWidget(self.table)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        cancel_button = QPushButton("Cancelar")
        save_button = QPushButton("Salvar valores")
        save_button.setProperty("variant", "primary")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.submit)
        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    def submit(self):
        payload = [{"categoria": category, "valor_unitario": round(editor.value(), 2)} for category, editor in self.editors]
        try:
            self.api_client.update_wash_values(payload)
        except Exception as exc:
            show_notice(self, "Falha ao salvar valores", str(exc), icon_name="warning")
            return
        self.accept()


class ScheduleDetailDialog(QDialog):
    def __init__(self, title_text: str, schedule_items: list[dict], host_page, parent=None):
        super().__init__(parent)
        self.host_page = host_page
        self.schedule_items = schedule_items
        self.setWindowTitle("Cumprimento do cronograma")
        configure_dialog_window(self, width=1420, height=860, min_width=1240, min_height=720)
        self.setWindowState(self.windowState() | Qt.WindowMaximized)
        style_card(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        title = QLabel("Cumprimento do cronograma")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(title_text)
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QFrame()
        body.setObjectName("HeaderCard")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(12)

        headers = ["Turno", "Referencia", "Categoria", "Valor", "Status", "Foto", "OK", "X", "Reeditar"]
        self.table = QTableWidget(len(schedule_items), len(headers))
        self.table.setObjectName("DialogScheduleGrid")
        self.table.setHorizontalHeaderLabels(headers)
        configure_table(self.table, stretch_last=False, auto_fit=False)
        self.table.setColumnHidden(3, not self.host_page.can_view_values)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionsClickable(False)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.setMinimumHeight(640)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setDefaultSectionSize(136)
        self.table.horizontalHeader().setMinimumSectionSize(82)
        self.table.horizontalHeader().setFixedHeight(56)

        for row_index, item in enumerate(schedule_items):
            values = [
                "Manha" if item.get("scheduled_shift") == "MANHA" else "Tarde",
                item.get("referencia") or "-",
                item.get("categoria_lavagem") or "-",
                self.host_page._format_currency(item.get("valor_sugerido")) if self.host_page.can_view_values else "",
            ]
            for column, value in enumerate(values):
                cell = make_table_item(value)
                cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row_index, column, cell)

            self.table.setCellWidget(
                row_index,
                4,
                self.host_page._build_status_badge(
                    item.get("status_execucao") or "PENDENTE",
                    item.get("status_rotulo") or "Pendente",
                ),
            )
            photo_path = item.get("foto_path")
            if photo_path:
                photo_button = QPushButton("Ver")
                photo_button.setMinimumHeight(34)
                photo_button.setMinimumWidth(76)
                photo_button.clicked.connect(
                    lambda checked=False, path=photo_path: self.host_page.open_wash_photo(path)
                )
                self.table.setCellWidget(row_index, 5, photo_button)
            else:
                self.table.setItem(row_index, 5, make_table_item("-"))

            ok_button = QPushButton()
            ok_button.setIcon(make_icon("ok", "#E7EBF0", "#4D6A55", 20))
            ok_button.setToolTip("Confirmar que lavou")
            ok_button.setFixedSize(40, 34)
            ok_button.setProperty("compactAction", "ok")
            ok_button.clicked.connect(lambda checked=False, payload=item: self._handle_ok(payload))

            no_button = QPushButton()
            no_button.setIcon(make_icon("cancel", "#E7EBF0", "#7E6363", 20))
            no_button.setToolTip("Marcar que não lavou")
            no_button.setFixedSize(40, 34)
            no_button.setProperty("compactAction", "no")
            no_button.clicked.connect(lambda checked=False, payload=item: self._handle_no(payload))

            ok_button.setEnabled(item.get("status_execucao") != "LAVADO")
            no_button.setEnabled(item.get("status_execucao") != "NAO_CUMPRIDO")

            self.table.setCellWidget(row_index, 6, ok_button)
            self.table.setCellWidget(row_index, 7, no_button)
            reedit_button = QPushButton("Reeditar")
            reedit_button.setMinimumHeight(34)
            reedit_button.setMinimumWidth(116)
            reedit_button.setEnabled(item.get("status_execucao") in {"NAO_CUMPRIDO", "LAVADO"})
            reedit_button.clicked.connect(lambda checked=False, payload=item: self._handle_reedit(payload))
            self.table.setCellWidget(row_index, 8, reedit_button)
            self.table.setRowHeight(row_index, 62)

        self._apply_schedule_table_widths(headers)
        body_layout.addWidget(self.table, 1)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()
        close_button = QPushButton("Fechar")
        close_button.setProperty("variant", "primary")
        close_button.setMinimumWidth(120)
        close_button.setMinimumHeight(38)
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(close_button)

        layout.addWidget(header)
        layout.addWidget(body)
        layout.addWidget(footer)

    def _handle_ok(self, payload: dict):
        self.accept()
        self.host_page.confirm_schedule_success(payload)

    def _handle_no(self, payload: dict):
        self.accept()
        self.host_page.mark_schedule_not_completed(payload)

    def _handle_reedit(self, payload: dict):
        self.accept()
        self.host_page.reedit_schedule_decision(payload)

    def _apply_schedule_table_widths(self, headers: list[str]):
        header = self.table.horizontalHeader()
        for index, title in enumerate(headers):
            if title in {"OK", "X"}:
                header.setSectionResizeMode(index, QHeaderView.Fixed)
                self.table.setColumnWidth(index, 96)
                continue
            if title == "Reeditar":
                header.setSectionResizeMode(index, QHeaderView.Fixed)
                self.table.setColumnWidth(index, 140)
                continue
            if title == "Foto":
                header.setSectionResizeMode(index, QHeaderView.Fixed)
                self.table.setColumnWidth(index, 108)
                continue
            if title == "Valor":
                header.setSectionResizeMode(index, QHeaderView.Fixed)
                self.table.setColumnWidth(index, 132)
                continue
            header.setSectionResizeMode(index, QHeaderView.Stretch)


class WashesPage(QFrame):
    data_changed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.can_view_values = self._can_view_values()
        self.selected_year = date.today().year
        self.selected_month = date.today().month
        self.selected_day_iso: str | None = None
        self.day_index: dict[str, dict] = {}
        self.visible_queue_items: list[dict] = []
        self.overview: dict = {}
        self.category_values: dict[str, float] = {}
        self.trailers: list[dict] = []
        self.current_item: dict | None = None
        self._queue_filter_timer = QTimer(self)
        self._queue_filter_timer.setSingleShot(True)
        self._queue_filter_timer.timeout.connect(self.apply_filters)
        self.setObjectName("ContentSurface")

        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content = QWidget()
        content.setAttribute(Qt.WA_StyledBackground, False)
        scroll.setWidget(content)
        shell.addWidget(scroll)

        root = QVBoxLayout(content)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header_frame = QFrame()
        style_filter_bar(header_frame)
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(12, 10, 12, 10)
        header.setSpacing(12)
        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(4)
        title = QLabel("Gerenciamento de lavagem")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Controle a fila do CV, monte o cronograma mensal e acompanhe os indicadores do período.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)
        context_hint = QLabel("Operação diária - Cronograma - Fila - Histórico")
        context_hint.setObjectName("ContextHint")
        text_wrap.addWidget(context_hint)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.sync_button = QPushButton("Sincronizar frota")
        self.sync_button.setProperty("variant", "primary")
        self.sync_button.clicked.connect(self.sync_queue)
        self.reclassify_button = QPushButton("Reclassificar fila")
        self.reclassify_button.clicked.connect(self.reclassify_queue)
        self.message_button = QPushButton("Gerar mensagem")
        self.message_button.setProperty("variant", "primary")
        self.message_button.clicked.connect(self.generate_tomorrow_message)
        self.pdf_button = QPushButton("PDF mensal")
        self.pdf_button.clicked.connect(self.export_month_pdf)
        self.pdf_button.setVisible(self.can_view_values)
        self.schedule_pdf_button = QPushButton("PDF cronograma")
        self.schedule_pdf_button.clicked.connect(self.export_schedule_pdf)
        self.values_manage_button = QPushButton("Configurar valores")
        self.values_manage_button.clicked.connect(self.open_values_dialog)
        self.values_manage_button.setVisible(self.can_view_values)
        self.register_button = QPushButton("Registrar lavagem")
        self.register_button.setProperty("variant", "primary")
        self.register_button.clicked.connect(self.register_selected_wash)
        self.preventive_button = QPushButton("Programar preventiva")
        self.preventive_button.clicked.connect(self.schedule_preventive)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setProperty("variant", "success")
        self.refresh_button.clicked.connect(self.refresh)
        for action_button in (
            self.sync_button,
            self.reclassify_button,
            self.register_button,
            self.preventive_button,
            self.message_button,
            self.pdf_button,
            self.schedule_pdf_button,
            self.values_manage_button,
            self.refresh_button,
        ):
            action_button.setMinimumHeight(34)
            buttons.addWidget(action_button)
        buttons.setAlignment(Qt.AlignRight | Qt.AlignTop)

        header.addLayout(text_wrap, 1)
        header.addLayout(buttons)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(6)
        summary_grid.setVerticalSpacing(6)
        self.summary_cards: dict[str, tuple[QLabel, QLabel]] = {}
        self.summary_card_frames: dict[str, QFrame] = {}
        for index, (key, title_text) in enumerate(
            [
                ("proximo", "Próximo da vez"),
                ("lavados_mes", "Lavados no mês"),
                ("valor_total", "Valor total do mês"),
                ("indisponiveis", "Indisponíveis"),
                ("preventivas", "Com preventiva"),
            ]
        ):
            card = QFrame()
            style_table_card(card)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(9, 8, 9, 8)
            card_layout.setSpacing(1)
            card_title = QLabel(title_text)
            card_title.setObjectName("CardTitle")
            value_label = QLabel("-")
            value_label.setObjectName("SummaryMetric")
            subtitle_label = QLabel("")
            subtitle_label.setObjectName("SummaryMeta")
            subtitle_label.setWordWrap(True)
            card_layout.addWidget(card_title)
            card_layout.addWidget(value_label)
            card_layout.addWidget(subtitle_label)
            self.summary_cards[key] = (value_label, subtitle_label)
            self.summary_card_frames[key] = card
            summary_grid.addWidget(card, 0, index)
            card.setMinimumHeight(86)
            card.setMaximumHeight(94)
        self.summary_card_frames["valor_total"].setVisible(self.can_view_values)

        root.addWidget(header_frame)
        root.addLayout(summary_grid)

        self.plan_card = QFrame()
        style_filter_bar(self.plan_card)
        plan_layout = QGridLayout(self.plan_card)
        plan_layout.setContentsMargins(12, 10, 12, 10)
        plan_layout.setHorizontalSpacing(8)
        plan_layout.setVerticalSpacing(6)

        self.prev_month_button = QPushButton("◀")
        self.prev_month_button.clicked.connect(lambda: self.change_month(-1))
        self.current_month_button = QPushButton("Atual")
        self.current_month_button.clicked.connect(self.go_to_current_period)
        self.next_month_button = QPushButton("▶")
        self.next_month_button.clicked.connect(lambda: self.change_month(1))
        self.period_badge = QLabel("-")
        self.period_badge.setObjectName("TopBarPill")

        self.morning_capacity = QSpinBox()
        self.morning_capacity.setRange(0, 30)
        self.afternoon_capacity = QSpinBox()
        self.afternoon_capacity.setRange(0, 30)
        self.aux_interval = QSpinBox()
        self.aux_interval.setRange(1, 31)
        self.block_shift_combo = QComboBox()
        for label, value in SHIFT_OPTIONS:
            self.block_shift_combo.addItem(label, value)
        self.block_reason = QLineEdit()
        self.block_reason.setPlaceholderText("Motivo do bloqueio do dia")

        self.save_plan_button = QPushButton("Salvar planejamento")
        self.save_plan_button.setProperty("variant", "primary")
        self.save_plan_button.clicked.connect(self.save_plan)
        self.block_button = QPushButton("Sem lavagem")
        self.block_button.clicked.connect(lambda: self.toggle_block(True))
        self.unblock_button = QPushButton("Liberar dia")
        self.unblock_button.clicked.connect(lambda: self.toggle_block(False))
        self.save_plan_button.setMinimumHeight(38)
        self.block_button.setMinimumHeight(34)
        self.unblock_button.setMinimumHeight(34)
        self.save_plan_button.setMinimumHeight(34)

        plan_layout.addWidget(self.prev_month_button, 0, 0)
        plan_layout.addWidget(self.period_badge, 0, 1)
        plan_layout.addWidget(self.current_month_button, 0, 2)
        plan_layout.addWidget(self.next_month_button, 0, 3)
        plan_layout.addWidget(self._caption_field("Capacidade manhã", self.morning_capacity), 0, 4)
        plan_layout.addWidget(self._caption_field("Capacidade tarde", self.afternoon_capacity), 0, 5)
        plan_layout.addWidget(self._caption_field("Auxiliares a cada (dias)", self.aux_interval), 0, 6)
        plan_layout.addWidget(self.save_plan_button, 0, 7)
        plan_layout.addWidget(self._caption_field("Bloquear turno", self.block_shift_combo), 1, 0, 1, 2)
        plan_layout.addWidget(self._caption_field("Motivo", self.block_reason), 1, 2, 1, 3)
        plan_layout.addWidget(self.block_button, 1, 5)
        plan_layout.addWidget(self.unblock_button, 1, 6)

        root.addWidget(self.plan_card)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(720)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addWidget(self.tabs)

        self.calendar_tab = QWidget()
        calendar_layout = QVBoxLayout(self.calendar_tab)
        calendar_layout.setContentsMargins(0, 0, 0, 0)
        calendar_layout.setSpacing(10)

        self.calendar_card = QFrame()
        style_table_card(self.calendar_card)
        self.calendar_skeleton = TableSkeletonOverlay(self.calendar_card, rows=6)
        calendar_card_layout = QVBoxLayout(self.calendar_card)
        calendar_card_layout.setContentsMargins(10, 10, 10, 10)
        calendar_card_layout.setSpacing(6)

        calendar_title = QLabel("Cronograma mensal vivo")
        calendar_title.setObjectName("SectionTitle")
        calendar_caption = QLabel(
            "Mostra o que já foi lavado no mês, o que está planejado pela fila do CV e a programação automática dos auxiliares."
        )
        calendar_caption.setObjectName("SectionCaption")
        self.selected_day_badge = QLabel("Selecione um dia no cronograma")
        self.selected_day_badge.setObjectName("TopBarPill")

        calendar_top = QHBoxLayout()
        calendar_text = QVBoxLayout()
        calendar_text.addWidget(calendar_title)
        calendar_text.addWidget(calendar_caption)
        calendar_top.addLayout(calendar_text, 1)
        calendar_top.addWidget(self.selected_day_badge)

        self.calendar_table = QTableWidget(6, 7)
        self.calendar_table.setObjectName("WashCalendarTable")
        self.calendar_table.setHorizontalHeaderLabels(WEEKDAY_HEADERS)
        self.calendar_table.setItemDelegate(WashCalendarDelegate(self.calendar_table))
        configure_table(self.calendar_table, stretch_last=False, auto_fit=False)
        self.calendar_table.setSortingEnabled(False)
        self.calendar_table.horizontalHeader().setSectionsClickable(False)
        self.calendar_table.horizontalHeader().setSortIndicatorShown(False)
        self.calendar_table.setShowGrid(True)
        self.calendar_table.setGridStyle(Qt.SolidLine)
        self.calendar_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.calendar_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.calendar_table.itemSelectionChanged.connect(self._calendar_selection_changed)
        self.calendar_table.itemDoubleClicked.connect(self._calendar_item_double_clicked)
        self.calendar_table.setMinimumHeight(540)
        self.calendar_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.calendar_table.verticalHeader().setVisible(False)
        self.calendar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calendar_table.viewport().installEventFilter(self)
        self._resize_calendar_cells()

        calendar_card_layout.addLayout(calendar_top)
        calendar_card_layout.addWidget(self.calendar_table)

        self.day_detail_card = QFrame()
        style_table_card(self.day_detail_card)
        detail_layout = QVBoxLayout(self.day_detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Cumprimento do cronograma")
        detail_title.setObjectName("SectionTitle")
        detail_caption = QLabel("Selecione um dia acima e use os botões verdes/vermelhos para confirmar se lavou ou não lavou no turno planejado.")
        detail_caption.setObjectName("SectionCaption")
        self.day_detail_title = QLabel("Nenhum dia selecionado")
        self.day_detail_title.setObjectName("TopBarTitle")
        detail_head = QHBoxLayout()
        detail_text = QVBoxLayout()
        detail_text.setSpacing(4)
        detail_text.addWidget(detail_title)
        detail_text.addWidget(detail_caption)
        self.detail_expand_button = QPushButton("Abrir quadro")
        self.detail_expand_button.setMinimumHeight(36)
        self.detail_expand_button.clicked.connect(self.open_schedule_detail_dialog)
        detail_head.addLayout(detail_text, 1)
        detail_head.addWidget(self.detail_expand_button, 0)
        self.day_detail_table = QTableWidget(0, 8)
        self.day_detail_table.setHorizontalHeaderLabels(
            ["Turno", "Referencia", "Categoria", "Valor", "Status", "OK", "X", "Reeditar"]
        )
        configure_table(self.day_detail_table, stretch_last=False)
        self.day_detail_table.setMinimumHeight(320)
        self.day_detail_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.day_detail_table.setColumnWidth(0, 90)
        self.day_detail_table.setColumnWidth(1, 120)
        self.day_detail_table.setColumnWidth(2, 120)
        self.day_detail_table.setColumnWidth(3, 96)
        self.day_detail_table.setColumnWidth(4, 160)
        self.day_detail_table.setColumnWidth(7, 116)
        self.day_detail_table.setColumnHidden(3, not self.can_view_values)
        detail_layout.addLayout(detail_head)
        detail_layout.addWidget(self.day_detail_title)
        detail_layout.addWidget(self.day_detail_table)

        self.day_detail_card.setVisible(False)
        calendar_layout.addWidget(self.calendar_card, 1)
        calendar_layout.addWidget(self.day_detail_card, 0)

        self.queue_tab = QWidget()
        queue_tab_layout = QVBoxLayout(self.queue_tab)
        queue_tab_layout.setContentsMargins(0, 0, 0, 0)
        queue_tab_layout.setSpacing(10)

        queue_filter = QFrame()
        style_filter_bar(queue_filter)
        queue_filter_layout = QHBoxLayout(queue_filter)
        queue_filter_layout.setContentsMargins(12, 10, 12, 10)
        queue_filter_layout.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por referência, placa, modelo ou local")
        self.search_input.returnPressed.connect(self.apply_filters)
        self.search_input.textChanged.connect(self._schedule_queue_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos", "")
        self.status_filter.addItem("Disponíveis", "DISPONIVEL")
        self.status_filter.addItem("Indisponíveis", "INDISPONIVEL")
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todos", "")
        self.category_filter.addItem("Cavalos", "cavalo")
        self.category_filter.addItem("Auxiliares", "auxiliar")
        self.category_filter.currentIndexChanged.connect(self.apply_filters)
        apply_button = QPushButton("Aplicar filtros")
        apply_button.setMinimumHeight(34)
        apply_button.clicked.connect(self.apply_filters)
        queue_filter_layout.addWidget(self.search_input, 1)
        queue_filter_layout.addWidget(self.status_filter)
        queue_filter_layout.addWidget(self.category_filter)
        queue_filter_layout.addWidget(apply_button)

        self.queue_card = QFrame()
        style_table_card(self.queue_card)
        self.queue_skeleton = TableSkeletonOverlay(self.queue_card, rows=7)
        queue_layout = QVBoxLayout(self.queue_card)
        queue_layout.setContentsMargins(12, 10, 12, 10)
        queue_layout.setSpacing(8)

        queue_title = QLabel("Fila operacional")
        queue_title.setObjectName("SectionTitle")
        queue_caption = QLabel(
            "O primeiro disponível é o da vez. Lavou, vai para o fim da fila. Se estiver indisponível, o próximo assume automaticamente."
        )
        queue_caption.setObjectName("SectionCaption")
        self.selection_badge = QLabel("0 selecionados")
        self.selection_badge.setObjectName("TopBarPill")

        queue_top = QHBoxLayout()
        queue_text = QVBoxLayout()
        queue_text.addWidget(queue_title)
        queue_text.addWidget(queue_caption)
        queue_top.addLayout(queue_text, 1)
        queue_top.addWidget(self.selection_badge)

        self.queue_table = QTableWidget(0, 10)
        self.queue_table.setHorizontalHeaderLabels(
            [
                "Fila",
                "Referência",
                "Placa",
                "Modelo",
                "Categoria",
                "Valor",
                "Última lavagem",
                "Próxima preventiva",
                "Status",
                "Ação",
            ]
        )
        configure_table(self.queue_table, stretch_last=False)
        self.queue_table.setColumnHidden(5, not self.can_view_values)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.queue_table.setMinimumHeight(420)
        self.queue_table.itemSelectionChanged.connect(self._queue_selection_changed)

        queue_layout.addLayout(queue_top)
        queue_layout.addWidget(self.queue_table)

        queue_tab_layout.addWidget(queue_filter)
        queue_tab_layout.addWidget(self.queue_card)

        self.history_tab = QWidget()
        history_tab_layout = QVBoxLayout(self.history_tab)
        history_tab_layout.setContentsMargins(0, 0, 0, 0)
        history_tab_layout.setSpacing(10)

        self.history_card = QFrame()
        style_table_card(self.history_card)
        self.history_skeleton = TableSkeletonOverlay(self.history_card, rows=6)
        history_layout = QVBoxLayout(self.history_card)
        history_layout.setContentsMargins(12, 10, 12, 10)
        history_layout.setSpacing(8)
        history_title = QLabel("Histórico do mês")
        history_title.setObjectName("SectionTitle")
        history_caption = QLabel("Lavagens já realizadas no período selecionado, com valor, categoria e carreta.")
        history_caption.setObjectName("SectionCaption")
        history_filter_bar = QFrame()
        style_filter_bar(history_filter_bar)
        history_filter_layout = QHBoxLayout(history_filter_bar)
        history_filter_layout.setContentsMargins(10, 8, 10, 8)
        history_filter_layout.setSpacing(8)
        self.history_filter_mode = QComboBox()
        self.history_filter_mode.addItem("Mês selecionado", "MONTH")
        self.history_filter_mode.addItem("Dia selecionado", "SELECTED_DAY")
        self.history_filter_mode.addItem("Hoje", "TODAY")
        self.history_filter_mode.currentIndexChanged.connect(self._fill_history)
        self.history_date_filter = QDateEdit()
        self.history_date_filter.setCalendarPopup(True)
        self.history_date_filter.setDate(QDate.currentDate())
        apply_date_popup_style(self.history_date_filter)
        self.history_date_filter.dateChanged.connect(self._fill_history)
        self.history_today_button = QPushButton("Hoje")
        self.history_today_button.setMinimumHeight(34)
        self.history_today_button.clicked.connect(self.focus_today)
        self.history_month_button = QPushButton("Mês atual")
        self.history_month_button.setMinimumHeight(34)
        self.history_month_button.clicked.connect(self.go_to_current_period)
        history_filter_layout.addWidget(self.history_filter_mode)
        history_filter_layout.addWidget(self.history_date_filter)
        history_filter_layout.addWidget(self.history_today_button)
        history_filter_layout.addWidget(self.history_month_button)
        history_filter_layout.addStretch()
        self.history_table = QTableWidget(0, 8)
        self.history_table.setHorizontalHeaderLabels(
            ["Data", "Referência", "Carreta", "Categoria", "Turno", "Local", "Valor", "Observação"]
        )
        configure_table(self.history_table, stretch_last=False)
        self.history_table.setColumnHidden(6, not self.can_view_values)
        self.history_table.setMinimumHeight(320)
        history_layout.addWidget(history_title)
        history_layout.addWidget(history_caption)
        history_layout.addWidget(history_filter_bar)
        history_layout.addWidget(self.history_table)

        indicator_row = QHBoxLayout()
        indicator_row.setSpacing(14)

        self.category_card = QFrame()
        style_table_card(self.category_card)
        category_layout = QVBoxLayout(self.category_card)
        category_layout.setContentsMargins(14, 14, 14, 14)
        category_layout.setSpacing(10)
        category_title = QLabel("Indicadores por categoria")
        category_title.setObjectName("SectionTitle")
        self.category_table = QTableWidget(0, 3)
        self.category_table.setHorizontalHeaderLabels(["Categoria", "Qtde", "Valor"])
        configure_table(self.category_table, stretch_last=False)
        self.category_table.setColumnHidden(2, not self.can_view_values)
        self.category_table.setMinimumHeight(240)
        category_layout.addWidget(category_title)
        category_layout.addWidget(self.category_table)

        self.vehicle_card = QFrame()
        style_table_card(self.vehicle_card)
        vehicle_layout = QVBoxLayout(self.vehicle_card)
        vehicle_layout.setContentsMargins(14, 14, 14, 14)
        vehicle_layout.setSpacing(10)
        vehicle_title = QLabel("Indicadores por veículo")
        vehicle_title.setObjectName("SectionTitle")
        self.vehicle_table = QTableWidget(0, 3)
        self.vehicle_table.setHorizontalHeaderLabels(["Referência", "Qtde", "Valor"])
        configure_table(self.vehicle_table, stretch_last=False)
        self.vehicle_table.setColumnHidden(2, not self.can_view_values)
        self.vehicle_table.setMinimumHeight(240)
        vehicle_layout.addWidget(vehicle_title)
        vehicle_layout.addWidget(self.vehicle_table)

        indicator_row.addWidget(self.category_card, 1)
        indicator_row.addWidget(self.vehicle_card, 1)

        history_tab_layout.addWidget(self.history_card)
        history_tab_layout.addLayout(indicator_row)

        self.tabs.addTab(self.calendar_tab, "Cronograma")
        self.tabs.addTab(self.queue_tab, "Fila")
        self.tabs.addTab(self.history_tab, "Histórico")

        self.register_button.setEnabled(False)
        self.preventive_button.setEnabled(False)

    def _can_view_values(self) -> bool:
        return str((self.api_client.user or {}).get("tipo") or "").lower() in {"admin", "gestor"}

    def set_loading_state(self, loading: bool):
        if loading:
            self.calendar_skeleton.show_skeleton("Montando cronograma mensal")
        else:
            self.calendar_skeleton.hide_skeleton()

    def refresh(self):
        self.overview = self.api_client.get_wash_overview(self.selected_year, self.selected_month)
        self.category_values = {
            item.get("categoria"): float(item.get("valor_unitario") or 0)
            for item in self.overview.get("tabela_valores", [])
        }
        self.trailers = self.overview.get("carretas", [])
        self._fill_summary()
        self._fill_plan_controls()
        self._fill_calendar()
        self.apply_filters()
        self._fill_history()

    def change_month(self, delta: int):
        month = self.selected_month + delta
        year = self.selected_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self.selected_year = year
        self.selected_month = month
        self.selected_day_iso = None
        self.refresh()

    def go_to_current_period(self):
        today = date.today()
        self.selected_year = today.year
        self.selected_month = today.month
        self.selected_day_iso = today.isoformat()
        self.history_date_filter.setDate(QDate(today.year, today.month, today.day))
        self.refresh()

    def focus_today(self):
        today = date.today()
        if (self.selected_year, self.selected_month) != (today.year, today.month):
            self.selected_year = today.year
            self.selected_month = today.month
            self.selected_day_iso = today.isoformat()
            self.history_date_filter.setDate(QDate(today.year, today.month, today.day))
            self.refresh()
            return
        self.selected_day_iso = today.isoformat()
        self.history_date_filter.setDate(QDate(today.year, today.month, today.day))
        self._refresh_selected_day_badge()
        self._fill_day_detail()
        self._fill_history()

    def save_plan(self):
        try:
            self.api_client.update_wash_plan(
                {
                    "ano": self.selected_year,
                    "mes": self.selected_month,
                    "capacidade_manha": self.morning_capacity.value(),
                    "capacidade_tarde": self.afternoon_capacity.value(),
                    "intervalo_auxiliares": self.aux_interval.value(),
                    "observacao": f"Planejamento {self.period_badge.text()}",
                }
            )
            show_notice(self, "Planejamento salvo", "Capacidades e intervalo dos auxiliares atualizados com sucesso.", icon_name="dashboard")
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao salvar", str(exc), icon_name="warning")

    def toggle_block(self, blocked: bool):
        if not self.selected_day_iso:
            show_notice(self, "Selecione um dia", "Clique em um dia do cronograma para bloquear ou liberar a lavagem.", icon_name="warning")
            return
        try:
            self.api_client.set_wash_blocked_day(
                {
                    "ano": self.selected_year,
                    "mes": self.selected_month,
                    "data": self.selected_day_iso,
                    "turno": self.block_shift_combo.currentData(),
                    "bloqueado": blocked,
                    "motivo": self.block_reason.text().strip(),
                }
            )
            message = "Dia/turno bloqueado com sucesso." if blocked else "Dia/turno liberado para lavagem."
            show_notice(self, "Planejamento atualizado", message, icon_name="dashboard")
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha no bloqueio", str(exc), icon_name="warning")

    def generate_tomorrow_message(self):
        try:
            payload = self.api_client.get_wash_tomorrow_message()
            package = build_wash_tomorrow_message_package(payload, self._generated_by())
            MessageComposerDialog(package, self).exec()
        except Exception as exc:
            show_notice(self, "Falha ao gerar mensagem", str(exc), icon_name="warning")

    def export_month_pdf(self):
        logo_path = asset_path("app-logo-cover.png")
        overview = dict(self.overview)

        def task(progress):
            progress(12, "Preparando relatório mensal de lavagens")
            progress(48, "Montando indicadores e histórico")
            path = export_wash_month_pdf(
                overview,
                logo_path=logo_path if logo_path.exists() else None,
                generated_by=self._generated_by(),
            )
            return path

        start_export_task(
            self,
            "Exportando PDF mensal",
            task,
            success_template="Relatório salvo em:\n{result}",
            failure_title="Falha ao exportar",
        )

    def export_schedule_pdf(self):
        logo_path = asset_path("app-logo-cover.png")
        overview = dict(self.overview)

        def task(progress):
            progress(12, "Preparando cronograma de lavagens")
            progress(48, "Montando programação mensal")
            path = export_wash_schedule_pdf(
                overview,
                logo_path=logo_path if logo_path.exists() else None,
                generated_by=self._generated_by(),
            )
            return path

        start_export_task(
            self,
            "Exportando PDF do cronograma",
            task,
            success_title="PDF do cronograma",
            success_template="Relatório salvo em:\n{result}",
            failure_title="Falha ao exportar",
        )

    def open_values_dialog(self):
        rows = self.overview.get("tabela_valores", [])
        if not rows:
            show_notice(self, "Sem dados", "Não há categorias de lavagem carregadas no momento.", icon_name="warning")
            return
        dialog = WashValuesDialog(self.api_client, rows, self)
        if dialog.exec():
            self.refresh()

    def open_schedule_detail_dialog(self):
        if not self.selected_day_iso:
            show_notice(self, "Selecione um dia", "Clique em um dia do cronograma para abrir o cumprimento.", icon_name="warning")
            return
        day_payload = self.day_index.get(self.selected_day_iso, {})
        items = []
        for slot in ("morning", "afternoon"):
            items.extend(day_payload.get(slot, []) or [])
        dialog = ScheduleDetailDialog(self.day_detail_title.text(), items, self, self)
        dialog.exec()

    def sync_queue(self):
        try:
            result = self.api_client.sync_wash_queue()
            history = result.get("history") or {}
            show_notice(
                self,
                "Fila sincronizada",
                f"Novos itens: {result.get('created', 0)}\nHistórico importado: {history.get('imported', 0)}",
                icon_name="dashboard",
            )
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao sincronizar", str(exc), icon_name="warning")

    def reclassify_queue(self):
        try:
            result = self.api_client.reclassify_wash_queue()
            show_notice(
                self,
                "Fila reclassificada",
                f"Itens atualizados: {result.get('updated', 0)}",
                icon_name="dashboard",
            )
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao reclassificar", str(exc), icon_name="warning")

    def apply_filters(self):
        search = self.search_input.text().strip().lower()
        status = self.status_filter.currentData()
        category = self.category_filter.currentData()

        filtered = []
        for item in self.overview.get("fila", []):
            vehicle = item.get("vehicle") or {}
            haystack = " ".join(
                [
                    item.get("referencia") or "",
                    vehicle.get("placa") or "",
                    vehicle.get("modelo") or "",
                    item.get("last_location") or "",
                ]
            ).lower()
            if search and search not in haystack:
                continue
            if status and item.get("status_fila") != status:
                continue
            if category and item.get("categoria") != category:
                continue
            filtered.append(item)

        self.visible_queue_items = filtered
        self._fill_queue_table(filtered)

    def _schedule_queue_filter(self, *_args):
        self._queue_filter_timer.start(180)

    def _fill_summary(self):
        summary = self.overview.get("resumo") or {}
        next_item = summary.get("proximo") or {}
        vehicle = next_item.get("vehicle") or {}

        proximo_value, proximo_subtitle = self.summary_cards["proximo"]
        proximo_value.setText(next_item.get("referencia") or "-")
        proximo_subtitle.setText(f"{vehicle.get('placa') or '-'} • {vehicle.get('modelo') or '-'}")

        lavados_value, lavados_subtitle = self.summary_cards["lavados_mes"]
        lavados_value.setText(str(summary.get("lavados_mes", 0)))
        lavados_subtitle.setText("Executadas no período.")

        if self.can_view_values:
            valor_value, valor_subtitle = self.summary_cards["valor_total"]
            valor_value.setText(self._format_currency(summary.get("valor_total")))
            valor_subtitle.setText("Total do mês.")

        indisponiveis_value, indisponiveis_subtitle = self.summary_cards["indisponiveis"]
        indisponiveis_value.setText(str(summary.get("indisponiveis", 0)))
        indisponiveis_subtitle.setText("Fora da vez.")

        prev_value, prev_subtitle = self.summary_cards["preventivas"]
        prev_value.setText(str(summary.get("programados_preventiva", 0)))
        prev_subtitle.setText("Antes da preventiva.")

    def _fill_plan_controls(self):
        periodo = self.overview.get("periodo") or {}
        cronograma = self.overview.get("cronograma") or {}
        config = cronograma.get("config") or {}
        self.period_badge.setText(periodo.get("rotulo") or f"{self.selected_month}/{self.selected_year}")
        self.morning_capacity.setValue(int(config.get("morning_capacity") or 0))
        self.afternoon_capacity.setValue(int(config.get("afternoon_capacity") or 0))
        self.aux_interval.setValue(int(config.get("auxiliary_interval_days") or 15))

    def _fill_calendar(self):
        self.calendar_table.clearContents()
        self.day_index = {item.get("date"): item for item in (self.overview.get("cronograma") or {}).get("days", [])}
        weeks = calendar.monthcalendar(self.selected_year, self.selected_month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        for row, week in enumerate(weeks[:6]):
            for column, day in enumerate(week):
                cell_item = QTableWidgetItem("")
                cell_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                base_font = QFont(cell_item.font())
                base_font.setPointSize(9)
                base_font.setBold(True)
                cell_item.setFont(base_font)
                if day == 0:
                    cell_item.setFlags(Qt.NoItemFlags)
                    cell_item.setBackground(QColor("#F8FAFC"))
                    self.calendar_table.setItem(row, column, cell_item)
                    continue

                current_date = date(self.selected_year, self.selected_month, day).isoformat()
                day_payload = self.day_index.get(current_date, {})
                cell_item.setData(Qt.UserRole, current_date)
                cell_item.setText(self._calendar_cell_text(day, day_payload))
                cell_item.setBackground(self._calendar_cell_background(day_payload, current_date == date.today().isoformat()))
                cell_item.setToolTip(self._calendar_cell_tooltip(day_payload, current_date == date.today().isoformat()))
                cell_item.setForeground(QColor("#0F172A"))
                if current_date == date.today().isoformat():
                    highlight_font = QFont(cell_item.font())
                    highlight_font.setBold(True)
                    cell_item.setFont(highlight_font)
                self.calendar_table.setItem(row, column, cell_item)

        self._resize_calendar_cells()
        self._refresh_selected_day_badge()
        self._fill_day_detail()

    def _resize_calendar_cells(self):
        rows = max(1, self.calendar_table.rowCount())
        header_height = self.calendar_table.horizontalHeader().height()
        frame = self.calendar_table.frameWidth() * 2
        available_height = max(0, self.calendar_table.height() - header_height - frame - 4)
        row_height = max(118, available_height // rows)
        for row in range(rows):
            self.calendar_table.setRowHeight(row, row_height)

    def eventFilter(self, obj, event):
        if obj is self.calendar_table.viewport() and event.type() == QEvent.Resize:
            self._resize_calendar_cells()
        return super().eventFilter(obj, event)

    def _fill_queue_table(self, items: list[dict]):
        self.queue_table.setSortingEnabled(False)
        self.queue_table.blockSignals(True)
        self.queue_table.setUpdatesEnabled(False)
        try:
            self.queue_table.setRowCount(len(items))
            self.current_item = None

            for row, item in enumerate(items):
                vehicle = item.get("vehicle") or {}
                values = [
                    str(item.get("queue_position") or "-"),
                    item.get("referencia") or "-",
                    vehicle.get("placa") or "-",
                    vehicle.get("modelo") or "-",
                    item.get("categoria_sugerida") or "-",
                    self._format_currency(item.get("valor_sugerido")) if self.can_view_values else "",
                    self._format_date(item.get("last_wash_at")),
                    self._format_date(item.get("proxima_preventiva")),
                    "Indisponível" if item.get("indisponivel") else "Disponível",
                ]
                for column, value in enumerate(values):
                    self.queue_table.setItem(row, column, make_table_item(value, payload=item if column == 0 else None))

                action_button = QPushButton("Liberar" if item.get("indisponivel") else "Pular")
                action_button.setMinimumHeight(34)
                action_button.setProperty("variant", "secondary")
                action_button.clicked.connect(lambda checked=False, payload=item: self.toggle_queue_item(payload))
                self.queue_table.setCellWidget(row, 9, action_button)
        finally:
            self.queue_table.setUpdatesEnabled(True)
            self.queue_table.blockSignals(False)
            self.queue_table.setSortingEnabled(True)
        self.selection_badge.setText(f"{len(self._selected_queue_payloads())} selecionados")
        self.register_button.setEnabled(False)
        self.preventive_button.setEnabled(False)

    def _fill_history(self):
        history = self.overview.get("historico", [])
        mode = self.history_filter_mode.currentData()
        selected_pydate = self.history_date_filter.date().toPython()
        if mode == "TODAY":
            target_day = date.today()
        elif mode == "SELECTED_DAY" and self.selected_day_iso:
            try:
                target_day = datetime.fromisoformat(self.selected_day_iso).date()
            except ValueError:
                target_day = selected_pydate
        else:
            target_day = selected_pydate

        if mode in {"TODAY", "SELECTED_DAY"}:
            filtered_history = []
            for item in history:
                raw_date = item.get("wash_date")
                try:
                    item_day = datetime.fromisoformat((raw_date or "").replace("Z", "")).date()
                except ValueError:
                    item_day = None
                if item_day == target_day:
                    filtered_history.append(item)
            history = filtered_history

        for table in (self.history_table, self.category_table, self.vehicle_table):
            table.setSortingEnabled(False)
            table.setUpdatesEnabled(False)
            table.blockSignals(True)
        try:
            self.history_table.setRowCount(len(history))
            for row, item in enumerate(history):
                values = [
                    self._format_datetime(item.get("wash_date")),
                    item.get("referencia") or "-",
                    item.get("carreta") or "-",
                    item.get("tipo_equipamento") or "-",
                    (item.get("turno") or "-").title(),
                    item.get("local") or "-",
                    self._format_currency(item.get("valor")) if self.can_view_values else "",
                    item.get("observacao") or "-",
                ]
                for column, value in enumerate(values):
                    self.history_table.setItem(row, column, make_table_item(value))

            category_rows = (self.overview.get("indicadores") or {}).get("por_categoria", [])
            self.category_table.setRowCount(len(category_rows))
            for row, item in enumerate(category_rows):
                self.category_table.setItem(row, 0, make_table_item(item.get("categoria") or "-"))
                self.category_table.setItem(row, 1, make_table_item(item.get("quantidade") or 0))
                self.category_table.setItem(row, 2, make_table_item(self._format_currency(item.get("valor")) if self.can_view_values else ""))

            vehicle_rows = (self.overview.get("indicadores") or {}).get("por_veiculo", [])
            self.vehicle_table.setRowCount(len(vehicle_rows))
            for row, item in enumerate(vehicle_rows):
                self.vehicle_table.setItem(row, 0, make_table_item(item.get("referencia") or "-"))
                self.vehicle_table.setItem(row, 1, make_table_item(item.get("quantidade") or 0))
                self.vehicle_table.setItem(row, 2, make_table_item(self._format_currency(item.get("valor")) if self.can_view_values else ""))
        finally:
            for table in (self.history_table, self.category_table, self.vehicle_table):
                table.blockSignals(False)
                table.setUpdatesEnabled(True)
                table.setSortingEnabled(True)

    def _fill_day_detail(self):
        if not self.selected_day_iso:
            self.day_detail_title.setText("Nenhum dia selecionado")
            self.day_detail_table.setRowCount(0)
            return

        payload = self.day_index.get(self.selected_day_iso, {})
        is_current_day = self._is_selected_day_current()
        suffix = " • Ações liberadas" if is_current_day else " • Somente visualização"
        self.day_detail_title.setText(f"Programação do dia {self._format_date(self.selected_day_iso)}{suffix}")
        rows = []
        for shift_key, label in (("morning", "Manha"), ("afternoon", "Tarde")):
            for item in payload.get(shift_key, []) or []:
                rows.append((label, item))

        self.day_detail_table.setSortingEnabled(False)
        self.day_detail_table.setUpdatesEnabled(False)
        self.day_detail_table.blockSignals(True)
        try:
            self.day_detail_table.setRowCount(len(rows))
            for row_index, (shift_label, item) in enumerate(rows):
                values = [
                    shift_label,
                    item.get("referencia") or "-",
                    item.get("categoria_lavagem") or "-",
                    self._format_currency(item.get("valor_sugerido")) if self.can_view_values else "",
                ]
                for column, value in enumerate(values):
                    self.day_detail_table.setItem(row_index, column, make_table_item(value))

                self.day_detail_table.setCellWidget(
                    row_index,
                    4,
                    self._build_status_badge(
                        item.get("status_execucao") or "PENDENTE",
                        item.get("status_rotulo") or "Pendente",
                    ),
                )

                ok_button = QPushButton()
                ok_button.setIcon(make_icon("ok", "#E7EBF0", "#4D6A55", 20))
                ok_button.setToolTip("Confirmar que lavou")
                ok_button.setFixedSize(40, 34)
                ok_button.setProperty("compactAction", "ok")
                ok_button.clicked.connect(lambda checked=False, payload=item: self.confirm_schedule_success(payload))

                no_button = QPushButton()
                no_button.setIcon(make_icon("cancel", "#E7EBF0", "#7E6363", 20))
                no_button.setToolTip("Marcar que não lavou")
                no_button.setFixedSize(40, 34)
                no_button.setProperty("compactAction", "no")
                no_button.clicked.connect(lambda checked=False, payload=item: self.mark_schedule_not_completed(payload))

                ok_button.setEnabled(item.get("status_execucao") != "LAVADO")
                no_button.setEnabled(item.get("status_execucao") != "NAO_CUMPRIDO")

                reedit_button = QPushButton("Reeditar")
                reedit_button.setMinimumHeight(32)
                reedit_button.setEnabled(item.get("status_execucao") in {"NAO_CUMPRIDO", "LAVADO"})
                reedit_button.clicked.connect(lambda checked=False, payload=item: self.reedit_schedule_decision(payload))

                self.day_detail_table.setCellWidget(row_index, 5, ok_button)
                self.day_detail_table.setCellWidget(row_index, 6, no_button)
                self.day_detail_table.setCellWidget(row_index, 7, reedit_button)
        finally:
            self.day_detail_table.blockSignals(False)
            self.day_detail_table.setUpdatesEnabled(True)
            self.day_detail_table.setSortingEnabled(True)

    def _build_status_badge(self, status_key: str, status_label: str) -> QWidget:
        frame = QFrame()
        outer = QHBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = QFrame()
        inner = QHBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(8)

        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet("QFrame {border-radius:5px; background:#9AA3AD;}")

        badge = QLabel(status_label.upper())
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumHeight(28)

        if status_key == "LAVADO":
            dot.setStyleSheet("QFrame {border-radius:5px; background:#627A66;}")
            badge.setStyleSheet(
                "QLabel {background:#E5ECE5; color:#3F5643; border:1px solid #B6C3B7; border-radius:2px; font-weight:900; padding:4px 10px;}"
            )
        elif status_key == "NAO_CUMPRIDO":
            dot.setStyleSheet("QFrame {border-radius:5px; background:#7E6363;}")
            badge.setStyleSheet(
                "QLabel {background:#ECE2E2; color:#5F4949; border:1px solid #C7B3B3; border-radius:2px; font-weight:900; padding:4px 10px;}"
            )
        else:
            dot.setStyleSheet("QFrame {border-radius:5px; background:#7C7256;}")
            badge.setStyleSheet(
                "QLabel {background:#ECE7D8; color:#5F563F; border:1px solid #C9BFA3; border-radius:2px; font-weight:900; padding:4px 10px;}"
            )

        inner.addWidget(dot, 0, Qt.AlignVCenter)
        inner.addWidget(badge, 0, Qt.AlignVCenter)

        outer.addStretch()
        outer.addWidget(container, 0, Qt.AlignCenter)
        outer.addStretch()
        return frame

    def _queue_selection_changed(self):
        selected = self._selected_queue_payloads()
        self.selection_badge.setText(f"{len(selected)} selecionados")
        self.current_item = selected[0] if selected else None
        self.register_button.setEnabled(bool(self.current_item))
        self.preventive_button.setEnabled(bool(selected))

    def _selected_queue_payloads(self) -> list[dict]:
        rows = sorted({item.row() for item in self.queue_table.selectedItems()})
        selected = []
        for row in rows:
            first_cell = self.queue_table.item(row, 0)
            payload = first_cell.data(Qt.UserRole) if first_cell else None
            if payload:
                selected.append(payload)
        if selected:
            return selected
        references = [self.queue_table.item(row, 1).text() for row in rows if self.queue_table.item(row, 1)]
        return [item for item in self.visible_queue_items if item.get("referencia") in references]

    def toggle_queue_item(self, item: dict):
        try:
            if item.get("indisponivel"):
                self.api_client.set_wash_available(item["id"])
                show_notice(self, "Veículo liberado", "O equipamento voltou para a fila de lavagem.", icon_name="dashboard")
            else:
                dialog = WashUnavailableDialog(item, self)
                if not dialog.exec():
                    return
                self.api_client.set_wash_unavailable(item["id"], dialog.result_payload)
                show_notice(
                    self,
                    "Veículo indisponível",
                    "A vez foi pulada e o próximo disponível assumiu automaticamente.",
                    icon_name="warning",
                )
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao atualizar fila", str(exc), icon_name="warning")

    def register_selected_wash(self):
        if not self.current_item:
            show_notice(self, "Seleção obrigatória", "Selecione um equipamento da fila para registrar a lavagem.", icon_name="warning")
            return
        dialog = WashRegisterDialog(self.current_item, self.trailers, self.category_values, self, show_values=self.can_view_values)
        if not dialog.exec():
            return
        try:
            payload = {"queue_item_id": self.current_item["id"], **dialog.result_payload}
            self.api_client.register_wash(payload)
            show_notice(
                self,
                "Lavagem registrada",
                "Lavagem salva com sucesso. O equipamento foi enviado para o fim da fila.",
                icon_name="dashboard",
            )
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao registrar", str(exc), icon_name="warning")

    def confirm_schedule_success(self, schedule_item: dict):
        queue_item_id = schedule_item.get("queue_item_id")
        if not queue_item_id:
            show_notice(self, "Item inválido", "Não foi possível identificar o item da fila para esta lavagem.", icon_name="warning")
            return
        queue_item = next((item for item in self.overview.get("fila", []) if item.get("id") == queue_item_id), None)
        if not queue_item:
            show_notice(self, "Item inválido", "O item não está mais disponível na fila atual.", icon_name="warning")
            return

        dialog = ScheduleQuickConfirmDialog(schedule_item, queue_item, self.trailers, self)
        if not dialog.exec():
            return
        try:
            raw_date = schedule_item.get("scheduled_date")
            if raw_date:
                try:
                    scheduled_dt = datetime.fromisoformat(raw_date)
                except ValueError:
                    scheduled_dt = datetime.now()
            else:
                scheduled_dt = datetime.now()

            payload = {
                "queue_item_id": queue_item["id"],
                "wash_date": scheduled_dt.isoformat(timespec="seconds"),
                "turno": schedule_item.get("scheduled_shift") or "MANHA",
                "carreta": dialog.result_payload.get("carreta"),
                "tipo_equipamento": dialog.result_payload.get("tipo_equipamento"),
            }

            photo_file_path = dialog.result_payload.get("photo_file_path")
            if photo_file_path:
                upload = self.api_client.upload_file(
                    photo_file_path,
                    queue_item.get("referencia") or "LAVAGEM",
                    "lavagem",
                    self._generated_by(),
                )
                payload["foto_path"] = upload.get("path")

            self.api_client.register_wash(payload)
            show_notice(self, "Lavagem confirmada", "O cronograma do dia foi atualizado como cumprido.", icon_name="dashboard")
            self.refresh()
            self.data_changed.emit()
        except Exception as exc:
            show_notice(self, "Falha ao confirmar", str(exc), icon_name="warning")

    def mark_schedule_not_completed(self, schedule_item: dict):
        dialog = WashDecisionDialog(
            schedule_item.get("referencia") or "-",
            "manha" if schedule_item.get("scheduled_shift") == "MANHA" else "tarde",
            self,
        )
        if not dialog.exec():
            return
        try:
            self.api_client.set_wash_schedule_decision(
                {
                    "queue_item_id": schedule_item.get("queue_item_id"),
                    "data": schedule_item.get("scheduled_date"),
                    "turno": schedule_item.get("scheduled_shift"),
                    "motivo": dialog.result_payload.get("motivo"),
                }
            )
            show_notice(self, "Cronograma atualizado", "A lavagem foi marcada como não cumprida nesse turno.", icon_name="warning")
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao atualizar", str(exc), icon_name="warning")

    def reedit_schedule_decision(self, schedule_item: dict):
        status = str(schedule_item.get("status_execucao") or "").upper()
        if status == "LAVADO":
            decision = QMessageBox.question(
                self,
                "Reabrir cumprimento",
                "Este item está como LAVADO. Deseja reabrir e voltar para PENDENTE?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if decision != QMessageBox.Yes:
                return
        try:
            self.api_client.reedit_wash_schedule_decision(
                {
                    "queue_item_id": schedule_item.get("queue_item_id"),
                    "data": schedule_item.get("scheduled_date"),
                    "turno": schedule_item.get("scheduled_shift"),
                    "status_execucao": status,
                }
            )
            show_notice(self, "Item reeditado", "O item voltou para pendente e pode ser marcado novamente.", icon_name="dashboard")
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao reeditar", str(exc), icon_name="warning")

    def schedule_preventive(self):
        items = self._selected_queue_payloads()
        if not items:
            show_notice(self, "Seleção obrigatória", "Selecione um ou mais cavalos para programar antes da preventiva.", icon_name="warning")
            return
        dialog = PreventiveScheduleDialog(len(items), self)
        if not dialog.exec():
            return
        try:
            payload = {"queue_item_ids": [item["id"] for item in items], **dialog.result_payload}
            self.api_client.schedule_wash_preventive(payload)
            show_notice(self, "Preventiva programada", "Programação salva na fila de lavagem.", icon_name="dashboard")
            self.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao programar", str(exc), icon_name="warning")

    def _calendar_selection_changed(self):
        selected_items = self.calendar_table.selectedItems()
        if not selected_items:
            self.selected_day_iso = None
            self._refresh_selected_day_badge()
            self._fill_day_detail()
            self._fill_history()
            return
        self.selected_day_iso = selected_items[0].data(Qt.UserRole)
        if self.selected_day_iso:
            try:
                selected_day = datetime.fromisoformat(self.selected_day_iso).date()
                self.history_date_filter.setDate(QDate(selected_day.year, selected_day.month, selected_day.day))
            except ValueError:
                pass
        self._refresh_selected_day_badge()
        self._fill_day_detail()
        self._fill_history()

    def _calendar_item_double_clicked(self, item: QTableWidgetItem):
        day_iso = item.data(Qt.UserRole)
        if not day_iso:
            return
        self.selected_day_iso = day_iso
        try:
            selected_day = datetime.fromisoformat(day_iso).date()
            self.history_date_filter.setDate(QDate(selected_day.year, selected_day.month, selected_day.day))
        except ValueError:
            pass
        self._refresh_selected_day_badge()
        self._fill_day_detail()
        self._fill_history()
        self.open_schedule_detail_dialog()

    def _refresh_selected_day_badge(self):
        if not self.selected_day_iso:
            self.selected_day_badge.setText("Selecione um dia no cronograma")
            return
        day_payload = self.day_index.get(self.selected_day_iso, {})
        morning = len(day_payload.get("morning") or [])
        afternoon = len(day_payload.get("afternoon") or [])
        ok_count = self._status_count(day_payload, "LAVADO")
        no_count = self._status_count(day_payload, "NAO_CUMPRIDO")
        pending_count = self._status_count(day_payload, "PENDENTE")
        self.selected_day_badge.setText(
            f"{self._format_date(self.selected_day_iso)} • manhã {morning} • tarde {afternoon} • OK {ok_count} • X {no_count} • pendentes {pending_count}"
        )

    def _calendar_cell_text(self, day: int, payload: dict) -> str:
        if not payload:
            current_date = date(self.selected_year, self.selected_month, day).isoformat()
            if current_date == date.today().isoformat():
                return f"HOJE\n{day}"
            return str(day)

        def detailed(items: list[dict]) -> str:
            if not items:
                return "-"
            entries = [item.get("referencia") or "-" for item in items[:4]]
            return ", ".join(entries) + ("..." if len(items) > 4 else "")

        ok_count = self._status_count(payload, "LAVADO")
        no_count = self._status_count(payload, "NAO_CUMPRIDO")
        pending_count = self._status_count(payload, "PENDENTE")
        current_date = date(self.selected_year, self.selected_month, day).isoformat()
        lines = [f"HOJE • {day}" if current_date == date.today().isoformat() else str(day)]
        lines.append("MANHÃ: sem lavagem" if payload.get("blocked_morning") else f"MANHÃ: {detailed(payload.get('morning') or [])}")
        lines.append("TARDE: sem lavagem" if payload.get("blocked_afternoon") else f"TARDE: {detailed(payload.get('afternoon') or [])}")
        lines.append(f"● OK {ok_count}   ● X {no_count}   ● PEND {pending_count}")
        return "\n".join(lines)

    @staticmethod
    def _calendar_cell_background(payload: dict, is_current_day: bool = False) -> QColor:
        if payload.get("blocked"):
            return QColor("#D2BCBC") if is_current_day else QColor("#E7DADB")
        total_items = len(payload.get("morning") or []) + len(payload.get("afternoon") or [])
        if total_items == 0:
            return QColor("#D3D8DE") if is_current_day else QColor("#ECEFF2")
        ok_count = sum(1 for item in (payload.get("morning") or []) + (payload.get("afternoon") or []) if item.get("status_execucao") == "LAVADO")
        no_count = sum(1 for item in (payload.get("morning") or []) + (payload.get("afternoon") or []) if item.get("status_execucao") == "NAO_CUMPRIDO")
        if no_count > 0 and ok_count == 0:
            return QColor("#CDB8B8") if is_current_day else QColor("#E5D8D8")
        if ok_count == total_items:
            return QColor("#C8D4C8") if is_current_day else QColor("#E3EAE3")
        if ok_count > 0 or no_count > 0:
            return QColor("#D2CCB8") if is_current_day else QColor("#ECE6D6")
        return QColor("#D3D8DE") if is_current_day else QColor("#ECEFF2")

    def _calendar_cell_tooltip(self, payload: dict, is_current_day: bool) -> str:
        ok_count = self._status_count(payload, "LAVADO")
        no_count = self._status_count(payload, "NAO_CUMPRIDO")
        pending_count = self._status_count(payload, "PENDENTE")
        lines = []
        if is_current_day:
            lines.append("HOJE: botoes OK e X liberados.")
        if payload.get("blocked"):
            lines.append("Dia com bloqueio de lavagem.")
            if payload.get("reason"):
                lines.append(f"Motivo: {payload.get('reason')}")
        lines.append(f"✔ Lavados: {ok_count}")
        lines.append(f"✖ Não lavados: {no_count}")
        lines.append(f"Pendentes: {pending_count}")
        return "\n".join(lines)

    @staticmethod
    def _status_count(payload: dict, status: str) -> int:
        items = (payload.get("morning") or []) + (payload.get("afternoon") or [])
        return sum(1 for item in items if item.get("status_execucao") == status)

    def _caption_field(self, title: str, widget, row_stretch: int = 1) -> QWidget:
        wrapper = QFrame()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("SectionCaption")
        layout.addWidget(label)
        layout.addWidget(widget, row_stretch)
        return wrapper

    def _generated_by(self) -> str:
        user = self.api_client.user or {}
        return user.get("nome") or user.get("login") or "Sistema"

    def open_wash_photo(self, relative_path: str | None):
        if not relative_path:
            show_notice(self, "Sem foto", "Esta lavagem ainda não possui foto anexada.", icon_name="warning")
            return
        try:
            url = self.api_client.make_absolute_url(relative_path)
            if not url:
                show_notice(self, "Sem foto", "Não foi possível abrir a foto desta lavagem.", icon_name="warning")
                return
            webbrowser.open(url)
        except Exception as exc:
            show_notice(self, "Falha ao abrir foto", str(exc), icon_name="warning")

    def _is_selected_day_current(self) -> bool:
        if not self.selected_day_iso:
            return False
        return self.selected_day_iso == date.today().isoformat()

    @staticmethod
    def _is_schedule_item_current_day(schedule_item: dict) -> bool:
        return (schedule_item.get("scheduled_date") or "") == date.today().isoformat()

    @staticmethod
    def _format_currency(value) -> str:
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            amount = 0.0
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value.replace("Z", "")).strftime("%d/%m/%Y")
        except ValueError:
            return value

    @staticmethod
    def _format_datetime(value: str | None) -> str:
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(value.replace("Z", "")).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value

