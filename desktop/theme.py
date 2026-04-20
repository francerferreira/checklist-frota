from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QHBoxLayout,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


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
    background: #E9EEF5;
}
QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0B1220, stop:0.58 #0F1A2E, stop:1 #16243C);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 28px;
}
QWidget#ContentSurface, QWidget#PanelCard, QWidget#ImagePanel, QWidget#HeaderCard, QWidget#FilterBar, QWidget#TableCard, QWidget#TopBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:1 #F8FBFF);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 24px;
}
QDialog#PanelCard {
    background: #FFFFFF;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 24px;
}
QFrame#DialogHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
    border: none;
    border-radius: 20px;
}
QFrame#DialogFooter {
    background: #F8FAFC;
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 18px;
}
QFrame#DialogIconBadge {
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 16px;
}
QFrame#DialogInfoBlock {
    background: #EFF6FF;
    border: 1px solid rgba(37, 99, 235, 0.14);
    border-radius: 16px;
}
QFrame#PhotoFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F8FBFF, stop:1 #EEF5FF);
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-radius: 20px;
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
    color: #1E3A8A;
    font-size: 14px;
    font-weight: 700;
}
QLabel#PhotoStatus {
    background: #DBEAFE;
    color: #1D4ED8;
    border: 1px solid rgba(37, 99, 235, 0.20);
    border-radius: 12px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#PhotoCaption {
    color: #475569;
    font-size: 12px;
}
QLabel#PhotoRibbon {
    background: #1D4ED8;
    color: #FFFFFF;
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.04em;
}
QFrame#TopNavStrip {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F8FBFF, stop:1 #EEF5FF);
    border: 1px solid rgba(37, 99, 235, 0.10);
    border-radius: 18px;
}
QFrame#TopBar {
    border-radius: 28px;
}
QFrame#TopBarActionCluster {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F8FAFC, stop:1 #EFF6FF);
    border: 1px solid rgba(37, 99, 235, 0.10);
    border-radius: 22px;
}
QFrame#TopBarBadge {
    background: rgba(255, 255, 255, 0.84);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 18px;
}
QLabel#TopBarPill {
    background: #DBEAFE;
    color: #1D4ED8;
    border: 1px solid rgba(37, 99, 235, 0.24);
    border-radius: 16px;
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
    color: #0B1220;
    font-size: 25px;
    font-weight: 760;
}
QLabel#TopBarSubtitle {
    color: #5B6E8A;
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
    color: #1D4ED8;
    font-size: 16px;
    font-weight: 720;
}
QLabel#SectionCaption {
    color: #64748B;
    font-size: 12px;
}
QPushButton {
    border: none;
    border-radius: 14px;
    background: #E2E8F0;
    color: #0F172A;
    padding: 11px 18px;
    font-weight: 650;
}
QPushButton:hover {
    background: #DBEAFE;
}
QPushButton:disabled {
    background: #E5E7EB;
    color: #94A3B8;
}
QPushButton[variant="primary"] {
    background: #2563EB;
    color: #FFFFFF;
}
QPushButton[variant="success"] {
    background: #22C55E;
    color: #FFFFFF;
}
QPushButton[variant="danger"] {
    background: #EF4444;
    color: #FFFFFF;
}
QLineEdit, QTextEdit, QComboBox {
    background: #FFFFFF;
    border: 1px solid rgba(148, 163, 184, 0.30);
    border-radius: 12px;
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
    border-radius: 6px;
    border: 1px solid rgba(148, 163, 184, 0.40);
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #2563EB;
    border: 1px solid #2563EB;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid rgba(37, 99, 235, 0.55);
}
QTableWidget {
    background: transparent;
    border: none;
    gridline-color: rgba(226, 232, 240, 0.50);
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    alternate-background-color: #FAFCFF;
}
QTableWidget::item {
    padding: 13px 12px;
    border: none;
}
QTableWidget::item:selected,
QTableWidget::item:selected:active,
QTableWidget::item:selected:!active,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active {
    background: #2563EB;
    color: #FFFFFF;
}
QTableWidget::item:hover,
QTableView::item:hover {
    background: rgba(37, 99, 235, 0.08);
}
QHeaderView::section {
    background: #F8FAFC;
    color: #334155;
    border: none;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    padding: 16px 14px;
    font-weight: 700;
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
    background: #E2E8F0;
    color: #0F172A;
    border: none;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    padding: 12px 16px;
    margin-right: 6px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #FFFFFF;
    color: #0B1220;
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
    background: #F8FAFC;
    color: #334155;
    border-top: 1px solid rgba(148, 163, 184, 0.12);
}
"""


def apply_soft_shadow(widget, blur: int = 28, y_offset: int = 10, alpha: int = 18) -> None:
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
    apply_soft_shadow(frame, blur=22, y_offset=8, alpha=14)


def style_filter_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "FilterBar")
    apply_soft_shadow(frame, blur=18, y_offset=6, alpha=12)


def style_top_bar(frame: QWidget) -> None:
    _prepare_styled_widget(frame, "TopBar")
    apply_soft_shadow(frame, blur=20, y_offset=8, alpha=14)


def configure_dialog_window(
    dialog: QDialog,
    *,
    width: int,
    height: int,
    min_width: int = 760,
    min_height: int = 560,
) -> None:
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
    animation.setDuration(220)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()
    dialog._dialog_intro_animation = animation


def configure_table(table: QTableWidget, stretch_last: bool = True) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setFrameShape(QFrame.NoFrame)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(50)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.horizontalHeader().setMinimumSectionSize(110)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setFocusPolicy(Qt.NoFocus)

    header = table.horizontalHeader()
    if not stretch_last:
        header.setSectionResizeMode(QHeaderView.Stretch)
    else:
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
