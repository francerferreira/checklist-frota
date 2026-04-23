from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton


class AnimatedButton(QPushButton):
    def __init__(self, text: str, parent=None, *, tone: str = "nav"):
        super().__init__(text, parent)
        self._elevation = 0.0
        self._active = False
        self._tone = tone
        self._hovered = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(30)

        self.animation = QPropertyAnimation(self, b"elevation", self)
        self.animation.setDuration(80)
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
        self._apply_style()

    elevation = Property(float, get_elevation, set_elevation)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._tone == "danger":
            background = "#8A5B5B" if not self._hovered else "#7A4F4F"
            border = "#724B4B"
            color = "#FFFFFF"
            bottom_border = "1px solid #6A4343"
            padding_left = 10
        else:
            if self._active:
                background = "#D8E6F7"
                border = "#7EA2C6"
                color = "#15416D"
                bottom_border = "1px solid #6D93B8"
            else:
                background = "#EDF4FD" if not self._hovered else "#E3EEFB"
                border = "#A2BCD8"
                color = "#1F4F80"
                bottom_border = "1px solid #97B3D0"
            padding_left = 10
        font_size = 11 if self.property("moduleNav") == "true" else 12
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
                font-size: {font_size}px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {background};
                color: {color};
            }}
            """
        )
