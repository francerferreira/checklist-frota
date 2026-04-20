from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QEvent, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QVBoxLayout, QWidget


class TableSkeletonOverlay(QWidget):
    def __init__(self, parent: QWidget, rows: int = 6):
        super().__init__(parent)
        self._rows = rows
        self._progress = 0.0
        self._animation = None

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            QWidget#TableSkeletonOverlay {
                background: rgba(248, 250, 252, 0.92);
                border-radius: 22px;
            }
            QLabel#SkeletonCaption {
                color: #64748B;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
            """
        )
        self.setObjectName("TableSkeletonOverlay")

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)
        layout.addStretch(1)
        self.caption = QLabel("Carregando dados da tabela")
        self.caption.setObjectName("SkeletonCaption")
        layout.addWidget(self.caption, 0, Qt.AlignRight | Qt.AlignBottom)

        parent.installEventFilter(self)
        self.hide()
        self._sync_geometry()

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() in {QEvent.Resize, QEvent.Move, QEvent.Show}:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def _sync_geometry(self):
        parent = self.parentWidget()
        if parent:
            self.setGeometry(parent.rect())

    def show_skeleton(self, message: str = "Carregando dados da tabela"):
        self.caption.setText(message)
        self._sync_geometry()
        self.raise_()
        self.show()
        self._fade_to(1.0)
        self._start_animation()

    def hide_skeleton(self):
        if not self.isVisible():
            return
        if self._animation:
            self._animation.stop()
        self._fade_to(0.0, on_finished=self.hide)

    def _fade_to(self, target: float, duration: int = 180, on_finished=None):
        animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(self.opacity_effect.opacity())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        if on_finished:
            animation.finished.connect(on_finished)
        animation.start()

    def _start_animation(self):
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.setDuration(1400)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.InOutSine)
        self._animation.start()

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float):
        self._progress = value
        self.update()

    progress = Property(float, get_progress, set_progress)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        base = QColor("#EAF0F8")
        shimmer = QColor("#DBEAFE")

        left = 22
        top = 22
        width = max(280, self.width() - 44)
        header_height = 18
        row_height = 20
        row_gap = 18

        header_rect = (left, top, width, header_height)
        self._draw_bar(painter, *header_rect, radius=8, base=base, shimmer=shimmer)

        top += 42
        for row in range(self._rows):
            factor = 1.0 - (0.08 * (row % 3))
            bar_width = int(width * factor)
            self._draw_bar(painter, left, top, bar_width, row_height, radius=8, base=base, shimmer=shimmer)
            top += row_height + row_gap

    def _draw_bar(self, painter, x, y, width, height, *, radius: int, base: QColor, shimmer: QColor):
        painter.setPen(Qt.NoPen)
        painter.setBrush(base)
        painter.drawRoundedRect(x, y, width, height, radius, radius)

        glow_width = max(84, int(width * 0.22))
        shimmer_x = x - glow_width + int((width + glow_width * 2) * self._progress)
        painter.setBrush(shimmer)
        painter.setOpacity(0.42)
        painter.drawRoundedRect(shimmer_x, y, glow_width, height, radius, radius)
        painter.setOpacity(1.0)
