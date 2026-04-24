from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


TABLE_SORT_ROLE = Qt.UserRole + 100


class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        left = self.data(TABLE_SORT_ROLE)
        right = other.data(TABLE_SORT_ROLE) if isinstance(other, QTableWidgetItem) else None
        if left is not None and right is not None:
            try:
                return left < right
            except TypeError:
                return str(left).casefold() < str(right).casefold()
        return super().__lt__(other)


def _coerce_sort_value(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text == "-":
        return ""

    numeric = text.replace("R$", "").replace("%", "").replace(" ", "")
    if "," in numeric:
        numeric = numeric.replace(".", "").replace(",", ".")
    try:
        return float(numeric)
    except ValueError:
        pass

    normalized_date = text.replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized_date, fmt).timestamp()
        except ValueError:
            continue

    return text.casefold()


def make_table_item(value="", *, payload=None, sort_value=None) -> QTableWidgetItem:
    display = "-" if value is None else str(value)
    item = SortableTableWidgetItem(display)
    if payload is not None:
        item.setData(Qt.UserRole, payload)
    item.setData(TABLE_SORT_ROLE, _coerce_sort_value(value) if sort_value is None else sort_value)
    return item


APP_STYLE = """
QWidget {
    background: transparent;
    color: #16385E;
    font-family: "Tahoma", "Segoe UI", sans-serif;
    font-size: 12px;
}
QLabel {
    background: transparent;
}
QMainWindow, QWidget#MainContainer {
    background: #FFFFFF;
}
QFrame#Sidebar {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QWidget#ContentSurface {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QWidget#PanelCard, QWidget#ImagePanel, QWidget#HeaderCard, QWidget#FilterBar, QWidget#TableCard {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QDialog#PanelCard {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#DialogHeader {
    background: #EAF3FF;
    border: none;
    border-radius: 2px;
}
QFrame#DialogFooter {
    background: #F6FAFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#DialogIconBadge {
    background: #2F6FB2;
    border: 1px solid #245F9C;
    border-radius: 2px;
}
QFrame#DialogInfoBlock {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#PhotoFrame {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QLabel#DialogHeaderTitle {
    color: #113A67;
    font-size: 20px;
    font-weight: 760;
}
QLabel#DialogHeaderSubtitle {
    color: #3F638B;
    font-size: 12px;
}
QLabel#DialogInfoValue {
    color: #123D6C;
    font-size: 12px;
    font-weight: 700;
}
QLabel#PhotoStatus {
    background: #EAF3FF;
    color: #2F557A;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 700;
}
QLabel#PhotoCaption {
    color: #4A6E93;
    font-size: 12px;
}
QLabel#PhotoRibbon {
    background: #2F6FB2;
    color: #FFFFFF;
    border-radius: 2px;
    padding: 5px 8px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0;
}
QFrame#TopNavStrip {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#TopNavGridHost {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#TopBar {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#TopBarActionCluster {
    background: #F6FAFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QFrame#TopBarBadge {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
}
QLabel#TopBarPill {
    background: #EAF3FF;
    color: #163F6A;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 700;
}
QLabel#TopBarSessionText {
    color: #4F75A0;
    font-size: 10px;
}
QLabel#TopBarBadgeTitle {
    color: #0E2C4D;
    font-size: 12px;
    font-weight: 700;
}
QLabel#CompactTitle {
    font-size: 13px;
    font-weight: 760;
    color: #0F3A68;
}
QLabel#SidebarTitle {
    color: #FFFFFF;
    font-size: 20px;
    font-weight: 760;
}
QLabel#SidebarCaption {
    color: rgba(255, 255, 255, 0.72);
    font-size: 12px;
}
QLabel#SidebarSection {
    color: rgba(255, 255, 255, 0.54);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QLabel#TopBarTitle {
    color: #113A67;
    font-size: 20px;
    font-weight: 760;
}
QLabel#TopBarSubtitle {
    color: #3F638B;
    font-size: 12px;
}
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 780;
    color: #123A64;
}
QLabel#PageSubtitle {
    color: #4A6F97;
    font-size: 12px;
}
QLabel#SectionTitle {
    color: #1D4C7D;
    font-size: 15px;
    font-weight: 760;
}
QLabel#SectionCaption {
    color: #4E729A;
    font-size: 11px;
}
QLabel#ContextHint {
    color: #4A7099;
    font-size: 11px;
}
QLabel#DialogBodyText {
    color: #133A63;
    font-size: 14px;
    font-weight: 700;
}
QPushButton {
    background: #2C78D3;
    background-color: #2C78D3;
    border: 1px solid #1D67B8;
    border-style: solid;
    border-radius: 2px;
    color: #FFFFFF;
    padding: 6px 10px;
    font-weight: 700;
}
QPushButton:enabled {
    background: #2C78D3;
    background-color: #2C78D3;
    border: 1px solid #1D67B8;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton:hover {
    background: #1E67BF;
    background-color: #1E67BF;
    color: #FFFFFF;
}
QPushButton:pressed {
    background: #155AA8;
    background-color: #155AA8;
    color: #FFFFFF;
}
QPushButton:disabled {
    background: #8DB8E8;
    background-color: #8DB8E8;
    border: 1px solid #5E91CC;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="primary"] {
    background: #115FC0;
    background-color: #115FC0;
    border: 1px solid #0E4E9E;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="primary"]:enabled {
    background: #115FC0;
    background-color: #115FC0;
    border: 1px solid #0E4E9E;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="primary"]:disabled {
    background: #85B2E6;
    background-color: #85B2E6;
    border: 1px solid #4E86C8;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="success"] {
    background: #159789;
    background-color: #159789;
    border: 1px solid #0F756A;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="success"]:enabled {
    background: #159789;
    background-color: #159789;
    border: 1px solid #0F756A;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="success"]:disabled {
    background: #74CFC5;
    background-color: #74CFC5;
    border: 1px solid #3E9F94;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="danger"] {
    background: #D06A6A;
    background-color: #D06A6A;
    border: 1px solid #B65858;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="danger"]:enabled {
    background: #D06A6A;
    background-color: #D06A6A;
    border: 1px solid #B65858;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[variant="danger"]:disabled {
    background: #E2A0A0;
    background-color: #E2A0A0;
    border: 1px solid #C77575;
    border-style: solid;
    color: #FFFFFF;
}
QPushButton[moduleNav="true"] {
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 720;
}
QPushButton[compactAction="ok"] {
    background: #2272CC;
    background-color: #2272CC;
    color: #FFFFFF;
    border: 1px solid #185DAA;
    border-style: solid;
}
QPushButton[compactAction="ok"]:hover {
    background: #1A62B3;
    background-color: #1A62B3;
}
QPushButton[compactAction="no"] {
    background: #CF7B7B;
    background-color: #CF7B7B;
    color: #FFFFFF;
    border: 1px solid #B66868;
    border-style: solid;
}
QPushButton[compactAction="no"]:hover {
    background: #BB6B6B;
    background-color: #BB6B6B;
}
QLineEdit, QTextEdit, QComboBox {
    background: #FFFFFF;
    border: 1px solid #AFC4DA;
    border-radius: 2px;
    padding: 6px 8px;
    min-height: 20px;
}
QDateEdit, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid #AFC4DA;
    border-radius: 2px;
    padding: 4px 6px;
    min-height: 20px;
}
QComboBox::drop-down, QDateEdit::drop-down {
    border: none;
    width: 24px;
    background: #EAF3FF;
}
QComboBox::down-arrow, QDateEdit::down-arrow {
    width: 9px;
    height: 9px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background: #EAF3FF;
    border-left: 1px solid #AFC4DA;
    width: 18px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #D5E4F5;
}
QCheckBox {
    color: #234D7D;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 2px;
    border: 1px solid #AFC4DA;
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #2F6FB2;
    border: 1px solid #2F6FB2;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #3F76AF;
}
QMenuBar {
    background: #FFFFFF;
    color: #123A64;
    border: 1px solid #B7CBE3;
    font-size: 12px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
}
QMenuBar::item:selected {
    background: #EAF3FF;
}
QMenu {
    background: #FFFFFF;
    color: #123A64;
    border: 1px solid #B7CBE3;
}
QMenu::item {
    padding: 6px 22px 6px 22px;
}
QMenu::item:selected {
    background: #EAF3FF;
}
QMenu::separator {
    height: 1px;
    background: #B7CBE3;
    margin: 4px 6px;
}
QTreeWidget, QTreeView {
    background: #FFFFFF;
    color: #123A64;
    border: 1px solid #B7CBE3;
    alternate-background-color: #F6FAFF;
}
QTreeWidget::item, QTreeView::item {
    padding: 4px 3px;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background: #2F6FB2;
    color: #FFFFFF;
}
QMdiArea {
    background: #FFFFFF;
    border: 1px solid #B7CBE3;
}
QGroupBox {
    border: 1px solid #B7CBE3;
    border-radius: 2px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 700;
    color: #1D4C7D;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px 0 4px;
}
QTableWidget {
    background: #FFFFFF;
    border: none;
    gridline-color: rgba(145, 173, 204, 0.65);
    selection-background-color: #2F6FB2;
    selection-color: #FFFFFF;
    alternate-background-color: #F6FAFF;
    font-size: 12px;
}
QTableWidget::item {
    padding: 7px 9px;
    border: none;
}
QTableWidget::item:selected,
QTableWidget::item:selected:active,
QTableWidget::item:selected:!active,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active {
    background: #2F6FB2;
    color: #FFFFFF;
}
QTableWidget::item:hover,
QTableView::item:hover {
    background: rgba(47, 111, 178, 0.14);
}
QTableWidget#DialogScheduleGrid {
    font-size: 13px;
}
QTableWidget#DialogScheduleGrid::item {
    padding: 6px 8px;
}
QTableWidget#DialogScheduleGrid QHeaderView::section {
    font-size: 13px;
    font-weight: 760;
    padding: 7px 8px;
}
QTableWidget#CalendarGrid,
QTableWidget#WashCalendarTable {
    background: #FFFFFF;
    border: 1px solid #8FB2D9;
    border-radius: 2px;
    gridline-color: rgba(126, 165, 209, 0.62);
    selection-background-color: #1F6FCA;
    selection-color: #FFFFFF;
}
QTableWidget#CalendarGrid::item,
QTableWidget#WashCalendarTable::item {
    border: 1px solid #B7CDE6;
    padding: 8px 8px;
}
QTableWidget#CalendarGrid::item:selected,
QTableWidget#WashCalendarTable::item:selected {
    border: 1px solid #185DAA;
    background: #1F6FCA;
    color: #FFFFFF;
}
QTableWidget#CalendarGrid QHeaderView::section,
QTableWidget#WashCalendarTable QHeaderView::section {
    background: #2F6FB2;
    color: #FFFFFF;
    border-right: 1px solid #245F9C;
    border-bottom: 1px solid #245F9C;
    padding: 8px 6px;
    font-weight: 760;
}
QHeaderView::section {
    background: #2B73C6;
    color: #FFFFFF;
    border: none;
    border-right: 1px solid #1F5FA7;
    border-bottom: 1px solid #1F5FA7;
    padding: 7px 9px;
    font-weight: 760;
}
QHeaderView::section:hover {
    background: #3A81D3;
}
QScrollBar:vertical {
    width: 11px;
    background: #EAF3FF;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #6FA0D8;
    min-height: 28px;
    border-radius: 2px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    height: 11px;
    background: #EAF3FF;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #6FA0D8;
    min-width: 28px;
    border-radius: 2px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}
QScrollArea, QStackedWidget {
    border: none;
    background: transparent;
}
QTabWidget::pane {
    border: 1px solid #B7CBE3;
    background: #FFFFFF;
    top: -1px;
}
QTabBar::tab {
    background: #EAF3FF;
    color: #113A67;
    border: none;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    padding: 6px 10px;
    margin-right: 6px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #1A4A7B;
    border: 1px solid #B7CBE3;
    border-bottom-color: #FFFFFF;
}
QToolTip {
    background: #FFFFFF;
    color: #123A64;
    border: 1px solid #B7CBE3;
    padding: 4px 6px;
}
QMessageBox {
    background: #FFFFFF;
}
QMessageBox QLabel {
    color: #133A63;
}
QMessageBox QPushButton {
    min-width: 90px;
}
QSplitter::handle {
    background: transparent;
    width: 14px;
}
QLabel#CardTitle {
    color: #4C729B;
    font-size: 12px;
    font-weight: 700;
}
QLabel#CardValue {
    color: #0E2C4D;
    font-size: 34px;
    font-weight: 780;
}
QLabel#CardSubtitle {
    color: #4C729B;
    font-size: 12px;
}
QLabel#SummaryMetric {
    font-size: 18px;
    font-weight: 760;
    color: #124E83;
}
QLabel#SummaryMeta {
    font-size: 10px;
    color: #4D739A;
}
QLabel#BadgeStrong {
    background: #3D6898;
    color: #FFFFFF;
    border: 1px solid #315B88;
    border-radius: 2px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#BadgeSoft {
    background: #EAF3FF;
    color: #2C5A88;
    border: 1px solid #B7CBE3;
    border-radius: 2px;
    padding: 5px 9px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#CloudSummaryLabel {
    font-size: 18px;
    font-weight: 800;
    color: #133A63;
}
QLabel#ImageTitle {
    font-size: 16px;
    font-weight: 720;
    color: #0E2C4D;
}
QLabel#MutedText {
    color: #4C729B;
}
QStatusBar {
    background: #FFFFFF;
    color: #295780;
    border-top: 1px solid #B7CBE3;
}
"""


