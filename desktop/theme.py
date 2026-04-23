from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QHBoxLayout,
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
    color: #0F172A;
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
    font-size: 14px;
}
QLabel {
    background: transparent;
}
QMainWindow, QWidget#MainContainer {
    background: #E6EBF2;
}
QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #17324A, stop:0.58 #123148, stop:1 #0E2A41);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
}
QWidget#ContentSurface, QWidget#PanelCard, QWidget#ImagePanel, QWidget#HeaderCard, QWidget#FilterBar, QWidget#TableCard {
    background: #FFFFFF;
    border: 1px solid rgba(115, 132, 156, 0.24);
    border-radius: 10px;
}
QDialog#PanelCard {
    background: #FFFFFF;
    border: 1px solid rgba(115, 132, 156, 0.24);
    border-radius: 10px;
}
QFrame#DialogHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0F5E84, stop:1 #10719E);
    border: none;
    border-radius: 8px;
}
QFrame#DialogFooter {
    background: #F4F7FB;
    border: 1px solid rgba(115, 132, 156, 0.20);
    border-radius: 8px;
}
QFrame#DialogIconBadge {
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 16px;
}
QFrame#DialogInfoBlock {
    background: #EDF5FB;
    border: 1px solid rgba(16, 94, 132, 0.18);
    border-radius: 8px;
}
QFrame#PhotoFrame {
    background: #F3F7FC;
    border: 1px solid rgba(16, 94, 132, 0.18);
    border-radius: 10px;
}
QLabel#DialogHeaderTitle {
    color: #FFFFFF;
    font-size: 24px;
    font-weight: 760;
}
QLabel#DialogHeaderSubtitle {
    color: rgba(255, 255, 255, 0.84);
    font-size: 13px;
}
QLabel#DialogInfoValue {
    color: #124869;
    font-size: 14px;
    font-weight: 700;
}
QLabel#PhotoStatus {
    background: #E1F0FB;
    color: #0F5E84;
    border: 1px solid rgba(16, 94, 132, 0.26);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#PhotoCaption {
    color: #475569;
    font-size: 12px;
}
QLabel#PhotoRibbon {
    background: #0F5E84;
    color: #FFFFFF;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.04em;
}
QFrame#TopNavStrip {
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 8px;
}
QFrame#TopBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0D5A7D, stop:1 #0B709B);
    border: 1px solid rgba(6, 53, 76, 0.65);
    border-radius: 10px;
}
QFrame#TopBarActionCluster {
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 8px;
}
QFrame#TopBarBadge {
    background: rgba(255, 255, 255, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.36);
    border-radius: 8px;
}
QLabel#TopBarPill {
    background: rgba(255, 255, 255, 0.20);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.32);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 700;
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
    color: #FFFFFF;
    font-size: 25px;
    font-weight: 760;
}
QLabel#TopBarSubtitle {
    color: rgba(255, 255, 255, 0.88);
    font-size: 15px;
}
QLabel#PageTitle {
    font-size: 30px;
    font-weight: 760;
    color: #0B1220;
}
QLabel#PageSubtitle {
    color: #64748B;
    font-size: 13px;
}
QLabel#SectionTitle {
    color: #0F5E84;
    font-size: 16px;
    font-weight: 720;
}
QLabel#SectionCaption {
    color: #64748B;
    font-size: 12px;
}
QPushButton {
    border: 1px solid rgba(115, 132, 156, 0.28);
    border-radius: 8px;
    background: #F4F7FB;
    color: #1B2A40;
    padding: 11px 18px;
    font-weight: 700;
}
QPushButton:hover {
    background: #E9F0F8;
}
QPushButton:disabled {
    background: #E6EBF0;
    color: #94A3B8;
}
QPushButton[variant="primary"] {
    background: #0F5E84;
    border: 1px solid #0E5477;
    color: #FFFFFF;
}
QPushButton[variant="success"] {
    background: #1E9F6B;
    border: 1px solid #198A5C;
    color: #FFFFFF;
}
QPushButton[variant="danger"] {
    background: #CC4747;
    border: 1px solid #B03C3C;
    color: #FFFFFF;
}
QLineEdit, QTextEdit, QComboBox {
    background: #FFFFFF;
    border: 1px solid rgba(115, 132, 156, 0.30);
    border-radius: 8px;
    padding: 10px 12px;
    min-height: 20px;
}
QCheckBox {
    color: #334155;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid rgba(148, 163, 184, 0.40);
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #0F5E84;
    border: 1px solid #0F5E84;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid rgba(15, 94, 132, 0.55);
}
QTableWidget {
    background: transparent;
    border: none;
    gridline-color: rgba(226, 232, 240, 0.50);
    selection-background-color: #0F5E84;
    selection-color: #FFFFFF;
    alternate-background-color: #FAFCFF;
}
QTableWidget::item {
    padding: 10px 10px;
    border: none;
}
QTableWidget::item:selected,
QTableWidget::item:selected:active,
QTableWidget::item:selected:!active,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active {
    background: #0F5E84;
    color: #FFFFFF;
}
QTableWidget::item:hover,
QTableView::item:hover {
    background: rgba(15, 94, 132, 0.08);
}
QHeaderView::section {
    background: #E8EDF4;
    color: #25364A;
    border: none;
    border-right: 1px solid rgba(148, 163, 184, 0.16);
    border-bottom: 1px solid rgba(148, 163, 184, 0.20);
    padding: 10px 10px;
    font-weight: 720;
}
QHeaderView::section:hover {
    background: #E7EDF4;
}
QScrollArea, QStackedWidget {
    border: none;
    background: transparent;
}
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: #E5EBF3;
    color: #1B2A40;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 14px;
    margin-right: 6px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #12334B;
}
QSplitter::handle {
    background: transparent;
    width: 14px;
}
QLabel#CardTitle {
    color: #64748B;
    font-size: 12px;
    font-weight: 700;
}
QLabel#CardValue {
    color: #0B1220;
    font-size: 34px;
    font-weight: 780;
}
QLabel#CardSubtitle {
    color: #64748B;
    font-size: 12px;
}
QLabel#ImageTitle {
    font-size: 16px;
    font-weight: 720;
    color: #0B1220;
}
QLabel#MutedText {
    color: #64748B;
}
QStatusBar {
    background: #F1F5FA;
    color: #334155;
    border-top: 1px solid rgba(115, 132, 156, 0.20);
}
"""


def apply_soft_shadow(widget, blur: int = 14, y_offset: int = 4, alpha: int = 10) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(shadow)


def _prepare_styled_widget(widget: QWidget, object_name: str) -> None:
    widget.setObjectName(object_name)
    widget.setAttribute(Qt.WA_StyledBackground, True)


def style_card(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "PanelCard")
    apply_soft_shadow(frame)


def style_table_card(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "TableCard")
    apply_soft_shadow(frame, blur=10, y_offset=3, alpha=8)


def style_filter_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "FilterBar")
    apply_soft_shadow(frame, blur=8, y_offset=2, alpha=6)


def style_top_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "TopBar")
    apply_soft_shadow(frame, blur=10, y_offset=2, alpha=8)


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

        target_width = min(max(width, int(max_width * 0.86)), max_width)
        target_height = min(max(height, int(max_height * 0.86)), max_height)

        dialog.resize(target_width, target_height)
        dialog.setMinimumSize(
            min(max(min_width, int(max_width * 0.68)), max_width),
            min(max(min_height, int(max_height * 0.68)), max_height),
        )
    else:
        dialog.resize(width, height)
        dialog.setMinimumSize(min_width, min_height)
    dialog.setSizeGripEnabled(True)
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    dialog.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    dialog.setWindowFlag(Qt.WindowCloseButtonHint, True)
    QTimer.singleShot(0, lambda d=dialog: animate_dialog_in(d))


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
    if max_content_width > 0:
        content.setMaximumWidth(max_content_width)
        viewport_layout.addStretch(1)
        viewport_layout.addWidget(content, 0)
        viewport_layout.addStretch(1)
    else:
        viewport_layout.addWidget(content, 1)

    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)

    scroll.setWidget(viewport)
    root.addWidget(scroll)
    return layout


def animate_dialog_in(dialog: QDialog) -> None:
    if getattr(dialog, "_dialog_intro_running", False):
        return
    dialog._dialog_intro_running = True
    dialog.setWindowOpacity(0.0)
    animation = QPropertyAnimation(dialog, b"windowOpacity", dialog)
    animation.setDuration(140)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()
    dialog._dialog_intro_animation = animation


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
    table.verticalHeader().setDefaultSectionSize(44)
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
