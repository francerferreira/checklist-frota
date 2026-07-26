from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QTimer, Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
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
    QApplication,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from access import PAGE_ACCESS_BY_ROLE, allowed_pages_for_role, normalize_user_role
from components import LoadingOverlay, make_icon, show_notice
from runtime_paths import asset_path
from theme import APP_STYLE, apply_button_styles, install_button_style_enforcer
from ui.activities_page import ActivitiesPage
from ui.availability_page import AvailabilityPage
from ui.admin_rules_page import AdminRulesPage
from ui.audit_logs_page import AuditLogsPage
from ui.checklist_items_page import ChecklistItemsPage
from ui.checklist_history_page import ChecklistHistoryPage
from ui.spreader_history_page import SpreaderHistoryPage
from ui.cloud_backup_page import CloudBackupPage
from ui.dashboard_page import DashboardPage
from ui.equipment_page import EquipmentPage
from ui.emergencies_page import EmergenciesPage
from ui.employees_page import EmployeesPage
from ui.attendance_page import AttendancePage
from ui.employee_records_page import EmployeeRecordsPage
from ui.hr_management_page import HRManagementPage
from ui.vacations_page import VacationsPage
from ui.global_search_dialog import GlobalSearchDialog
from ui.inspection_templates_page import InspectionTemplatesPage
from ui.materials_page import MaterialsPage
from ui.maintenance_page import MaintenancePage
from ui.non_conformities_page import NonConformitiesPage
from ui.operational_center_page import OperationalCenterPage
from ui.productivity_page import ProductivityPage
from ui.purchases_page import PurchasesPage
from ui.pcm_page import PCMPage
from ui.supply_library_page import SupplyLibraryPage
from ui.reports_page import ReportsPage
from ui.resources_page import ResourcesPage
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
    PAGE_ACCESS_BY_ROLE = PAGE_ACCESS_BY_ROLE

    def __init__(self, api_client, user, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.user = user
        self.page_animation = None
        self.user_role = normalize_user_role(self.user)
        self.is_admin = self.user_role == "admin"
        self.can_manage = self.user_role in {"admin", "gestor"}
        self.allowed_pages = allowed_pages_for_role(self.user_role)
        self.app_icon_path = asset_path("app-icon.ico")
        self.current_page_key = ""
        self.dirty_pages: set[str] = set()
        self.pending_refreshes: set[str] = set()
        self.page_subwindows: dict[str, QWidget] = {}
        self.tree_items: dict[str, QWidget] = {}
        self.section_items: list[QTreeWidgetItem] = []
        self.favorite_page_keys: set[str] = set()
        self.recent_page_keys: list[str] = []
        self._syncing_tree = False
        self.sidebar_visible = True
        self.pending_navigation_target: dict | None = None

        self.setWindowTitle("Sistema de Manutenção de Frota")
        self.setMinimumSize(1280, 760)
        app = QApplication.instance()
        if app is not None:
            if not app.styleSheet():
                app.setStyleSheet(APP_STYLE)
            install_button_style_enforcer(app)
        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))

        self._build_pages()
        self._build_menu_bar()
        self.toggle_sidebar_shortcut = QShortcut(QKeySequence("F9"), self)
        self.toggle_sidebar_shortcut.setContext(Qt.ApplicationShortcut)
        self.toggle_sidebar_shortcut.activated.connect(self.toggle_sidebar)
        self.global_search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.global_search_shortcut.setContext(Qt.ApplicationShortcut)
        self.global_search_shortcut.activated.connect(self.open_global_search)

        container = QWidget()
        container.setObjectName("MainContainer")
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(True)
        self.tree_panel = self._build_tree_panel()
        self.mdi_area = self._build_mdi_area()
        splitter.addWidget(self.tree_panel)
        splitter.addWidget(self.mdi_area)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1200])
        self.main_splitter = splitter

        root.addWidget(splitter, 1)

        self.setCentralWidget(container)
        self._build_status_bar()
        self._load_navigation_preferences()
        self.loading_overlay = LoadingOverlay(self.mdi_area.viewport())
        self._build_mdi_placeholder_logo()
        apply_button_styles(self)

        self.showMaximized()
        QTimer.singleShot(0, lambda: self.switch_page("dashboard"))

    def _build_pages(self):
        self.dashboard_page = DashboardPage(self.api_client)
        self.nc_page = NonConformitiesPage(self.api_client)
        self.productivity_page = ProductivityPage(self.api_client)
        self.operational_center_page = OperationalCenterPage(self.api_client)
        self.equipment_page = EquipmentPage(self.api_client)
        self.checklist_items_page = ChecklistItemsPage(self.api_client)
        self.inspection_templates_page = InspectionTemplatesPage(self.api_client)
        self.checklist_history_page = ChecklistHistoryPage(self.api_client)
        self.spreader_history_page = SpreaderHistoryPage(self.api_client)
        self.materials_page = MaterialsPage(self.api_client)
        self.washes_page = WashesPage(self.api_client)
        self.activities_page = ActivitiesPage(self.api_client)
        self.availability_page = AvailabilityPage(self.api_client)
        self.emergencies_page = EmergenciesPage(self.api_client)
        self.maintenance_page = MaintenancePage(self.api_client)
        self.pcm_page = PCMPage(self.api_client)
        self.resources_page = ResourcesPage(self.api_client)
        self.purchases_page = PurchasesPage(self.api_client)
        self.employees_page = EmployeesPage(self.api_client, self.user)
        self.attendance_page = AttendancePage(self.api_client, self.user)
        self.employee_records_page = EmployeeRecordsPage(self.api_client, self.user)
        self.hr_management_page = HRManagementPage(self.api_client, self.user)
        self.vacations_page = VacationsPage(self.api_client)
        self.supply_library_page = SupplyLibraryPage(self.api_client)
        self.reports_page = ReportsPage(self.api_client)
        self.users_page = UsersPage(self.api_client, self.user)
        self.cloud_backup_page = CloudBackupPage(self.api_client)
        self.audit_logs_page = AuditLogsPage(self.api_client)
        self.admin_rules_page = AdminRulesPage(self.api_client)

        all_pages = {
            "dashboard": self.dashboard_page,
            "nc": self.nc_page,
            "productivity": self.productivity_page,
            "operations_center": self.operational_center_page,
            "checklist_history": self.checklist_history_page,
            "spreader_history": self.spreader_history_page,
            "reports": self.reports_page,
            "equipment": self.equipment_page,
            "checklist_items": self.checklist_items_page,
            "inspection_templates": self.inspection_templates_page,
            "materials": self.materials_page,
            "washes": self.washes_page,
            "activities": self.activities_page,
            "availability": self.availability_page,
            "emergencies": self.emergencies_page,
            "maintenance": self.maintenance_page,
            "pcm": self.pcm_page,
            "resources": self.resources_page,
            "purchases": self.purchases_page,
            "employees": self.employees_page,
            "attendance": self.attendance_page,
            "employee_records": self.employee_records_page,
            "hr_management": self.hr_management_page,
            "vacations": self.vacations_page,
            "supply_library": self.supply_library_page,
            "users": self.users_page,
            "cloud_backup": self.cloud_backup_page,
            "audit_logs": self.audit_logs_page,
            "admin_rules": self.admin_rules_page,
        }
        self.page_map = {key: page for key, page in all_pages.items() if key in self.allowed_pages}

        self.page_titles = {
            "dashboard": "Dashboard",
            "nc": "Central de Resolução",
            "productivity": "Produtividade",
            "operations_center": "Central Operacional",
            "equipment": "Equipamentos",
            "checklist_items": "Checklist",
            "inspection_templates": "Templates Técnicos",
            "materials": "Materiais",
            "washes": "Lavagens",
            "activities": "Inspeções",
            "availability": "Disponibilidade",
            "emergencies": "Emergenciais e OS",
            "maintenance": "Manutenção",
            "pcm": "PCM",
            "resources": "Recursos e ferramentas",
            "purchases": "Compras e fornecedores",
            "employees": "Recursos Humanos",
            "attendance": "Frequência e ocorrências",
            "employee_records": "Documentos e treinamentos",
            "hr_management": "Central de RH",
            "vacations": "Férias",
            "supply_library": "Suprimentos e Biblioteca",
            "reports": "Relatórios",
            "checklist_history": "Histórico Checklist",
            "spreader_history": "Histórico Spreaders",
            "users": "Logins",
            "cloud_backup": "Backup",
            "audit_logs": "Logs de Auditoria",
            "admin_rules": "Configuração Administrativa",
        }
        self.dirty_pages = set(self.page_map.keys())

        self.nc_page.data_changed.connect(lambda: self.handle_data_changed("nc"))
        self.dashboard_page.alert_open_requested.connect(self.open_contextual_alert)
        self.dashboard_page.web_mobile_requested.connect(self.open_web_mobile)
        self.dashboard_page.tv_dashboard_requested.connect(self.open_tv_dashboard)
        if "equipment" in self.page_map:
            self.equipment_page.data_changed.connect(lambda: self.handle_data_changed("equipment"))
        if "checklist_items" in self.page_map:
            self.checklist_items_page.data_changed.connect(lambda: self.handle_data_changed("checklist_items"))
        if "materials" in self.page_map:
            self.materials_page.data_changed.connect(lambda: self.handle_data_changed("materials"))
        if "washes" in self.page_map:
            self.washes_page.data_changed.connect(lambda: self.handle_data_changed("washes"))
        if "activities" in self.page_map:
            self.activities_page.data_changed.connect(lambda: self.handle_data_changed("activities"))
        if "maintenance" in self.page_map:
            self.maintenance_page.data_changed.connect(lambda: self.handle_data_changed("maintenance"))
        if "emergencies" in self.page_map:
            self.emergencies_page.data_changed.connect(lambda: self.handle_data_changed("emergencies"))
        if "pcm" in self.page_map:
            self.pcm_page.data_changed.connect(lambda: self.handle_data_changed("pcm"))
        if "supply_library" in self.page_map:
            self.supply_library_page.data_changed.connect(lambda: self.handle_data_changed("supply_library"))
        if "users" in self.page_map:
            self.users_page.data_changed.connect(lambda: self.handle_data_changed("users"))
        if "admin_rules" in self.page_map:
            self.admin_rules_page.data_changed.connect(lambda: self.handle_data_changed("admin_rules"))
        if "employees" in self.page_map:
            self.employees_page.data_changed.connect(lambda: self.handle_data_changed("employees"))
        if "attendance" in self.page_map:
            self.attendance_page.data_changed.connect(lambda: self.handle_data_changed("attendance"))
        if "employee_records" in self.page_map:
            self.employee_records_page.data_changed.connect(lambda: self.handle_data_changed("employee_records"))
        if "hr_management" in self.page_map:
            self.hr_management_page.data_changed.connect(lambda: self.handle_data_changed("hr_management"))
            self.hr_management_page.open_page_requested.connect(self.switch_page)
        if "vacations" in self.page_map:
            self.vacations_page.data_changed.connect(lambda: self.handle_data_changed("vacations"))

    def _build_menu_bar(self):
        menubar = self.menuBar()
        menubar.clear()

        menu_groups = {
            "Operação": ["dashboard", "operations_center", "availability", "emergencies"],
            "Manutenção": ["maintenance", "pcm", "resources", "activities", "washes", "inspection_templates"],
            "Ativos e suprimentos": ["equipment", "spreader_history", "checklist_items", "materials", "supply_library", "purchases"],
            "Gestão": ["nc", "reports", "productivity", "checklist_history"],
            "RH": ["hr_management", "employees", "attendance", "vacations", "employee_records"],
            "Administração": ["users", "cloud_backup", "audit_logs", "admin_rules"],
        }

        for menu_title, keys in menu_groups.items():
            available_keys = [key for key in keys if key in self.page_map]
            if not available_keys:
                continue
            menu = menubar.addMenu(menu_title)
            for key in available_keys:
                action = menu.addAction(self.page_titles.get(key, key))
                action.triggered.connect(lambda checked=False, page_key=key: self.switch_page(page_key))

        web_panels_menu = menubar.addMenu("Painéis Web")
        web_mobile_action = web_panels_menu.addAction("Abrir Web Mobile")
        web_mobile_action.triggered.connect(self.open_web_mobile)
        tv_dashboard_action = web_panels_menu.addAction("Abrir Dashboard TV")
        tv_dashboard_action.triggered.connect(self.open_tv_dashboard)

        account_menu = menubar.addMenu("Conta")
        global_search_action = account_menu.addAction("Busca global")
        global_search_action.setShortcut("Ctrl+K")
        global_search_action.triggered.connect(self.open_global_search)
        toggle_nav_action = account_menu.addAction("Ocultar/mostrar navegação")
        toggle_nav_action.setShortcut("F9")
        toggle_nav_action.triggered.connect(self.toggle_sidebar)
        access_action = account_menu.addAction("Meu acesso")
        access_action.triggered.connect(self.open_access_dialog)
        exit_action = account_menu.addAction("Encerrar sessão")
        exit_action.triggered.connect(self.close)

    def _web_panel_url(self, relative_path: str) -> str:
        api_url = quote(str(self.api_client.base_url or "").rstrip("/"), safe="")
        return f"http://127.0.0.1:5500/{relative_path.lstrip('/')}?api={api_url}"

    def _open_web_panel(self, label: str, relative_path: str) -> None:
        url = self._web_panel_url(relative_path)
        if not QDesktopServices.openUrl(QUrl(url)):
            show_notice(
                self,
                f"Não foi possível abrir {label}",
                "Inicie o atalho ABRIR_WEB_MOBILE_E_DESKTOP_LOCAL.bat e tente novamente.",
                icon_name="warning",
            )

    def open_web_mobile(self) -> None:
        self._open_web_panel("o Web Mobile", "")

    def open_tv_dashboard(self) -> None:
        self._open_web_panel("o Dashboard TV", "dashboard-manutencao/tv/")

    def _build_tree_panel(self):
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(380)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(6)

        title = QLabel("Gestão de Manutenção")
        title.setObjectName("SectionTitle")
        panel_layout.addWidget(title)

        self.navigation_search = QLineEdit()
        self.navigation_search.setObjectName("NavigationSearch")
        self.navigation_search.setPlaceholderText("Buscar tela ou módulo...")
        self.navigation_search.setClearButtonEnabled(True)
        self.navigation_search.textChanged.connect(self._filter_navigation)
        panel_layout.addWidget(self.navigation_search)

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
        self.section_items = []

        root = self._make_tree_item(self.nav_tree, "Sistema de Manutenção de Frota", icon_name="dashboard")
        favorite_keys = [key for key in self.page_titles if key in self.favorite_page_keys and key in self.page_map]
        recent_keys = [key for key in self.recent_page_keys if key in self.page_map]
        for section_label, keys in (("Favoritos", favorite_keys), ("Recentes", recent_keys)):
            if not keys:
                continue
            section_item = self._make_tree_item(root, section_label, icon_name="dashboard")
            self.section_items.append(section_item)
            for key in keys:
                item = self._make_tree_item(section_item, self.page_titles.get(key, key), page_key=key, icon_name="dashboard")
                self.tree_items[key] = item
        sections = [
            ("1 - Operação", ["dashboard", "operations_center", "availability", "emergencies"]),
            ("2 - Manutenção e PCM", ["maintenance", "pcm", "resources", "activities", "washes", "inspection_templates"]),
            ("3 - Ativos e suprimentos", ["equipment", "spreader_history", "checklist_items", "materials", "supply_library", "purchases"]),
            ("4 - Gestão e histórico", ["nc", "reports", "productivity", "checklist_history"]),
            ("5 - Recursos Humanos", ["hr_management", "employees", "attendance", "vacations", "employee_records"]),
            ("6 - Administração", ["users", "cloud_backup", "audit_logs", "admin_rules"]),
        ]

        for section_label, keys in sections:
            section_item = self._make_tree_item(root, section_label, icon_name="reports")
            self.section_items.append(section_item)
            for key in keys:
                if key not in self.page_map:
                    continue
                item = self._make_tree_item(section_item, self.page_titles.get(key, key), page_key=key, icon_name="dashboard")
                self.tree_items[key] = item

        self.nav_tree.expandAll()
        if self.current_page_key:
            self._sync_tree_selection(self.current_page_key)

    def _filter_navigation(self, search_text: str):
        query = search_text.strip().casefold()
        for item in self.tree_items.values():
            item.setHidden(bool(query) and query not in item.text(0).casefold())

        for section_item in self.section_items:
            has_visible_page = any(not section_item.child(index).isHidden() for index in range(section_item.childCount()))
            section_item.setHidden(bool(query) and not has_visible_page)

        root = self.nav_tree.topLevelItem(0)
        if root is not None:
            has_visible_section = any(not section_item.isHidden() for section_item in self.section_items)
            root.setHidden(bool(query) and not has_visible_section)
        self.nav_tree.expandAll()

    def _make_tree_item(self, parent, label: str, *, page_key: str | None = None, icon_name: str = "dashboard"):
        item = QTreeWidgetItem(parent, [label])
        item.setIcon(0, make_icon(icon_name, "#DDEBFA", "#1E5E98", 14))
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
        # Modo clássico de painel único: sem barra de abas no topo.
        mdi.setViewMode(QMdiArea.SubWindowView)
        mdi.setOption(QMdiArea.DontMaximizeSubWindowOnActivation, False)
        mdi.setBackground(QBrush(QColor("#FFFFFF")))
        mdi.viewport().setAutoFillBackground(True)
        palette = mdi.viewport().palette()
        palette.setColor(mdi.viewport().backgroundRole(), QColor("#FFFFFF"))
        mdi.viewport().setPalette(palette)
        mdi.viewport().setStyleSheet("background:#FFFFFF;")
        mdi.setActivationOrder(QMdiArea.CreationOrder)
        mdi.subWindowActivated.connect(self._on_subwindow_activated)
        return mdi

    def _build_mdi_placeholder_logo(self):
        self.mdi_logo_label = QLabel(self.mdi_area.viewport())
        self.mdi_logo_label.setObjectName("MdiPlaceholderLogo")
        self.mdi_logo_label.setAlignment(Qt.AlignCenter)
        self.mdi_logo_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.mdi_logo_label.setStyleSheet("background: transparent;")

        logo_path = asset_path("cf-logo-cover.png")
        if not logo_path.exists():
            logo_path = asset_path("app-logo-cover.png")
        self._mdi_logo_pixmap = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap()

        self.mdi_area.viewport().installEventFilter(self)
        self._resize_mdi_placeholder_logo()
        self.mdi_logo_label.lower()
        QTimer.singleShot(0, self._resize_mdi_placeholder_logo)
        QTimer.singleShot(120, self._resize_mdi_placeholder_logo)

    def _build_status_bar(self):
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.setStyleSheet("QStatusBar::item { border: none; }")

        def make_cell(text: str, min_width: int):
            label = QLabel(text)
            label.setMinimumWidth(min_width)
            label.setStyleSheet(
                "padding: 2px 8px; border-right: 1px solid #B7CBE3; color: #1D4C7D; background: #FFFFFF;"
            )
            return label

        current_user = (self.api_client.user or self.user or {})
        toggle_button = QPushButton("☰ Navegação")
        toggle_button.setMinimumHeight(24)
        toggle_button.clicked.connect(self.toggle_sidebar)
        status.addPermanentWidget(toggle_button)
        self.favorite_page_button = QPushButton("☆ Favoritar")
        self.favorite_page_button.setMinimumHeight(24)
        self.favorite_page_button.clicked.connect(self.toggle_current_page_favorite)
        status.addPermanentWidget(self.favorite_page_button)
        self.breadcrumb_label = make_cell("INÍCIO", 250)
        status.addPermanentWidget(self.breadcrumb_label)
        self.navigation_context_label = make_cell("NAVEGAÇÃO › INÍCIO", 240)
        status.addPermanentWidget(self.navigation_context_label)
        status.addPermanentWidget(make_cell("REV 1.0.0.0", 120))
        status.addPermanentWidget(
            make_cell(((current_user.get("nome") or current_user.get("login") or "-").upper()), 160)
        )
        status.addPermanentWidget(make_cell("Manual ISO", 120))

    def open_access_dialog(self):
        AccessDialog(self.api_client, self.user, self).exec()

    def open_global_search(self):
        dialog = GlobalSearchDialog(self.api_client, self)
        dialog.result_selected.connect(self.open_navigation_target)
        dialog.exec()

    def open_contextual_alert(self, alert: dict):
        target_page = {
            "MATERIAL": "materials",
            "PREVENTIVE_PLAN": "pcm",
            "EMERGENCY_EVENT": "emergencies",
        }.get(str(alert.get("entity_type") or "").upper(), "dashboard")
        self.open_navigation_target({
            "kind": "ALERTA",
            "entity_id": alert.get("entity_id"),
            "title": alert.get("message") or "Alerta operacional",
            "page_key": target_page,
        })

    def open_navigation_target(self, target: dict):
        page_key = str(target.get("page_key") or "")
        if page_key not in self.page_map:
            show_notice(self, "Acesso indisponível", "Este registro não está disponível para o seu perfil.", icon_name="warning")
            return
        self.pending_navigation_target = dict(target)
        self.dirty_pages.add(page_key)
        self.switch_page(page_key)

    def _ensure_subwindow(self, page_key: str, *, show_if_hidden: bool = True):
        sub = self.page_subwindows.get(page_key)
        if sub is not None and sub.widget() is None:
            self.page_subwindows.pop(page_key, None)
            sub = None
        if sub is None:
            sub = QMdiSubWindow(self.mdi_area)
            sub.setAttribute(Qt.WA_DeleteOnClose, False)
            sub.setWindowTitle(self.page_titles.get(page_key, page_key))
            sub.setWindowIcon(make_icon("dashboard", "#DDEBFA", "#1E5E98"))
            sub.setWindowFlags(
                Qt.SubWindow
                | Qt.CustomizeWindowHint
                | Qt.WindowTitleHint
                | Qt.WindowSystemMenuHint
                | Qt.WindowMinMaxButtonsHint
            )
            sub.setWidget(self.page_map[page_key])
            self.mdi_area.addSubWindow(sub)
            sub.destroyed.connect(lambda *_: self.page_subwindows.pop(page_key, None))
            self.page_subwindows[page_key] = sub

        if show_if_hidden and sub.isHidden():
            sub.setWindowState(Qt.WindowNoState)
            sub.show()
        return sub

    def _on_subwindow_activated(self, subwindow):
        if subwindow is None:
            self.current_page_key = ""
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

    def _update_navigation_context(self, page_key: str):
        if hasattr(self, "navigation_context_label"):
            page_title = self.page_titles.get(page_key, page_key)
            self.navigation_context_label.setText(f"NAVEGAÇÃO › {page_title.upper()}")
            if hasattr(self, "breadcrumb_label"):
                self.breadcrumb_label.setText(f"INÍCIO › {self._navigation_section(page_key)} › {page_title.upper()}")

    @staticmethod
    def _navigation_section(page_key: str) -> str:
        if page_key in {"dashboard", "operations_center", "availability", "emergencies"}:
            return "OPERAÇÃO"
        if page_key in {"maintenance", "pcm", "resources", "activities", "washes", "inspection_templates"}:
            return "MANUTENÇÃO"
        if page_key in {"equipment", "checklist_items", "materials", "supply_library", "purchases"}:
            return "ATIVOS"
        if page_key in {"users", "cloud_backup", "audit_logs", "admin_rules"}:
            return "ADMINISTRAÇÃO"
        return "GESTÃO"

    def _load_navigation_preferences(self):
        try:
            preferences = self.api_client.get_navigation_preferences() or {}
        except Exception:
            return
        self.favorite_page_keys = {
            str(row.get("page_key"))
            for row in preferences.get("favorites", [])
            if str(row.get("page_key") or "") in self.page_map
        }
        self.recent_page_keys = [
            str(row.get("page_key"))
            for row in preferences.get("recent", [])
            if str(row.get("page_key") or "") in self.page_map
        ]
        self._populate_tree()

    def _update_favorite_button(self):
        if not hasattr(self, "favorite_page_button"):
            return
        if self.current_page_key in self.favorite_page_keys:
            self.favorite_page_button.setText("★ Desfavoritar")
        else:
            self.favorite_page_button.setText("☆ Favoritar")
        self.favorite_page_button.setEnabled(bool(self.current_page_key))

    def toggle_current_page_favorite(self):
        page_key = self.current_page_key
        if not page_key:
            return
        try:
            preference = self.api_client.toggle_navigation_favorite(page_key)
        except Exception as exc:
            show_notice(self, "Favorito não alterado", str(exc), icon_name="warning")
            return
        if preference.get("is_favorite"):
            self.favorite_page_keys.add(page_key)
        else:
            self.favorite_page_keys.discard(page_key)
        self._populate_tree()
        self._update_favorite_button()

    def _record_navigation_access(self, page_key: str):
        try:
            self.api_client.register_navigation_access(page_key)
        except Exception:
            return
        self.recent_page_keys = [key for key in self.recent_page_keys if key != page_key]
        self.recent_page_keys.insert(0, page_key)
        self.recent_page_keys = self.recent_page_keys[:6]
        self._populate_tree()

    def switch_page(self, page_key: str):
        if page_key not in self.page_map:
            return
        same_page = self.current_page_key == page_key
        self.current_page_key = page_key
        self._sync_tree_selection(page_key)
        self._update_navigation_context(page_key)
        self._update_favorite_button()

        sub = self._ensure_subwindow(page_key)
        for other_key, other_sub in self.page_subwindows.items():
            if other_key != page_key and other_sub is not None and not other_sub.isHidden():
                other_sub.hide()
        self.mdi_area.setActiveSubWindow(sub)
        sub.setWindowState(Qt.WindowNoState)
        sub.show()
        if sub.widget() is not None:
            sub.widget().show()
            sub.widget().raise_()
        sub.raise_()
        sub.showMaximized()
        QTimer.singleShot(0, lambda s=sub: s.showMaximized() if s and not s.isHidden() else None)
        self.mdi_logo_label.lower()

        page = self.page_map[page_key]
        if not same_page:
            self._animate_page(page)
        self.request_page_refresh(page_key)
        QTimer.singleShot(0, lambda key=page_key: self._record_navigation_access(key))

    def _resize_mdi_placeholder_logo(self):
        if not hasattr(self, "mdi_logo_label"):
            return
        viewport = self.mdi_area.viewport()
        rect = viewport.rect()
        self.mdi_logo_label.setGeometry(rect)
        if self._mdi_logo_pixmap.isNull() or rect.width() <= 0 or rect.height() <= 0:
            self.mdi_logo_label.clear()
            return
        target_w = max(220, min(int(rect.width() * 0.52), 960))
        target_h = max(140, min(int(rect.height() * 0.52), 620))
        self.mdi_logo_label.setPixmap(
            self._mdi_logo_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def eventFilter(self, watched, event):
        if watched is self.mdi_area.viewport() and event.type() == QEvent.Resize:
            self._resize_mdi_placeholder_logo()
            self.mdi_logo_label.lower()
            active = self.mdi_area.activeSubWindow()
            if active and not active.isHidden():
                active.showMaximized()
        return super().eventFilter(watched, event)

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
            target = self.pending_navigation_target if (self.pending_navigation_target or {}).get("page_key") == page_key else None
            target_id = target.get("entity_id") if target else None
            if page_key == "dashboard":
                self.dashboard_page.refresh()
            elif page_key == "nc":
                self.nc_page.refresh()
            elif page_key == "productivity":
                self.productivity_page.refresh()
            elif page_key == "operations_center":
                self.operational_center_page.refresh()
            elif page_key == "equipment":
                self.equipment_page.refresh(target_id)
            elif page_key == "checklist_items":
                self.checklist_items_page.refresh()
            elif page_key == "inspection_templates":
                self.inspection_templates_page.refresh()
            elif page_key == "materials":
                self.materials_page.refresh(target_id)
            elif page_key == "washes":
                self.washes_page.refresh()
            elif page_key == "activities":
                self.activities_page.refresh()
            elif page_key == "availability":
                self.availability_page.refresh()
            elif page_key == "emergencies":
                self.emergencies_page.refresh()
            elif page_key == "maintenance":
                self.maintenance_page.refresh()
            elif page_key == "pcm":
                self.pcm_page.refresh()
            elif page_key == "resources":
                self.resources_page.refresh()
            elif page_key == "purchases":
                self.purchases_page.refresh()
            elif page_key == "supply_library":
                self.supply_library_page.refresh()
            elif page_key == "reports":
                self.reports_page.refresh()
            elif page_key == "checklist_history":
                self.checklist_history_page.refresh()
            elif page_key == "spreader_history":
                self.spreader_history_page.refresh()
            elif page_key == "users":
                self.users_page.refresh()
            elif page_key == "employees":
                self.employees_page.refresh(target_id)
            elif page_key == "attendance":
                self.attendance_page.refresh()
            elif page_key == "employee_records":
                self.employee_records_page.refresh()
            elif page_key == "hr_management":
                self.hr_management_page.refresh()
            elif page_key == "vacations":
                self.vacations_page.refresh()
            elif page_key == "cloud_backup":
                self.cloud_backup_page.refresh()
            elif page_key == "audit_logs":
                self.audit_logs_page.refresh()
            elif page_key == "admin_rules":
                self.admin_rules_page.refresh()
            if target:
                self.pending_navigation_target = None
        except Exception as exc:
            show_notice(self, "Falha ao carregar dados", str(exc), icon_name="warning")

    def handle_data_changed(self, source_page_key: str):
        # Invalidar cache de toda a aplicacao quando dados sao alterados
        # Especialmente importante para frota, que aparece em multiplos lugares
        for page_key in self.page_map:
            if page_key != source_page_key:
                self.dirty_pages.add(page_key)

        # Se equipamentos foram alterados, forcar refresh de tudo que usa frota
        if source_page_key == "equipment":
            self.dirty_pages.update(["activities", "maintenance", "washes", "nc", "reports", "spreader_history"])

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
            "nc": ("Carregando central", "Buscando não conformidades, filtros e histórico visual."),
            "productivity": ("Carregando produtividade", "Consolidando checklists, manutenções, lavagens e resoluções."),
            "equipment": ("Carregando equipamentos", "Organizando a base da frota e os detalhes técnicos."),
            "checklist_items": ("Carregando itens", "Atualizando catálogo, ordem e fotos de referência do checklist."),
            "materials": ("Carregando materiais", "Atualizando saldo, alertas de estoque e itens cadastrados."),
            "washes": ("Carregando lavagens", "Montando fila, histórico mensal e programação preventiva."),
            "activities": ("Carregando inspeções", "Montando conferências em massa, seleção e auditoria individual."),
            "maintenance": ("Carregando manutenção", "Montando cronograma mensal e tabela de programação."),
            "emergencies": ("Carregando emergenciais", "Buscando ocorrências, criticidade e ordens de serviço."),
            "pcm": ("Carregando PCM", "Consolidando planos preventivos, agenda e backlog."),
            "supply_library": ("Carregando suprimentos", "Montando depósitos, reservas e biblioteca técnica."),
            "reports": ("Montando relatórios", "Consolidando dados macro, micro e exportações."),
            "checklist_history": ("Carregando histórico", "Montando matriz de checklists por frota e data."),
            "vacations": ("Carregando férias", "Montando o calendário e os períodos programados."),
            "spreader_history": ("Carregando histórico", "Montando conferências diárias, vínculos e evidências dos Spreaders."),
            "users": ("Carregando acessos", "Atualizando perfis, logins e permissões disponíveis."),
            "cloud_backup": ("Verificando nuvem", "Consultando uso de banco, fotos e status do backup."),
            "audit_logs": ("Carregando auditoria", "Montando histórico completo de acessos e alterações."),
            "admin_rules": ("Carregando configuração", "Montando regras inteligentes e leitura de compatibilidade dos dados."),
        }
        title, subtitle = context_map.get(page_key, ("Carregando painel", "Preparando dados da tela atual."))
        self.loading_overlay.show_loading(title, subtitle)

    def toggle_sidebar(self):
        if not hasattr(self, "main_splitter"):
            return
        if self.sidebar_visible:
            left_size = 0
            try:
                sizes = self.main_splitter.sizes()
                left_size = int(sizes[0]) if sizes else 0
            except Exception:
                left_size = 0
            if left_size > 80:
                self._last_sidebar_width = left_size
            self.tree_panel.hide()
            self.main_splitter.setSizes([0, max(1, self.width())])
            self.sidebar_visible = False
            return

        self.tree_panel.setMinimumWidth(280)
        self.tree_panel.setMaximumWidth(380)
        self.tree_panel.show()
        target = int(getattr(self, "_last_sidebar_width", 300) or 300)
        if target < 280 or target > 380:
            target = 300
        self.main_splitter.setSizes([target, max(1, self.width() - target)])
        self.sidebar_visible = True