_BUTTON_PALETTE = {
    "default": ("#2C78D3", "#1E67BF", "#155AA8", "#1D67B8", "#8DB8E8", "#5E91CC"),
    "primary": ("#115FC0", "#0E56AE", "#0B468F", "#0E4E9E", "#85B2E6", "#4E86C8"),
    "success": ("#159789", "#0F8578", "#0B6B61", "#0F756A", "#74CFC5", "#3E9F94"),
    "danger": ("#D06A6A", "#BC5D5D", "#A84E4E", "#B65858", "#E2A0A0", "#C77575"),
}


def _button_tone(button: QPushButton) -> str:
    compact = button.property("compactAction")
    if compact == "ok":
        return "success"
    if compact == "no":
        return "danger"
    variant = button.property("variant")
    if variant in {"primary", "success", "danger"}:
        return str(variant)
    return "default"


def apply_button_style(button: QPushButton) -> None:
    if button.property("_skip_app_button_style"):
        return
    if button.__class__.__name__ == "AnimatedButton":
        return

    base, hover, pressed, border, disabled, disabled_border = _BUTTON_PALETTE[_button_tone(button)]
    text_align = "left" if button.property("moduleNav") == "true" else "center"
    button.setFlat(False)
    button.setAutoFillBackground(False)
    button.setStyleSheet(
        f"""
        QPushButton {{
            background: {base};
            background-color: {base};
            color: #FFFFFF;
            border: 1px solid {border};
            border-style: solid;
            border-radius: 2px;
            padding: 6px 10px;
            font-weight: 700;
            text-align: {text_align};
        }}
        QPushButton:hover {{
            background: {hover};
            background-color: {hover};
            color: #FFFFFF;
        }}
        QPushButton:pressed {{
            background: {pressed};
            background-color: {pressed};
            color: #FFFFFF;
        }}
        QPushButton:disabled {{
            background: {disabled};
            background-color: {disabled};
            color: #FFFFFF;
            border: 1px solid {disabled_border};
            border-style: solid;
        }}
        """
    )


