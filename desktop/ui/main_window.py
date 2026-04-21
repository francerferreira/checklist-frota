from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
from ui.dashboard_page import DashboardPage
from ui.equipment_page import EquipmentPage
from ui.materials_page import MaterialsPage
from ui.non_conformities_page import NonConformitiesPage
from ui.productivity_page import ProductivityPage
from ui.reports_page import ReportsPage
from ui.users_page import UsersPage
from ui.washes_page import WashesPage


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

        layout = QVBoxLayout(top_bar)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
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

        subtitle = QLabel("Operação portuária • Porto Chibatão")
        subtitle.setObjectName("TopBarSubtitle")

        text_wrap.addWidget(self.top_bar_pill, 0, Qt.AlignLeft)
        text_wrap.addWidget(title)
        text_wrap.addWidget(subtitle)

        badge = QFrame()
        badge.setObjectName("TopBarBadge")
        badge.setMinimumWidth(148)
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

        header_row.addWidget(logo_label, 0)
        header_row.addLayout(text_wrap, 1)

        header_actions_card = QFrame()
        header_actions_card.setObjectName("TopBarActionCluster")
        header_actions = QHBoxLayout()
        header_actions.setContentsMargins(14, 12, 14, 12)
        header_actions.setSpacing(12)
        header_actions.addWidget(badge, 0)
        header_actions.addWidget(logout_button, 0)
        header_actions_card.setLayout(header_actions)
        header_row.addWidget(header_actions_card, 0)

        nav_strip = QFrame()
        nav_strip.setObjectName("TopNavStrip")
        nav_strip.setMinimumHeight(66)
        nav_strip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout = QHBoxLayout(nav_strip)
        nav_layout.setContentsMargins(8, 6, 8, 6)
        nav_layout.setSpacing(8)
        nav_layout.setAlignment(Qt.AlignLeft)

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "Dashboard", make_icon("dashboard")),
            ("nc", "Não Conformidades", make_icon("warning", "#DBEAFE", "#1D4ED8")),
            ("productivity", "Produtividade", make_icon("dashboard", "#DCFCE7", "#166534")),
        ]
        if self.can_manage:
            nav_items.append(("equipment", "Equipamentos", make_icon("equipment")))
            nav_items.append(("checklist_items", "Itens Checklist", make_icon("reports")))
            nav_items.append(("materials", "Controle de Material", make_icon("materials", "#DBEAFE", "#1D4ED8")))
            nav_items.append(("washes", "Lavagens", make_icon("activities", "#DBEAFE", "#1D4ED8")))
            nav_items.append(("activities", "Atividades", make_icon("activities", "#DBEAFE", "#1D4ED8")))
        nav_items.append(("reports", "Relatórios", make_icon("reports")))
        if self.is_admin:
            nav_items.append(("users", "Logins", make_icon("users", "#EEF2FF", "#4338CA")))

        for key, label, icon in nav_items:
            button = AnimatedButton(label)
            button.setIcon(icon)
            button.setMinimumWidth(max(132, 70 + (len(label) * 4)))
            button.setMinimumHeight(48)
            button.clicked.connect(lambda checked=False, page_key=key: self.switch_page(page_key))
            nav_layout.addWidget(button)
            self.nav_buttons[key] = button

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setMinimumHeight(72)
        nav_scroll.setMaximumHeight(72)
        nav_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_scroll.setWidget(nav_strip)

        layout.addLayout(header_row)
        layout.addWidget(nav_scroll)
        return top_bar

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
        self.reports_page = ReportsPage(self.api_client)
        self.users_page = UsersPage(self.api_client, self.user)

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
            if self.is_admin:
                self.page_map["users"] = self.users_page

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
            elif page_key == "reports":
                self.reports_page.refresh()
            elif page_key == "users":
                self.users_page.refresh()
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
            "reports": ("Montando relatórios", "Consolidando dados macro, micro e exportações."),
            "users": ("Carregando acessos", "Atualizando perfis, logins e permissões disponíveis."),
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
            "reports": "DETALHES DE RELATÓRIOS",
            "users": "DETALHES DE ACESSOS",
        }
        self.top_bar_pill.setText(context_map.get(page_key, "PAINEL OPERACIONAL"))

