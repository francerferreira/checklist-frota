from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton


class AnimatedButton(QPushButton):
    def __init__(self, text: str, parent=None, *, tone: str = "nav"):
        super().__init__(text, parent)
        self._elevation = 0.0
        self._active = False
        self._tone = tone
        self._hovered = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(46)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(8)
        self.shadow.setOffset(0, 2)
        self.shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(self.shadow)

        self.animation = QPropertyAnimation(self, b"elevation", self)
        self.animation.setDuration(120)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.pressed.connect(self._handle_pressed)
        self.released.connect(self._handle_released)
        self._apply_style()

    def enterEvent(self, event):
        self._hovered = True
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._animate_to(0.0)
        super().leaveEvent(event)

    def _handle_pressed(self):
        self._animate_to(0.32 if self._tone == "danger" else 0.46)

    def _handle_released(self):
        self._animate_to(1.0 if self._hovered else 0.0)

    def _animate_to(self, value: float):
        self.animation.stop()
        self.animation.setStartValue(self._elevation)
        self.animation.setEndValue(value)
        self.animation.start()

    def get_elevation(self) -> float:
        return self._elevation

    def set_elevation(self, value: float):
        self._elevation = value
        self.shadow.setBlurRadius(8 + (6 * value))
        self.shadow.setOffset(0, 2 + (1.2 * value))
        self._apply_style()

    elevation = Property(float, get_elevation, set_elevation)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._tone == "danger":
            background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #C94C4C, stop:0.55 #D15757, stop:1 #B64040)"
            )
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #B64040, stop:0.60 #BE4949, stop:1 #9F3535)"
            )
            border = "rgba(159, 53, 53, 0.30)"
            color = "#FFFFFF"
            bottom_border = "2px solid #973030"
            shadow_color = QColor(201, 76, 76, 44 if self._hovered else 28)
            padding_left = 14 + int(self._elevation * 2)
        else:
            if self._active:
                background = (
                    "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                    "stop:0 #EFF7FD, stop:1 #DCECF9)"
                )
                border = "#0F5E84"
                color = "#0F5E84"
                bottom_border = "2px solid #0F5E84"
                shadow_color = QColor(15, 94, 132, 30)
            else:
                background = "rgba(255, 255, 255, 0.94)"
                border = "rgba(15, 94, 132, 0.18)"
                color = "#0F4E70"
                bottom_border = "2px solid transparent"
                shadow_color = QColor(15, 94, 132, 18)
            padding_left = 13 + int(self._elevation * 2)
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #F1F8FD, stop:1 #E1EFF9)"
            )

        self.shadow.setColor(shadow_color)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                color: {color};
                border-radius: 7px;
                border: 1px solid {border};
                border-bottom: {bottom_border};
                padding: 8px 10px 7px {padding_left}px;
                text-align: left;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {hover_background};
                color: {color};
            }}
            """
        )