def apply_button_styles(root: QWidget | QApplication) -> None:
    widgets = root.allWidgets() if isinstance(root, QApplication) else root.findChildren(QPushButton)
    for widget in widgets:
        if isinstance(widget, QPushButton):
            apply_button_style(widget)


class _ButtonStyleEnforcer(QObject):
    def eventFilter(self, watched, event):
        event_type = event.type()
        if isinstance(watched, QPushButton) and event_type in {
            QEvent.Polish,
            QEvent.Show,
            QEvent.EnabledChange,
            QEvent.DynamicPropertyChange,
        }:
            QTimer.singleShot(0, lambda button=watched: apply_button_style(button))
        elif event_type == QEvent.ChildAdded:
            child = event.child()
            if isinstance(child, QPushButton):
                child.installEventFilter(self)
                QTimer.singleShot(0, lambda button=child: apply_button_style(button))
        return False


def install_button_style_enforcer(app: QApplication) -> None:
    enforcer = getattr(app, "_button_style_enforcer", None)
    if enforcer is None:
        enforcer = _ButtonStyleEnforcer(app)
        app.installEventFilter(enforcer)
        app._button_style_enforcer = enforcer
    for widget in app.allWidgets():
        widget.installEventFilter(enforcer)
    apply_button_styles(app)


