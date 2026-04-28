from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from components.icon_factory import make_icon
from theme import style_card


class ConfirmationDialog(QDialog):
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        *,
        confirm_text: str = "Yes",
        cancel_text: str = "Não",
        icon_name: str = "warning",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(620, 300)
        self.setMinimumSize(520, 250)
        self.setMaximumSize(820, 420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, False)
        self.setStyleSheet(
            """
            QDialog {
                background: #FFFFFF;
            }
            QFrame#ConfirmationCard {
                background: #FFFFFF;
                border: 1px solid #B7CBE3;
                border-radius: 2px;
            }
            QPushButton#ConfirmButton {
                background-color: #2F6FB2;
                color: #FFFFFF;
                border: 1px solid #245F97;
                border-radius: 2px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#ConfirmButton:hover {
                background-color: #285F98;
            }
            QPushButton#CancelButton {
                background-color: #EAF3FF;
                color: #113A67;
                border: 1px solid #86AEDA;
                border-radius: 2px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#CancelButton:hover {
                background-color: #D9EAFF;
            }
            """
        )
        style_card(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("ConfirmationCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon_name, "#DDEBFA", "#1E5E98", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("DialogHeaderTitle")
        subtitle_label = QLabel("Confirme esta ação para continuar.")
        subtitle_label.setObjectName("DialogHeaderSubtitle")
        subtitle_label.setWordWrap(True)
        title_wrap.addWidget(title_label)
        title_wrap.addWidget(subtitle_label)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        body = QFrame()
        body.setObjectName("DialogInfoBlock")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(8)

        body_label = QLabel(message)
        body_label.setObjectName("DialogBodyText")
        body_label.setWordWrap(True)
        body_layout.addWidget(body_label)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        cancel_button = QPushButton(cancel_text)
        cancel_button.setObjectName("CancelButton")
        cancel_button.setMinimumHeight(40)
        cancel_button.setMinimumWidth(132)
        cancel_button.clicked.connect(self.reject)

        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName("ConfirmButton")
        confirm_button.setMinimumHeight(40)
        confirm_button.setMinimumWidth(132)
        confirm_button.clicked.connect(self.accept)

        footer_layout.addWidget(cancel_button)
        footer_layout.addWidget(confirm_button)

        card_layout.addWidget(header)
        card_layout.addWidget(body)
        card_layout.addWidget(footer)

        root.addStretch(1)
        root.addWidget(card)
        root.addStretch(1)


class NoticeDialog(QDialog):
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        *,
        button_text: str = "OK",
        icon_name: str = "dashboard",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 270)
        self.setMinimumSize(500, 230)
        self.setMaximumSize(800, 390)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, False)
        is_warning = icon_name in {"warning", "cancel"}
        icon_bg = "#FBE7E7" if is_warning else "#DDEBFA"
        icon_fg = "#B14B4B" if is_warning else "#1E5E98"
        subtitle_text = "Atenção: revise a mensagem abaixo." if is_warning else "Operação concluída."
        body_text_color = "#8E2F2F" if is_warning else "#123A64"
        button_bg = "#B14B4B" if is_warning else "#2F6FB2"
        button_hover = "#973E3E" if is_warning else "#285F98"
        button_border = "#973E3E" if is_warning else "#245F97"
        self.setStyleSheet(
            f"""
            QDialog {{
                background: #FFFFFF;
            }}
            QFrame#NoticeCard {{
                background: #FFFFFF;
                border: 1px solid #B7CBE3;
                border-radius: 2px;
            }}
            QPushButton#NoticeButton {{
                background-color: {button_bg};
                color: #FFFFFF;
                border: 1px solid {button_border};
                border-radius: 2px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#NoticeButton:hover {{
                background-color: {button_hover};
            }}
            QLabel#NoticeSubtitle {{
                color: #3E5C7D;
                font-size: 12px;
            }}
            QLabel#NoticeBody {{
                color: {body_text_color};
                font-size: 13px;
                font-weight: 760;
            }}
            """
        )
        style_card(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("NoticeCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("DialogHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(14)

        icon_badge = QFrame()
        icon_badge.setObjectName("DialogIconBadge")
        icon_badge.setAttribute(Qt.WA_StyledBackground, True)
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(10, 10, 10, 10)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon_name, icon_bg, icon_fg, 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("DialogHeaderTitle")
        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setObjectName("NoticeSubtitle")
        subtitle_label.setWordWrap(True)
        title_wrap.addWidget(title_label)
        title_wrap.addWidget(subtitle_label)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        body = QFrame()
        body.setObjectName("DialogInfoBlock")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(8)

        body_label = QLabel(message)
        body_label.setObjectName("NoticeBody")
        body_label.setWordWrap(True)
        body_layout.addWidget(body_label)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        ok_button = QPushButton(button_text)
        ok_button.setObjectName("NoticeButton")
        ok_button.setMinimumHeight(40)
        ok_button.setMinimumWidth(132)
        ok_button.clicked.connect(self.accept)
        footer_layout.addWidget(ok_button)

        card_layout.addWidget(header)
        card_layout.addWidget(body)
        card_layout.addWidget(footer)

        root.addStretch(1)
        root.addWidget(card)
        root.addStretch(1)


def ask_confirmation(
    parent,
    title: str,
    message: str,
    *,
    confirm_text: str = "Sim",
    cancel_text: str = "Não",
    icon_name: str = "warning",
) -> bool:
    dialog = ConfirmationDialog(
        parent,
        title,
        message,
        confirm_text=confirm_text,
        cancel_text=cancel_text,
        icon_name=icon_name,
    )
    return dialog.exec() == QDialog.Accepted


def show_notice(
    parent,
    title: str,
    message: str,
    *,
    button_text: str = "OK",
    icon_name: str = "dashboard",
) -> None:
    dialog = NoticeDialog(parent, title, message, button_text=button_text, icon_name=icon_name)
    dialog.exec()
