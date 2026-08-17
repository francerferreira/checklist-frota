from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML_PATH = PROJECT_ROOT / "web_app" / "index.html"
LEGACY_README_PATH = PROJECT_ROOT / "web_app" / "static" / "js" / "README_LEGADO.txt"


class WebMobileShellContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        cls.legacy_readme = LEGACY_README_PATH.read_text(encoding="utf-8")

    def test_index_uses_canonical_frontend_bundle(self):
        self.assertIn('./static/js/app.js?v=20260816-10', self.index_html)
        self.assertIn('./static/css/styles.css?v=20260816-10', self.index_html)
        self.assertNotIn("app-20260419-", self.index_html)

    def test_frontend_uses_manaus_timezone_for_dates(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const MANAUS_TIME_ZONE = "America/Manaus"', app_js)
        self.assertIn("window.CHECKLIST_TIME_ZONE = MANAUS_TIME_ZONE", app_js)
        self.assertIn("formatManausDateTime", app_js)

    def test_frontend_expires_session_after_inactivity(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const SESSION_LAST_ACTIVITY_AT_KEY = "sessionLastActivityAt"', app_js)
        self.assertIn("const SESSION_INACTIVITY_LIMIT_MS = 30 * 60 * 1000", app_js)
        self.assertIn("expireSessionForInactivity", app_js)
        self.assertIn("trackSessionActivity", app_js)

    def test_non_conformity_macro_filter_and_photo_url_normalization_remain_available(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("selectedNonConformityItem", app_js)
        self.assertIn("filterChecklistNonConformitiesBySelectedItem", app_js)
        self.assertIn('data-nc-filter-item', app_js)
        self.assertIn("TIPOS DE NÃO CONFORMIDADE", app_js)
        self.assertNotIn("TOP ITENS COM NÃO CONFORMIDADE", app_js)
        self.assertIn('const normalizedPath = path.startsWith("/") ? path : `/${path}`;', app_js)

    def test_index_does_not_restore_removed_inline_fallbacks(self):
        self.assertNotIn("data-inline-fallback", self.index_html)
        self.assertNotIn("fetch(cssUrl", self.index_html)
        self.assertNotIn("stopImmediatePropagation", self.index_html)

    def test_operational_screens_and_wash_structure_remain_available(self):
        expected_fragments = [
            'id="open-checklist-history-menu"',
            'id="open-checklist-catalog-menu"',
            'id="open-rh-admin-menu"',
            'id="open-equipment-reports-menu"',
            'id="open-maintenance-reports-menu"',
            'id="open-maintenance-menu"',
            'id="open-availability-menu"',
            'id="open-technical-inspections-menu"',
            'id="checklist-history-screen"',
            'id="checklist-catalog-screen"',
            'id="checklist-catalog-list"',
            'id="checklist-catalog-modal"',
            'id="rh-admin-screen"',
            'id="rh-admin-employee-form"',
            'id="module-reports-screen"',
            'id="rh-admin-reports-panel"',
            'class="module-section history-filter-card"',
            'id="checklist-history-equipment-search"',
            'id="checklist-history-summary-card"',
            'id="maintenance-screen"',
            'id="availability-screen"',
            'id="availability-list"',
            'id="technical-inspections-screen"',
            'id="technical-inspection-form"',
            'id="open-technical-library-menu"',
            'id="technical-library-screen"',
            'id="technical-library-vehicle"',
            'id="wash-calendar"',
            'id="wash-day-panel"',
            'id="washes-list"',
            'id="pull-refresh-indicator"',
            'id="photo-viewer-modal"',
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)
        self.assertNotIn('id="checklist-history-apply-filter"', self.index_html)

    def test_checklist_catalog_admin_crud_is_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openChecklistCatalogMenu", app_js)
        self.assertIn('apiFetch("/checklist-itens?ativos=all")', app_js)
        self.assertIn('method: editingId ? "PUT" : "POST"', app_js)
        self.assertIn('method: "DELETE"', app_js)
        self.assertIn("hasWashReportAccess()", app_js)

    def test_rh_admin_web_area_is_connected_to_management_routes(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openRhAdminMenu", app_js)
        self.assertIn('apiFetch("/rh/gestao")', app_js)
        self.assertIn('apiFetch("/rh/colaboradores")', app_js)
        self.assertIn('method: editingId ? "PUT" : "POST"', app_js)
        self.assertIn("/rh/colaboradores/usuarios-disponiveis", app_js)
        self.assertIn("hasWashReportAccess()", app_js)

    def test_reports_are_scoped_inside_operational_modules(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("MODULE_REPORT_DEFINITIONS", app_js)
        self.assertIn('openModuleReports("equipment")', app_js)
        self.assertIn('openModuleReports("maintenance")', app_js)
        self.assertIn('data-rh-admin-tab="reports"', self.index_html)
        self.assertNotIn('id="open-central-reports-menu"', self.index_html)

    def test_admin_settings_web_area_is_restricted_and_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for fragment in [
            'id="open-admin-settings-menu"',
            'id="admin-settings-screen"',
            'id="admin-settings-feedback"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)
        self.assertIn("openAdminSettings", app_js)
        self.assertIn("hasAdminAccess()", app_js)
        self.assertIn('apiFetch("/usuarios")', app_js)
        self.assertIn('apiFetch("/admin/intelligent-rules")', app_js)
        self.assertIn('apiFetch("/admin/audit-health")', app_js)
        self.assertIn('data-admin-settings-action="purchase-import"', self.index_html)
        self.assertIn('id="admin-purchases-import-file"', app_js)
        self.assertIn("openAdminPurchaseImport", app_js)
        self.assertNotIn('id="open-public-admin-settings-menu"', self.index_html)

    def test_mmp_stock_web_flow_is_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for fragment in [
            'id="open-mmp-stock-menu"',
            'id="mmp-stock-screen"',
            'id="mmp-transfer-form"',
            'id="mmp-issue-form"',
            'id="mmp-stock-list"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)
        self.assertIn("openMmpStockMenu", app_js)
        self.assertIn('apiFetch("/suprimentos/depositos")', app_js)
        self.assertIn('apiFetch("/suprimentos/mmp/saldos")', app_js)
        self.assertIn('apiFetch("/suprimentos/transferencias"', app_js)
        self.assertIn('apiFetch("/suprimentos/mmp/saidas"', app_js)
        self.assertIn("scanMmpQr", app_js)

    def test_purchases_foundation_web_flow_is_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openPurchasesMenu", app_js)
        self.assertIn('apiFetch("/compras/solicitacoes")', app_js)
        self.assertIn('apiFetch("/compras/importacoes",', app_js)
        self.assertIn("submitPurchaseImport", app_js)
        self.assertIn("loadMaterialPurchaseHistory", app_js)
        self.assertIn('id="purchases-screen"', self.index_html)
        self.assertIn('id="purchases-material-history"', self.index_html)
        self.assertNotIn('id="purchases-import-panel"', self.index_html)
        self.assertNotIn('id="purchases-import-count"', self.index_html)
        self.assertIn("Solicitações, pedidos, notas fiscais, recebimentos e histórico de materiais.", self.index_html)
        self.assertIn('id="maintenance-kanban"', self.index_html)
        self.assertIn("renderMaintenanceKanban", app_js)
        self.assertIn("data-maintenance-filter", app_js)
        self.assertIn('id="open-planning-menu"', self.index_html)
        self.assertIn('id="planning-screen"', self.index_html)
        self.assertIn("openPlanningMenu", app_js)
        self.assertIn("renderPlanning", app_js)
        self.assertIn("/manutencao/visao?ano=", app_js)
        self.assertIn("excluir_checklist=true", app_js)

    def test_admin_catalogs_and_purchase_providers_are_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for fragment in [
            'id="open-admin-catalogs-menu"',
            'id="admin-catalogs-screen"',
            'data-admin-catalog-action="providers"',
            'id="purchases-provider-panel"',
            'id="purchases-provider-form"',
            'id="purchases-provider-list"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)
        self.assertIn("openAdminCatalogs", app_js)
        self.assertIn('apiFetch("/compras/provedores")', app_js)
        self.assertIn('method: providerId ? "PUT" : "POST"', app_js)
        self.assertIn('elements.purchasesProviderPanel?.classList.toggle("hidden", !hasAdminAccess())', app_js)

    def test_availability_and_hourmeter_mobile_operations_are_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openAvailabilityMenu", app_js)
        self.assertIn("submitOperationalStatus", app_js)
        self.assertIn("submitHourmeter", app_js)
        self.assertIn("/disponibilidade/visao", app_js)
        self.assertIn("/status-operacional", app_js)
        self.assertIn('submitMobileOperation("HORIMETRO"', app_js)
        self.assertIn("/operacao-mobile/sincronizar", app_js)
        self.assertIn('capture="environment"', app_js)

    def test_versioned_technical_inspection_and_offline_queue_are_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openTechnicalInspectionsMenu", app_js)
        self.assertIn("sendTechnicalInspectionDraft", app_js)
        self.assertIn("syncPendingTechnicalInspections", app_js)
        self.assertIn('const INSPECTION_QUEUE_STORE = "technicalInspectionQueue"', app_js)
        self.assertIn("/inspecoes-tecnicas/modelos", app_js)
        self.assertIn("/inspecoes-tecnicas/execucoes", app_js)

    def test_mobile_asset_access_and_operation_queue_are_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const MOBILE_OPERATION_QUEUE_STORE = "mobileOperationQueue"', app_js)
        self.assertIn("openMobileAssetByCode", app_js)
        self.assertIn("scanMobileAssetQr", app_js)
        self.assertIn("scanMobileAssetNfc", app_js)
        self.assertIn("syncPendingMobileOperations", app_js)
        self.assertIn("/operacao-mobile/sincronizar", app_js)
        self.assertIn("MANUTENCAO_ATUALIZAR_ITEM", app_js)
        self.assertIn("refreshPendingMaintenanceItemIds", app_js)
        self.assertIn('id="asset-access-code"', self.index_html)

    def test_vehicle_family_cards_show_counts_and_filter_by_family(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        for fragment in [
            'data-vehicle-family="LBS"',
            'data-vehicle-family="RTG"',
            'data-vehicle-family="SPREADER"',
            'id="vehicle-family-count-lbs"',
            'id="vehicle-family-count-rtg"',
            'id="vehicle-family-count-spreader"',
            'id="vehicle-family-screen"',
            'id="vehicle-family-screen-list"',
            'id="vehicles-list" class="vehicle-list hidden"',
            'id="asset-access-toggle"',
            'id="asset-access-panel" class="asset-access-panel hidden"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.index_html)
        self.assertIn("vehicleFamilyFilter", app_js)
        self.assertIn("getVehicleFamilyKey", app_js)
        self.assertIn("renderVehicleFamilyScreen", app_js)
        self.assertIn("toggleAssetAccessPanel", app_js)

    def test_vehicle_search_reveals_matching_equipment_on_family_screen(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('elements.vehiclesList.classList.toggle("hidden", !query)', app_js)
        self.assertIn("vehicle.nome", app_js)
        self.assertIn("vehicle.referencia", app_js)
        self.assertIn('color: #ffffff;', (PROJECT_ROOT / "web_app" / "static" / "css" / "styles.css").read_text(encoding="utf-8"))

    def test_preventive_services_remain_available_in_mobile_maintenance_flow(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openMaintenanceMenu", app_js)
        self.assertIn("/manutencao/visao", app_js)
        self.assertIn("renderMaintenance", app_js)
        self.assertIn("os_mais_antigas", app_js)

    def test_mobile_hr_journey_and_offline_read_cache_are_connected(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-hr-journey-menu"', self.index_html)
        self.assertIn('id="hr-journey-screen"', self.index_html)
        self.assertIn("openHrJourneyMenu", app_js)
        self.assertIn("/operacao-mobile/minha-jornada", app_js)
        self.assertIn('const OFFLINE_HR_JOURNEY_KEY = "offlineHrJourney"', app_js)
        self.assertIn('const OFFLINE_MAINTENANCE_KEY = "offlineMaintenanceOverview"', app_js)

    def test_mobile_weekly_dsr_is_connected_to_hr_routes(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-weekly-dsr-menu"', self.index_html)
        self.assertIn('id="weekly-dsr-screen"', self.index_html)
        self.assertIn("openWeeklyDsrMenu", app_js)
        self.assertIn("/rh/dsr-semanal", app_js)
        self.assertIn("isoWeekToMonday", app_js)

    def test_mobile_special_schedule_registers_dsr_by_employee(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="open-special-schedule-menu"', self.index_html)
        self.assertIn('id="special-schedule-screen"', self.index_html)
        self.assertIn("openSpecialScheduleMenu", app_js)
        self.assertIn("/rh/escalas-especiais", app_js)
        self.assertIn("confirmar-presenca", app_js)
        self.assertIn("nao-compareceu", app_js)
        self.assertIn("isoWeekStartForDate", app_js)

    def test_technical_library_is_available_for_field_consultation(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("openTechnicalLibraryMenu", app_js)
        self.assertIn("/biblioteca-tecnica?vehicle_id=", app_js)
        self.assertIn("openTechnicalDocument", app_js)

    def test_checklist_history_has_auto_filters_and_sortable_headers(self):
        app_js = (PROJECT_ROOT / "web_app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("updateChecklistHistoryEquipmentSearch", app_js)
        self.assertIn("scheduleChecklistHistoryFilters", app_js)
        self.assertIn("makeChecklistHistorySortHeader", app_js)
        self.assertIn("data-history-sort", app_js)

    def test_index_removes_screen_overlines_from_operational_shell(self):
        self.assertNotIn('class="overline"', self.index_html)

    def test_legacy_readme_keeps_app_js_as_single_frontend_reference(self):
        self.assertIn("app.js", self.legacy_readme)
        self.assertIn("arquivo canonico", self.legacy_readme.lower())


if __name__ == "__main__":
    unittest.main()
