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
        self.setMinimumHeight(52)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(18)
        self.shadow.setOffset(0, 6)
        self.shadow.setColor(QColor(0, 0, 0, 35))
        self.setGraphicsEffect(self.shadow)

        self.animation = QPropertyAnimation(self, b"elevation", self)
        self.animation.setDuration(180)
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
        self.shadow.setBlurRadius(18 + (14 * value))
        self.shadow.setOffset(0, 6 + (2 * value))
        self._apply_style()

    elevation = Property(float, get_elevation, set_elevation)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._tone == "danger":
            background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #EF4444, stop:0.55 #F14F56, stop:1 #DC2626)"
            )
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #DC2626, stop:0.60 #E53E3E, stop:1 #B91C1C)"
            )
            border = "rgba(185, 28, 28, 0.26)"
            color = "#FFFFFF"
            bottom_border = "4px solid #B91C1C"
            shadow_color = QColor(239, 68, 68, 68 if self._hovered else 42)
            padding_left = 22 + int(self._elevation * 5)
        else:
            if self._active:
                background = (
                    "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                    "stop:0 #F8FBFF, stop:1 #E8F1FF)"
                )
                border = "#2563EB"
                color = "#1D4ED8"
                bottom_border = "4px solid #2563EB"
                shadow_color = QColor(37, 99, 235, 48)
            else:
                background = "rgba(255, 255, 255, 0.92)"
                border = "rgba(37, 99, 235, 0.18)"
                color = "#1D4ED8"
                bottom_border = "4px solid transparent"
                shadow_color = QColor(37, 99, 235, 28)
            padding_left = 20 + int(self._elevation * 4)
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #F1F7FF, stop:1 #DBEAFE)"
            )

        self.shadow.setColor(shadow_color)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                color: {color};
                border-radius: 18px;
                border: 1px solid {border};
                border-bottom: {bottom_border};
                padding: 12px 22px 10px {padding_left}px;
                text-align: center;
                font-size: 14px;
                font-weight: 750;
            }}
            QPushButton:hover {{
                background: {hover_background};
                color: {color};
            }}
            """
        )