def apply_soft_shadow(widget, blur: int = 14, y_offset: int = 4, alpha: int = 10) -> None:
    _ = (blur, y_offset, alpha)
    widget.setGraphicsEffect(None)


def _prepare_styled_widget(widget: QWidget, object_name: str) -> None:
    widget.setObjectName(object_name)
    widget.setAttribute(Qt.WA_StyledBackground, True)


def style_card(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "PanelCard")


def style_table_card(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "TableCard")


def style_filter_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "FilterBar")


def style_top_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "TopBar")


def configure_dialog_window(
    dialog: QDialog,
    *,
    width: int,
    height: int,
    min_width: int = 760,
    min_height: int = 560,
) -> None:
    screen = dialog.screen() or QGuiApplication.primaryScreen()
    if screen:
        available = screen.availableGeometry()
        max_width = max(640, available.width() - 40)
        max_height = max(520, available.height() - 40)
        target_width = min(max(640, width), max_width)
        target_height = min(max(520, height), max_height)

        dialog.resize(target_width, target_height)
        dialog.setMinimumSize(
            min(max(520, min_width), max_width),
            min(max(420, min_height), max_height),
        )
    else:
        dialog.resize(width, height)
        dialog.setMinimumSize(min_width, min_height)
    dialog.setSizeGripEnabled(True)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    dialog.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    dialog.setWindowFlag(Qt.WindowCloseButtonHint, True)
    QTimer.singleShot(0, lambda d=dialog: d.setWindowOpacity(1.0))


