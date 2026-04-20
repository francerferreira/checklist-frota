from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout

from components.icon_factory import make_icon


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str, icon_name: str = "dashboard", parent=None):
        super().__init__(parent)
        self._lift = 0.0
        self.setObjectName("PanelCard")
        self.setCursor(Qt.PointingHandCursor)
        self.icon_name = icon_name

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(24)
        self.shadow.setOffset(0, 8)
        self.shadow.setColor(QColor(15, 23, 42, 28))
        self.setGraphicsEffect(self.shadow)

        self.animation = QPropertyAnimation(self, b"lift", self)
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setPixmap(make_icon(self.icon_name, size=28).pixmap(28, 28))
        header_row.addWidget(self.title_label, 1)
        header_row.addWidget(self.icon_label, 0, Qt.AlignRight)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("CardSubtitle")
        self.subtitle_label.setWordWrap(True)

        layout.addLayout(header_row)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_content(self, title: str, value: str, subtitle: str):
        self.title_label.setText(title)
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)

    def enterEvent(self, event):
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        super().leaveEvent(event)

    def _animate_to(self, value: float):
        self.animation.stop()
        self.animation.setStartValue(self._lift)
        self.animation.setEndValue(value)
        self.animation.start()

    def get_lift(self) -> float:
        return self._lift

    def set_lift(self, value: float):
        self._lift = value
        self.shadow.setBlurRadius(24 + (12 * value))
        self.shadow.setOffset(0, 8 + (4 * value))

    lift = Property(float, get_lift, set_lift)
