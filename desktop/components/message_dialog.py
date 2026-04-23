from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QDialog,
)

from components.icon_factory import make_icon
from services.message_service import MessagePackage
from theme import build_dialog_layout, configure_dialog_window, style_card


class MessageComposerDialog(QDialog):
    def __init__(self, message: MessagePackage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setWindowTitle("Gerar mensagem")
        configure_dialog_window(self, width=1120, height=840, min_width=920, min_height=720)
        style_card(self)

        layout = build_dialog_layout(self, max_content_width=1160)

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
        icon_label.setPixmap(make_icon("reports", "#E7EBF0", "#5B6571", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title = QLabel("Gerar mensagem")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel(self.message.title)
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        summary_card = QFrame()
        summary_card.setObjectName("HeaderCard")
        summary_card.setAttribute(Qt.WA_StyledBackground, True)
        summary_layout = QHBoxLayout(summary_card)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(10)
        for label, value in self.message.summary_items:
            pill = QLabel(f"{label}: {value}")
            pill.setObjectName("TopBarPill")
            summary_layout.addWidget(pill)
        summary_layout.addStretch()

        subject_card = QFrame()
        subject_card.setObjectName("DialogInfoBlock")
        subject_card.setAttribute(Qt.WA_StyledBackground, True)
        subject_layout = QVBoxLayout(subject_card)
        subject_layout.setContentsMargins(16, 16, 16, 16)
        subject_layout.setSpacing(10)

        subject_top = QHBoxLayout()
        subject_top.setSpacing(10)
        subject_label = QLabel("Assunto do e-mail")
        subject_label.setObjectName("SectionTitle")
        self.subject_field = QLineEdit(self.message.email_subject)
        self.subject_field.setReadOnly(True)
        self.subject_field.setCursorPosition(0)
        copy_subject = QPushButton("Copiar assunto")
        copy_subject.clicked.connect(lambda: self._copy(self.message.email_subject, "Assunto copiado"))
        subject_top.addWidget(subject_label, 1)
        subject_top.addWidget(copy_subject, 0, Qt.AlignRight)
        subject_layout.addLayout(subject_top)
        subject_layout.addWidget(self.subject_field)

        self.feedback = QLabel("")
        self.feedback.setObjectName("SectionCaption")

        whatsapp_card = QFrame()
        whatsapp_card.setObjectName("DialogInfoBlock")
        whatsapp_card.setAttribute(Qt.WA_StyledBackground, True)
        whatsapp_layout = QVBoxLayout(whatsapp_card)
        whatsapp_layout.setContentsMargins(16, 16, 16, 16)
        whatsapp_layout.setSpacing(10)
        whatsapp_top = QHBoxLayout()
        whatsapp_label = QLabel("Mensagem para WhatsApp")
        whatsapp_label.setObjectName("SectionTitle")
        copy_whatsapp = QPushButton("Copiar WhatsApp")
        copy_whatsapp.clicked.connect(lambda: self._copy(self.message.whatsapp_text, "Mensagem do WhatsApp copiada"))
        whatsapp_top.addWidget(whatsapp_label, 1)
        whatsapp_top.addWidget(copy_whatsapp, 0, Qt.AlignRight)
        whatsapp_layout.addLayout(whatsapp_top)
        self.whatsapp_text = QTextEdit()
        self.whatsapp_text.setReadOnly(True)
        self.whatsapp_text.setPlainText(self.message.whatsapp_text)
        self.whatsapp_text.setMinimumHeight(240)
        whatsapp_layout.addWidget(self.whatsapp_text)
        whatsapp_tip = QLabel("Use * para negrito e _ para destaque em WhatsApp.")
        whatsapp_tip.setObjectName("SectionCaption")
        whatsapp_layout.addWidget(whatsapp_tip)

        email_card = QFrame()
        email_card.setObjectName("DialogInfoBlock")
        email_card.setAttribute(Qt.WA_StyledBackground, True)
        email_layout = QVBoxLayout(email_card)
        email_layout.setContentsMargins(16, 16, 16, 16)
        email_layout.setSpacing(10)
        email_top = QHBoxLayout()
        email_label = QLabel("Corpo do e-mail")
        email_label.setObjectName("SectionTitle")
        copy_email = QPushButton("Copiar e-mail")
        copy_email.clicked.connect(lambda: self._copy(self.message.email_body, "Corpo do e-mail copiado"))
        email_top.addWidget(email_label, 1)
        email_top.addWidget(copy_email, 0, Qt.AlignRight)
        email_layout.addLayout(email_top)
        self.email_text = QTextEdit()
        self.email_text.setReadOnly(True)
        self.email_text.setPlainText(self.message.email_body)
        self.email_text.setMinimumHeight(240)
        email_layout.addWidget(self.email_text)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addWidget(self.feedback, 1)
        copy_all = QPushButton("Copiar tudo")
        copy_all.setProperty("variant", "primary")
        copy_all.clicked.connect(self.copy_all)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(copy_all)
        footer_layout.addWidget(close_button)

        layout.addWidget(header)
        layout.addWidget(summary_card)
        layout.addWidget(subject_card)
        layout.addWidget(whatsapp_card, 1)
        layout.addWidget(email_card, 1)
        layout.addWidget(footer)

    def _copy(self, text: str, feedback: str):
        QApplication.clipboard().setText(text)
        self.feedback.setText(feedback)
        QTimer.singleShot(2200, lambda: self.feedback.setText(""))

    def copy_all(self):
        combined = (
            f"Assunto: {self.message.email_subject}\n\n"
            f"WhatsApp:\n{self.message.whatsapp_text}\n\n"
            f"E-mail:\n{self.message.email_body}"
        )
        self._copy(combined, "Texto completo copiado")

