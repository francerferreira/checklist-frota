from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from components import AnimatedButton, LoadingOverlay, make_icon, show_notice
from runtime_paths import asset_path
from theme import APP_STYLE, style_top_bar
from ui.activities_page import ActivitiesPage
from ui.checklist_items_page import ChecklistItemsPage
from ui.cloud_backup_page import CloudBackupPage
from ui.dashboard_page import DashboardPage
from ui.equipment_page import EquipmentPage
from ui.materials_page import MaterialsPage
from ui.maintenance_page import MaintenancePage
from ui.non_conformities_page import NonConformitiesPage
from ui.productivity_page import ProductivityPage
from ui.reports_page import ReportsPage
from ui.users_page import UsersPage
from ui.washes_page import WashesPage


class AccessDialog(QDialog):
    def __init__(self, api_client, user: dict, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = user
        self.setWindowTitle("Meu acesso")
        self.setMinimumSize(560, 430)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

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
        icon_label.setPixmap(make_icon("users", "#FFFFFF", "#1D4ED8", 28).pixmap(28, 28))
        icon_layout.addWidget(icon_label)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Meu acesso")
        title.setObjectName("DialogHeaderTitle")
        subtitle = QLabel("Consulte sua sessão atual e altere sua própria senha.")
        subtitle.setObjectName("DialogHeaderSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header_layout.addWidget(icon_badge, 0, Qt.AlignTop)
        header_layout.addLayout(title_wrap, 1)

        info_card = QFrame()
        info_card.setObjectName("HeaderCard")
        info_card.setAttribute(Qt.WA_StyledBackground, True)
        info_layout = QGridLayout(info_card)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setHorizontalSpacing(16)
        info_layout.setVerticalSpacing(10)

        started = self.api_client.login_started_at
        started_text = started.strftime("%d/%m/%Y %H:%M:%S") if started else "-"
        info_rows = [
            ("Nome", user.get("nome") or "-"),
            ("Login", user.get("login") or "-"),
            ("Perfil", user.get("tipo") or "-"),
            ("Logado desde", started_text),
            ("Tempo de sessão", self._session_duration(started)),
        ]
        for row, (label_text, value_text) in enumerate(info_rows):
            label = QLabel(label_text)
            label.setObjectName("SectionCaption")
            value = QLabel(value_text)
            value.setObjectName("DialogInfoValue")
            value.setWordWrap(True)
            info_layout.addWidget(label, row, 0)
            info_layout.addWidget(value, row, 1)

        password_card = QFrame()
        password_card.setObjectName("DialogInfoBlock")
        password_card.setAttribute(Qt.WA_StyledBackground, True)
        password_layout = QGridLayout(password_card)
        password_layout.setContentsMargins(16, 16, 16, 16)
        password_layout.setHorizontalSpacing(12)
        password_layout.setVerticalSpacing(10)

        password_title = QLabel("Alterar minha senha")
        password_title.setObjectName("SectionTitle")
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.Password)
        self.current_password.setPlaceholderText("Senha atual")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_password.setPlaceholderText("Nova senha")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("Confirmar nova senha")

        password_layout.addWidget(password_title, 0, 0, 1, 2)
        password_layout.addWidget(QLabel("Senha atual"), 1, 0)
        password_layout.addWidget(self.current_password, 1, 1)
        password_layout.addWidget(QLabel("Nova senha"), 2, 0)
        password_layout.addWidget(self.new_password, 2, 1)
        password_layout.addWidget(QLabel("Confirmar senha"), 3, 0)
        password_layout.addWidget(self.confirm_password, 3, 1)

        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 14, 16, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        save_button = QPushButton("Salvar nova senha")
        save_button.setProperty("variant", "primary")
        save_button.clicked.connect(self.change_password)
        footer_layout.addWidget(close_button)
        footer_layout.addWidget(save_button)

        layout.addWidget(header)
        layout.addWidget(info_card)
        layout.addWidget(password_card)
        layout.addWidget(footer)

    def change_password(self):
        current = self.current_password.text()
        new = self.new_password.text()
        confirmation = self.confirm_password.text()
        if not current or not new:
            show_notice(self, "Campos obrigatórios", "Informe a senha atual e a nova senha.", icon_name="warning")
            return
        if new != confirmation:
            show_notice(self, "Confirmação inválida", "A confirmação precisa ser igual à nova senha.", icon_name="warning")
            return
        if len(new) < 6:
            show_notice(self, "Senha curta", "A nova senha deve ter pelo menos 6 caracteres.", icon_name="warning")
            return
        try:
            self.api_client.update_own_password(current, new)
            self.current_password.clear()
            self.new_password.clear()
            self.confirm_password.clear()
            show_notice(self, "Senha alterada", "Sua senha foi atualizada com sucesso.", icon_name="dashboard")
        except Exception as exc:
            show_notice(self, "Falha ao alterar senha", str(exc), icon_name="warning")

    @staticmethod
    def _session_duration(started: datetime | None) -> str:
        if not started:
            return "-"
        elapsed = datetime.now() - started
        total_seconds = max(0, int(elapsed.total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}min"
        if minutes:
            return f"{minutes}min {seconds}s"
        return f"{seconds}s"


class MainWindow(QMainWindow):
    def __init__(self, api_client, user, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = user
        self.page_animation = None
        self.is_admin = self.user["tipo"] == "admin"
        self.can_manage = self.user["tipo"] in {"admin", "gestor"}
        self.logo_path = asset_path("app-logo-cover.png")
        self.app_icon_path = asset_path("app-icon.ico")
        self.current_page_key = ""
        self.top_bar_collapsed = False
        self.dirty_pages: set[str] = set()
        self.pending_refreshes: set[str] = set()

        self.setWindowTitle("CF - Checklist de Frota")
        self.setMinimumSize(1280, 760)
        self.setStyleSheet(APP_STYLE)
        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))

        container = QWidget()
        container.setObjectName("MainContainer")

        root = QVBoxLayout(container)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        self.content = self._build_content()
        root.addWidget(self.content, 1)

        self.setCentralWidget(container)
        self.statusBar().hide()
        self.showMaximized()
        self.switch_page("dashboard")

    def _build_top_bar(self):
        top_bar = QFrame()
        style_top_bar(top_bar)

        self.top_bar_layout = QVBoxLayout(top_bar)
        self.top_bar_layout.setContentsMargins(20, 12, 20, 12)
        self.top_bar_layout.setSpacing(10)

        self.header_content = QFrame()
        self.header_content.setFrameShape(QFrame.NoFrame)
        header_row = QHBoxLayout()
        self.header_content.setLayout(header_row)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(16)

        logo_label = QLabel()
        logo_label.setFixedSize(132, 76)
        logo_label.setAlignment(Qt.AlignCenter)
        if self.logo_path.exists():
            pixmap = QPixmap(str(self.logo_path))
            logo_label.setPixmap(
                pixmap.scaled(
                    logo_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(6)

        self.top_bar_pill = QLabel("PAINEL OPERACIONAL")
        self.top_bar_pill.setObjectName("TopBarPill")

        title = QLabel("Sistema de Checklist de Frota")
        title.setObjectName("TopBarTitle")

        subtitle = QLabel("Gestão de Frota")
        subtitle.setObjectName("TopBarSubtitle")

        text_wrap.addWidget(self.top_bar_pill, 0, Qt.AlignLeft)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        badge = QFrame()
        badge.setObjectName("TopBarBadge")
        badge.setMinimumWidth(148)
        badge.setCursor(Qt.PointingHandCursor)
        badge.mousePressEvent = lambda event: self.open_access_dialog()
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(16, 12, 16, 12)
        badge_layout.setSpacing(2)

        badge_title = QLabel(self.user["nome"])
        badge_title.setStyleSheet(
            "font-size:13px; font-weight:700; color:#0B1220; background: transparent;"
        )
        badge_subtitle = QLabel(f"Acesso {self.user['tipo']}")
        badge_subtitle.setObjectName("MutedText")
        badge_layout.addWidget(badge_title)
        badge_layout.addWidget(badge_subtitle)

        logout_button = AnimatedButton("Encerrar sessão", tone="danger")
        logout_button.setMinimumWidth(206)
        logout_button.setMinimumHeight(54)
        logout_button.setIcon(make_icon("logout", "#26FFFFFF", "#FFFFFF"))
        logout_button.clicked.connect(self.close)

        collapse_button = QPushButton("Recolher topo")
        collapse_button.setMinimumHeight(54)
        collapse_button.setMinimumWidth(158)
        collapse_button.setIcon(make_icon("cancel", "#EFF6FF", "#1D4ED8"))
        collapse_button.clicked.connect(self.toggle_top_bar)

        header_row.addWidget(logo_label, 0)
        header_row.addLayout(text_wrap, 1)

        header_actions_card = QFrame()
        header_actions_card.setObjectName("TopBarActionCluster")
        header_actions = QHBoxLayout()
        header_actions.setContentsMargins(14, 12, 14, 12)
        header_actions.setSpacing(12)
        header_actions.addWidget(badge, 0)
        header_actions.addWidget(collapse_button, 0)
        header_actions.addWidget(logout_button, 0)
        header_actions_card.setLayout(header_actions)
        header_row.addWidget(header_actions_card, 0)

        nav_strip = QFrame()
        nav_strip.setObjectName("TopNavStrip")
        nav_strip.setMinimumHeight(118)
        nav_strip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout = QGridLayout(nav_strip)
        nav_layout.setContentsMargins(8, 6, 8, 6)
        nav_layout.setSpacing(8)

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "Dashboard", make_icon("dashboard")),
            ("nc", "Ocorrências", make_icon("warning", "#FEE2E2", "#B91C1C")),
            ("productivity", "Produtividade", make_icon("productivity", "#DCFCE7", "#166534")),
        ]
        if self.can_manage:
            nav_items.append(("equipment", "Frota", make_icon("equipment", "#E0F2FE", "#0369A1")))
            nav_items.append(("checklist_items", "Checklist", make_icon("checklist", "#EDE9FE", "#6D28D9")))
            nav_items.append(("materials", "Materiais", make_icon("materials", "#DBEAFE", "#1D4ED8")))
            nav_items.append(("washes", "Lavagens", make_icon("washes", "#CCFBF1", "#0F766E")))
            nav_items.append(("activities", "Atividades", make_icon("activities", "#FEF3C7", "#B45309")))
            nav_items.append(("maintenance", "Manutenção", make_icon("activities", "#DBEAFE", "#1D4ED8")))
        nav_items.append(("reports", "Relatórios", make_icon("reports", "#E0E7FF", "#4338CA")))
        if self.is_admin:
            nav_items.append(("users", "Logins", make_icon("users", "#EEF2FF", "#4338CA")))
            nav_items.append(("cloud_backup", "Backup", make_icon("cloud", "#DBEAFE", "#1D4ED8")))

        max_columns = 6
        for index, (key, label, icon) in enumerate(nav_items):
            button = AnimatedButton(label)
            button.setIcon(icon)
            button.setMinimumWidth(154)
            button.setMaximumWidth(196)
            button.setMinimumHeight(50)
            button.clicked.connect(lambda checked=False, page_key=key: self.switch_page(page_key))
            row = index // max_columns
            column = index % max_columns
            nav_layout.addWidget(button, row, column)
            self.nav_buttons[key] = button
        for column in range(max_columns):
            nav_layout.setColumnStretch(column, 1)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_scroll.setFrameShape(QFrame.NoFrame)
        self.nav_scroll.setMinimumHeight(124)
        self.nav_scroll.setMaximumHeight(124)
        self.nav_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.nav_scroll.setWidget(nav_strip)

        self.compact_top_bar = self._build_compact_top_bar()
        self.compact_top_bar.hide()

        self.top_bar_layout.addWidget(self.header_content)
        self.top_bar_layout.addWidget(self.nav_scroll)
        self.top_bar_layout.addWidget(self.compact_top_bar)
        return top_bar

    def _build_compact_top_bar(self):
        compact = QFrame()
        compact.setObjectName("TopBarActionCluster")
        compact.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(compact)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self.compact_context_label = QLabel("PAINEL OPERACIONAL")
        self.compact_context_label.setObjectName("TopBarPill")

        self.compact_title_label = QLabel("Sistema de Checklist de Frota")
        self.compact_title_label.setStyleSheet("font-size:16px; font-weight:760; color:#0B1220;")

        user_label = QPushButton(f"{self.user['nome']} • {self.user['tipo']}")
        user_label.setMinimumHeight(42)
        user_label.clicked.connect(self.open_access_dialog)

        expand_button = QPushButton("Expandir menu")
        expand_button.setMinimumHeight(42)
        expand_button.setIcon(make_icon("dashboard", "#DBEAFE", "#1D4ED8"))
        expand_button.clicked.connect(self.toggle_top_bar)

        logout_button = QPushButton("Sair")
        logout_button.setMinimumHeight(42)
        logout_button.setProperty("variant", "danger")
        logout_button.setIcon(make_icon("logout", "#26FFFFFF", "#FFFFFF"))
        logout_button.clicked.connect(self.close)

        layout.addWidget(self.compact_context_label, 0)
        layout.addWidget(self.compact_title_label, 1)
        layout.addWidget(user_label, 0)
        layout.addWidget(expand_button, 0)
        layout.addWidget(logout_button, 0)
        return compact

    def open_access_dialog(self):
        AccessDialog(self.api_client, self.user, self).exec()

    def toggle_top_bar(self):
        self.top_bar_collapsed = not self.top_bar_collapsed
        self.header_content.setVisible(not self.top_bar_collapsed)
        self.nav_scroll.setVisible(not self.top_bar_collapsed)
        self.compact_top_bar.setVisible(self.top_bar_collapsed)
        if self.top_bar_collapsed:
            self.top_bar_layout.setContentsMargins(12, 8, 12, 8)
            self.top_bar.setMaximumHeight(88)
        else:
            self.top_bar_layout.setContentsMargins(20, 12, 20, 12)
            self.top_bar.setMaximumHeight(16777215)
        self.top_bar.updateGeometry()

    def _build_content(self):
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(10)

        self.top_bar = self._build_top_bar()
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.dashboard_page = DashboardPage(self.api_client)
        self.nc_page = NonConformitiesPage(self.api_client)
        self.productivity_page = ProductivityPage(self.api_client)
        self.equipment_page = EquipmentPage(self.api_client)
        self.checklist_items_page = ChecklistItemsPage(self.api_client)
        self.materials_page = MaterialsPage(self.api_client)
        self.washes_page = WashesPage(self.api_client)
        self.activities_page = ActivitiesPage(self.api_client)
        self.maintenance_page = MaintenancePage(self.api_client)
        self.reports_page = ReportsPage(self.api_client)
        self.users_page = UsersPage(self.api_client, self.user)
        self.cloud_backup_page = CloudBackupPage(self.api_client)

        self.page_map = {
            "dashboard": self.dashboard_page,
            "nc": self.nc_page,
            "productivity": self.productivity_page,
            "reports": self.reports_page,
        }
        if self.can_manage:
            self.page_map["equipment"] = self.equipment_page
            self.page_map["checklist_items"] = self.checklist_items_page
            self.page_map["materials"] = self.materials_page
            self.page_map["washes"] = self.washes_page
            self.page_map["activities"] = self.activities_page
            self.page_map["maintenance"] = self.maintenance_page
            if self.is_admin:
                self.page_map["users"] = self.users_page
                self.page_map["cloud_backup"] = self.cloud_backup_page

        for page in self.page_map.values():
            self.stack.addWidget(page)

        self.loading_overlay = LoadingOverlay(self.stack)

        self.dirty_pages = set(self.page_map.keys())

        self.nc_page.data_changed.connect(lambda: self.handle_data_changed("nc"))
        if self.can_manage:
            self.equipment_page.data_changed.connect(lambda: self.handle_data_changed("equipment"))
            self.checklist_items_page.data_changed.connect(lambda: self.handle_data_changed("checklist_items"))
            self.materials_page.data_changed.connect(lambda: self.handle_data_changed("materials"))
            self.washes_page.data_changed.connect(lambda: self.handle_data_changed("washes"))
            self.activities_page.data_changed.connect(lambda: self.handle_data_changed("activities"))
            self.maintenance_page.data_changed.connect(lambda: self.handle_data_changed("maintenance"))
            if self.is_admin:
                self.users_page.data_changed.connect(lambda: self.handle_data_changed("users"))

        shell_layout.addWidget(self.top_bar)
        shell_layout.addWidget(self.stack, 1)
        return shell

    def switch_page(self, page_key: str):
        self.current_page_key = page_key
        self._update_top_bar_context(page_key)
        for key, button in self.nav_buttons.items():
            button.set_active(key == page_key)
        page = self.page_map[page_key]
        self.stack.setCurrentWidget(page)
        self._animate_page(page)
        self.request_page_refresh(page_key)

    def request_page_refresh(self, page_key: str):
        if page_key not in self.dirty_pages or page_key in self.pending_refreshes:
            return
        self.pending_refreshes.add(page_key)
        page = self.page_map.get(page_key)
        if page and hasattr(page, "set_loading_state"):
            page.set_loading_state(True)
        self._show_page_loading(page_key)
        QTimer.singleShot(12, lambda key=page_key: self._execute_page_refresh(key))

    def _execute_page_refresh(self, page_key: str):
        self.pending_refreshes.discard(page_key)
        page = self.page_map.get(page_key)
        if page_key != self.current_page_key:
            if page and hasattr(page, "set_loading_state"):
                page.set_loading_state(False)
            self.loading_overlay.hide_loading()
            return
        if page_key not in self.dirty_pages:
            if page and hasattr(page, "set_loading_state"):
                page.set_loading_state(False)
            self.loading_overlay.hide_loading()
            return
        self._refresh_page(page_key)
        self.dirty_pages.discard(page_key)
        if page and hasattr(page, "set_loading_state"):
            QTimer.singleShot(120, lambda p=page: p.set_loading_state(False))
        QTimer.singleShot(140, self.loading_overlay.hide_loading)

    def _refresh_page(self, page_key: str):
        try:
            if page_key == "dashboard":
                self.dashboard_page.refresh()
            elif page_key == "nc":
                self.nc_page.refresh()
            elif page_key == "productivity":
                self.productivity_page.refresh()
            elif page_key == "equipment":
                self.equipment_page.refresh()
            elif page_key == "checklist_items":
                self.checklist_items_page.refresh()
            elif page_key == "materials":
                self.materials_page.refresh()
            elif page_key == "washes":
                self.washes_page.refresh()
            elif page_key == "activities":
                self.activities_page.refresh()
            elif page_key == "maintenance":
                self.maintenance_page.refresh()
            elif page_key == "reports":
                self.reports_page.refresh()
            elif page_key == "users":
                self.users_page.refresh()
            elif page_key == "cloud_backup":
                self.cloud_backup_page.refresh()
        except Exception as exc:
            show_notice(self, "Falha ao carregar dados", str(exc), icon_name="warning")

    def handle_data_changed(self, source_page_key: str):
        for page_key in self.page_map:
            if page_key != source_page_key:
                self.dirty_pages.add(page_key)

        if source_page_key != "dashboard" and self.current_page_key != source_page_key:
            self._refresh_page("dashboard")

        if self.current_page_key and self.current_page_key != source_page_key and self.current_page_key != "dashboard":
            self.request_page_refresh(self.current_page_key)

    def _animate_page(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(260)
        animation.setStartValue(0.42)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start()
        self.page_animation = animation

    def _show_page_loading(self, page_key: str):
        context_map = {
            "dashboard": ("Atualizando dashboard", "Preparando indicadores, prioridades e visão executiva."),
            "nc": ("Carregando ocorrências", "Buscando não conformidades, filtros e histórico visual."),
            "productivity": ("Carregando produtividade", "Consolidando checklists, manutencoes, lavagens e resolucoes."),
            "equipment": ("Carregando equipamentos", "Organizando a base da frota e os detalhes técnicos."),
            "checklist_items": ("Carregando itens", "Atualizando catalogo, ordem e fotos de referencia do checklist."),
            "materials": ("Carregando materiais", "Atualizando saldo, alertas de estoque e itens cadastrados."),
            "washes": ("Carregando lavagens", "Montando fila, histórico mensal e programação preventiva."),
            "activities": ("Carregando atividades", "Montando auditorias em massa, seleção e execução."),
            "maintenance": ("Carregando manutenção", "Montando cronograma mensal e tabela de programação."),
            "reports": ("Montando relatórios", "Consolidando dados macro, micro e exportações."),
            "users": ("Carregando acessos", "Atualizando perfis, logins e permissões disponíveis."),
            "cloud_backup": ("Verificando nuvem", "Consultando uso de banco, fotos e status do backup."),
        }
        title, subtitle = context_map.get(page_key, ("Carregando painel", "Preparando dados da tela atual."))
        self.loading_overlay.show_loading(title, subtitle)

    def _update_top_bar_context(self, page_key: str):
        context_map = {
            "dashboard": "PAINEL OPERACIONAL",
            "nc": "DETALHES DE OCORRÊNCIAS",
            "productivity": "PRODUTIVIDADE OPERACIONAL",
            "equipment": "DETALHES DE EQUIPAMENTOS",
            "checklist_items": "CONFIGURACAO DO CHECKLIST",
            "materials": "DETALHES DE MATERIAIS",
            "washes": "DETALHES DE LAVAGENS",
            "activities": "DETALHES DE ATIVIDADES",
            "maintenance": "DETALHES DE MANUTENÇÃO",
            "reports": "DETALHES DE RELATÓRIOS",
            "users": "DETALHES DE ACESSOS",
            "cloud_backup": "NUVEM E BACKUP",
        }
        context = context_map.get(page_key, "PAINEL OPERACIONAL")
        self.top_bar_pill.setText(context)
        if hasattr(self, "compact_context_label"):
            self.compact_context_label.setText(context)