def build_dialog_layout(
    dialog: QDialog,
    *,
    max_content_width: int = 1320,
    margins: tuple[int, int, int, int] = (16, 16, 16, 16),
    spacing: int = 14,
) -> QVBoxLayout:
    root = QVBoxLayout(dialog)
    root.setContentsMargins(*margins)
    root.setSpacing(0)

    scroll = QScrollArea(dialog)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.NoFrame)

    viewport = QWidget()
    viewport_layout = QHBoxLayout(viewport)
    viewport_layout.setContentsMargins(0, 0, 0, 0)
    viewport_layout.setSpacing(0)

    content = QWidget()
    # Padrão clássico ERP: conteúdo ocupa toda a janela redimensionável.
    viewport_layout.addWidget(content, 1)

    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)

    scroll.setWidget(viewport)
    root.addWidget(scroll)
    return layout


def animate_dialog_in(dialog: QDialog) -> None:
    dialog.setWindowOpacity(1.0)


def _apply_table_autofit(table: QTableWidget) -> None:
    try:
        if table is None or not bool(table.property("_auto_fit_enabled")):
            return
        if table.columnCount() <= 0:
            return
    except RuntimeError:
        return

    header = table.horizontalHeader()
    stretch_last = bool(table.property("_stretch_last_enabled"))
    sorting_enabled = table.isSortingEnabled()

    table.setSortingEnabled(False)
    try:
        header.setStretchLastSection(False)
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        header.setStretchLastSection(stretch_last)
    finally:
        table.setSortingEnabled(sorting_enabled)


def _schedule_table_autofit(table: QTableWidget) -> None:
    try:
        if table is None or not bool(table.property("_auto_fit_enabled")):
            return
    except RuntimeError:
        return
    timer = getattr(table, "_auto_fit_timer", None)
    if timer is None:
        timer = QTimer(table)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda target=table: _apply_table_autofit(target))
        table._auto_fit_timer = timer
    timer.start(45)


def configure_table(table: QTableWidget, stretch_last: bool = True, auto_fit: bool = True) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSortingEnabled(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setFrameShape(QFrame.NoFrame)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(40)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.horizontalHeader().setMinimumSectionSize(110)
    table.horizontalHeader().setSectionsClickable(True)
    table.horizontalHeader().setSortIndicatorShown(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setFocusPolicy(Qt.NoFocus)
    table.setProperty("_stretch_last_enabled", stretch_last)
    table.setProperty("_auto_fit_enabled", auto_fit)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(stretch_last)

    if auto_fit and not bool(table.property("_auto_fit_connected")):
        model = table.model()
        model.modelReset.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        model.rowsInserted.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        model.rowsRemoved.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        model.columnsInserted.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        model.columnsRemoved.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        model.dataChanged.connect(lambda *_args, target=table: _schedule_table_autofit(target))
        table.setProperty("_auto_fit_connected", True)
        _schedule_table_autofit(table)

