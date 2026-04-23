from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMdiArea,
    QMdiSubWindow,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from components import LoadingOverlay, make_icon, show_notice
from runtime_paths import asset_path
from theme import APP_STYLE
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
        icon_label.setPixmap(make_icon("users", "#FFFFFF", "#5B6571", 28).pixmap(28, 28))
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
        self.app_icon_path = asset_path("app-icon.ico")
        self.current_page_key = ""
        self.dirty_pages: set[str] = set()
        self.pending_refreshes: set[str] = set()
        self.page_subwindows: dict[str, QWidget] = {}
        self.tree_items: dict[str, QWidget] = {}
        self._syncing_tree = False

        self.setWindowTitle("Sistema Portuario")
        self.setMinimumSize(1280, 760)
        self.setStyleSheet(APP_STYLE)
        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))

        self._build_pages()
        self._build_menu_bar()

        container = QWidget()
        container.setObjectName("MainContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.tree_panel = self._build_tree_panel()
        self.mdi_area = self._build_mdi_area()
        splitter.addWidget(self.tree_panel)
        splitter.addWidget(self.mdi_area)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1200])

        root.addWidget(splitter, 1)

        self.setCentralWidget(container)
        self._build_status_bar()
        self.loading_overlay = LoadingOverlay(self.mdi_area.viewport())

        self.showMaximized()
        self.switch_page("dashboard")

    def _build_pages(self):
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

        self.page_titles = {
            "dashboard": "Dashboard",
            "nc": "Ocorrencias",
            "productivity": "Produtividade",
            "equipment": "Frota",
            "checklist_items": "Checklist",
            "materials": "Materiais",
            "washes": "Lavagens",
            "activities": "Atividades",
            "maintenance": "Manutencao",
            "reports": "Relatorios",
            "users": "Logins",
            "cloud_backup": "Backup",
        }
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

    def _build_menu_bar(self):
        menubar = self.menuBar()
        menubar.clear()

        menu_groups = {
            "Cadastro": ["equipment", "checklist_items", "materials", "users"],
            "Tabelas": ["checklist_items", "materials"],
            "Movimento": ["nc", "activities", "washes", "maintenance"],
            "Relatorios": ["reports", "productivity"],
            "Sistema": ["dashboard", "cloud_backup"],
            "Utilitarios": ["dashboard"],
        }

        for menu_title, keys in menu_groups.items():
            menu = menubar.addMenu(menu_title)
            added = 0
            for key in keys:
                if key not in self.page_map:
                    continue
                action = menu.addAction(self.page_titles.get(key, key))
                action.triggered.connect(lambda checked=False, page_key=key: self.switch_page(page_key))
                added += 1
            if added == 0:
                menu.setEnabled(False)

        account_menu = menubar.addMenu("Conta")
        access_action = account_menu.addAction("Meu acesso")
        access_action.triggered.connect(self.open_access_dialog)
        exit_action = account_menu.addAction("Encerrar sessao")
        exit_action.triggered.connect(self.close)

    def _build_tree_panel(self):
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(380)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(6)

        title = QLabel("Modulo Portuario")
        title.setObjectName("SectionTitle")
        panel_layout.addWidget(title)

        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setIndentation(16)
        self.nav_tree.itemActivated.connect(self._on_tree_item_activated)
        self.nav_tree.itemClicked.connect(self._on_tree_item_activated)
        panel_layout.addWidget(self.nav_tree, 1)
        self._populate_tree()
        return panel

    def _populate_tree(self):
        self.nav_tree.clear()
        self.tree_items = {}

        root = self._make_tree_item(self.nav_tree, "Modulo Portuario", icon_name="dashboard")
        sections = [
            ("1 - Cadastro", ["equipment", "checklist_items", "materials", "users"]),
            ("2 - Tabelas", ["checklist_items", "materials"]),
            ("3 - Movimento", ["nc", "activities", "washes", "maintenance"]),
            ("4 - Relatorios", ["reports", "productivity"]),
            ("5 - Utilitarios", ["dashboard", "cloud_backup"]),
        ]

        for section_label, keys in sections:
            section_item = self._make_tree_item(root, section_label, icon_name="reports")
            for key in keys:
                if key not in self.page_map:
                    continue
                item = self._make_tree_item(section_item, self.page_titles.get(key, key), page_key=key, icon_name="dashboard")
                self.tree_items[key] = item

        self.nav_tree.expandAll()

    def _make_tree_item(self, parent, label: str, *, page_key: str | None = None, icon_name: str = "dashboard"):
        item = QTreeWidgetItem(parent, [label])
        item.setIcon(0, make_icon(icon_name, "#E7EBF0", "#4F5B69", 14))
        if page_key:
            item.setData(0, Qt.UserRole, page_key)
        return item

    def _on_tree_item_activated(self, item):
        if self._syncing_tree:
            return
        page_key = item.data(0, Qt.UserRole)
        if page_key:
            self.switch_page(page_key)

    def _build_mdi_area(self):
        mdi = QMdiArea()
        mdi.setViewMode(QMdiArea.SubWindowView)
        mdi.setActivationOrder(QMdiArea.ActivationHistoryOrder)
        mdi.subWindowActivated.connect(self._on_subwindow_activated)
        return mdi

    def _build_status_bar(self):
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.setStyleSheet("QStatusBar::item { border: none; }")

        def make_cell(text: str, min_width: int):
            label = QLabel(text)
            label.setMinimumWidth(min_width)
            label.setStyleSheet(
                "padding: 2px 8px; border-right: 1px solid #B8BDC3; color: #2F3E50; background: #E7EAEE;"
            )
            return label

        status.addPermanentWidget(make_cell("V:2.0.10.37", 120))
        status.addPermanentWidget(make_cell((self.user.get("nome") or "-").upper(), 160))
        status.addPermanentWidget(make_cell("CHIBATAO NAVEGACAO E COMERCIO LTDA", 360), 1)
        status.addPermanentWidget(make_cell("Manual ISO", 120))

    def open_access_dialog(self):
        AccessDialog(self.api_client, self.user, self).exec()

    def _ensure_subwindow(self, page_key: str):
        sub = self.page_subwindows.get(page_key)
        if sub is None:
            sub = QMdiSubWindow(self.mdi_area)
            sub.setAttribute(Qt.WA_DeleteOnClose, False)
            sub.setWindowTitle(self.page_titles.get(page_key, page_key))
            sub.setWindowIcon(make_icon("dashboard", "#E7EBF0", "#4F5B69"))
            sub.setWindowFlags(
                Qt.SubWindow
                | Qt.CustomizeWindowHint
                | Qt.WindowTitleHint
                | Qt.WindowSystemMenuHint
                | Qt.WindowMinMaxButtonsHint
            )
            sub.setWidget(self.page_map[page_key])
            self.mdi_area.addSubWindow(sub)
            self.page_subwindows[page_key] = sub

        if sub.isHidden():
            sub.show()
        return sub

    def _on_subwindow_activated(self, subwindow):
        if subwindow is None:
            return
        for key, sub in self.page_subwindows.items():
            if sub is subwindow:
                self.current_page_key = key
                self._sync_tree_selection(key)
                break

    def _sync_tree_selection(self, page_key: str):
        item = self.tree_items.get(page_key)
        if item is None:
            return
        self._syncing_tree = True
        try:
            self.nav_tree.setCurrentItem(item)
        finally:
            self._syncing_tree = False

    def switch_page(self, page_key: str):
        if page_key not in self.page_map:
            return
        same_page = self.current_page_key == page_key
        self.current_page_key = page_key
        self._sync_tree_selection(page_key)

        sub = self._ensure_subwindow(page_key)
        self.mdi_area.setActiveSubWindow(sub)
        sub.showMaximized()

        page = self.page_map[page_key]
        if not same_page:
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
            QTimer.singleShot(70, lambda p=page: p.set_loading_state(False))
        QTimer.singleShot(80, self.loading_overlay.hide_loading)

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
        animation.setDuration(90)
        animation.setStartValue(0.88)
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


