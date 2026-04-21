from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from api_client import APIClient, DEFAULT_API_BASE_URL
from components import show_notice
from runtime_paths import asset_path, data_path
from theme import apply_soft_shadow


LOGIN_STYLE = """
QDialog {
    background: #07111F;
}
QFrame#LoginShell {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #08162D, stop:0.55 #0C1E3D, stop:1 #112B54);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 30px;
}
QFrame#LoginHero {
    background: qlineargradient(x1:0, y1:0, x2:0.9, y2:1, stop:0 #132C57, stop:1 #0B1C36);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 26px;
}
QFrame#LoginCard {
    background: #FFFFFF;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 26px;
}
QFrame#StatusCard {
    background: rgba(37, 99, 235, 0.08);
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-radius: 18px;
}
QFrame#AdvancedCard {
    background: #F8FAFC;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 18px;
}
QFrame#FieldCard,
QFrame#LoginScrollContent {
    background: transparent;
    border: none;
}
QScrollArea#LoginScroll {
    background: transparent;
    border: none;
}
QScrollArea#LoginScroll > QWidget > QWidget {
    background: transparent;
}
QLabel {
    background: transparent;
}
QLabel#HeroEyebrow {
    color: rgba(255, 255, 255, 0.68);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.16em;
}
QLabel#HeroTitle {
    color: #FFFFFF;
    font-size: 31px;
    font-weight: 790;
}
QLabel#HeroSubtitle {
    color: rgba(255, 255, 255, 0.82);
    font-size: 14px;
    line-height: 1.55;
}
QLabel#HeroPoint {
    color: #DBEAFE;
    font-size: 13px;
    font-weight: 600;
}
QLabel#FormEyebrow {
    color: #2563EB;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
}
QLabel#FormTitle {
    color: #0B1220;
    font-size: 28px;
    font-weight: 800;
}
QLabel#FormSubtitle {
    color: #64748B;
    font-size: 13px;
    line-height: 1.45;
}
QLabel#StatusTitle {
    color: #0B1220;
    font-size: 14px;
    font-weight: 760;
}
QLabel#StatusHint {
    color: #64748B;
    font-size: 12px;
}
QLabel#FieldLabel {
    color: #0F172A;
    font-size: 13px;
    font-weight: 700;
}
QLabel#ServerBadge {
    border-radius: 14px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 800;
}
QLabel#MicroText {
    color: #64748B;
    font-size: 12px;
}
QLineEdit {
    background: #F8FAFC;
    color: #0F172A;
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 14px;
    padding: 12px 14px;
    min-height: 22px;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid rgba(37, 99, 235, 0.56);
    background: #FFFFFF;
}
QCheckBox {
    color: #475569;
    spacing: 8px;
    font-size: 12px;
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
QPushButton {
    border: none;
    border-radius: 14px;
    background: #E2E8F0;
    color: #0F172A;
    padding: 12px 18px;
    font-weight: 700;
}
QPushButton:hover {
    background: #DBEAFE;
}
QPushButton[variant="primary"] {
    background: #2563EB;
    color: #FFFFFF;
}
QPushButton[variant="primary"]:hover {
    background: #1D4ED8;
}
QPushButton[variant="ghost"] {
    background: #FFFFFF;
    color: #2563EB;
    border: 1px solid rgba(37, 99, 235, 0.22);
}
QPushButton[variant="ghost"]:hover {
    background: #EFF6FF;
}
"""


