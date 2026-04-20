from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from components.icon_factory import make_icon


class LoadingOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.hide()

        self._base_message = "Carregando painel"
        self._visible_since = None
        self._fade_animation = None

        self._timer = QTimer(self)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._advance_dots)
        self._dot_index = 0

        self.setStyleSheet(
            """
            QWidget#LoadingOverlay {
                background: rgba(5, 16, 31, 0.16);
            }
            QFrame#LoadingCard {
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(37, 99, 235, 0.16);
                border-radius: 24px;
            }
            QFrame#LoadingOrb {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1D4ED8, stop:1 #2563EB);
                border-radius: 22px;
                border: 1px solid rgba(255, 255, 255, 0.24);
            }
            QLabel#LoadingTitle {
                color: #0B1220;
                font-size: 19px;
                font-weight: 780;
            }
            QLabel#LoadingSubtitle {
                color: #64748B;
                font-size: 13px;
            }
            QLabel#LoadingPulse {
                color: #2563EB;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 0.22em;
            }
            """
        )
        self.setObjectName("LoadingOverlay")

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        root.addStretch(1)

        center = QHBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)
        center.addStretch(1)

        self.card = QFrame()
        self.card.setObjectName("LoadingCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(15, 23, 42, 30))
        self.card.setGraphicsEffect(shadow)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(16)

        orb = QFrame()
        orb.setObjectName("LoadingOrb")
        orb.setFixedSize(44, 44)
        orb_layout = QVBoxLayout(orb)
        orb_layout.setContentsMargins(8, 8, 8, 8)
        orb_icon = QLabel()
        orb_icon.setPixmap(make_icon("dashboard", "#FFFFFF", "#1D4ED8", 22).pixmap(22, 22))
        orb_icon.setAlignment(Qt.AlignCenter)
        orb_layout.addWidget(orb_icon)

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)

        self.title_label = QLabel("Carregando painel")
        self.title_label.setObjectName("LoadingTitle")

        self.subtitle_label = QLabel("Aguarde um instante enquanto os dados são preparados.")
        self.subtitle_label.setObjectName("LoadingSubtitle")

        self.pulse_label = QLabel("•")
        self.pulse_label.setObjectName("LoadingPulse")

        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.subtitle_label)
        text_wrap.addWidget(self.pulse_label, 0, Qt.AlignLeft)

        card_layout.addWidget(orb, 0, Qt.AlignVCenter)
        card_layout.addLayout(text_wrap, 1)

        center.addWidget(self.card, 0)
        center.addStretch(1)

        root.addLayout(center)
        root.addStretch(1)

        parent.installEventFilter(self)
        self._sync_geometry()

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() in {QEvent.Resize, QEvent.Move, QEvent.Show}:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def _sync_geometry(self):
        parent = self.parentWidget()
        if parent:
            self.setGeometry(parent.rect())

    def show_loading(self, title: str, subtitle: str | None = None):
        self._base_message = title
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle or "Aguarde um instante enquanto os dados são preparados.")
        self._dot_index = 0
        self._advance_dots()
        self._timer.start()
        self._sync_geometry()
        self.raise_()
        self.show()

        self._fade_to(1.0, 180)

    def hide_loading(self):
        if not self.isVisible():
            return
        self._timer.stop()
        self._fade_to(0.0, 180, on_finished=self.hide)

    def _advance_dots(self):
        dots = "." * ((self._dot_index % 3) + 1)
        self.pulse_label.setText(f"• {dots}")
        self._dot_index += 1

    def _fade_to(self, target: float, duration: int, on_finished=None):
        animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(self.opacity_effect.opacity())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        if on_finished:
            animation.finished.connect(on_finished)
        animation.start()
        self._fade_animation = animation
