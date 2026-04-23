from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
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
    color: #1E293B;
    font-family: "Tahoma", "Segoe UI", sans-serif;
    font-size: 12px;
}
QLabel {
    background: transparent;
}
QMainWindow, QWidget#MainContainer {
    background: #D8D8D8;
}
QFrame#Sidebar {
    background: #D8D8D8;
    border: 1px solid #A8A8A8;
    border-radius: 2px;
}
QWidget#ContentSurface, QWidget#PanelCard, QWidget#ImagePanel, QWidget#HeaderCard, QWidget#FilterBar, QWidget#TableCard {
    background: #F3F3F3;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QDialog#PanelCard {
    background: #F3F3F3;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QFrame#DialogHeader {
    background: #CDD2D8;
    border: none;
    border-radius: 2px;
}
QFrame#DialogFooter {
    background: #E8EAED;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QFrame#DialogIconBadge {
    background: #E3E6EA;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QFrame#DialogInfoBlock {
    background: #ECEFF2;
    border: 1px solid #C4C9CF;
    border-radius: 2px;
}
QFrame#PhotoFrame {
    background: #ECEFF2;
    border: 1px solid #C4C9CF;
    border-radius: 2px;
}
QLabel#DialogHeaderTitle {
    color: #223447;
    font-size: 20px;
    font-weight: 760;
}
QLabel#DialogHeaderSubtitle {
    color: #4B5D72;
    font-size: 12px;
}
QLabel#DialogInfoValue {
    color: #243447;
    font-size: 12px;
    font-weight: 700;
}
QLabel#PhotoStatus {
    background: #E8EAED;
    color: #344556;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 700;
}
QLabel#PhotoCaption {
    color: #475569;
    font-size: 12px;
}
QLabel#PhotoRibbon {
    background: #6D7783;
    color: #FFFFFF;
    border-radius: 2px;
    padding: 5px 8px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0;
}
QFrame#TopNavStrip {
    background: #E3E6EA;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QFrame#TopBar {
    background: #D4D9DF;
    border: 1px solid #AEB5BC;
    border-radius: 2px;
}
QFrame#TopBarActionCluster {
    background: #E8EBEF;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QFrame#TopBarBadge {
    background: #F3F3F3;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
}
QLabel#TopBarPill {
    background: #E8EAED;
    color: #2C3E50;
    border: 1px solid #B8BDC3;
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 11px;
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
    color: #223447;
    font-size: 20px;
    font-weight: 760;
}
QLabel#TopBarSubtitle {
    color: #4B5D72;
    font-size: 12px;
}
QLabel#PageTitle {
    font-size: 20px;
    font-weight: 760;
    color: #1E2F43;
}
QLabel#PageSubtitle {
    color: #55697F;
    font-size: 12px;
}
QLabel#SectionTitle {
    color: #2F3E50;
    font-size: 14px;
    font-weight: 720;
}
QLabel#SectionCaption {
    color: #667A90;
    font-size: 11px;
}
QPushButton {
    border: 1px solid #AEB5BC;
    border-radius: 2px;
    background: #ECEFF2;
    color: #223447;
    padding: 6px 10px;
    font-weight: 700;
}
QPushButton:hover {
    background: #E1E5EA;
}
QPushButton:disabled {
    background: #E3E6EA;
    color: #8F9DAA;
}
QPushButton[variant="primary"] {
    background: #6D7783;
    border: 1px solid #5D6671;
    color: #FFFFFF;
}
QPushButton[variant="success"] {
    background: #6E7E70;
    border: 1px solid #5F6D61;
    color: #FFFFFF;
}
QPushButton[variant="danger"] {
    background: #866565;
    border: 1px solid #715454;
    color: #FFFFFF;
}
QLineEdit, QTextEdit, QComboBox {
    background: #FFFFFF;
    border: 1px solid #B6BDC5;
    border-radius: 2px;
    padding: 6px 8px;
    min-height: 20px;
}
QCheckBox {
    color: #334155;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 2px;
    border: 1px solid #B6BDC5;
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #6D7783;
    border: 1px solid #6D7783;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #7A8591;
}
QTableWidget {
    background: transparent;
    border: none;
    gridline-color: rgba(182, 189, 197, 0.65);
    selection-background-color: #6D7783;
    selection-color: #FFFFFF;
    alternate-background-color: #F2F3F5;
}
QTableWidget::item {
    padding: 6px 8px;
    border: none;
}
QTableWidget::item:selected,
QTableWidget::item:selected:active,
QTableWidget::item:selected:!active,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active {
    background: #6D7783;
    color: #FFFFFF;
}
QTableWidget::item:hover,
QTableView::item:hover {
    background: rgba(109, 119, 131, 0.14);
}
QHeaderView::section {
    background: #E2E6EB;
    color: #2C3E50;
    border: none;
    border-right: 1px solid rgba(148, 163, 184, 0.16);
    border-bottom: 1px solid rgba(148, 163, 184, 0.20);
    padding: 6px 8px;
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
    background: #E7EAEE;
    color: #223447;
    border: none;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    padding: 6px 10px;
    margin-right: 6px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #2E4155;
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
    background: #E7EAEE;
    color: #3E4F62;
    border-top: 1px solid #B8BDC3;
}
"""


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
    _ = (QEasingCurve, QPropertyAnimation)
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