class LoginWindow(QDialog):
    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = None
        self.logo_path = asset_path("app-logo-cover.png")
        self.app_icon_path = asset_path("app-icon.ico")
        self.login_prefs_path = data_path("login_prefs.json")
        self._advanced_visible = False

        self.setWindowTitle("Acesso ao CF - Checklist de Frota")
        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))
        self.setModal(True)
        self.resize(1040, 720)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(LOGIN_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("LoginShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        apply_soft_shadow(shell, blur=34, y_offset=12, alpha=24)

        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(22, 22, 22, 22)
        shell_layout.setSpacing(22)

        shell_layout.addWidget(self._build_hero_panel(), 5)
        shell_layout.addWidget(self._build_form_panel(), 6)

        root.addWidget(shell)

    def _build_hero_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("LoginHero")
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        logo_label = QLabel()
        logo_label.setFixedSize(170, 108)
        logo_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        if self.logo_path.exists():
            pixmap = QPixmap(str(self.logo_path))
            logo_label.setPixmap(pixmap.scaled(160, 104, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        eyebrow = QLabel("PLATAFORMA CORPORATIVA")
        eyebrow.setObjectName("HeroEyebrow")

        title = QLabel("Checklist\nPortuário")
        title.setObjectName("HeroTitle")

        subtitle = QLabel(
            "Controle de manutenção, auditoria operacional, estoque e atividades em massa com visual executivo."
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)

        points = QVBoxLayout()
        points.setContentsMargins(0, 10, 0, 0)
        points.setSpacing(10)
        for text in (
            "Gestão integrada de equipamentos, materiais e evidências",
            "Acompanhamento de não conformidades e atividades por lote",
            "Relatórios executivos em PDF, Excel e CSV",
        ):
            point = QLabel(f"• {text}")
            point.setObjectName("HeroPoint")
            point.setWordWrap(True)
            points.addWidget(point)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        footer = QLabel("Porto Chibatão")
        footer.setObjectName("HeroSubtitle")

        layout.addWidget(logo_label, 0, Qt.AlignLeft)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(points)
        layout.addWidget(spacer, 1)
        layout.addWidget(footer)
        return panel

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("LoginCard")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(18)

        eyebrow = QLabel("ACESSO AO SISTEMA")
        eyebrow.setObjectName("FormEyebrow")

        title = QLabel("Entrar")
        title.setObjectName("FormTitle")

        subtitle = QLabel(
            "Use seu usuário para acessar o painel. A conexão avançada aparece só quando for realmente necessária."
        )
        subtitle.setObjectName("FormSubtitle")
        subtitle.setWordWrap(True)

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Digite seu login")
        self.login_input.setMinimumHeight(50)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Digite sua senha")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(50)
        self.password_input.returnPressed.connect(self.handle_login)

        self.show_password_check = QCheckBox("Mostrar senha")
        self.show_password_check.toggled.connect(self.toggle_password)
        self.remember_login_check = QCheckBox("Lembrar login")
        self.remember_login_check.setChecked(True)

        self.advanced_toggle = QPushButton("Conexão avançada")
        self.advanced_toggle.setProperty("variant", "ghost")
        self.advanced_toggle.setMinimumHeight(42)
        self.advanced_toggle.clicked.connect(self.toggle_advanced)

        self.base_url_input = QLineEdit(DEFAULT_API_BASE_URL)
        self.base_url_input.setPlaceholderText(DEFAULT_API_BASE_URL)
        self.base_url_input.setMinimumHeight(50)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("AdvancedCard")
        self.advanced_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.advanced_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(16, 16, 16, 16)
        advanced_layout.setSpacing(10)

        advanced_title = QLabel("Servidor da API")
        advanced_title.setObjectName("FieldLabel")

        advanced_hint = QLabel("Altere apenas se este desktop for apontar para outra máquina ou ambiente.")
        advanced_hint.setObjectName("MicroText")
        advanced_hint.setWordWrap(True)

        advanced_layout.addWidget(advanced_title)
        advanced_layout.addWidget(advanced_hint)
        advanced_layout.addWidget(self.base_url_input)
        self.advanced_panel.setVisible(False)
        self.advanced_panel.setMaximumHeight(0)

        scroll = QScrollArea()
        scroll.setObjectName("LoginScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        scroll_content = QWidget()
        scroll_content.setObjectName("LoginScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 6, 0)
        scroll_layout.setSpacing(16)

        scroll_layout.addWidget(self._build_field("Login", self.login_input))
        scroll_layout.addWidget(self._build_field("Senha", self.password_input))

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(12)
        options_row.addWidget(self.show_password_check, 0, Qt.AlignVCenter)
        options_row.addWidget(self.remember_login_check, 0, Qt.AlignVCenter)
        options_row.addStretch(1)
        options_row.addWidget(self.advanced_toggle, 0, Qt.AlignVCenter)

        scroll_layout.addLayout(options_row)
        scroll_layout.addWidget(self.advanced_panel)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(14)

        helper = QLabel("No uso normal, abra pelo iniciador e entre com seu usuário.")
        helper.setObjectName("MicroText")
        helper.setWordWrap(True)

        self.submit_button = QPushButton("Entrar no sistema")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.setMinimumHeight(56)
        self.submit_button.setMinimumWidth(240)
        self.submit_button.clicked.connect(self.handle_login)

        footer.addWidget(helper, 1)
        footer.addWidget(self.submit_button, 0)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(scroll, 1)
        layout.addLayout(footer)
        self._load_login_prefs()
        return panel

    def _build_field(self, label_text: str, widget: QWidget) -> QFrame:
        field = QFrame()
        field.setObjectName("FieldCard")
        field.setAttribute(Qt.WA_StyledBackground, True)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        label.setMinimumHeight(18)

        field_layout.addWidget(label)
        field_layout.addWidget(widget)
        return field

    def _load_login_prefs(self):
        try:
            if not self.login_prefs_path.exists():
                return
            payload = json.loads(self.login_prefs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        remember_login = bool(payload.get("remember_login", False))
        login_value = str(payload.get("login") or "").strip()
        self.remember_login_check.setChecked(remember_login)
        if remember_login and login_value:
            self.login_input.setText(login_value)
            self.login_input.setCursorPosition(len(login_value))
            self.password_input.setFocus()

    def _save_login_prefs(self):
        payload = {
            "remember_login": bool(self.remember_login_check.isChecked()),
            "login": self.login_input.text().strip() if self.remember_login_check.isChecked() else "",
        }
        try:
            self.login_prefs_path.parent.mkdir(parents=True, exist_ok=True)
            self.login_prefs_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def toggle_password(self, visible: bool):
        self.password_input.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)

    def toggle_advanced(self):
        self._advanced_visible = not self._advanced_visible
        self.advanced_panel.setVisible(self._advanced_visible)
        self.advanced_panel.setMaximumHeight(16777215 if self._advanced_visible else 0)
        self.advanced_toggle.setText("Ocultar conexão" if self._advanced_visible else "Conexão avançada")

    def handle_login(self):
        self.submit_button.setEnabled(False)
        try:
            self.api_client.set_base_url(self.base_url_input.text().strip())
            payload = self.api_client.login(
                self.login_input.text().strip(),
                self.password_input.text(),
            )
            self._save_login_prefs()
            self.user = payload["user"]
            self.accept()
        except Exception as exc:
            show_notice(self, "Falha no login", str(exc), icon_name="warning")
        finally:
            self.submit_button.setEnabled(True)
