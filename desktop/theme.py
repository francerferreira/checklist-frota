from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, Qt
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
    color: #16385E;
    font-family: "Tahoma", "Segoe UI", sans-serif;
    font-size: 12px;
}
QLabel {
    background: transparent;
}
QMainWindow, QWidget#MainContainer {
    background: #D4E1F2;
}
QFrame#Sidebar {
    background: #D4E1F2;
    border: 1px solid #97AFCB;
    border-radius: 2px;
}
QWidget#ContentSurface {
    background: #FFFFFF;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QWidget#PanelCard, QWidget#ImagePanel, QWidget#HeaderCard, QWidget#FilterBar, QWidget#TableCard {
    background: #F2F7FE;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QDialog#PanelCard {
    background: #F2F7FE;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#DialogHeader {
    background: #C7D8EC;
    border: none;
    border-radius: 2px;
}
QFrame#DialogFooter {
    background: #E7F0FB;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#DialogIconBadge {
    background: #DCE8F7;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#DialogInfoBlock {
    background: #ECF3FC;
    border: 1px solid #BDD0E5;
    border-radius: 2px;
}
QFrame#PhotoFrame {
    background: #ECF3FC;
    border: 1px solid #BDD0E5;
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
    background: #E7F0FB;
    color: #2F557A;
    border: 1px solid #AFC3DA;
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
    background: #DCE8F7;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#TopNavGridHost {
    background: #E8F1FC;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#TopBar {
    background: #CCDDF1;
    border: 1px solid #9FB7D3;
    border-radius: 2px;
}
QFrame#TopBarActionCluster {
    background: #E3EDF9;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QFrame#TopBarBadge {
    background: #F2F7FE;
    border: 1px solid #AFC3DA;
    border-radius: 2px;
}
QLabel#TopBarPill {
    background: #E7F0FB;
    color: #163F6A;
    border: 1px solid #AFC3DA;
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
    border: 1px solid #1D67B8;
    border-radius: 2px;
    background: #2C78D3;
    color: #FFFFFF;
    padding: 6px 10px;
    font-weight: 700;
}
QPushButton:hover {
    background: #1E67BF;
}
QPushButton:disabled {
    background: #CFE1F5;
    border: 1px solid #9CB9DB;
    color: #EEF5FD;
}
QPushButton[variant="primary"] {
    background: #115FC0;
    border: 1px solid #0E4E9E;
    color: #FFFFFF;
}
QPushButton[variant="primary"]:disabled {
    background: #C6DBF3;
    border: 1px solid #97B8DE;
    color: #E9F2FC;
}
QPushButton[variant="success"] {
    background: #159789;
    border: 1px solid #0F756A;
    color: #FFFFFF;
}
QPushButton[variant="success"]:disabled {
    background: #C9E9E5;
    border: 1px solid #91CDC6;
    color: #EAF7F5;
}
QPushButton[variant="danger"] {
    background: #D06A6A;
    border: 1px solid #B65858;
    color: #FFFFFF;
}
QPushButton[variant="danger"]:disabled {
    background: #EFD7D7;
    border: 1px solid #D8AFAF;
    color: #F8EFEF;
}
QPushButton[moduleNav="true"] {
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 720;
}
QPushButton[compactAction="ok"] {
    background: #2272CC;
    color: #FFFFFF;
    border: 1px solid #185DAA;
}
QPushButton[compactAction="ok"]:hover {
    background: #1A62B3;
}
QPushButton[compactAction="no"] {
    background: #CF7B7B;
    color: #FFFFFF;
    border: 1px solid #B66868;
}
QPushButton[compactAction="no"]:hover {
    background: #BB6B6B;
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
    background: #E7F0FB;
}
QComboBox::down-arrow, QDateEdit::down-arrow {
    width: 9px;
    height: 9px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background: #E7F0FB;
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
    background: #DCE8F7;
    color: #123A64;
    border: 1px solid #AFC3DA;
    font-size: 12px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
}
QMenuBar::item:selected {
    background: #C9DCF2;
}
QMenu {
    background: #F2F7FE;
    color: #123A64;
    border: 1px solid #AFC3DA;
}
QMenu::item {
    padding: 6px 22px 6px 22px;
}
QMenu::item:selected {
    background: #C9DCF2;
}
QMenu::separator {
    height: 1px;
    background: #C0D3E8;
    margin: 4px 6px;
}
QTreeWidget, QTreeView {
    background: #F2F7FE;
    color: #123A64;
    border: 1px solid #AFC3DA;
    alternate-background-color: #ECF3FC;
}
QTreeWidget::item, QTreeView::item {
    padding: 4px 3px;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background: #2F6FB2;
    color: #FFFFFF;
}
QMdiArea {
    background: #D9E8F7;
    border: 1px solid #AFC3DA;
}
QGroupBox {
    border: 1px solid #AFC3DA;
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
    background: transparent;
    border: none;
    gridline-color: rgba(145, 173, 204, 0.65);
    selection-background-color: #2F6FB2;
    selection-color: #FFFFFF;
    alternate-background-color: #F3F7FD;
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
    background: #EAF2FC;
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
    background: #DEEAFA;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #8FAFD0;
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
    background: #DEEAFA;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #8FAFD0;
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
    border: 1px solid #AFC3DA;
    background: #F2F7FE;
    top: -1px;
}
QTabBar::tab {
    background: #E6EFFA;
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
    border: 1px solid #AFC3DA;
    border-bottom-color: #FFFFFF;
}
QToolTip {
    background: #F2F7FE;
    color: #123A64;
    border: 1px solid #AFC3DA;
    padding: 4px 6px;
}
QMessageBox {
    background: #D4E1F2;
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
    background: #E8F1FC;
    color: #2C5A88;
    border: 1px solid #B8CCE3;
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
    background: #E6EFFA;
    color: #295780;
    border-top: 1px solid #AFC3DA;
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

