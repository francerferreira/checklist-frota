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
        self.shadow.setBlurRadius(0)
        self.shadow.setOffset(0, 0)
        self.shadow.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(self.shadow)

        self.animation = QPropertyAnimation(self, b"elevation", self)
        self.animation.setDuration(90)
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
        self.shadow.setBlurRadius(0)
        self.shadow.setOffset(0, 0)
        self._apply_style()

    elevation = Property(float, get_elevation, set_elevation)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._tone == "danger":
            background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #866565, stop:0.55 #8C6A6A, stop:1 #785A5A)"
            )
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                "stop:0 #785A5A, stop:0.60 #805F5F, stop:1 #6E5353)"
            )
            border = "rgba(113, 84, 84, 0.40)"
            color = "#FFFFFF"
            bottom_border = "1px solid #694F4F"
            shadow_color = QColor(0, 0, 0, 0)
            padding_left = 10
        else:
            if self._active:
                background = (
                    "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                    "stop:0 #E7EAEE, stop:1 #DCE1E7)"
                )
                border = "#8F98A2"
                color = "#2E3F52"
                bottom_border = "1px solid #87919B"
                shadow_color = QColor(0, 0, 0, 0)
            else:
                background = "#ECEFF2"
                border = "rgba(143, 152, 162, 0.85)"
                color = "#33475C"
                bottom_border = "1px solid #A1A9B2"
                shadow_color = QColor(0, 0, 0, 0)
            padding_left = 10
            hover_background = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #E8EBEF, stop:1 #DEE3E9)"
            )

        self.shadow.setColor(shadow_color)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                color: {color};
                border-radius: 2px;
                border: 1px solid {border};
                border-bottom: {bottom_border};
                padding: 6px 8px 6px {padding_left}px;
                text-align: left;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {hover_background};
                color: {color};
            }}
            """
        )
