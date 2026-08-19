const MODULE_ORDER = [
    "ILUMINAÇÃO",
    "CABINE E PAINEL",
    "MOTOR E FLUIDOS",
    "FREIOS E RODAGEM",
    "ACOPLAMENTO E ESTRUTURA",
    "EXTERNO E ACESSOS",
    "SEGURANÇA OPERACIONAL",
    "OUTROS",
];

const OFFLINE_DB_NAME = "checklist-live-offline";
const OFFLINE_DB_VERSION = 4;
const CHECKLIST_QUEUE_STORE = "checklistQueue";
const CHECKLIST_DRAFT_STORE = "checklistDrafts";
const INSPECTION_QUEUE_STORE = "technicalInspectionQueue";
const MOBILE_OPERATION_QUEUE_STORE = "mobileOperationQueue";
const OFFLINE_VEHICLES_KEY = "offlineVehicles";
const OFFLINE_CATALOG_KEY = "offlineCatalog";
const OFFLINE_INSPECTION_TEMPLATES_KEY = "offlineInspectionTemplates";
const OFFLINE_AVAILABILITY_KEY = "offlineAvailabilityOverview";
const OFFLINE_EMERGENCIES_KEY = "offlineEmergencies";
const OFFLINE_MAINTENANCE_KEY = "offlineMaintenanceOverview";
const OFFLINE_HR_JOURNEY_KEY = "offlineHrJourney";
const PORT_EQUIPMENT_FAMILIES = new Set(["LBS", "RTG", "SPREADER"]);
const ACTIVE_CHECKLIST_DRAFT_KEY = "activeChecklistDraftVehicleId";
const SESSION_STARTED_AT_KEY = "sessionStartedAt";
const SESSION_LAST_ACTIVITY_AT_KEY = "sessionLastActivityAt";
const SESSION_INACTIVITY_LIMIT_MS = 30 * 60 * 1000;
const THEME_STORAGE_KEY = "sisMmpTheme";
const NOTIFICATIONS_STORAGE_KEY = "sisMmpNotifications";
const NOTIFICATION_CENTER_STORAGE_KEY = "sisMmpNotificationCenter";
const NOTIFICATION_FILTER_STORAGE_KEY = "sisMmpNotificationFilters";
const NOTIFICATION_CENTER_LIMIT = 40;
const LANGUAGE_STORAGE_KEY = "sisMmpLanguage";
const DENSITY_STORAGE_KEY = "sisMmpDensity";
const appTopbar = document.querySelector(".app-topbar");
const PULL_REFRESH_TRIGGER_PX = 84;
const PULL_REFRESH_MAX_PX = 112;
const MANAUS_TIME_ZONE = "America/Manaus";
const MANAUS_DATE_TIME_FORMAT = new Intl.DateTimeFormat("pt-BR", {
    timeZone: MANAUS_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});
const MANAUS_DATE_TIME_SHORT_FORMAT = new Intl.DateTimeFormat("pt-BR", {
    timeZone: MANAUS_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
});
const MANAUS_DATE_PARTS_FORMAT = new Intl.DateTimeFormat("en-CA", {
    timeZone: MANAUS_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
});

window.CHECKLIST_TIME_ZONE = MANAUS_TIME_ZONE;

function getManausDateParts(date = new Date()) {
    const parts = Object.fromEntries(MANAUS_DATE_PARTS_FORMAT.formatToParts(date).map((part) => [part.type, part.value]));
    return {
        year: Number(parts.year),
        month: Number(parts.month),
        day: Number(parts.day),
    };
}

function getManausDateKey(date = new Date()) {
    const parts = getManausDateParts(date);
    return formatDateKey(parts.year, parts.month, parts.day);
}

function parseNaiveIsoDateTime(value) {
    const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?$/);
    if (!match) {
        return null;
    }
    return {
        year: match[1],
        month: match[2],
        day: match[3],
        hour: match[4],
        minute: match[5],
        second: match[6] || "00",
    };
}

function hasExplicitTimezone(value) {
    return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(String(value || ""));
}

function formatManausDateTime(value, { short = false } = {}) {
    if (!value) {
        return short ? "" : "-";
    }
    if (value instanceof Date) {
        return (short ? MANAUS_DATE_TIME_SHORT_FORMAT : MANAUS_DATE_TIME_FORMAT).format(value);
    }
    const raw = String(value);
    const naive = !hasExplicitTimezone(raw) ? parseNaiveIsoDateTime(raw) : null;
    if (naive) {
        return short
            ? `${naive.day}/${naive.month}, ${naive.hour}:${naive.minute}`
            : `${naive.day}/${naive.month}/${naive.year}, ${naive.hour}:${naive.minute}`;
    }
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) {
        return short ? "" : raw;
    }
    return (short ? MANAUS_DATE_TIME_SHORT_FORMAT : MANAUS_DATE_TIME_FORMAT).format(date);
}

const INITIAL_MANAUS_DATE = getManausDateParts();

function readJsonStorage(key, fallback = null) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
    } catch {
        localStorage.removeItem(key);
        return fallback;
    }
}

function hasValidSession() {
    const token = localStorage.getItem("token") || "";
    const user = readJsonStorage("user", null);
    const lastActivityAt = Number(
        localStorage.getItem(SESSION_LAST_ACTIVITY_AT_KEY)
            || localStorage.getItem(SESSION_STARTED_AT_KEY)
            || 0
    );
    return Boolean(token && user && lastActivityAt && Date.now() - lastActivityAt < SESSION_INACTIVITY_LIMIT_MS);
}

function saveSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    localStorage.setItem(SESSION_LAST_ACTIVITY_AT_KEY, String(Date.now()));
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
}

function clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem(SESSION_LAST_ACTIVITY_AT_KEY);
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
    document.body.classList.remove("first-access-only");
}

let sessionInactivityTimer = null;

function refreshSessionActivity() {
    if (!state.token || !state.user) {
        return;
    }
    localStorage.setItem(SESSION_LAST_ACTIVITY_AT_KEY, String(Date.now()));
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
    scheduleSessionInactivityCheck();
}

function resetLoginControls() {
    if (elements.loginForm) {
        elements.loginForm.reset();
    }
    if (elements.loginButton) {
        elements.loginButton.disabled = false;
        elements.loginButton.textContent = "Entrar";
    }
}

function expireSessionForInactivity() {
    state.token = "";
    state.user = null;
    state.selectedVehicle = null;
    if (sessionInactivityTimer) {
        window.clearTimeout(sessionInactivityTimer);
        sessionInactivityTimer = null;
    }
    closePasswordResetModal();
    clearSession();
    resetLoginControls();
    setActiveScreen("login");
    setLoginStatus("Sessao encerrada por 30 minutos de inatividade. Informe login e senha novamente.", true);
}

function scheduleSessionInactivityCheck() {
    if (sessionInactivityTimer) {
        window.clearTimeout(sessionInactivityTimer);
        sessionInactivityTimer = null;
    }
    if (!state.token || !state.user) {
        return;
    }
    const lastActivityAt = Number(localStorage.getItem(SESSION_LAST_ACTIVITY_AT_KEY) || 0);
    const remainingMs = SESSION_INACTIVITY_LIMIT_MS - (Date.now() - lastActivityAt);
    if (remainingMs <= 0) {
        expireSessionForInactivity();
        return;
    }
    sessionInactivityTimer = window.setTimeout(expireSessionForInactivity, remainingMs + 250);
}

function trackSessionActivity() {
    if (!state.token || !state.user) {
        return;
    }
    if (!hasValidSession()) {
        expireSessionForInactivity();
        return;
    }
    refreshSessionActivity();
}

const state = {
    apiBaseUrl: resolveApiBaseUrl(),
    token: "",
    user: null,
    firstAccessRequired: false,
    justCompletedFirstAccess: false,
    welcomePhotoData: "",
    firstAccessPhotoFile: null,
    firstAccessCameraStream: null,
    vehicles: [],
    catalog: {},
    activities: [],
    materials: [],
    washOverview: null,
    nonConformityMacro: [],
    nonConformityMicro: [],
    nonConformityChecklist: [],
    nonConformityMechanic: [],
    selectedNonConformityItem: "",
    maintenanceOverview: null,
    pendingMaintenanceItemIds: new Set(),
    preventives: { items: [], summary: {}, totalPlans: 0 },
    hrJourney: null,
    weeklyDsr: { employees: [], overview: null },
    specialSchedule: { employees: [], rows: [] },
    absenteeism: { rows: [], summary: {} },
    pendingAbsenteeismAtestado: null,
    availabilityOverview: null,
    availabilityFilters: { search: "", family: "TODOS", status: "" },
    technicalInspectionTemplates: [],
    emergencies: [],
    technicalDocuments: [],
    ncChecklistStatus: "abertas",
    ncMechanicStatus: "abertas",
    washYear: INITIAL_MANAUS_DATE.year,
    washMonth: INITIAL_MANAUS_DATE.month,
    selectedWashDate: "",
    selectedWashShiftTab: "TODOS",
    maintenanceYear: INITIAL_MANAUS_DATE.year,
    maintenanceMonth: INITIAL_MANAUS_DATE.month,
    selectedMaintenanceDate: "",
    maintenanceStatusFilter: "ABERTAS",
    maintenanceFamilyFilter: "TODOS",
    maintenanceDashboardView: "KANBAN",
    maintenanceDashboardFilter: "TODOS",
    planningStatusFilter: "ABERTAS",
    selectedActivity: null,
    selectedVehicle: null,
    focusedAvailabilityVehicleId: null,
    currentModule: "TODOS",
    vehicleFamilyFilter: "",
    currentChecklistDraftUpdatedAt: "",
    currentChecklistDraftRestored: false,
    checklistHistory: {
        tipo: "",
        dataInicio: "",
        dataFim: "",
        equipmentSearch: "",
        sortKey: "frota",
        sortDirection: "asc",
        columns: [],
        rows: [],
        expandedVehicleId: "",
    },
    checklistCatalogAdmin: {
        items: [],
        filters: { search: "", type: "", active: "true" },
        editingId: null,
        existingPhotoPath: "",
    },
    rhAdmin: {
        tab: "overview",
        overview: null,
        employees: [],
        editingEmployeeId: null,
        existingEmployeePhoto: "",
    },
    adminSettings: {
        feedbackTitle: "AGUARDANDO AÇÃO",
        feedbackHtml: "Escolha um controle acima para consultar seu estado.",
        users: [],
        editingUserId: null,
    },
    mmpStock: {
        warehouses: [],
        locations: [],
        mainStocks: [],
        mmpStocks: [],
        transfers: [],
        selectedStock: null,
    },
    purchases: {
        requests: [],
        pendingPcItems: [],
        orders: [],
        pendingInvoices: { pending_nf: [], pending_receipts: [] },
        processCenter: { summary: {}, items: [] },
        reportSummary: { summary: {}, by_status: {}, by_type: {}, by_provider: {} },
        reportSchedules: [],
        activeArea: "process",
        views: { process: "QUADRO", requests: "CARTOES", orders: "QUADRO", invoices: "QUADRO" },
        materialHistory: null,
        selectedRequestId: null,
        selectedInvoiceId: null,
        selectedInvoiceItemId: null,
        providers: [],
        editingProviderId: null,
    },
    moduleReports: "",
};

const screens = {
    login: document.getElementById("login-screen"),
    home: document.getElementById("home-screen"),
    vehicles: document.getElementById("vehicles-screen"),
    vehicleFamily: document.getElementById("vehicle-family-screen"),
    checklist: document.getElementById("checklist-screen"),
    activities: document.getElementById("activities-screen"),
    activityDetail: document.getElementById("activity-detail-screen"),
    washes: document.getElementById("washes-screen"),
    checklistHistory: document.getElementById("checklist-history-screen"),
    checklistCatalog: document.getElementById("checklist-catalog-screen"),
    rhAdmin: document.getElementById("rh-admin-screen"),
    adminSettings: document.getElementById("admin-settings-screen"),
    adminCatalogs: document.getElementById("admin-catalogs-screen"),
    purchases: document.getElementById("purchases-screen"),
    mmpStock: document.getElementById("mmp-stock-screen"),
    moduleReports: document.getElementById("module-reports-screen"),
    nonConformities: document.getElementById("non-conformities-screen"),
    maintenance: document.getElementById("maintenance-screen"),
    planning: document.getElementById("planning-screen"),
    preventives: document.getElementById("preventives-screen"),
    hrJourney: document.getElementById("hr-journey-screen"),
    weeklyDsr: document.getElementById("weekly-dsr-screen"),
    specialSchedule: document.getElementById("special-schedule-screen"),
    absenteeism: document.getElementById("absenteeism-screen"),
    availability: document.getElementById("availability-screen"),
    technicalInspections: document.getElementById("technical-inspections-screen"),
    emergencies: document.getElementById("emergencies-screen"),
    technicalLibrary: document.getElementById("technical-library-screen"),
    success: document.getElementById("success-screen"),
};

const elements = {
    mobileShell: document.querySelector(".mobile-shell"),
    topbarHomeButton: document.getElementById("topbar-home-button"),
    topbarMobileToggle: document.getElementById("topbar-mobile-toggle"),
    topbarNavigation: document.getElementById("topbar-navigation"),
    topbarContext: document.getElementById("topbar-context"),
    topbarUserName: document.getElementById("topbar-user-name"),
    topbarUserAvatar: document.getElementById("topbar-user-avatar"),
    topbarNotificationsButton: document.getElementById("topbar-notifications-button"),
    topbarNotificationsMenu: document.getElementById("topbar-notifications-menu"),
    topbarNotificationsBadge: document.getElementById("topbar-notifications-badge"),
    topbarNotificationsCount: document.getElementById("topbar-notifications-count"),
    topbarNotificationsList: document.getElementById("topbar-notifications-list"),
    topbarNotificationsMarkRead: document.getElementById("topbar-notifications-mark-read"),
    topbarNotificationsClear: document.getElementById("topbar-notifications-clear"),
    topbarNotificationsOriginFilter: document.getElementById("topbar-notifications-origin-filter"),
    topbarNotificationsPriorityFilter: document.getElementById("topbar-notifications-priority-filter"),
    topbarNotificationsFromFilter: document.getElementById("topbar-notifications-from-filter"),
    topbarNotificationsToFilter: document.getElementById("topbar-notifications-to-filter"),
    topbarNotificationsResetFilters: document.getElementById("topbar-notifications-reset-filters"),
    topbarNotificationsFilterSummary: document.getElementById("topbar-notifications-filter-summary"),
    topbarUserSettingsButton: document.getElementById("topbar-user-settings-button"),
    topbarSettingsMenu: document.getElementById("topbar-settings-menu"),
    topbarSettingsItems: Array.from(document.querySelectorAll("[data-settings-action]")),
    topbarNotificationsLabel: document.getElementById("topbar-notifications-label"),
    topbarLanguageSelect: document.getElementById("topbar-language-select"),
    topbarDensityLabel: document.getElementById("topbar-density-label"),
    topbarThemeLabel: document.getElementById("topbar-theme-label"),
    themeToggleButton: document.getElementById("theme-toggle-button"),
    topbarLogoutButton: document.getElementById("topbar-logout-button"),
    topbarModuleTriggers: Array.from(document.querySelectorAll("[data-topbar-module-trigger]")),
    topbarActionButtons: Array.from(document.querySelectorAll("[data-topbar-action]")),
    pullRefreshIndicator: document.getElementById("pull-refresh-indicator"),
    apiBaseUrl: document.getElementById("api-base-url"),
    loginForm: document.getElementById("login-form"),
    loginButton: document.getElementById("login-button"),
    forgotPasswordButton: document.getElementById("forgot-password-button"),
    adminResetPanel: document.getElementById("admin-reset-panel"),
    adminResetList: document.getElementById("admin-reset-list"),
    resetRequestModal: document.getElementById("reset-request-modal"),
    resetRequestForm: document.getElementById("reset-request-form"),
    resetRequestLogin: document.getElementById("reset-request-login"),
    resetRequestClose: document.getElementById("reset-request-close"),
    firstAccessModal: document.getElementById("first-access-modal"),
    firstAccessPhoto: document.getElementById("first-access-photo"),
    firstAccessCameraOpen: document.getElementById("first-access-camera-open"),
    firstAccessPhotoFile: document.getElementById("first-access-photo-file"),
    firstAccessCameraPanel: document.getElementById("first-access-camera-panel"),
    firstAccessCameraVideo: document.getElementById("first-access-camera-video"),
    firstAccessCameraCapture: document.getElementById("first-access-camera-capture"),
    firstAccessPhotoPreview: document.getElementById("first-access-photo-preview"),
    firstAccessPhotoPreviewImage: document.getElementById("first-access-photo-preview-image"),
    firstAccessPhotoRetake: document.getElementById("first-access-photo-retake"),
    firstAccessSignature: document.getElementById("first-access-signature"),
    firstAccessClear: document.getElementById("first-access-clear"),
    firstAccessBack: document.getElementById("first-access-back"),
    firstAccessSubmit: document.getElementById("first-access-submit"),
    firstAccessStatus: document.getElementById("first-access-status"),
    welcomeModal: document.getElementById("welcome-modal"),
    welcomePhotoWrap: document.getElementById("welcome-photo-wrap"),
    welcomePhoto: document.getElementById("welcome-photo"),
    welcomeInitials: document.getElementById("welcome-initials"),
    welcomeMessage: document.getElementById("welcome-message"),
    welcomeStart: document.getElementById("welcome-start"),
    vehiclesList: document.getElementById("vehicles-list"),
    vehicleSearch: document.getElementById("vehicle-search"),
    vehicleCounter: document.getElementById("vehicle-counter"),
    vehicleFamilyBackButton: document.getElementById("vehicle-family-back-button"),
    vehicleFamilyTitle: document.getElementById("vehicle-family-title"),
    vehicleFamilyScreenCounter: document.getElementById("vehicle-family-screen-counter"),
    vehicleFamilyScreenList: document.getElementById("vehicle-family-screen-list"),
    assetAccessToggle: document.getElementById("asset-access-toggle"),
    assetAccessPanel: document.getElementById("asset-access-panel"),
    vehicleFamilyCards: Array.from(document.querySelectorAll("[data-vehicle-family]")),
    vehicleFamilyCounts: {
        LBS: document.getElementById("vehicle-family-count-lbs"),
        RTG: document.getElementById("vehicle-family-count-rtg"),
        SPREADER: document.getElementById("vehicle-family-count-spreader"),
    },
    assetAccessCode: document.getElementById("asset-access-code"),
    openAssetCodeButton: document.getElementById("open-asset-code-button"),
    scanAssetQrButton: document.getElementById("scan-asset-qr-button"),
    scanAssetNfcButton: document.getElementById("scan-asset-nfc-button"),
    assetQrPreview: document.getElementById("asset-qr-preview"),
    userSummary: document.getElementById("user-summary"),
    checklistForm: document.getElementById("checklist-form"),
    checklistTitle: document.getElementById("checklist-title"),
    checklistSubtitle: document.getElementById("checklist-subtitle"),
    checklistProgress: document.getElementById("checklist-progress"),
    progressBar: document.getElementById("progress-bar"),
    moduleTabs: document.getElementById("module-tabs"),
    resetChecklist: document.getElementById("reset-checklist"),
    submitChecklist: document.getElementById("submit-checklist"),
    successSummary: document.getElementById("success-summary"),
    toast: document.getElementById("toast"),
    homeSummary: document.getElementById("home-summary"),
    syncPanel: document.getElementById("sync-panel"),
    syncCounter: document.getElementById("sync-counter"),
    syncList: document.getElementById("sync-list"),
    syncNowButton: document.getElementById("sync-now-button"),
    cloudAdminPanel: document.getElementById("cloud-admin-panel"),
    cloudStorageSummary: document.getElementById("cloud-storage-summary"),
    cloudStorageDetail: document.getElementById("cloud-storage-detail"),
    cloudBackupButton: document.getElementById("cloud-backup-button"),
    homeLogoutButton: document.getElementById("home-logout-button"),
    passwordModal: document.getElementById("password-modal"),
    passwordChangeForm: document.getElementById("password-change-form"),
    passwordCurrentInput: document.getElementById("password-current-input"),
    passwordNewInput: document.getElementById("password-new-input"),
    passwordConfirmInput: document.getElementById("password-confirm-input"),
    passwordChangeCancel: document.getElementById("password-change-cancel"),
    passwordChangeSubmit: document.getElementById("password-change-submit"),
    photoViewerModal: document.getElementById("photo-viewer-modal"),
    photoViewerImage: document.getElementById("photo-viewer-image"),
    openChecklistMenu: document.getElementById("open-checklist-menu"),
    openChecklistHistoryMenu: document.getElementById("open-checklist-history-menu"),
    openChecklistCatalogMenu: document.getElementById("open-checklist-catalog-menu"),
    openRhAdminMenu: document.getElementById("open-rh-admin-menu"),
    openAdminSettingsMenu: document.getElementById("open-admin-settings-menu"),
    openAdminCatalogsMenu: document.getElementById("open-admin-catalogs-menu"),
    openMmpStockMenu: document.getElementById("open-mmp-stock-menu"),
    openPurchasesMenu: document.getElementById("open-purchases-menu"),
    openPurchasesReportsMenu: document.getElementById("open-purchases-reports-menu"),
    openEquipmentReportsMenu: document.getElementById("open-equipment-reports-menu"),
    openMaintenanceReportsMenu: document.getElementById("open-maintenance-reports-menu"),
    openActivitiesMenu: document.getElementById("open-activities-menu"),
    openWashesMenu: document.getElementById("open-washes-menu"),
    openNonConformitiesMenu: document.getElementById("open-non-conformities-menu"),
    openMaintenanceMenu: document.getElementById("open-maintenance-menu"),
    openPlanningMenu: document.getElementById("open-planning-menu"),
    openPreventivesMenu: document.getElementById("open-preventives-menu"),
    openAvailabilityMenu: document.getElementById("open-availability-menu"),
    openTechnicalInspectionsMenu: document.getElementById("open-technical-inspections-menu"),
    openEmergenciesMenu: document.getElementById("open-emergencies-menu"),
    openTechnicalLibraryMenu: document.getElementById("open-technical-library-menu"),
    openMaintenanceDashboardMenu: document.getElementById("open-maintenance-dashboard-menu"),
    openHrJourneyMenu: document.getElementById("open-hr-journey-menu"),
    openWeeklyDsrMenu: document.getElementById("open-weekly-dsr-menu"),
    openSpecialScheduleMenu: document.getElementById("open-special-schedule-menu"),
    openAbsenteeismMenu: document.getElementById("open-absenteeism-menu"),
    vehiclesBackButton: document.getElementById("vehicles-back-button"),
    activitiesBackButton: document.getElementById("activities-back-button"),
    activityCounter: document.getElementById("activity-counter"),
    activitiesList: document.getElementById("activities-list"),
    activityDetailBackButton: document.getElementById("activity-detail-back-button"),
    activityTitle: document.getElementById("activity-title"),
    activitySummary: document.getElementById("activity-summary"),
    activityItemsList: document.getElementById("activity-items-list"),
    washesBackButton: document.getElementById("washes-back-button"),
    checklistHistoryBackButton: document.getElementById("checklist-history-back-button"),
    checklistHistoryCounter: document.getElementById("checklist-history-counter"),
    checklistHistoryEquipmentSearch: document.getElementById("checklist-history-equipment-search"),
    checklistHistoryTypeFilter: document.getElementById("checklist-history-type-filter"),
    checklistHistoryStartDate: document.getElementById("checklist-history-start-date"),
    checklistHistoryEndDate: document.getElementById("checklist-history-end-date"),
    checklistHistorySummaryCard: document.getElementById("checklist-history-summary-card"),
    checklistHistoryTableWrap: document.getElementById("checklist-history-table-wrap"),
    checklistCatalogBackButton: document.getElementById("checklist-catalog-back-button"),
    checklistCatalogNewButton: document.getElementById("checklist-catalog-new-button"),
    checklistCatalogCounter: document.getElementById("checklist-catalog-counter"),
    checklistCatalogSearch: document.getElementById("checklist-catalog-search"),
    checklistCatalogTypeFilter: document.getElementById("checklist-catalog-type-filter"),
    checklistCatalogActiveFilter: document.getElementById("checklist-catalog-active-filter"),
    checklistCatalogClearFilters: document.getElementById("checklist-catalog-clear-filters"),
    checklistCatalogSummary: document.getElementById("checklist-catalog-summary"),
    checklistCatalogList: document.getElementById("checklist-catalog-list"),
    checklistCatalogModal: document.getElementById("checklist-catalog-modal"),
    checklistCatalogModalTitle: document.getElementById("checklist-catalog-modal-title"),
    checklistCatalogForm: document.getElementById("checklist-catalog-form"),
    checklistCatalogItemName: document.getElementById("checklist-catalog-item-name"),
    checklistCatalogItemType: document.getElementById("checklist-catalog-item-type"),
    checklistCatalogPosition: document.getElementById("checklist-catalog-position"),
    checklistCatalogGroupType: document.getElementById("checklist-catalog-group-type"),
    checklistCatalogParentItem: document.getElementById("checklist-catalog-parent-item"),
    checklistCatalogPart: document.getElementById("checklist-catalog-part"),
    checklistCatalogPhoto: document.getElementById("checklist-catalog-photo"),
    checklistCatalogPhotoStatus: document.getElementById("checklist-catalog-photo-status"),
    checklistCatalogItemActive: document.getElementById("checklist-catalog-item-active"),
    checklistCatalogCancel: document.getElementById("checklist-catalog-cancel"),
    checklistCatalogSave: document.getElementById("checklist-catalog-save"),
    rhAdminBackButton: document.getElementById("rh-admin-back-button"),
    rhAdminRoleBadge: document.getElementById("rh-admin-role-badge"),
    rhAdminTabs: Array.from(document.querySelectorAll("[data-rh-admin-tab]")),
    rhAdminOverviewPanel: document.getElementById("rh-admin-overview-panel"),
    rhAdminEmployeesPanel: document.getElementById("rh-admin-employees-panel"),
    rhAdminOperationsPanel: document.getElementById("rh-admin-operations-panel"),
    rhAdminReportsPanel: document.getElementById("rh-admin-reports-panel"),
    rhAdminRefreshOverview: document.getElementById("rh-admin-refresh-overview"),
    rhAdminOverviewCards: document.getElementById("rh-admin-overview-cards"),
    rhAdminAlertCount: document.getElementById("rh-admin-alert-count"),
    rhAdminAlertList: document.getElementById("rh-admin-alert-list"),
    rhAdminTeamList: document.getElementById("rh-admin-team-list"),
    rhAdminNewEmployee: document.getElementById("rh-admin-new-employee"),
    rhAdminEmployeeSearch: document.getElementById("rh-admin-employee-search"),
    rhAdminEmployeeStatus: document.getElementById("rh-admin-employee-status"),
    rhAdminRefreshEmployees: document.getElementById("rh-admin-refresh-employees"),
    rhAdminEmployeesCounter: document.getElementById("rh-admin-employees-counter"),
    rhAdminEmployeesList: document.getElementById("rh-admin-employees-list"),
    rhAdminEmployeeModal: document.getElementById("rh-admin-employee-modal"),
    rhAdminEmployeeModalTitle: document.getElementById("rh-admin-employee-modal-title"),
    rhAdminEmployeeForm: document.getElementById("rh-admin-employee-form"),
    rhAdminEmployeeRegistration: document.getElementById("rh-admin-employee-registration"),
    rhAdminEmployeeName: document.getElementById("rh-admin-employee-name"),
    rhAdminEmployeeFunction: document.getElementById("rh-admin-employee-function"),
    rhAdminEmployeeTeam: document.getElementById("rh-admin-employee-team"),
    rhAdminEmployeeShift: document.getElementById("rh-admin-employee-shift"),
    rhAdminEmployeeStatusField: document.getElementById("rh-admin-employee-status-field"),
    rhAdminEmployeeHiredOn: document.getElementById("rh-admin-employee-hired-on"),
    rhAdminEmployeeUser: document.getElementById("rh-admin-employee-user"),
    rhAdminEmployeeNotes: document.getElementById("rh-admin-employee-notes"),
    rhAdminEmployeePhoto: document.getElementById("rh-admin-employee-photo"),
    rhAdminEmployeePhotoStatus: document.getElementById("rh-admin-employee-photo-status"),
    rhAdminEmployeeCancel: document.getElementById("rh-admin-employee-cancel"),
    rhAdminEmployeeSave: document.getElementById("rh-admin-employee-save"),
    adminSettingsBackButton: document.getElementById("admin-settings-back-button"),
    adminSettingsRoleBadge: document.getElementById("admin-settings-role-badge"),
    adminSettingsGrid: document.getElementById("admin-settings-grid"),
    adminSettingsFeedback: document.getElementById("admin-settings-feedback"),
    adminSettingsFeedbackContent: document.getElementById("admin-settings-feedback-content"),
    adminUserModal: document.getElementById("admin-user-modal"),
    adminUserForm: document.getElementById("admin-user-form"),
    adminUserModalTitle: document.getElementById("admin-user-modal-title"),
    adminUserId: document.getElementById("admin-user-id"),
    adminUserName: document.getElementById("admin-user-name"),
    adminUserLogin: document.getElementById("admin-user-login"),
    adminUserType: document.getElementById("admin-user-type"),
    adminUserPassword: document.getElementById("admin-user-password"),
    adminUserActive: document.getElementById("admin-user-active"),
    adminUserCancel: document.getElementById("admin-user-cancel"),
    adminCatalogsBackButton: document.getElementById("admin-catalogs-back-button"),
    adminCatalogsGrid: document.getElementById("admin-catalogs-grid"),
    mmpStockBackButton: document.getElementById("mmp-stock-back-button"),
    mmpStockRoleBadge: document.getElementById("mmp-stock-role-badge"),
    mmpAdminPanel: document.getElementById("mmp-admin-panel"),
    mmpOperationPanel: document.getElementById("mmp-operation-panel"),
    mmpCreatePrincipalButton: document.getElementById("mmp-create-principal-button"),
    mmpCreateWarehouseButton: document.getElementById("mmp-create-warehouse-button"),
    mmpLocationForm: document.getElementById("mmp-location-form"),
    mmpLocationWarehouse: document.getElementById("mmp-location-warehouse"),
    mmpLocationShelf: document.getElementById("mmp-location-shelf"),
    mmpLocationCode: document.getElementById("mmp-location-code"),
    mmpLocationPosition: document.getElementById("mmp-location-position"),
    mmpTransferForm: document.getElementById("mmp-transfer-form"),
    mmpTransferLocation: document.getElementById("mmp-transfer-location"),
    mmpMainStockList: document.getElementById("mmp-main-stock-list"),
    mmpAdminFeedback: document.getElementById("mmp-admin-feedback"),
    mmpQrCode: document.getElementById("mmp-qr-code"),
    mmpLookupButton: document.getElementById("mmp-lookup-button"),
    mmpScanQrButton: document.getElementById("mmp-scan-qr-button"),
    mmpQrPreview: document.getElementById("mmp-qr-preview"),
    mmpSelectedStock: document.getElementById("mmp-selected-stock"),
    mmpIssueForm: document.getElementById("mmp-issue-form"),
    mmpIssueQuantity: document.getElementById("mmp-issue-quantity"),
    mmpIssueVehicle: document.getElementById("mmp-issue-vehicle"),
    purchasesBackButton: document.getElementById("purchases-back-button"),
    purchasesRoleBadge: document.getElementById("purchases-role-badge"),
    purchasesOpenCount: document.getElementById("purchases-open-count"),
    purchasesAwaitingPcCount: document.getElementById("purchases-awaiting-pc-count"),
    purchasesAwaitingNfCount: document.getElementById("purchases-awaiting-nf-count"),
    purchasesRequestsCount: document.getElementById("purchases-requests-count"),
    purchasesRequestSearch: document.getElementById("purchases-request-search"),
    purchasesRequestStatus: document.getElementById("purchases-request-status"),
    purchasesRequestSort: document.getElementById("purchases-request-sort"),
    purchasesRequestList: document.getElementById("purchases-request-list"),
    purchasesRequestNew: document.getElementById("purchases-request-new"),
    purchaseRequestModal: document.getElementById("purchase-request-modal"),
    purchaseRequestForm: document.getElementById("purchase-request-form"),
    purchaseRequestScDate: document.getElementById("purchase-request-sc-date"),
    purchaseRequestQuote: document.getElementById("purchase-request-quote"),
    purchaseRequestRequester: document.getElementById("purchase-request-requester"),
    purchaseRequestCostCenter: document.getElementById("purchase-request-cost-center"),
    purchaseRequestModule: document.getElementById("purchase-request-module"),
    purchaseRequestEquipment: document.getElementById("purchase-request-equipment"),
    purchaseRequestWorkOrder: document.getElementById("purchase-request-work-order"),
    purchaseRequestItems: document.getElementById("purchase-request-items"),
    purchaseRequestAddItem: document.getElementById("purchase-request-add-item"),
    purchaseRequestPriority: document.getElementById("purchase-request-priority"),
    purchaseRequestExpectedDate: document.getElementById("purchase-request-expected-date"),
    purchaseRequestObservation: document.getElementById("purchase-request-observation"),
    purchaseRequestCancel: document.getElementById("purchase-request-cancel"),
    purchaseRequestSubmit: document.getElementById("purchase-request-submit"),
    purchaseDetailModal: document.getElementById("purchase-detail-modal"),
    purchaseDetailTitle: document.getElementById("purchase-detail-title"),
    purchaseDetailContent: document.getElementById("purchase-detail-content"),
    purchaseDetailClose: document.getElementById("purchase-detail-close"),
    purchaseDetailApprove: document.getElementById("purchase-detail-approve"),
    purchaseDetailReceive: document.getElementById("purchase-detail-receive"),
    purchaseReceiveModal: document.getElementById("purchase-receive-modal"),
    purchaseReceiveForm: document.getElementById("purchase-receive-form"),
    purchaseReceiveId: document.getElementById("purchase-receive-id"),
    purchaseReceiveQuantity: document.getElementById("purchase-receive-quantity"),
    purchaseReceiveInvoiceNumber: document.getElementById("purchase-receive-invoice-number"),
    purchaseReceiveInvoiceSeries: document.getElementById("purchase-receive-invoice-series"),
    purchaseReceiveInvoiceDate: document.getElementById("purchase-receive-invoice-date"),
    purchaseReceiveInvoiceValue: document.getElementById("purchase-receive-invoice-value"),
    purchaseReceiveInvoice: document.getElementById("purchase-receive-invoice"),
    purchaseReceiveNotes: document.getElementById("purchase-receive-notes"),
    purchaseReceiveCancel: document.getElementById("purchase-receive-cancel"),
    purchaseReceiveHelp: document.getElementById("purchase-receive-help"),
    purchasesProviderPanel: document.getElementById("purchases-provider-panel"),
    purchasesOrdersPendingCount: document.getElementById("purchases-orders-pending-count"),
    purchasesOrdersRefresh: document.getElementById("purchases-orders-refresh"),
    purchaseOrderForm: document.getElementById("purchase-order-form"),
    purchaseOrderNumber: document.getElementById("purchase-order-number"),
    purchaseOrderDate: document.getElementById("purchase-order-date"),
    purchaseOrderProvider: document.getElementById("purchase-order-provider"),
    purchaseOrderDeliveryDate: document.getElementById("purchase-order-delivery-date"),
    purchaseOrderTotal: document.getElementById("purchase-order-total"),
    purchaseOrderPaymentTerms: document.getElementById("purchase-order-payment-terms"),
    purchaseOrderNotes: document.getElementById("purchase-order-notes"),
    purchaseOrderPendingList: document.getElementById("purchase-order-pending-list"),
    purchaseOrderSubmit: document.getElementById("purchase-order-submit"),
    purchasesInvoicesPendingCount: document.getElementById("purchases-invoices-pending-count"),
    purchasesReceiptsPendingCount: document.getElementById("purchases-receipts-pending-count"),
    purchasesInvoicesRefresh: document.getElementById("purchases-invoices-refresh"),
    purchasesInvoicePendingList: document.getElementById("purchases-invoice-pending-list"),
    purchasesReceiptPendingList: document.getElementById("purchases-receipt-pending-list"),
    purchasesProcessCenterCount: document.getElementById("purchases-process-center-count"),
    purchasesProcessPcCount: document.getElementById("purchases-process-pc-count"),
    purchasesProcessNfCount: document.getElementById("purchases-process-nf-count"),
    purchasesProcessReceiptCount: document.getElementById("purchases-process-receipt-count"),
    purchasesProcessCenterRefresh: document.getElementById("purchases-process-center-refresh"),
    purchasesProcessSearch: document.getElementById("purchases-process-search"),
    purchasesProcessStatus: document.getElementById("purchases-process-status"),
    purchasesProcessType: document.getElementById("purchases-process-type"),
    purchasesProcessList: document.getElementById("purchases-process-list"),
    purchasesReportRefresh: document.getElementById("purchases-report-refresh"),
    purchasesReportExportPdf: document.getElementById("purchases-report-export-pdf"),
    purchasesReportExportXlsx: document.getElementById("purchases-report-export-xlsx"),
    purchasesReportDateFrom: document.getElementById("purchases-report-date-from"),
    purchasesReportDateTo: document.getElementById("purchases-report-date-to"),
    purchasesReportMetrics: document.getElementById("purchases-report-metrics"),
    purchasesReportStatusList: document.getElementById("purchases-report-status-list"),
    purchasesReportTypeList: document.getElementById("purchases-report-type-list"),
    purchasesReportProviderList: document.getElementById("purchases-report-provider-list"),
    purchasesReportSchedulesPanel: document.getElementById("purchases-report-schedules-panel"),
    purchasesReportScheduleForm: document.getElementById("purchases-report-schedule-form"),
    purchasesReportScheduleName: document.getElementById("purchases-report-schedule-name"),
    purchasesReportScheduleFrequency: document.getElementById("purchases-report-schedule-frequency"),
    purchasesReportSchedulePeriodDays: document.getElementById("purchases-report-schedule-period-days"),
    purchasesReportScheduleFormat: document.getElementById("purchases-report-schedule-format"),
    purchasesReportScheduleNextRun: document.getElementById("purchases-report-schedule-next-run"),
    purchasesReportSchedulesList: document.getElementById("purchases-report-schedules-list"),
    purchasesReportsPanel: document.querySelector(".purchases-reports-panel"),
    purchasesWorkflowNav: document.getElementById("purchases-workflow-nav"),
    purchasesProcessBoard: document.getElementById("purchases-process-board"),
    purchasesRequestBoard: document.getElementById("purchases-request-board"),
    purchasesOrderBoard: document.getElementById("purchases-order-board"),
    purchasesInvoiceBoard: document.getElementById("purchases-invoice-board"),
    purchaseInvoiceModal: document.getElementById("purchase-invoice-modal"),
    purchaseInvoiceForm: document.getElementById("purchase-invoice-form"),
    purchaseInvoicePcId: document.getElementById("purchase-invoice-pc-id"),
    purchaseInvoiceNumber: document.getElementById("purchase-invoice-number"),
    purchaseInvoiceSeries: document.getElementById("purchase-invoice-series"),
    purchaseInvoiceDate: document.getElementById("purchase-invoice-date"),
    purchaseInvoiceValue: document.getElementById("purchase-invoice-value"),
    purchaseInvoiceFile: document.getElementById("purchase-invoice-file"),
    purchaseInvoiceItems: document.getElementById("purchase-invoice-items"),
    purchaseInvoiceNotes: document.getElementById("purchase-invoice-notes"),
    purchaseInvoiceCancel: document.getElementById("purchase-invoice-cancel"),
    purchaseInvoiceSubmit: document.getElementById("purchase-invoice-submit"),
    purchaseInvoiceReceiveModal: document.getElementById("purchase-invoice-receive-modal"),
    purchaseInvoiceReceiveForm: document.getElementById("purchase-invoice-receive-form"),
    purchaseInvoiceReceiveId: document.getElementById("purchase-invoice-receive-id"),
    purchaseInvoiceReceiveItemId: document.getElementById("purchase-invoice-receive-item-id"),
    purchaseInvoiceReceiveQuantity: document.getElementById("purchase-invoice-receive-quantity"),
    purchaseInvoiceReceiveNotes: document.getElementById("purchase-invoice-receive-notes"),
    purchaseInvoiceReceiveCancel: document.getElementById("purchase-invoice-receive-cancel"),
    purchaseInvoiceReceiveHelp: document.getElementById("purchase-invoice-receive-help"),
    purchasesProviderEditor: document.getElementById("purchases-provider-editor"),
    purchasesProviderEditorTitle: document.getElementById("purchases-provider-editor-title"),
    purchasesProviderNew: document.getElementById("purchases-provider-new"),
    purchasesProviderCount: document.getElementById("purchases-provider-count"),
    purchasesProviderForm: document.getElementById("purchases-provider-form"),
    purchasesProviderCode: document.getElementById("purchases-provider-code"),
    purchasesProviderName: document.getElementById("purchases-provider-name"),
    purchasesProviderLegalName: document.getElementById("purchases-provider-legal-name"),
    purchasesProviderTradeName: document.getElementById("purchases-provider-trade-name"),
    purchasesProviderTaxId: document.getElementById("purchases-provider-tax-id"),
    purchasesProviderContact: document.getElementById("purchases-provider-contact"),
    purchasesProviderEmail: document.getElementById("purchases-provider-email"),
    purchasesProviderPhone: document.getElementById("purchases-provider-phone"),
    purchasesProviderNotes: document.getElementById("purchases-provider-notes"),
    purchasesProviderActive: document.getElementById("purchases-provider-active"),
    purchasesProviderHomologated: document.getElementById("purchases-provider-homologated"),
    purchasesProviderPreferred: document.getElementById("purchases-provider-preferred"),
    purchasesProviderSubmit: document.getElementById("purchases-provider-submit"),
    purchasesProviderCancel: document.getElementById("purchases-provider-cancel"),
    purchasesProviderList: document.getElementById("purchases-provider-list"),
    purchasesMaterialId: document.getElementById("purchases-material-id"),
    purchasesMaterialHistoryButton: document.getElementById("purchases-material-history-button"),
    purchasesMaterialHistory: document.getElementById("purchases-material-history"),
    mmpIssueApplication: document.getElementById("mmp-issue-application"),
    mmpRefreshButton: document.getElementById("mmp-refresh-button"),
    mmpStockSummary: document.getElementById("mmp-stock-summary"),
    mmpStockList: document.getElementById("mmp-stock-list"),
    mmpTransferHistory: document.getElementById("mmp-transfer-history"),
    moduleReportsBackButton: document.getElementById("module-reports-back-button"),
    moduleReportsTitle: document.getElementById("module-reports-title"),
    moduleReportsSubtitle: document.getElementById("module-reports-subtitle"),
    moduleReportsBadge: document.getElementById("module-reports-badge"),
    moduleReportsContext: document.getElementById("module-reports-context"),
    moduleReportsList: document.getElementById("module-reports-list"),
    washCounter: document.getElementById("wash-counter"),
    washMonthTitle: document.getElementById("wash-month-title"),
    washPrevMonth: document.getElementById("wash-prev-month"),
    washNextMonth: document.getElementById("wash-next-month"),
    washReportPanel: document.getElementById("wash-report-panel"),
    washExportPdfButton: document.getElementById("wash-export-pdf-button"),
    washCalendar: document.getElementById("wash-calendar"),
    washDayPanel: document.getElementById("wash-day-panel"),
    washesList: document.getElementById("washes-list"),
    nonConformitiesBackButton: document.getElementById("non-conformities-back-button"),
    nonConformitiesSummary: document.getElementById("non-conformities-summary"),
    nonConformitiesCounter: document.getElementById("non-conformities-counter"),
    nonConformitiesMacroCounter: document.getElementById("non-conformities-macro-counter"),
    nonConformitiesChecklistCounter: document.getElementById("non-conformities-checklist-counter"),
    nonConformitiesMechanicCounter: document.getElementById("non-conformities-mechanic-counter"),
    nonConformitiesMacroList: document.getElementById("non-conformities-macro-list"),
    nonConformitiesMicroList: document.getElementById("non-conformities-micro-list"),
    nonConformitiesChecklistList: document.getElementById("non-conformities-checklist-list"),
    nonConformitiesMechanicList: document.getElementById("non-conformities-mechanic-list"),
    nonConformitiesTotalToolbar: document.getElementById("non-conformities-total-toolbar"),
    nonConformitiesFilterSection: document.getElementById("non-conformities-filter-section"),
    nonConformitiesChecklistSection: document.getElementById("non-conformities-checklist-section"),
    nonConformitiesMechanicSection: document.getElementById("non-conformities-mechanic-section"),
    maintenanceBackButton: document.getElementById("maintenance-back-button"),
    maintenanceCounter: document.getElementById("maintenance-counter"),
    maintenanceSummary: document.getElementById("maintenance-summary"),
    maintenanceMonthTitle: document.getElementById("maintenance-month-title"),
    maintenancePrevMonth: document.getElementById("maintenance-prev-month"),
    maintenanceNextMonth: document.getElementById("maintenance-next-month"),
    maintenanceFamilyTabs: Array.from(document.querySelectorAll("[data-maintenance-family]")),
    maintenanceViewButtons: Array.from(document.querySelectorAll("[data-maintenance-view]")),
    maintenanceDashboardFilterButtons: Array.from(document.querySelectorAll("[data-maintenance-dashboard-filter]")),
    maintenanceCalendar: document.getElementById("maintenance-calendar"),
    maintenanceDayPanel: document.getElementById("maintenance-day-panel"),
    maintenanceKanban: document.getElementById("maintenance-kanban"),
    maintenanceTableWrap: document.getElementById("maintenance-table-wrap"),
    maintenanceTableBody: document.getElementById("maintenance-table-body"),
    maintenanceCards: document.getElementById("maintenance-cards"),
    maintenanceList: document.getElementById("maintenance-list"),
    planningBackButton: document.getElementById("planning-back-button"),
    planningCounter: document.getElementById("planning-counter"),
    planningPeriodLabel: document.getElementById("planning-period-label"),
    planningMonthTitle: document.getElementById("planning-month-title"),
    planningPrevMonth: document.getElementById("planning-prev-month"),
    planningNextMonth: document.getElementById("planning-next-month"),
    planningRefreshButton: document.getElementById("planning-refresh-button"),
    planningSummary: document.getElementById("planning-summary"),
    planningList: document.getElementById("planning-list"),
    planningFilterButtons: Array.from(document.querySelectorAll("[data-planning-filter]")),
    preventivesBackButton: document.getElementById("preventives-back-button"),
    preventivesCounter: document.getElementById("preventives-counter"),
    preventivesSummary: document.getElementById("preventives-summary"),
    preventivesList: document.getElementById("preventives-list"),
    hrJourneyBackButton: document.getElementById("hr-journey-back-button"),
    hrJourneyCounter: document.getElementById("hr-journey-counter"),
    hrJourneySummary: document.getElementById("hr-journey-summary"),
    hrJourneyList: document.getElementById("hr-journey-list"),
    weeklyDsrBackButton: document.getElementById("weekly-dsr-back-button"),
    weeklyDsrWeek: document.getElementById("weekly-dsr-week"),
    weeklyDsrRefreshButton: document.getElementById("weekly-dsr-refresh-button"),
    weeklyDsrCounter: document.getElementById("weekly-dsr-counter"),
    weeklyDsrSummary: document.getElementById("weekly-dsr-summary"),
    weeklyDsrList: document.getElementById("weekly-dsr-list"),
    weeklyDsrSaveButton: document.getElementById("weekly-dsr-save-button"),
    weeklyDsrSearch: document.getElementById("weekly-dsr-search"),
    weeklyDsrArea: document.getElementById("weekly-dsr-area"),
    weeklyDsrTeam: document.getElementById("weekly-dsr-team"),
    weeklyDsrShift: document.getElementById("weekly-dsr-shift"),
    weeklyDsrFunction: document.getElementById("weekly-dsr-function"),
    specialScheduleBackButton: document.getElementById("special-schedule-back-button"),
    specialScheduleDate: document.getElementById("special-schedule-date"),
    specialScheduleType: document.getElementById("special-schedule-type"),
    specialScheduleHolidayLabel: document.getElementById("special-schedule-holiday-label"),
    specialScheduleHolidayName: document.getElementById("special-schedule-holiday-name"),
    specialScheduleDsrLabel: document.getElementById("special-schedule-dsr-label"),
    specialScheduleDsrActions: document.getElementById("special-schedule-dsr-actions"),
    specialScheduleDefaultDsr: document.getElementById("special-schedule-default-dsr"),
    specialScheduleRefreshButton: document.getElementById("special-schedule-refresh-button"),
    specialScheduleCounter: document.getElementById("special-schedule-counter"),
    specialScheduleSummary: document.getElementById("special-schedule-summary"),
    specialScheduleList: document.getElementById("special-schedule-list"),
    specialScheduleSaveButton: document.getElementById("special-schedule-save-button"),
    specialScheduleSearch: document.getElementById("special-schedule-search"),
    specialScheduleArea: document.getElementById("special-schedule-area"),
    specialScheduleTeam: document.getElementById("special-schedule-team"),
    specialScheduleShift: document.getElementById("special-schedule-shift"),
    specialScheduleFunction: document.getElementById("special-schedule-function"),
    specialScheduleSelectAll: document.getElementById("special-schedule-select-all"),
    specialScheduleSelectedCount: document.getElementById("special-schedule-selected-count"),
    specialScheduleHistoryButton: document.getElementById("special-schedule-history-button"),
    specialSchedulePdfButton: document.getElementById("special-schedule-pdf-button"),
    specialScheduleHistoryModal: document.getElementById("special-schedule-history-modal"),
    specialScheduleHistoryDate: document.getElementById("special-schedule-history-date"),
    specialScheduleHistoryLoad: document.getElementById("special-schedule-history-load"),
    specialScheduleHistoryClose: document.getElementById("special-schedule-history-close"),
    specialScheduleHistoryList: document.getElementById("special-schedule-history-list"),
    absenteeismBackButton: document.getElementById("absenteeism-back-button"), absenteeismDate: document.getElementById("absenteeism-date"), absenteeismName: document.getElementById("absenteeism-name"), absenteeismRegistration: document.getElementById("absenteeism-registration"), absenteeismShift: document.getElementById("absenteeism-shift"), absenteeismSector: document.getElementById("absenteeism-sector"), absenteeismFunction: document.getElementById("absenteeism-function"), absenteeismStatus: document.getElementById("absenteeism-status"), absenteeismRefreshButton: document.getElementById("absenteeism-refresh-button"), absenteeismPdfButton: document.getElementById("absenteeism-pdf-button"), absenteeismCounter: document.getElementById("absenteeism-counter"), absenteeismSummary: document.getElementById("absenteeism-summary"), absenteeismList: document.getElementById("absenteeism-list"), absenteeismSaveButton: document.getElementById("absenteeism-save-button"), absenteeismAtestadoModal: document.getElementById("absenteeism-atestado-modal"), absenteeismAtestadoForm: document.getElementById("absenteeism-atestado-form"), absenteeismAtestadoEmployee: document.getElementById("absenteeism-atestado-employee"), absenteeismAtestadoStart: document.getElementById("absenteeism-atestado-start"), absenteeismAtestadoDays: document.getElementById("absenteeism-atestado-days"), absenteeismAtestadoEnd: document.getElementById("absenteeism-atestado-end"), absenteeismAtestadoNotes: document.getElementById("absenteeism-atestado-notes"), absenteeismAtestadoCancel: document.getElementById("absenteeism-atestado-cancel"),
    availabilityBackButton: document.getElementById("availability-back-button"),
    availabilityCounter: document.getElementById("availability-counter"),
    availabilitySummary: document.getElementById("availability-summary"),
    availabilityList: document.getElementById("availability-list"),
    availabilitySearch: document.getElementById("availability-search"),
    availabilityStatusFilter: document.getElementById("availability-status-filter"),
    availabilityClearFilters: document.getElementById("availability-clear-filters"),
    availabilityFamilyTabs: Array.from(document.querySelectorAll("[data-availability-family]")),
    technicalInspectionsBackButton: document.getElementById("technical-inspections-back-button"),
    technicalInspectionVehicle: document.getElementById("technical-inspection-vehicle"),
    technicalInspectionTemplate: document.getElementById("technical-inspection-template"),
    technicalInspectionTemplateInfo: document.getElementById("technical-inspection-template-info"),
    technicalInspectionForm: document.getElementById("technical-inspection-form"),
    technicalInspectionGeneralNotes: document.getElementById("technical-inspection-general-notes"),
    technicalInspectionSubmit: document.getElementById("technical-inspection-submit"),
    emergenciesBackButton: document.getElementById("emergencies-back-button"),
    emergencyCreateForm: document.getElementById("emergency-create-form"),
    emergencyVehicle: document.getElementById("emergency-vehicle"),
    emergencySeverity: document.getElementById("emergency-severity"),
    emergencyStopped: document.getElementById("emergency-stopped"),
    emergencyTitle: document.getElementById("emergency-title"),
    emergencyDescription: document.getElementById("emergency-description"),
    emergencyLocation: document.getElementById("emergency-location"),
    emergencyEvidence: document.getElementById("emergency-evidence"),
    emergencySubmit: document.getElementById("emergency-submit"),
    emergenciesCounter: document.getElementById("emergencies-counter"),
    emergenciesList: document.getElementById("emergencies-list"),
    technicalLibraryBackButton: document.getElementById("technical-library-back-button"),
    technicalLibraryVehicle: document.getElementById("technical-library-vehicle"),
    technicalLibraryList: document.getElementById("technical-library-list"),
    ncChecklistFilterOpen: document.getElementById("nc-checklist-filter-open"),
    ncChecklistFilterClosed: document.getElementById("nc-checklist-filter-closed"),
    ncMechanicFilterOpen: document.getElementById("nc-mechanic-filter-open"),
    ncMechanicFilterClosed: document.getElementById("nc-mechanic-filter-closed"),
    mechanicNcCreateForm: document.getElementById("mechanic-nc-create-form"),
    mechanicNcVehicle: document.getElementById("mechanic-nc-vehicle"),
    mechanicNcItemName: document.getElementById("mechanic-nc-item-name"),
    mechanicNcObservation: document.getElementById("mechanic-nc-observation"),
    mechanicNcBeforePhoto: document.getElementById("mechanic-nc-before-photo"),
    mechanicNcBeforePreview: document.getElementById("mechanic-nc-before-preview"),
    backButton: document.getElementById("back-button"),
    newChecklistButton: document.getElementById("new-checklist-button"),
    connectionStatus: document.getElementById("connection-status"),
};

let passwordModalFocusOrigin = null;
let photoViewerFocusOrigin = null;
let checklistHistoryFilterTimer = null;
let absenteeismFilterTimer = null;
const pullRefresh = {
    active: false,
    armed: false,
    refreshing: false,
    startY: 0,
    distance: 0,
};

const I18N_MESSAGES = {
    "pt-BR": {},
    "en-US": {
        "SISTEMA OPERACIONAL": "OPERATIONAL SYSTEM",
        "Sistema de Manutenção de Máquinas Pesadas": "Heavy Equipment Maintenance System",
        "Acesso ao Sistema": "System Access",
        "Usuário": "User",
        "Senha": "Password",
        "Entrar": "Sign in",
        "Esqueci minha senha": "I forgot my password",
        "Ambiente seguro": "Secure environment",
        "Olá,": "Hello,",
        "MÓDULOS": "MODULES",
        "CENTRAL OPERACIONAL": "OPERATIONAL CENTER",
        "EQUIPAMENTOS": "EQUIPMENT",
        "MANUTENÇÃO": "MAINTENANCE",
        "PESSOAS": "PEOPLE",
        "MATERIAIS E COMPRAS": "MATERIALS & PURCHASING",
        "ADMINISTRAÇÃO": "ADMINISTRATION",
        "OPERAÇÃO E CONTROLE": "OPERATION & CONTROL",
        "PLANEJAMENTO E EXECUÇÃO": "PLANNING & EXECUTION",
        "RH, JORNADA E ESCALA": "HR, WORK SCHEDULE & ROSTER",
        "ESTOQUE E AQUISIÇÃO": "INVENTORY & PROCUREMENT",
        "CONTROLE ADMINISTRATIVO": "ADMINISTRATIVE CONTROL",
        "CONFIGURAÇÕES": "SETTINGS",
        "Realizar checklist": "Run checklist",
        "Histórico de checklist": "Checklist history",
        "Catálogo de checklist": "Checklist catalog",
        "Inspeções": "Inspections",
        "Disponibilidade e horímetro": "Availability & hour meter",
        "Inspeção técnica": "Technical inspection",
        "Biblioteca técnica": "Technical library",
        "Relatórios de equipamentos": "Equipment reports",
        "Planejamento e backlog": "Planning & backlog",
        "Central de resolução": "Resolution center",
        "Emergencial": "Emergency",
        "Lavagens": "Washing",
        "Preventivas": "Preventive maintenance",
        "Dashboard de manutenção": "Maintenance dashboard",
        "Relatórios de manutenção": "Maintenance reports",
        "Minha jornada": "My work schedule",
        "Gestão de RH": "HR management",
        "Absenteísmo diário": "Daily absenteeism",
        "DSR semanal": "Weekly roster",
        "Escala de domingo e feriado": "Sunday & holiday roster",
        "Armazém e Estoque MMP": "MMP warehouse & stock",
        "Área de compras": "Purchasing area",
        "Cadastros": "Registrations",
        "Sala de controle": "Control room",
        "Usuários": "Users",
        "Minha senha": "My password",
        "Auditoria": "Audit",
        "Notificações": "Notifications",
        "Idioma": "Language",
        "Densidade": "Density",
        "Preferências": "Preferences",
        "NOTIFICAÇÕES": "NOTIFICATIONS",
        "MARCAR TODAS COMO LIDAS": "MARK ALL AS READ",
        "LIMPAR HISTÓRICO": "CLEAR HISTORY",
        "Alertas desativados.": "Alerts are disabled.",
        "Alertas ativados.": "Alerts are enabled.",
        "Exibição confortável.": "Comfortable display.",
        "Exibição compacta.": "Compact display.",
        "Alternar tema claro ou escuro.": "Switch light or dark theme.",
        "Usar tema claro.": "Use light theme.",
        "Usar tema escuro.": "Use dark theme.",
        "MENU": "MENU",
        "SAIR": "LOG OUT",
        "ATUALIZAR": "REFRESH",
        "CARREGAR": "LOAD",
        "SALVAR": "SAVE",
        "CANCELAR": "CANCEL",
        "FECHAR": "CLOSE",
        "DISPONÍVEL": "AVAILABLE",
        "INDISPONÍVEL": "UNAVAILABLE",
        "BLOQUEADO": "BLOCKED",
        "EM EXECUÇÃO": "IN PROGRESS",
        "CONCLUÍDO": "COMPLETED",
        "CRÍTICA": "CRITICAL",
        "NENHUMA NÃO LIDA": "NO UNREAD NOTIFICATIONS",
        "Nenhuma notificação interna.": "No internal notifications.",
        "Acesso realizado": "Sign-in completed",
        "Sua sessão no SIS MMP foi iniciada.": "Your SIS MMP session has started.",
    },
};

// Mensagens devolvidas pela API. O backend continua com seu contrato em
// português; a Web traduz a mensagem somente no ponto de apresentação.
const API_MESSAGE_TRANSLATIONS = {
    "Login ou senha invalidos.": "Invalid login or password.",
    "Nao autorizado.": "Not authorized.",
    "Não autorizado.": "Not authorized.",
    "Servidor indisponível ou sem conexão.": "Server unavailable or offline.",
    "FALHA NA COMUNICAÇÃO COM A API.": "API communication failed.",
    "Veículo não encontrado.": "Vehicle not found.",
    "Ordem de serviço não encontrada.": "Work order not found.",
    "Colaborador nao encontrado.": "Employee not found.",
    "Colaborador não encontrado.": "Employee not found.",
    "Material nao encontrado.": "Material not found.",
    "Backup nao encontrado.": "Backup not found.",
    "Escala não encontrada.": "Roster not found.",
    "Nenhuma não conformidade encontrada.": "No nonconformities found.",
    "Checklist incompleto.": "Checklist incomplete.",
    "Solicitação de reset não encontrada ou já atendida.": "Password reset request not found or already handled.",
    "A nova senha deve ter pelo menos 6 caracteres.": "The new password must contain at least 6 characters.",
    "Informe uma nova senha com pelo menos 6 caracteres.": "Enter a new password with at least 6 characters.",
    "Senha atual invalida.": "Current password is invalid.",
    "Informe a senha atual e a nova senha.": "Enter the current and new passwords.",
    "Login ja cadastrado.": "Login is already registered.",
    "Ja existe um item com este nome para este tipo de equipamento.": "An item with this name already exists for this equipment type.",
    "Ja existe um material com esta referencia.": "A material with this reference already exists.",
    "Ja existe leitura neste mesmo instante.": "A reading already exists for this exact time.",
    "A data final deve ser maior ou igual à data inicial.": "The end date must be on or after the start date.",
    "A escala já possui lançamento para um dos colaboradores.": "This roster already has an entry for one of the employees.",
    "Esta escala já foi concluída.": "This roster has already been completed.",
    "Este periodo de ferias ja esta cancelado.": "This vacation period has already been cancelled.",
    "Lancamento cancelado nao pode ser alterado.": "A cancelled entry cannot be changed.",
    "Lancamento ja esta cancelado.": "This entry has already been cancelled.",
    "Não foi possível registrar a presença e a DSR.": "Attendance and the weekly roster could not be recorded.",
    "Não foi possível identificar equipamentos válidos.": "Valid equipment could not be identified.",
    "Não é permitido alterar material de item já instalado.": "The material of an installed item cannot be changed.",
    "Importação direta de NC para manutenção foi desativada. Use a Central de Resolução para criar pacote e depois enviar para a manutenção.": "Direct nonconformity import to maintenance is disabled. Use the Resolution Center to create a package and send it to maintenance.",
    "Este login nao esta vinculado a um colaborador.": "This login is not linked to an employee.",
    "Este login não está vinculado a um colaborador.": "This login is not linked to an employee.",
    "Acesso restrito a manutencao.": "Access restricted to maintenance.",
    "Acesso negado para resolução.": "Access denied for resolution.",
    "Acesso negado para abertura de atividade.": "Access denied for opening an activity.",
    "Perfil sem permissão para registrar aplicação no Estoque MMP.": "Your profile cannot register an issue in MMP Stock.",
    "Material informado é inválido ou inativo.": "The selected material is invalid or inactive.",
    "Material inválido ou inativo.": "Material is invalid or inactive.",
    "Quantidade deve ser maior que zero.": "Quantity must be greater than zero.",
    "Quantidade por equipamento inválida.": "Quantity per equipment is invalid.",
    "Quantidade do material inválida.": "Material quantity is invalid.",
    "Informe ao menos um campo de material para atualizar.": "Enter at least one material field to update.",
    "Selecione ao menos um equipamento para atualizar material.": "Select at least one equipment to update the material.",
    "Selecione ao menos um equipamento para a atividade.": "Select at least one equipment for the activity.",
    "Selecione ao menos um equipamento para atualizar material.": "Select at least one equipment to update the material.",
    "Informe a não conformidade para abrir a atividade.": "Enter the nonconformity to open the activity.",
    "Informe o colaborador.": "Select an employee.",
    "Informe o mecânico para consulta.": "Select a mechanic for the query.",
    "Informe o motivo do cancelamento.": "Enter the cancellation reason.",
    "Informe o motivo da correcao.": "Enter the correction reason.",
    "Informe o usuário para solicitar o reset.": "Enter the user to request a reset.",
    "Informe codigo e nome da familia.": "Enter the family code and name.",
    "Informe codigo e nome do local.": "Enter the location code and name.",
    "Informe o Spreader do vinculo.": "Select the Spreader for the link.",
    "Selecione DOMINGO ou FERIADO para o tipo da escala.": "Select SUNDAY or HOLIDAY as the roster type.",
    "A busca pode ter no maximo 80 caracteres.": "The search can contain up to 80 characters.",
    "Informe ao menos 2 caracteres para a busca.": "Enter at least 2 characters to search.",
    "Tipo de local invalido.": "Location type is invalid.",
    "Local superior invalido.": "Parent location is invalid.",
    "Local superior nao encontrado.": "Parent location not found.",
    "Um local nao pode ser superior de si mesmo.": "A location cannot be its own parent.",
    "Spreader nao encontrado.": "Spreader not found.",
    "Formato de exportacao invalido.": "Export format is invalid.",
    "Formato invalido. Use json, csv ou xlsx.": "Invalid format. Use json, csv or xlsx.",
    "Arquivo de inventário não encontrado.": "Inventory file not found.",
    "Envie o arquivo Excel no campo file ou informe source_path.": "Upload the Excel file in the file field or provide source_path.",
};

const API_MESSAGE_REPLACEMENTS = [
    [/^Somente admin, gestor ou mecânico podem/i, "Only an administrator, manager or mechanic can"],
    [/^Somente admin ou gestor podem/i, "Only an administrator or manager can"],
    [/^Somente admin pode/i, "Only an administrator can"],
    [/^Somente o administrador pode/i, "Only the administrator can"],
    [/^Somente gestão/i, "Only management"],
    [/^Somente admin/i, "Only an administrator can"],
    [/^Apenas admin ou gestor pode/i, "Only an administrator or manager can"],
    [/^Acesso restrito/i, "Access restricted"],
    [/^Acesso negado/i, "Access denied"],
    [/^Não autorizado\.?$/i, "Not authorized."],
    [/^Nao autorizado\.?$/i, "Not authorized."],
    [/\bgerenciar\b/gi, "manage"],
    [/\bconsultar\b/gi, "view"],
    [/\bacessar\b/gi, "access"],
    [/\bvisualizar\b/gi, "view"],
    [/\bexportar\b/gi, "export"],
    [/\bcriar\b/gi, "create"],
    [/\batualizar\b/gi, "update"],
    [/\beditar\b/gi, "edit"],
    [/\bregistrar\b/gi, "record"],
    [/\brealizar\b/gi, "perform"],
    [/\bgerar\b/gi, "generate"],
    [/\binválid[ao]\b/gi, "invalid"],
    [/\binvalido\b/gi, "invalid"],
    [/\bnão encontrado\b/gi, "not found"],
    [/\bnao encontrado\b/gi, "not found"],
    [/\bnão encontrada\b/gi, "not found"],
    [/\bnao encontrada\b/gi, "not found"],
];

const i18nOriginalTextNodes = new WeakMap();
const i18nOriginalAttributes = new WeakMap();

function translateStaticText(language) {
    const messages = I18N_MESSAGES[language] || I18N_MESSAGES["pt-BR"];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach((node) => {
        const parent = node.parentElement;
        if (!parent || ["SCRIPT", "STYLE", "OPTION"].includes(parent.tagName)) return;
        const raw = node.nodeValue || "";
        const current = raw.trim();
        if (!current) return;
        const original = (parent === elements.topbarContext && parent.dataset.i18nKey)
            || i18nOriginalTextNodes.get(node)
            || current;
        i18nOriginalTextNodes.set(node, original);
        if (parent.childNodes.length === 1 && !parent.dataset.i18nKey) parent.dataset.i18nKey = original;
        const translated = messages[original] || original;
        node.nodeValue = raw.replace(current, translated);
    });
    document.querySelectorAll("[placeholder], [title], [aria-label]").forEach((element) => {
        const attrs = i18nOriginalAttributes.get(element) || {};
        ["placeholder", "title", "aria-label"].forEach((attribute) => {
            if (!element.hasAttribute(attribute)) return;
            const current = element.getAttribute(attribute) || "";
            const original = attrs[attribute] || current;
            attrs[attribute] = original;
            element.setAttribute(attribute, messages[original] || original);
        });
        i18nOriginalAttributes.set(element, attrs);
    });
    if (elements.topbarContext?.dataset.i18nKey) {
        elements.topbarContext.textContent = localizedMessage(elements.topbarContext.dataset.i18nKey).toUpperCase();
    }
}

function localizedMessage(value) {
    const language = document.documentElement.lang === "en-US" ? "en-US" : "pt-BR";
    const message = String(value ?? "");
    if (language !== "en-US" || !message) return message;
    if (I18N_MESSAGES[language]?.[message]) return I18N_MESSAGES[language][message];
    if (API_MESSAGE_TRANSLATIONS[message]) return API_MESSAGE_TRANSLATIONS[message];
    return API_MESSAGE_REPLACEMENTS.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement), message);
}

function applyTheme(theme) {
    const dark = String(theme || "light").toLowerCase() === "dark";
    const value = dark ? "dark" : "light";
    document.documentElement.dataset.theme = value;
    document.body.dataset.theme = value;
    localStorage.setItem(THEME_STORAGE_KEY, value);
    if (elements.themeToggleButton) {
        elements.themeToggleButton.setAttribute("aria-pressed", String(dark));
        elements.themeToggleButton.setAttribute("title", dark ? "Usar tema claro" : "Usar tema escuro");
        elements.themeToggleButton.setAttribute("aria-label", dark ? "Usar tema claro" : "Usar tema escuro");
        const icon = elements.themeToggleButton.querySelector(".theme-toggle-icon");
        if (icon) icon.textContent = dark ? "☾" : "☼";
    }
}

function toggleTheme() {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    syncSettingsPreferenceLabels();
}

function applyLanguage(language) {
    const value = String(language || "pt-BR") === "en-US" ? "en-US" : "pt-BR";
    document.documentElement.lang = value;
    localStorage.setItem(LANGUAGE_STORAGE_KEY, value);
    if (elements.topbarLanguageSelect) elements.topbarLanguageSelect.value = value;
    translateStaticText(value);
    syncSettingsPreferenceLabels();
}

function applyDensity(density) {
    const value = String(density || "comfortable") === "compact" ? "compact" : "comfortable";
    document.body.dataset.density = value;
    localStorage.setItem(DENSITY_STORAGE_KEY, value);
    syncSettingsPreferenceLabels();
}

function notificationsEnabled() {
    return localStorage.getItem(NOTIFICATIONS_STORAGE_KEY) === "true";
}

function syncSettingsPreferenceLabels() {
    const notifications = notificationsEnabled();
    const density = document.body.dataset.density === "compact" ? "compact" : "comfortable";
    const dark = document.documentElement.dataset.theme === "dark";
    const english = document.documentElement.lang === "en-US";
    if (elements.topbarNotificationsLabel) {
        elements.topbarNotificationsLabel.textContent = notifications
            ? (english ? "Alerts are enabled." : "Alertas ativados.")
            : (english ? "Alerts are disabled." : "Alertas desativados.");
    }
    if (elements.topbarDensityLabel) {
        elements.topbarDensityLabel.textContent = density === "compact"
            ? (english ? "Compact display." : "Exibição compacta.")
            : (english ? "Comfortable display." : "Exibição confortável.");
    }
    if (elements.topbarThemeLabel) {
        elements.topbarThemeLabel.textContent = dark
            ? (english ? "Use light theme." : "Usar tema claro.")
            : (english ? "Use dark theme." : "Usar tema escuro.");
    }
}

async function toggleBrowserNotifications() {
    if (notificationsEnabled()) {
        localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, "false");
        syncSettingsPreferenceLabels();
        showToast("NOTIFICAÇÕES DESATIVADAS.");
        return;
    }
    if (!("Notification" in window)) {
        showToast("ESTE NAVEGADOR NÃO OFERECE NOTIFICAÇÕES.", true);
        return;
    }
    let permission = Notification.permission;
    if (permission === "default") permission = await Notification.requestPermission();
    const enabled = permission === "granted";
    localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, String(enabled));
    syncSettingsPreferenceLabels();
    showToast(enabled ? "NOTIFICAÇÕES ATIVADAS." : "PERMISSÃO DE NOTIFICAÇÃO NÃO CONCEDIDA.", !enabled);
}

function readInternalNotifications() {
    const value = readJsonStorage(NOTIFICATION_CENTER_STORAGE_KEY, []);
    return Array.isArray(value) ? value : [];
}

function saveInternalNotifications(notifications) {
    localStorage.setItem(
        NOTIFICATION_CENTER_STORAGE_KEY,
        JSON.stringify((Array.isArray(notifications) ? notifications : []).slice(0, NOTIFICATION_CENTER_LIMIT)),
    );
}

function readNotificationFilters() {
    const stored = readJsonStorage(NOTIFICATION_FILTER_STORAGE_KEY, {});
    return {
        origin: notificationOriginKey(stored?.origin || ""),
        priority: String(stored?.priority || "").toUpperCase(),
        from: String(stored?.from || ""),
        to: String(stored?.to || ""),
    };
}

function notificationOriginKey(value) {
    const normalized = String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toUpperCase()
        .replace(/\s+/g, "_");
    return {
        MANUTENCAO: "MAINTENANCE",
        RH: "HR",
        HR: "HR",
        COMPRAS: "PURCHASES",
        ESTOQUE_MMP: "MMP_STOCK",
        EMERGENCIA: "EMERGENCY",
        EQUIPAMENTOS: "EQUIPMENT",
        ADMINISTRACAO: "ADMIN",
    }[normalized] || normalized;
}

function saveNotificationFilters(filters) {
    localStorage.setItem(NOTIFICATION_FILTER_STORAGE_KEY, JSON.stringify(filters));
}

function syncNotificationFilterControls() {
    const filters = readNotificationFilters();
    if (elements.topbarNotificationsOriginFilter) elements.topbarNotificationsOriginFilter.value = filters.origin;
    if (elements.topbarNotificationsPriorityFilter) elements.topbarNotificationsPriorityFilter.value = filters.priority;
    if (elements.topbarNotificationsFromFilter) elements.topbarNotificationsFromFilter.value = filters.from;
    if (elements.topbarNotificationsToFilter) elements.topbarNotificationsToFilter.value = filters.to;
    return filters;
}

function notificationDateKey(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "";
    const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: MANAUS_TIME_ZONE,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).formatToParts(date).reduce((result, part) => {
        if (part.type !== "literal") result[part.type] = part.value;
        return result;
    }, {});
    return `${parts.year}-${parts.month}-${parts.day}`;
}

function notificationMatchesFilters(item, filters) {
    const origin = notificationOriginKey(item.origin || "SYSTEM");
    const priority = String(item.type || "INFO").toUpperCase();
    const date = notificationDateKey(item.createdAt);
    if (filters.origin && origin !== filters.origin) return false;
    if (filters.priority && priority !== filters.priority) return false;
    if (filters.from && (!date || date < filters.from)) return false;
    if (filters.to && (!date || date > filters.to)) return false;
    return true;
}

function notificationFiltersActive(filters) {
    return Boolean(filters.origin || filters.priority || filters.from || filters.to);
}

function renderNotificationFilterSummary(total, visible, filters) {
    if (!elements.topbarNotificationsFilterSummary) return;
    const english = document.documentElement.lang === "en-US";
    if (!notificationFiltersActive(filters)) {
        elements.topbarNotificationsFilterSummary.textContent = "";
        return;
    }
    elements.topbarNotificationsFilterSummary.textContent = english
        ? `${visible} of ${total} notifications shown.`
        : `${visible} de ${total} notificações exibidas.`;
}

function renderInternalNotifications() {
    const notifications = readInternalNotifications();
    const filters = syncNotificationFilterControls();
    const visibleNotifications = notifications.filter((item) => notificationMatchesFilters(item, filters));
    const unread = notifications.filter((item) => !item.read).length;
    const english = document.documentElement.lang === "en-US";
    if (elements.topbarNotificationsBadge) {
        elements.topbarNotificationsBadge.textContent = String(unread);
        elements.topbarNotificationsBadge.classList.toggle("hidden", unread === 0);
    }
    if (elements.topbarNotificationsCount) {
        elements.topbarNotificationsCount.textContent = unread
            ? (english ? `${unread} unread` : `${unread} não lida(s)`)
            : (english ? "No unread notifications" : "Nenhuma não lida");
    }
    renderNotificationFilterSummary(notifications.length, visibleNotifications.length, filters);
    if (!elements.topbarNotificationsList) return;
    if (!visibleNotifications.length) {
        const emptyMessage = notifications.length && notificationFiltersActive(filters)
            ? (english ? "No notification matches the selected filters." : "Nenhuma notificação corresponde aos filtros selecionados.")
            : (english ? "No internal notifications." : "Nenhuma notificação interna.");
        elements.topbarNotificationsList.innerHTML = `<p class="topbar-notifications-empty">${emptyMessage}</p>`;
        return;
    }
    elements.topbarNotificationsList.innerHTML = visibleNotifications.map((item) => `
        <article class="topbar-notification-item ${item.read ? "" : "is-unread"}">
            <span class="topbar-notification-dot" aria-hidden="true"></span>
            <div><strong>${escapeHtml(localizedMessage(item.title || (english ? "Notification" : "Notificação")))}</strong>
            <span>${escapeHtml(localizedMessage(item.message || ""))}</span>
            <small>${escapeHtml(formatManausDateTime(item.createdAt, { short: true }))}</small></div>
        </article>
    `).join("");
}

function updateNotificationFilters() {
    saveNotificationFilters({
        origin: elements.topbarNotificationsOriginFilter?.value || "",
        priority: elements.topbarNotificationsPriorityFilter?.value || "",
        from: elements.topbarNotificationsFromFilter?.value || "",
        to: elements.topbarNotificationsToFilter?.value || "",
    });
    renderInternalNotifications();
}

function clearNotificationFilters() {
    saveNotificationFilters({ origin: "", priority: "", from: "", to: "" });
    renderInternalNotifications();
}

function addInternalNotification(title, message, type = "info") {
    const notifications = readInternalNotifications();
    notifications.unshift({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        title,
        message,
        type,
        createdAt: new Date().toISOString(),
        read: false,
    });
    saveInternalNotifications(notifications);
    renderInternalNotifications();
}

function normalizeServerNotification(item) {
    return {
        id: `server-${item.id}`,
        serverId: item.id,
        title: item.title,
        message: item.message,
        type: String(item.priority || "INFO").toLowerCase(),
        origin: item.origin || "SYSTEM",
        entityType: item.entity_type || null,
        entityId: item.entity_id || null,
        createdAt: item.created_at,
        read: Boolean(item.read_at || item.read),
        server: true,
    };
}

async function syncServerNotifications({ silent = true } = {}) {
    if (!state.token || !state.user) return false;
    try {
        const payload = await apiFetch("/notifications?limit=40");
        const items = Array.isArray(payload) ? payload : (payload?.items || []);
        saveInternalNotifications(items.map(normalizeServerNotification));
        renderInternalNotifications();
        return true;
    } catch (error) {
        if (!silent) showToast(error.message || "NÃO FOI POSSÍVEL ATUALIZAR AS NOTIFICAÇÕES.", true);
        return false;
    }
}

async function markInternalNotificationsRead() {
    if (state.token) {
        try {
            await apiFetch("/notifications/read-all", { method: "POST" });
            await syncServerNotifications();
            return;
        } catch {
            // O histórico local continua disponível quando o servidor está offline.
        }
    }
    saveInternalNotifications(readInternalNotifications().map((item) => ({ ...item, read: true })));
    renderInternalNotifications();
}

async function clearInternalNotifications() {
    if (state.token) {
        try {
            await apiFetch("/notifications", { method: "DELETE" });
            saveInternalNotifications([]);
            renderInternalNotifications();
            return;
        } catch {
            // Permite limpar a cópia local mesmo sem conexão.
        }
    }
    saveInternalNotifications([]);
    renderInternalNotifications();
}

function closeTopbarNotificationsMenu() {
    elements.topbarNotificationsMenu?.classList.add("hidden");
    elements.topbarNotificationsButton?.setAttribute("aria-expanded", "false");
}

async function toggleTopbarNotificationsMenu() {
    if (!elements.topbarNotificationsMenu || !state.user) return;
    closeTopbarSettingsMenu();
    await syncServerNotifications();
    renderInternalNotifications();
    const open = elements.topbarNotificationsMenu.classList.toggle("hidden");
    elements.topbarNotificationsButton?.setAttribute("aria-expanded", String(!open));
}

function cycleDensity() {
    applyDensity(document.body.dataset.density === "compact" ? "comfortable" : "compact");
    showToast(document.body.dataset.density === "compact" ? "DENSIDADE COMPACTA APLICADA." : "DENSIDADE CONFORTÁVEL APLICADA.");
}

function applyUserPreferences() {
    applyLanguage(localStorage.getItem(LANGUAGE_STORAGE_KEY) || "pt-BR");
    applyDensity(localStorage.getItem(DENSITY_STORAGE_KEY) || "comfortable");
    syncSettingsPreferenceLabels();
}

applyTheme(localStorage.getItem(THEME_STORAGE_KEY) || "light");
applyUserPreferences();
renderInternalNotifications();
elements.apiBaseUrl.value = state.apiBaseUrl;
updateConnectionStatus();

function resolveApiBaseUrl() {
    const requestedUrl = new URLSearchParams(window.location.search).get("api")?.trim().replace(/\/$/, "");
    const savedUrl = localStorage.getItem("apiBaseUrl");
    const configuredUrl = window.CHECKLIST_CONFIG?.API_BASE_URL?.replace(/\/$/, "");
    const currentHost = window.location.hostname || "127.0.0.1";
    const currentProtocol = window.location.protocol === "https:" ? "https:" : "http:";
    const currentUrl = `${currentProtocol}//${currentHost}:5000`;
    const isLocalAccess = currentHost === "127.0.0.1" || currentHost === "localhost";
    const isRemoteAccess = currentHost !== "127.0.0.1" && currentHost !== "localhost";
    const isSavedLocal = savedUrl?.includes("127.0.0.1") || savedUrl?.includes("localhost");

    if (requestedUrl && /^https?:\/\//i.test(requestedUrl)) {
        localStorage.setItem("apiBaseUrl", requestedUrl);
        return requestedUrl;
    }

    // Quando a Web é aberta localmente, a fonte de dados principal é o
    // backend local. A URL pública só deve ser usada mediante o parâmetro
    // ?api= ou quando a interface estiver hospedada fora do computador.
    if (isLocalAccess) {
        const localUrl = isSavedLocal ? savedUrl : currentUrl;
        localStorage.setItem("apiBaseUrl", localUrl);
        return localUrl;
    }

    if (configuredUrl && (!savedUrl || isSavedLocal)) {
        localStorage.setItem("apiBaseUrl", configuredUrl);
        return configuredUrl;
    }

    if (isRemoteAccess && (!savedUrl || savedUrl.includes("127.0.0.1") || savedUrl.includes("localhost"))) {
        localStorage.setItem("apiBaseUrl", currentUrl);
        return currentUrl;
    }
    return savedUrl || currentUrl;
}

function updateConnectionStatus() {
    if (!elements.connectionStatus) {
        return;
    }
    elements.connectionStatus.textContent = navigator.onLine ? "ONLINE" : "OFFLINE";
    elements.connectionStatus.classList.toggle("offline", !navigator.onLine);
}

function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.CHECKLIST_CONFIG?.ENABLE_CHECKLIST_PWA) {
        return;
    }

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("./service-worker.js", { updateViaCache: "none" }).catch(() => {
            showToast("PWA NÃO PÔDE SER ATIVADO NESTE NAVEGADOR.", true);
        });
    });
}

function showToast(message, isError = false) {
    elements.toast.textContent = localizedMessage(message);
    elements.toast.classList.toggle("error", isError);
    elements.toast.classList.remove("hidden");
    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(() => {
        elements.toast.classList.add("hidden");
    }, 3200);
}

function renderStateCard(target, { title, message = "", tone = "neutral", compact = false } = {}) {
    if (!target) {
        return;
    }
    target.innerHTML = `
        <article class="state-card ${tone}${compact ? " compact" : ""}">
            <strong>${escapeHtml(localizedMessage(title || "AGUARDE"))}</strong>
            ${message ? `<span>${escapeHtml(localizedMessage(message))}</span>` : ""}
        </article>
    `;
}

function formatDateTimeShort(value) {
    return formatManausDateTime(value, { short: true });
}

function setLoginStatus(message, isError = false) {
    const status = document.getElementById("login-status");
    if (!status) {
        return;
    }
    status.textContent = localizedMessage(message || "");
    status.className = `login-status${isError ? " error" : ""}`;
}

function setActiveScreen(key) {
    Object.entries(screens).forEach(([screenKey, screen]) => {
        screen.classList.toggle("hidden", screenKey !== key);
    });
    const isEntryScreen = key === "login";
    const isEquipmentScreen = key === "vehicles" || key === "vehicleFamily";
    document.body.classList.toggle("entry-screen", isEntryScreen);
    document.body.classList.toggle("equipment-screen", isEquipmentScreen);
    appTopbar?.classList.toggle("hidden", isEntryScreen);
    syncTopbarActiveScreen(key);
    translateStaticText(document.documentElement.lang || "pt-BR");
    elements.mobileShell?.scrollTo({ top: 0, behavior: "auto" });
}

function topbarActionLabel(action) {
    const button = elements.topbarActionButtons.find((item) => item.dataset.topbarAction === action);
    const strong = button?.querySelector("strong");
    return localizedMessage(strong?.dataset.i18nKey || strong?.textContent?.trim() || "CENTRAL OPERACIONAL").toUpperCase();
}

function topbarUserInitials(name) {
    const parts = String(name || "USUÁRIO").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "US";
    return `${parts[0][0] || "U"}${parts.length > 1 ? parts[parts.length - 1][0] : ""}`.toUpperCase();
}

function syncTopbarUserIdentity() {
    const name = String(state.user?.nome || "USUÁRIO").trim();
    if (elements.topbarUserName) elements.topbarUserName.textContent = name.toUpperCase();
    if (elements.topbarUserAvatar) elements.topbarUserAvatar.textContent = topbarUserInitials(name);
    const authenticated = Boolean(state.user && state.token);
    const admin = hasAdminAccess();
    elements.topbarUserSettingsButton?.classList.toggle("hidden", !authenticated);
    elements.topbarNotificationsButton?.classList.toggle("hidden", !authenticated);
    if (!authenticated) closeTopbarNotificationsMenu();
    elements.topbarSettingsItems.forEach((item) => {
        item.classList.toggle("hidden", item.dataset.settingsAdminOnly === "true" && !admin);
    });
}

function syncTopbarActiveScreen(screenKey) {
    const screenActions = {
        home: "",
        vehicles: "checklist",
        vehicleFamily: "checklist",
        checklist: "checklist",
        checklistHistory: "checklistHistory",
        checklistCatalog: "checklistCatalog",
        activities: "activities",
        activityDetail: "activities",
        availability: "availability",
        technicalInspections: "technicalInspections",
        technicalLibrary: "technicalLibrary",
        maintenance: "maintenance",
        planning: "planning",
        nonConformities: "nonConformities",
        emergencies: "emergencies",
        washes: "washes",
        preventives: "preventives",
        hrJourney: "hrJourney",
        rhAdmin: "rhAdmin",
        weeklyDsr: "weeklyDsr",
        specialSchedule: "specialSchedule",
        absenteeism: "absenteeism",
        mmpStock: "mmpStock",
        purchases: "purchases",
        adminCatalogs: "adminCatalogs",
        adminSettings: "adminSettings",
    };
    const selectedAction = screenActions[screenKey] || "";
    elements.topbarActionButtons.forEach((button) => {
        const active = button.dataset.topbarAction === selectedAction;
        button.classList.toggle("is-active", active);
    });
    document.querySelectorAll(".topbar-module[data-topbar-module]").forEach((module) => {
        module.classList.toggle("has-active-item", Boolean(module.querySelector("[data-topbar-action].is-active")));
    });
    if (elements.topbarContext) {
        const activeButton = elements.topbarActionButtons.find((button) => button.dataset.topbarAction === selectedAction);
        const sourceLabel = activeButton?.querySelector("strong")?.dataset.i18nKey || "CENTRAL OPERACIONAL";
        elements.topbarContext.dataset.i18nKey = selectedAction ? sourceLabel : "CENTRAL OPERACIONAL";
        elements.topbarContext.textContent = selectedAction ? topbarActionLabel(selectedAction) : localizedMessage("CENTRAL OPERACIONAL");
    }
}

function setTopbarModuleOpen(moduleKey, open) {
    document.querySelectorAll(".topbar-module[data-topbar-module]").forEach((module) => {
        const active = module.dataset.topbarModule === moduleKey && open;
        module.classList.toggle("is-open", active);
        module.querySelector("[data-topbar-module-trigger]")?.setAttribute("aria-expanded", String(active));
    });
}

function closeTopbarNavigation() {
    setTopbarModuleOpen("", false);
    elements.topbarNavigation?.classList.remove("is-open");
    elements.topbarMobileToggle?.setAttribute("aria-expanded", "false");
    closeTopbarSettingsMenu();
    closeTopbarNotificationsMenu();
}

function closeTopbarSettingsMenu() {
    elements.topbarSettingsMenu?.classList.add("hidden");
    elements.topbarUserSettingsButton?.setAttribute("aria-expanded", "false");
}

function toggleTopbarSettingsMenu() {
    if (!elements.topbarSettingsMenu || !state.user) return;
    const open = elements.topbarSettingsMenu.classList.toggle("hidden");
    elements.topbarUserSettingsButton?.setAttribute("aria-expanded", String(!open));
}

async function openTopbarSettingsAction(action) {
    closeTopbarSettingsMenu();
    if (action === "password") {
        openPasswordResetModal();
    } else if (action === "notifications") {
        await toggleBrowserNotifications();
    } else if (action === "density") {
        cycleDensity();
    } else if (action === "theme") {
        toggleTheme();
    } else if (action === "users" || action === "audit") {
        openAdminSettings();
        await openAdminSettingsAction(action);
    }
}

function topbarActionAllowed(button) {
    const sourceId = button.dataset.sourceMenu;
    if (sourceId) return !document.getElementById(sourceId)?.classList.contains("hidden");
    if (button.dataset.topbarAccess === "management") return hasWashReportAccess();
    return true;
}

function syncTopbarNavigation() {
    if (!elements.topbarNavigation) return;
    elements.topbarActionButtons.forEach((button) => button.classList.toggle("hidden", !topbarActionAllowed(button)));
    document.querySelectorAll(".topbar-module[data-topbar-module]").forEach((module) => {
        const hasVisibleAction = Array.from(module.querySelectorAll("[data-topbar-action]")).some((button) => !button.classList.contains("hidden"));
        module.classList.toggle("is-empty", !hasVisibleAction);
    });
}

async function openTopbarAction(action) {
    const actions = {
        checklist: openChecklistMenu,
        checklistHistory: openChecklistHistoryMenu,
        checklistCatalog: openChecklistCatalogMenu,
        activities: openActivitiesMenu,
        availability: openAvailabilityMenu,
        technicalInspections: openTechnicalInspectionsMenu,
        technicalLibrary: openTechnicalLibraryMenu,
        equipmentReports: () => openModuleReports("equipment"),
        maintenance: openMaintenanceMenu,
        planning: openPlanningMenu,
        nonConformities: openNonConformitiesMenu,
        emergencies: openEmergenciesMenu,
        washes: openWashesMenu,
        preventives: openPreventivesMenu,
        maintenanceDashboard: () => { window.location.href = "./dashboard-manutencao/"; },
        maintenanceReports: () => openModuleReports("maintenance"),
        hrJourney: openHrJourneyMenu,
        rhAdmin: openRhAdminMenu,
        absenteeism: openAbsenteeismMenu,
        weeklyDsr: openWeeklyDsrMenu,
        specialSchedule: openSpecialScheduleMenu,
        mmpStock: openMmpStockMenu,
        purchases: openPurchasesMenu,
        purchaseReports: () => openModuleReports("purchases"),
        adminCatalogs: openAdminCatalogs,
        adminSettings: openAdminSettings,
    };
    const handler = actions[action];
    if (!handler) return;
    closeTopbarNavigation();
    await handler();
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 20000) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, {
            ...options,
            signal: controller.signal,
        });
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function apiFetch(path, options = {}) {
    try {
        const response = await fetchWithTimeout(`${state.apiBaseUrl}${path}`, {
            ...options,
            headers: {
                ...(options.headers || {}),
                Authorization: state.token ? `Bearer ${state.token}` : "",
            },
        }, 20000);

        const body = await response.json().catch(() => ({}));
        if (!response.ok || (Object.prototype.hasOwnProperty.call(body, "success") && body.success === false)) {
            const error = new Error(localizedMessage(body.error || body.message || "FALHA NA COMUNICAÇÃO COM A API."));
            error.status = response.status;
            throw error;
        }

        return Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error(localizedMessage("A API demorou demais para responder. Tente novamente em instantes."));
        }
        if (error.name === "TypeError" && (error.message.includes("fetch") || error.message.includes("NetworkError"))) {
            throw new Error(localizedMessage("SERVIDOR INDISPONÍVEL OU SEM CONEXÃO."));
        }
        throw error;
    }
}

async function downloadAuthenticatedFile(path, filenameHint = "arquivo.pdf") {
    const headers = new Headers(optionsLikeHeaders({}));
    const response = await fetch(`${state.apiBaseUrl}${path}`, {
        method: "GET",
        headers,
    });
    if (!response.ok) {
        let payload = {};
        try {
            payload = await response.json();
        } catch {
            payload = {};
        }
        throw new Error(localizedMessage(payload.error || "Falha ao baixar arquivo."));
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filenameHint;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function optionsLikeHeaders(customHeaders = {}) {
    const headers = {
        Accept: "application/json",
        ...customHeaders,
    };
    if (state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }
    return headers;
}

async function login(credentials) {
    let response;
    try {
        response = await fetchWithTimeout(`${state.apiBaseUrl}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials),
        }, 45000);
    } catch (error) {
        if (error.name === "AbortError") {
        throw new Error(localizedMessage("A API nao respondeu em 45 segundos (" + state.apiBaseUrl + "). Verifique a conexao ou abra pelo iniciar local."));
        }
        throw error;
    }

    const body = await response.json().catch(() => ({}));
    if (!response.ok || (Object.prototype.hasOwnProperty.call(body, "success") && body.success === false)) {
        throw new Error(localizedMessage(body.error || "NÃO FOI POSSÍVEL ENTRAR."));
    }

    const payload = Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    state.token = payload.token;
    state.user = payload.user;
    state.firstAccessRequired = Boolean(payload.first_access_required);
    state.user.first_access_required = state.firstAccessRequired;
    saveSession(payload.token, payload.user);
}

async function bootstrap() {
    setLoginStatus("");
    const hadSavedSession = Boolean(localStorage.getItem("token") && readJsonStorage("user", null));
    if (hasValidSession()) {
        state.token = localStorage.getItem("token") || "";
        state.user = readJsonStorage("user", null);
        refreshSessionActivity();
        await enterAuthenticatedApp();
        return;
    }
    state.token = "";
    state.user = null;
    clearSession();
    setActiveScreen("login");
    if (hadSavedSession) {
        setLoginStatus("Sessao encerrada por 30 minutos de inatividade. Informe login e senha novamente.", true);
    }
}

async function enterAuthenticatedApp() {
    try {
        await syncServerNotifications();
        if (state.firstAccessRequired || state.user?.first_access_required) {
            setActiveScreen("home");
            openFirstAccessModal();
            return;
        }
        setLoginStatus("Carregando dados do sistema...");
        await loadVehiclesAndCatalog();
        scheduleSessionInactivityCheck();
        const requestedAssetCode = new URLSearchParams(window.location.search).get("ativo");
        if (requestedAssetCode) {
            await openMobileAssetByCode(requestedAssetCode);
            maybeOpenWelcomeModal();
            setLoginStatus("");
            syncPendingChecklists({ silent: true });
            syncPendingTechnicalInspections();
            syncPendingMobileOperations();
            return;
        }
        const requestedModule = new URLSearchParams(window.location.search).get("modulo");
        if (requestedModule === "escala" && ["admin", "gestor"].includes(String(state.user?.tipo || "").toLowerCase())) {
            await openSpecialScheduleMenu();
            maybeOpenWelcomeModal();
            setLoginStatus("");
            syncPendingChecklists({ silent: true });
            syncPendingTechnicalInspections();
            syncPendingMobileOperations();
            return;
        }
        if (await restoreActiveChecklistDraft()) {
            maybeOpenWelcomeModal();
            setLoginStatus("");
            syncPendingChecklists({ silent: true });
            syncPendingTechnicalInspections();
            syncPendingMobileOperations();
            return;
        }
        renderHome();
        setActiveScreen("home");
        maybeOpenWelcomeModal();
        setLoginStatus("");
        syncPendingChecklists({ silent: true });
        syncPendingTechnicalInspections();
        syncPendingMobileOperations();
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            state.token = "";
            state.user = null;
            if (sessionInactivityTimer) {
                window.clearTimeout(sessionInactivityTimer);
                sessionInactivityTimer = null;
            }
            clearSession();
            setActiveScreen("login");
            setLoginStatus("Sessão expirada. Informe login e senha novamente.", true);
            return;
        }
        setActiveScreen("login");
        setLoginStatus(`Login OK, mas falhou ao carregar dados: ${error.message}`, true);
        showToast(error.message, true);
    }
}

window.enterChecklistApp = async () => {
    state.token = localStorage.getItem("token") || "";
    state.user = readJsonStorage("user", null);
    state.apiBaseUrl = localStorage.getItem("apiBaseUrl") || elements.apiBaseUrl.value.replace(/\/$/, "");
    elements.apiBaseUrl.value = state.apiBaseUrl;
    if (!state.token || !state.user) {
        setActiveScreen("login");
        setLoginStatus("Login salvo não encontrado. Informe usuário e senha novamente.", true);
        return;
    }
    localStorage.setItem(
        SESSION_LAST_ACTIVITY_AT_KEY,
        localStorage.getItem(SESSION_LAST_ACTIVITY_AT_KEY)
            || localStorage.getItem(SESSION_STARTED_AT_KEY)
            || String(Date.now())
    );
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
    if (!hasValidSession()) {
        expireSessionForInactivity();
        return;
    }
    refreshSessionActivity();
    await enterAuthenticatedApp();
};

async function loadVehiclesAndCatalog() {
    const now = getManausDateParts();
    try {
        const [vehicles, catalog, activities, washOverview, materials] = await Promise.all([
            apiFetch("/veiculos?ativos=true"),
            apiFetch("/config/checklists"),
            apiFetch("/atividades?status=ABERTA"),
            apiFetch(`/lavagens/visao?ano=${now.year}&mes=${now.month}`),
            apiFetch("/materiais?ativos=true"),
        ]);
        state.vehicles = vehicles.filter((vehicle) => vehicle.ativo !== false && isPortEquipment(vehicle));
        state.catalog = normalizeCatalog(catalog);
        state.activities = activities || [];
        state.washOverview = washOverview;
        state.materials = materials || [];
        cacheOfflineReferenceData();
    } catch (error) {
        if (loadOfflineReferenceData()) {
            state.activities = [];
            state.materials = [];
            state.washOverview = { cronograma: { days: [] }, periodo: { ano: state.washYear, mes: state.washMonth } };
            showToast("DADOS OFFLINE CARREGADOS PARA CHECKLIST.", false);
            return;
        }
        throw error;
    }
}

async function loadOpenActivities() {
    state.activities = await apiFetch("/atividades?status=ABERTA");
}

async function loadWashOverview() {
    state.washOverview = await apiFetch(`/lavagens/visao?ano=${state.washYear}&mes=${state.washMonth}`);
}

function syncMenuGroupHeadings() {
    const groups = {
        equipamentos: [
            "open-checklist-menu",
            "open-checklist-history-menu",
            "open-checklist-catalog-menu",
            "open-activities-menu",
            "open-availability-menu",
            "open-technical-inspections-menu",
            "open-technical-library-menu",
            "open-equipment-reports-menu",
        ],
        manutencao: [
            "open-maintenance-menu",
            "open-non-conformities-menu",
            "open-emergencies-menu",
            "open-washes-menu",
            "open-preventives-menu",
            "open-maintenance-dashboard-menu",
            "open-maintenance-reports-menu",
        ],
        rh: ["open-hr-journey-menu", "open-rh-admin-menu"],
        administracao: ["open-admin-settings-menu"],
        "materiais-compras": ["open-mmp-stock-menu", "open-purchases-menu"],
        absenteismo: ["open-absenteeism-menu"],
        "escala-dsr": ["open-special-schedule-menu"],
    };

    document.querySelectorAll(".menu-group-heading[data-menu-heading]").forEach((heading) => {
        const ids = groups[heading.dataset.menuHeading] || [];
        const hasVisibleCard = ids.some((id) => {
            const card = document.getElementById(id);
            return card && !card.classList.contains("hidden");
        });
        heading.classList.toggle("hidden", !hasVisibleCard);
    });
}

function renderHome() {
    syncTopbarUserIdentity();
    const canViewMaintenanceDashboard = ["admin", "gestor"].includes(String(state.user?.tipo || "").toLowerCase());
    elements.openChecklistCatalogMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openRhAdminMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openAdminSettingsMenu?.classList.toggle("hidden", !hasAdminAccess());
    elements.openAdminCatalogsMenu?.classList.toggle("hidden", !hasAdminAccess());
    elements.openMmpStockMenu?.classList.toggle("hidden", !hasMmpAccess());
    elements.openPurchasesMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openPurchasesReportsMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openEquipmentReportsMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openMaintenanceReportsMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openPlanningMenu?.classList.toggle("hidden", !hasWashReportAccess());
    elements.openMaintenanceDashboardMenu?.classList.toggle("hidden", !canViewMaintenanceDashboard);
    elements.openPreventivesMenu?.classList.toggle("hidden", !canViewMaintenanceDashboard);
    elements.openWeeklyDsrMenu?.classList.toggle("hidden", !canViewMaintenanceDashboard);
    elements.openSpecialScheduleMenu?.classList.toggle("hidden", !canViewMaintenanceDashboard);
    elements.openAbsenteeismMenu?.classList.toggle("hidden", !canViewMaintenanceDashboard);
    const openActivitiesCount = state.activities.filter((activity) => activity.status === "ABERTA").length;
    const programmedWashesCount = getWashScheduleItems().filter((item) => item.status_execucao !== "LAVADO").length;
    const canAccessMechanicModule = hasMechanicWorkspaceAccess();
    elements.homeSummary.innerHTML = `
        <div>
            <span>USUÁRIO</span>
            <strong>${escapeHtml(state.user.nome)}</strong>
        </div>
        <div>
            <span>EQUIPAMENTOS</span>
            <strong>${state.vehicles.length} ATIVOS</strong>
        </div>
        <div>
            <span>INSPEÇÕES</span>
            <strong>${openActivitiesCount} ABERTAS</strong>
        </div>
        <div>
            <span>LAVAGENS</span>
            <strong>${programmedWashesCount} PROGRAMADAS</strong>
        </div>
    `;
    if (elements.openNonConformitiesMenu) {
        elements.openNonConformitiesMenu.classList.toggle("hidden", !canAccessMechanicModule);
    }
    if (elements.openMaintenanceMenu) {
        elements.openMaintenanceMenu.classList.toggle("hidden", !canAccessMechanicModule);
    }
    syncMenuGroupHeadings();
    syncTopbarNavigation();
    refreshSyncQueuePanel();
    refreshCloudAdminPanel();
    refreshAdminResetPanel();
}

async function refreshAdminResetPanel() {
    if (!elements.adminResetPanel) return;
    if (!hasAdminAccess()) { elements.adminResetPanel.classList.add("hidden"); return; }
    elements.adminResetPanel.classList.remove("hidden");
    try {
        const rows = await apiFetch("/auth/reset-solicitacoes");
        const pending = (rows || []).filter((row) => row.status === "PENDENTE");
        elements.adminResetList.innerHTML = pending.length ? pending.map((row) => `
            <div class="reset-request-row"><strong>${escapeHtml(row.requested_login)}</strong><input data-reset-password="${row.id}" type="password" placeholder="Nova senha (6+)" minlength="6"><button class="icon-button" data-reset-request="${row.id}" type="button">ATENDER</button></div>
        `).join("") : "<span>Nenhuma solicitação pendente.</span>";
        elements.adminResetList.querySelectorAll("[data-reset-request]").forEach((button) => button.addEventListener("click", async () => {
            const id = button.dataset.resetRequest;
            const password = elements.adminResetList.querySelector(`[data-reset-password=\"${id}\"]`)?.value || "";
            if (password.length < 6) { showToast("Informe uma senha com pelo menos 6 caracteres.", true); return; }
            try { await apiFetch(`/auth/reset-solicitacoes/${id}/atender`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nova_senha: password }) }); showToast("RESET ATENDIDO."); refreshAdminResetPanel(); }
            catch (error) { showToast(error.message, true); }
        }));
    } catch (error) { elements.adminResetList.innerHTML = `<span>${escapeHtml(error.message || "Não foi possível carregar os resets.")}</span>`; }
}

function hasAdminAccess() {
    return String(state.user?.tipo || "").toLowerCase() === "admin";
}

function hasWashReportAccess() {
    const userType = String(state.user?.tipo || "").toLowerCase();
    return userType === "admin" || userType === "gestor";
}

function hasMechanicWorkspaceAccess() {
    const userType = String(state.user?.tipo || "").toLowerCase();
    return userType === "admin" || userType === "gestor" || userType === "mecanico" || userType === "operacional";
}

function hasMmpAccess() {
    return hasMechanicWorkspaceAccess();
}

function hasMaintenanceAccess() {
    return hasMechanicWorkspaceAccess();
}

function formatUsage(section) {
    return `${section.percent}% | ${section.used_mb} MB DE ${section.limit_mb} MB`;
}

function normalizeStorageSection(section) {
    return {
        used_mb: Number(section?.used_mb ?? 0),
        limit_mb: Number(section?.limit_mb ?? 0),
        percent: Number(section?.percent ?? 0),
        level: String(section?.level || "ok").toLowerCase(),
    };
}

async function refreshCloudAdminPanel() {
    if (!elements.cloudAdminPanel) {
        return;
    }
    if (!hasAdminAccess()) {
        elements.cloudAdminPanel.classList.add("hidden");
        return;
    }

    elements.cloudAdminPanel.classList.remove("hidden");
    elements.cloudStorageSummary.textContent = "VERIFICANDO ARMAZENAMENTO...";
    elements.cloudStorageDetail.innerHTML = "";
    try {
        const status = await apiFetch("/admin/storage/status");
        const database = normalizeStorageSection(status?.database);
        const storage = normalizeStorageSection(status?.storage);
        const level = [database.level, storage.level].includes("critico")
            ? "CRÍTICO"
            : [database.level, storage.level].includes("vermelho")
                ? "ATENÇÃO"
                : [database.level, storage.level].includes("amarelo")
                    ? "OBSERVAR"
                    : "OK";
        elements.cloudStorageSummary.textContent = `${level} | BANCO ${database.percent}% | FOTOS ${storage.percent}%`;
        elements.cloudStorageDetail.innerHTML = `
            <article class="sync-row">
                <div>
                    <strong>BANCO DE DADOS</strong>
                    <span>${escapeHtml(formatUsage(database))}</span>
                </div>
                <em>${escapeHtml(String(database.level).toUpperCase())}</em>
            </article>
            <article class="sync-row">
                <div>
                    <strong>FOTOS/STORAGE</strong>
                    <span>${escapeHtml(formatUsage(storage))}</span>
                </div>
                <em>${escapeHtml(String(storage.level).toUpperCase())}</em>
            </article>
        `;
        if (["critico", "vermelho", "amarelo"].includes(database.level) || ["critico", "vermelho", "amarelo"].includes(storage.level)) {
            showToast("ARMAZENAMENTO DA NUVEM PERTO DO LIMITE. GERE UM BACKUP.");
        }
    } catch (error) {
        elements.cloudStorageSummary.textContent = "NÃO FOI POSSÍVEL VERIFICAR A NUVEM.";
        elements.cloudStorageDetail.innerHTML = `
            <article class="sync-row">
                <div>
                    <strong>STATUS INDISPONIVEL</strong>
                    <span>${escapeHtml(error.message || "FALHA AO CONSULTAR BACKUP.")}</span>
                </div>
            </article>
        `;
    }
}

async function createCloudBackup() {
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE GERAR BACKUP.", true);
        return;
    }
    elements.cloudBackupButton.disabled = true;
    elements.cloudBackupButton.textContent = "GERANDO...";
    try {
        const backup = await apiFetch("/admin/backups/create", { method: "POST" });
        await downloadBackupFile(backup);
        showToast(`BACKUP GERADO: ${backup.filename}`);
        await refreshCloudAdminPanel();
    } catch (error) {
        showToast(error.message || "FALHA AO GERAR BACKUP.", true);
    } finally {
        elements.cloudBackupButton.disabled = false;
        elements.cloudBackupButton.textContent = "BACKUP";
    }
}

async function downloadBackupFile(backup) {
    const response = await fetch(makeAbsoluteUrl(backup.download_url), {
        headers: {
            Authorization: `Bearer ${state.token}`,
        },
    });
    if (!response.ok) {
        throw new Error("BACKUP GERADO, MAS NÃO FOI POSSÍVEL BAIXAR O ARQUIVO.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = backup.filename || "backup-checklist.zip";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function downloadAuthorizedFile(path, filename) {
    const response = await fetch(`${state.apiBaseUrl}${path}`, {
        headers: {
            Authorization: state.token ? `Bearer ${state.token}` : "",
        },
    });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "NÃO FOI POSSÍVEL BAIXAR O ARQUIVO.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const CHECKLIST_CATALOG_TYPE_LABELS = {
    cavalo: "CAVALO",
    carreta: "CARRETA",
    carro_simples: "CARRO SIMPLES",
    cavalo_auxiliar: "CAVALO AUXILIAR",
    ambulancia: "AMBULÂNCIA",
    caminhao_pipa: "CAMINHÃO PIPA",
    caminhao_brigada: "CAMINHÃO BRIGADA",
    onibus: "ÔNIBUS",
    van: "VAN",
};

function checklistCatalogGrouping(item) {
    const grouping = item?.agrupamento || {};
    return {
        type: String(grouping.tipo_agrupamento || item?.tipo_agrupamento || "simples").toLowerCase(),
        parent: String(grouping.item_principal || item?.item_principal || item?.item_nome || ""),
        part: String(grouping.parte || item?.parte || ""),
    };
}

function filteredChecklistCatalogItems() {
    const filters = state.checklistCatalogAdmin.filters;
    const query = filters.search.trim().toLocaleLowerCase("pt-BR");
    return state.checklistCatalogAdmin.items
        .filter((item) => {
            const grouping = checklistCatalogGrouping(item);
            const isActive = Boolean(item.ativo);
            const activeMatches = filters.active === "all"
                || (filters.active === "true" && isActive)
                || (filters.active === "false" && !isActive);
            const typeMatches = !filters.type || String(item.tipo || item.vehicle_type || "") === filters.type;
            const searchable = [item.item_nome, item.tipo, grouping.type, grouping.parent, grouping.part, item.id]
                .join(" ")
                .toLocaleLowerCase("pt-BR");
            return activeMatches && typeMatches && (!query || searchable.includes(query));
        })
        .sort((left, right) => {
            const leftType = String(left.tipo || left.vehicle_type || "");
            const rightType = String(right.tipo || right.vehicle_type || "");
            return leftType.localeCompare(rightType, "pt-BR")
                || Number(left.position || 0) - Number(right.position || 0)
                || String(left.item_nome || "").localeCompare(String(right.item_nome || ""), "pt-BR");
        });
}

function renderChecklistCatalogAdmin() {
    if (!elements.checklistCatalogList) return;
    const allItems = state.checklistCatalogAdmin.items;
    const items = filteredChecklistCatalogItems();
    const activeCount = allItems.filter((item) => item.ativo).length;
    const inactiveCount = allItems.length - activeCount;
    const groupedCount = allItems.filter((item) => checklistCatalogGrouping(item).type !== "simples").length;
    const photoCount = allItems.filter((item) => item.foto_path).length;

    elements.checklistCatalogCounter.textContent = `${items.length} DE ${allItems.length} ITENS`;
    elements.checklistCatalogSummary.innerHTML = `
        <article><span>TOTAL</span><strong>${allItems.length}</strong></article>
        <article><span>ATIVOS</span><strong>${activeCount}</strong></article>
        <article><span>INATIVOS</span><strong>${inactiveCount}</strong></article>
        <article><span>AGRUPADOS / COM FOTO</span><strong>${groupedCount} / ${photoCount}</strong></article>
    `;

    if (!items.length) {
        renderStateCard(elements.checklistCatalogList, {
            title: allItems.length ? "NENHUM ITEM NESTE FILTRO" : "CATÁLOGO VAZIO",
            message: allItems.length
                ? "Ajuste a busca, o tipo ou a situação para localizar o item."
                : "Use Novo item para cadastrar o primeiro item do checklist.",
        });
        return;
    }

    elements.checklistCatalogList.innerHTML = items.map((item) => {
        const grouping = checklistCatalogGrouping(item);
        const type = String(item.tipo || item.vehicle_type || "");
        const photo = item.foto_path
            ? `<img src="${escapeHtml(makeAbsoluteUrl(item.foto_path))}" alt="Foto de referência de ${escapeHtml(item.item_nome || "item")}" loading="lazy">`
            : `<span class="checklist-catalog-photo-empty">SEM FOTO</span>`;
        return `
            <article class="checklist-catalog-card${item.ativo ? "" : " inactive"}">
                <div class="checklist-catalog-photo">${photo}</div>
                <div class="checklist-catalog-card-body">
                    <div class="checklist-catalog-card-top">
                        <span>${escapeHtml(CHECKLIST_CATALOG_TYPE_LABELS[type] || type.toUpperCase() || "SEM TIPO")} · ORDEM ${escapeHtml(String(item.position || "-"))}</span>
                        <em class="checklist-catalog-status ${item.ativo ? "active" : "inactive"}">${item.ativo ? "ATIVO" : "INATIVO"}</em>
                    </div>
                    <strong>${escapeHtml(item.item_nome || "ITEM SEM NOME")}</strong>
                    <p>${grouping.type === "simples" ? "ITEM SIMPLES" : `${grouping.type.toUpperCase()} · ${grouping.parent}${grouping.part ? ` · ${grouping.part}` : ""}`}</p>
                    <div class="checklist-catalog-card-actions">
                        <button class="icon-button" type="button" data-checklist-catalog-action="edit" data-checklist-catalog-id="${Number(item.id)}">EDITAR</button>
                        <button class="icon-button ${item.ativo ? "danger" : ""}" type="button" data-checklist-catalog-action="${item.ativo ? "inactivate" : "activate"}" data-checklist-catalog-id="${Number(item.id)}">${item.ativo ? "INATIVAR" : "REATIVAR"}</button>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

async function loadChecklistCatalogItems() {
    renderStateCard(elements.checklistCatalogList, {
        title: "CARREGANDO CATÁLOGO",
        message: "Buscando os itens ativos e inativos.",
        tone: "loading",
    });
    const items = await apiFetch("/checklist-itens?ativos=all");
    state.checklistCatalogAdmin.items = Array.isArray(items) ? items : [];
    renderChecklistCatalogAdmin();
}

async function openChecklistCatalogMenu() {
    if (!hasWashReportAccess()) {
        showToast("SOMENTE ADMIN OU GESTOR PODE CONFIGURAR O CATÁLOGO.", true);
        return;
    }
    setActiveScreen("checklistCatalog");
    try {
        await loadChecklistCatalogItems();
    } catch (error) {
        renderStateCard(elements.checklistCatalogList, {
            title: "NÃO FOI POSSÍVEL CARREGAR",
            message: error.message || "Tente novamente.",
            tone: "error",
        });
        showToast(error.message || "FALHA AO CARREGAR CATÁLOGO.", true);
    }
}

function syncChecklistCatalogGroupingFields() {
    const grouped = elements.checklistCatalogGroupType.value !== "simples";
    elements.checklistCatalogParentItem.disabled = !grouped;
    elements.checklistCatalogPart.disabled = !grouped;
    elements.checklistCatalogParentItem.required = grouped;
    elements.checklistCatalogPart.required = grouped;
    if (!grouped) {
        elements.checklistCatalogParentItem.value = "";
        elements.checklistCatalogPart.value = "";
    } else if (!elements.checklistCatalogParentItem.value.trim()) {
        elements.checklistCatalogParentItem.value = elements.checklistCatalogItemName.value.trim();
    }
}

function openChecklistCatalogModal(item = null) {
    state.checklistCatalogAdmin.editingId = item ? Number(item.id) : null;
    state.checklistCatalogAdmin.existingPhotoPath = item?.foto_path || "";
    const grouping = checklistCatalogGrouping(item || {});
    elements.checklistCatalogModalTitle.textContent = item ? "Editar item" : "Novo item";
    elements.checklistCatalogItemName.value = item?.item_nome || "";
    elements.checklistCatalogItemType.value = item?.tipo || item?.vehicle_type || state.checklistCatalogAdmin.filters.type || "cavalo";
    elements.checklistCatalogPosition.value = String(item?.position || 1);
    elements.checklistCatalogGroupType.value = grouping.type;
    elements.checklistCatalogParentItem.value = grouping.type === "simples" ? "" : grouping.parent;
    elements.checklistCatalogPart.value = grouping.type === "simples" ? "" : grouping.part;
    elements.checklistCatalogItemActive.checked = item ? Boolean(item.ativo) : true;
    elements.checklistCatalogPhoto.value = "";
    elements.checklistCatalogPhotoStatus.textContent = item?.foto_path ? "Foto atual será mantida se nenhuma nova for escolhida." : "Nenhuma foto cadastrada.";
    syncChecklistCatalogGroupingFields();
    elements.checklistCatalogModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    elements.checklistCatalogItemName.focus();
}

function closeChecklistCatalogModal() {
    elements.checklistCatalogModal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    elements.checklistCatalogForm.reset();
    state.checklistCatalogAdmin.editingId = null;
    state.checklistCatalogAdmin.existingPhotoPath = "";
}

async function submitChecklistCatalogItem(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const itemName = elements.checklistCatalogItemName.value.trim();
    const groupType = elements.checklistCatalogGroupType.value;
    if (!itemName) {
        showToast("INFORME O NOME DO ITEM.", true);
        return;
    }
    const payload = {
        item_nome: itemName,
        tipo: elements.checklistCatalogItemType.value,
        position: Number(elements.checklistCatalogPosition.value || 1),
        ativo: elements.checklistCatalogItemActive.checked,
        tipo_agrupamento: groupType,
        item_principal: groupType === "simples" ? "" : elements.checklistCatalogParentItem.value.trim(),
        parte: groupType === "simples" ? null : elements.checklistCatalogPart.value.trim(),
        foto_path: state.checklistCatalogAdmin.existingPhotoPath || null,
    };
    const photo = elements.checklistCatalogPhoto.files?.[0];
    elements.checklistCatalogSave.disabled = true;
    elements.checklistCatalogSave.textContent = "SALVANDO...";
    try {
        if (photo) {
            payload.foto_path = await uploadEvidence(photo, payload.tipo, itemName, "referencia", "CATALOGO_CHECKLIST");
        }
        const editingId = state.checklistCatalogAdmin.editingId;
        await apiFetch(editingId ? `/checklist-itens/${editingId}` : "/checklist-itens", {
            method: editingId ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        closeChecklistCatalogModal();
        await loadChecklistCatalogItems();
        showToast(editingId ? "ITEM ATUALIZADO." : "ITEM CADASTRADO.");
    } catch (error) {
        showToast(error.message || "FALHA AO SALVAR ITEM.", true);
    } finally {
        elements.checklistCatalogSave.disabled = false;
        elements.checklistCatalogSave.textContent = "SALVAR ITEM";
    }
}

async function changeChecklistCatalogItemStatus(item, activate) {
    if (!item || !hasWashReportAccess()) return;
    if (!activate && !window.confirm(`Inativar o item ${item.item_nome || item.id}?`)) return;
    try {
        if (activate) {
            await apiFetch(`/checklist-itens/${item.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ativo: true }),
            });
        } else {
            await apiFetch(`/checklist-itens/${item.id}`, { method: "DELETE" });
        }
        await loadChecklistCatalogItems();
        showToast(activate ? "ITEM REATIVADO." : "ITEM INATIVADO.");
    } catch (error) {
        showToast(error.message || "FALHA AO ALTERAR ITEM.", true);
    }
}

function openChecklistMenu() {
    renderVehicles();
    setActiveScreen("vehicles");
}

function formatDateInputValue(date) {
    const parts = getManausDateParts(date);
    const year = parts.year;
    const month = String(parts.month).padStart(2, "0");
    const day = String(parts.day).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

async function openChecklistHistoryMenu() {
    setActiveScreen("checklistHistory");
    elements.checklistHistoryCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.checklistHistoryTableWrap, {
        title: "CARREGANDO HISTORICO",
        message: "Buscando o periodo e a matriz de checklist.",
        tone: "loading",
    });
    if (elements.checklistHistorySummaryCard) {
        elements.checklistHistorySummaryCard.innerHTML = "";
    }
    try {
        if (!state.checklistHistory.dataInicio || !state.checklistHistory.dataFim) {
            const endDate = new Date();
            const startDate = new Date(endDate);
            startDate.setDate(endDate.getDate() - 6);
            state.checklistHistory.dataInicio = formatDateInputValue(startDate);
            state.checklistHistory.dataFim = formatDateInputValue(endDate);
        }

        if (elements.checklistHistoryTypeFilter) {
            elements.checklistHistoryTypeFilter.value = state.checklistHistory.tipo || "";
        }
        if (elements.checklistHistoryEquipmentSearch) {
            elements.checklistHistoryEquipmentSearch.value = state.checklistHistory.equipmentSearch || "";
        }
        if (elements.checklistHistoryStartDate) {
            elements.checklistHistoryStartDate.value = state.checklistHistory.dataInicio || "";
        }
        if (elements.checklistHistoryEndDate) {
            elements.checklistHistoryEndDate.value = state.checklistHistory.dataFim || "";
        }

        await loadChecklistHistory();
    } catch (error) {
        elements.checklistHistoryCounter.textContent = "FALHA";
        renderStateCard(elements.checklistHistoryTableWrap, {
            title: "NÃO FOI POSSÍVEL CARREGAR O HISTÓRICO",
            message: error.message || "Tente novamente em instantes.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

async function openActivitiesMenu() {
    setActiveScreen("activities");
    elements.activityCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.activitiesList, {
        title: "CARREGANDO INSPEÇÕES",
        message: "Buscando as inspeções em aberto para conferência em campo.",
        tone: "loading",
    });
    try {
        await loadOpenActivities();
        renderHome();
        renderActivities();
    } catch (error) {
        elements.activityCounter.textContent = "FALHA";
        renderStateCard(elements.activitiesList, {
            title: "NÃO FOI POSSÍVEL CARREGAR AS INSPEÇÕES",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

async function openWashesMenu() {
    setActiveScreen("washes");
    elements.washCounter.textContent = "CARREGANDO...";
    elements.washDayPanel.innerHTML = "";
    renderStateCard(elements.washesList, {
        title: "CARREGANDO LAVAGENS",
        message: "Buscando o cronograma mensal e os pareceres do dia.",
        tone: "loading",
    });
    try {
        await loadWashOverview();
        renderHome();
        renderWashes();
    } catch (error) {
        elements.washCounter.textContent = "FALHA";
        elements.washDayPanel.innerHTML = "";
        renderStateCard(elements.washesList, {
            title: "NÃO FOI POSSÍVEL CARREGAR AS LAVAGENS",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

async function openNonConformitiesMenu() {
    if (!hasMechanicWorkspaceAccess()) {
        showToast("MÓDULO DE NÃO CONFORMIDADES RESTRITO AO MECÂNICO E GESTÃO.", true);
        return;
    }
    state.selectedNonConformityItem = "";
    setActiveScreen("nonConformities");
    elements.nonConformitiesCounter.textContent = "CARREGANDO...";
    elements.nonConformitiesMacroCounter.textContent = "CARREGANDO...";
    elements.nonConformitiesChecklistCounter.textContent = "CARREGANDO...";
    elements.nonConformitiesMechanicCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.nonConformitiesMacroList, {
        title: "CARREGANDO INDICADORES",
        message: "Buscando os dados macro e micro de não conformidades.",
        tone: "loading",
        compact: true,
    });
    renderStateCard(elements.nonConformitiesMicroList, {
        title: "AGUARDE",
        message: "Montando a leitura detalhada dos itens.",
        tone: "loading",
        compact: true,
    });
    renderStateCard(elements.nonConformitiesChecklistList, {
        title: "CARREGANDO REGISTROS DE CHECKLIST",
        message: "Buscando não conformidades abertas e resolvidas.",
        tone: "loading",
    });
    renderStateCard(elements.nonConformitiesMechanicList, {
        title: "CARREGANDO REGISTROS INTERNOS",
        message: "Buscando as não conformidades abertas pelo mecânico.",
        tone: "loading",
    });
    try {
        await loadNonConformityHubData();
        renderHome();
        renderNonConformities();
    } catch (error) {
        elements.nonConformitiesCounter.textContent = "FALHA";
        elements.nonConformitiesMacroCounter.textContent = "FALHA";
        elements.nonConformitiesChecklistCounter.textContent = "FALHA";
        elements.nonConformitiesMechanicCounter.textContent = "FALHA";
        renderStateCard(elements.nonConformitiesMacroList, {
            title: "NÃO FOI POSSÍVEL CARREGAR OS INDICADORES",
            message: error.message || "Tente novamente em instantes.",
            tone: "error",
            compact: true,
        });
        renderStateCard(elements.nonConformitiesMicroList, {
            title: "LEITURA DETALHADA INDISPONIVEL",
            message: "A consulta não retornou os dados deste momento.",
            tone: "error",
            compact: true,
        });
        renderStateCard(elements.nonConformitiesChecklistList, {
            title: "NÃO FOI POSSÍVEL CARREGAR AS NÃO CONFORMIDADES",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        renderStateCard(elements.nonConformitiesMechanicList, {
            title: "NÃO FOI POSSÍVEL CARREGAR OS REGISTROS INTERNOS",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

async function openMaintenanceMenu() {
    if (!hasMaintenanceAccess()) {
        showToast("MÓDULO DE MANUTENÇÃO RESTRITO AO MECÂNICO E GESTÃO.", true);
        return;
    }
    setActiveScreen("maintenance");
    elements.maintenanceCounter.textContent = "CARREGANDO...";
    elements.maintenanceDayPanel.innerHTML = "";
    renderStateCard(elements.maintenanceList, {
        title: "CARREGANDO MANUTENÇÃO",
        message: "Buscando o cronograma mensal e os serviços programados.",
        tone: "loading",
    });
    try {
        await refreshPendingMaintenanceItemIds();
        await loadMaintenanceOverview();
        localStorage.setItem(maintenanceOfflineCacheKey(), JSON.stringify(state.maintenanceOverview));
        renderHome();
        renderMaintenance();
    } catch (error) {
        const cachedOverview = readJsonStorage(maintenanceOfflineCacheKey(), null)
            || (state.maintenanceFamilyFilter === "TODOS" ? readJsonStorage(OFFLINE_MAINTENANCE_KEY, null) : null);
        if (cachedOverview) {
            state.maintenanceOverview = cachedOverview;
            renderHome();
            renderMaintenance();
            showToast("MANUTENÇÃO OFFLINE CARREGADA. OS LANÇAMENTOS EXIGEM CONEXÃO.");
            return;
        }
        elements.maintenanceCounter.textContent = "FALHA";
        elements.maintenanceDayPanel.innerHTML = "";
        if (elements.maintenanceKanban) elements.maintenanceKanban.innerHTML = "";
        renderStateCard(elements.maintenanceList, {
            title: "NÃO FOI POSSÍVEL CARREGAR A MANUTENÇÃO",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

async function openPlanningMenu() {
    if (!hasWashReportAccess()) {
        showToast("PLANEJAMENTO RESTRITO AO GESTOR E ADMINISTRADOR.", true);
        return;
    }
    state.planningStatusFilter = "ABERTAS";
    state.maintenanceFamilyFilter = "TODOS";
    setActiveScreen("planning");
    elements.planningCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.planningList, {
        title: "CARREGANDO PLANEJAMENTO",
        message: "Buscando programações, pendências e bloqueios.",
        tone: "loading",
    });
    try {
        await loadMaintenanceOverview();
        localStorage.setItem(maintenanceOfflineCacheKey(), JSON.stringify(state.maintenanceOverview));
        renderHome();
        renderPlanning();
    } catch (error) {
        const cachedOverview = readJsonStorage(maintenanceOfflineCacheKey(), null);
        if (cachedOverview) {
            state.maintenanceOverview = cachedOverview;
            renderPlanning();
            showToast("PLANEJAMENTO OFFLINE CARREGADO. REPROGRAMAR EXIGE CONEXÃO.");
            return;
        }
        renderStateCard(elements.planningList, {
            title: "NÃO FOI POSSÍVEL CARREGAR O PLANEJAMENTO",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

function preventiveStatusLabel(status) {
    const labels = {
        NO_PRAZO: "NO PRAZO",
        ATENCAO: "ATENÇÃO",
        PROXIMA: "PRÓXIMA",
        CRITICA: "CRÍTICA",
        VENCIDA: "VENCIDA",
        SEM_DADOS: "SEM LEITURA",
        LEITURA_DESATUALIZADA: "LEITURA DESATUALIZADA",
    };
    return labels[String(status || "SEM_DADOS").toUpperCase()] || String(status || "SEM DADOS").replaceAll("_", " ");
}

function preventiveStatusClass(status) {
    return String(status || "SEM_DADOS").toLowerCase().replaceAll("_", "-");
}

function preventiveVehicleLabel(vehicle) {
    if (!vehicle) return "EQUIPAMENTO NÃO IDENTIFICADO";
    return vehicle.frota || vehicle.nome || vehicle.referencia || `ATIVO ${vehicle.id || "-"}`;
}

function renderPreventives() {
    const payload = state.preventives || {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const summary = payload.summary || {};
    const cards = [
        ["NO PRAZO", summary.NO_PRAZO || 0, "no-prazo"],
        ["ATENÇÃO", summary.ATENCAO || 0, "atencao"],
        ["PRÓXIMAS", summary.PROXIMA || 0, "proxima"],
        ["CRÍTICAS", summary.CRITICA || 0, "critica"],
        ["VENCIDAS", summary.VENCIDA || 0, "vencida"],
        ["SEM LEITURA", summary.SEM_DADOS || 0, "sem-dados"],
    ];
    elements.preventivesCounter.textContent = `${payload.totalPlans || items.length} PLANOS ATIVOS | ${payload.total_due_or_overdue || 0} VENCENDO OU VENCIDOS`;
    elements.preventivesSummary.innerHTML = cards.map(([label, value, tone]) => `
        <article class="preventive-summary-card tone-${tone}">
            <span>${label}</span>
            <strong>${Number(value)}</strong>
        </article>
    `).join("");
    if (!items.length) {
        renderStateCard(elements.preventivesList, {
            title: "NENHUMA PREVENTIVA CADASTRADA",
            message: "Quando o Desktop cadastrar um plano, ele aparecerá aqui com horímetro, prazo e situação.",
            tone: "neutral",
        });
        return;
    }
    elements.preventivesList.innerHTML = items.map((item) => {
        const due = item.due || {};
        const status = due.calculation_status || "SEM_DADOS";
        const vehicle = item.vehicle || {};
        const execution = item.execution || null;
        const materialCount = Array.isArray(execution?.materiais) ? execution.materiais.length : 0;
        return `
            <article class="preventive-mobile-row status-${preventiveStatusClass(status)}">
                <div class="preventive-mobile-row-head">
                    <div><strong>${escapeHtml(preventiveVehicleLabel(vehicle))}</strong><span>${escapeHtml(item.title || "PLANO PREVENTIVO")}</span></div>
                    <b>${escapeHtml(preventiveStatusLabel(status))}</b>
                </div>
                <div class="preventive-mobile-row-grid">
                    <div><span>HORÍMETRO ATUAL</span><strong>${due.current_hourmeter ?? "-"}</strong></div>
                    <div><span>HORAS RESTANTES</span><strong>${due.hours_remaining ?? "-"}</strong></div>
                    <div><span>PRÓXIMA PREVENTIVA</span><strong>${due.next_due_hourmeter ?? "-"}</strong></div>
                    <div><span>DATA PREVISTA</span><strong>${formatDate(item.next_due_date)}</strong></div>
                </div>
                <div class="preventive-mobile-row-foot"><span>OS: ${execution?.work_order_id ? `#${execution.work_order_id}` : "NÃO GERADA"}</span><span>MATERIAL: ${materialCount ? `${materialCount} VINCULADO(S)` : "NÃO VINCULADO"}</span></div>
            </article>
        `;
    }).join("");
}

async function openPreventivesMenu() {
    if (!hasWashReportAccess()) {
        showToast("MÓDULO DE PREVENTIVAS RESTRITO AO ADMIN E GESTOR.", true);
        return;
    }
    setActiveScreen("preventives");
    elements.preventivesCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.preventivesList, {
        title: "CARREGANDO PREVENTIVAS",
        message: "Consultando os planos ativos de RTG e LBS.",
        tone: "loading",
    });
    try {
        state.preventives = await apiFetch("/dashboard-manutencao/preventivas");
        renderPreventives();
    } catch (error) {
        elements.preventivesCounter.textContent = "FALHA AO CARREGAR";
        renderStateCard(elements.preventivesList, {
            title: "PREVENTIVAS INDISPONÍVEIS",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

const MODULE_REPORT_DEFINITIONS = {
    equipment: {
        title: "RELATÓRIOS DE EQUIPAMENTOS",
        subtitle: "Históricos e indicadores operacionais dos ativos.",
        badge: "EQUIPAMENTOS",
        context: "EQUIPAMENTOS",
        reports: [
            { label: "CHECKLIST", title: "HISTÓRICO DE CHECKLIST", description: "Matriz por equipamento, período e usuário executor.", action: "checklistHistory" },
            { label: "OPERAÇÃO", title: "DISPONIBILIDADE E HORÍMETRO", description: "Situação operacional, motivos, evidências e leituras.", action: "availability" },
            { label: "INSPEÇÕES", title: "INSPEÇÃO TÉCNICA", description: "Execuções dos modelos publicados por equipamento.", action: "technicalInspections" },
        ],
    },
    maintenance: {
        title: "RELATÓRIOS DE MANUTENÇÃO",
        subtitle: "Acompanhamento de ordens, preventivas, paradas e tratativas.",
        badge: "MANUTENÇÃO",
        context: "MANUTENÇÃO",
        reports: [
            { label: "ORDENS", title: "MANUTENÇÕES E OS", description: "Serviços direcionados, execução e histórico mensal.", action: "maintenance" },
            { label: "PLANOS", title: "PREVENTIVAS", description: "Vencimentos por horímetro, data e criticidade.", action: "preventives" },
            { label: "TRATATIVAS", title: "CENTRAL DE RESOLUÇÃO", description: "Não conformidades abertas, concluídas e evidências.", action: "nonConformities" },
            { label: "LAVAGENS", title: "HISTÓRICO DE LAVAGENS", description: "Programação, execução e exportação do período.", action: "washes" },
            { label: "INDICADORES", title: "DASHBOARD DE MANUTENÇÃO", description: "Disponibilidade, ordens e equipamentos críticos.", action: "maintenanceDashboard" },
        ],
    },
    purchases: {
        title: "RELATÓRIOS DE COMPRAS",
        subtitle: "Visão consolidada do ciclo SC, PC, NF e recebimento.",
        badge: "COMPRAS",
        context: "COMPRAS",
        reports: [
            { label: "CENTRAL", title: "CENTRAL DE PROCESSOS", description: "Pendências por item e próximo passo operacional.", action: "purchaseProcessCenter" },
            { label: "INDICADORES", title: "RESUMO DE COMPRAS", description: "Quantidades solicitadas, faturadas, recebidas e saldo.", action: "purchaseSummary" },
        ],
    },
};

function openModuleReports(moduleKey) {
    if (!hasWashReportAccess()) {
        showToast("RELATÓRIOS RESTRITOS AO ADMIN E GESTOR.", true);
        return;
    }
    const definition = MODULE_REPORT_DEFINITIONS[moduleKey];
    if (!definition) return;
    state.moduleReports = moduleKey;
    elements.moduleReportsTitle.textContent = definition.title;
    elements.moduleReportsSubtitle.textContent = definition.subtitle;
    elements.moduleReportsBadge.textContent = definition.badge;
    elements.moduleReportsContext.textContent = definition.context;
    elements.moduleReportsList.innerHTML = definition.reports.map((report) => `
        <button class="module-report-card" type="button" data-module-report-action="${escapeHtml(report.action)}">
            <span>${escapeHtml(report.label)}</span>
            <strong>${escapeHtml(report.title)}</strong>
            <em>${escapeHtml(report.description)}</em>
            <b>ABRIR RELATÓRIO</b>
        </button>
    `).join("");
    setActiveScreen("moduleReports");
}

function openModuleReportAction(action) {
    if (action === "checklistHistory") openChecklistHistoryMenu();
    else if (action === "availability") openAvailabilityMenu();
    else if (action === "technicalInspections") openTechnicalInspectionsMenu();
    else if (action === "maintenance") openMaintenanceMenu();
    else if (action === "preventives") openPreventivesMenu();
    else if (action === "nonConformities") openNonConformitiesMenu();
    else if (action === "washes") openWashesMenu();
    else if (action === "maintenanceDashboard") window.location.href = "./dashboard-manutencao/";
    else if (action === "purchaseProcessCenter") openPurchasesMenu({ focusReports: true });
    else if (action === "purchaseSummary") openPurchasesMenu({ focusReports: true });
}

function setAdminSettingsFeedback(title, html) {
    state.adminSettings.feedbackTitle = title;
    state.adminSettings.feedbackHtml = html;
    const titleElement = elements.adminSettingsFeedback?.querySelector(".module-header strong");
    if (titleElement) titleElement.textContent = title;
    if (elements.adminSettingsFeedbackContent) elements.adminSettingsFeedbackContent.innerHTML = html;
}

function openAdminSettingsHomePanel(panelId) {
    renderHome();
    setActiveScreen("home");
    const panel = document.getElementById(panelId);
    panel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function formatAdminDuration(seconds) {
    const total = Math.max(0, Number(seconds || 0));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (days) return `${days}d ${hours}h ${minutes}min`;
    if (hours) return `${hours}h ${minutes}min`;
    return `${minutes}min`;
}

function formatAdminDate(value) {
    return value ? formatManausDateTime(value) : "NUNCA REGISTRADA";
}

async function loadAdminSettingsUsers() {
    setAdminSettingsFeedback("CONSULTANDO LOGINS", "Carregando usuários e permissões personalizadas...");
    try {
        const users = await apiFetch("/usuarios");
        const rows = Array.isArray(users) ? users : [];
        state.adminSettings.users = rows;
        const active = rows.filter((user) => user.ativo !== false).length;
        const content = rows.length ? `
            <strong>${active} LOGIN(S) ATIVO(S) DE ${rows.length}</strong>
            <div class="admin-settings-user-list admin-settings-user-table">${rows.map((user) => `
                <article class="admin-settings-user-row">
                    <div class="admin-settings-user-identity"><strong>${escapeHtml(String(user.nome || user.login || "USUÁRIO").toUpperCase())}</strong><span>${escapeHtml(`@${user.login || "-"}`)} · ${escapeHtml(String(user.tipo || "-").toUpperCase())} · ${user.ativo === false ? "INATIVO" : "ATIVO"}</span></div>
                    <div class="admin-settings-user-meta"><span><b>CRIADO EM</b>${escapeHtml(formatAdminDate(user.created_at))}</span><span><b>ÚLTIMA ENTRADA</b>${escapeHtml(formatAdminDate(user.last_login_at))}</span><span><b>${user.session_open ? "SESSÃO ABERTA" : "ÚLTIMA SESSÃO"}</b>${escapeHtml(formatAdminDuration(user.session_duration_seconds))}</span></div>
                    <button class="secondary-button admin-user-edit-button" type="button" data-admin-user-edit="${Number(user.id)}">EDITAR USUÁRIO</button>
                </article>
            `).join("")}</div>
        ` : "Nenhum login retornado pela API.";
        setAdminSettingsFeedback("LOGINS E PERMISSÕES", content);
    } catch (error) {
        setAdminSettingsFeedback("FALHA NA CONSULTA", `<span>${escapeHtml(error.message || "Não foi possível consultar os logins.")}</span>`);
    }
}

function openAdminUserModal(userId) {
    if (!hasAdminAccess()) return;
    const user = state.adminSettings.users.find((row) => Number(row.id) === Number(userId));
    if (!user) return;
    state.adminSettings.editingUserId = Number(user.id);
    elements.adminUserModalTitle.textContent = `Editar usuário: ${String(user.login || user.nome || "").toUpperCase()}`;
    elements.adminUserId.value = String(user.id);
    elements.adminUserName.value = user.nome || "";
    elements.adminUserLogin.value = user.login || "";
    elements.adminUserType.value = user.tipo || "operacional";
    elements.adminUserPassword.value = "";
    elements.adminUserActive.checked = user.ativo !== false;
    elements.adminUserModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    elements.adminUserName.focus();
}

function closeAdminUserModal() {
    elements.adminUserModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
    state.adminSettings.editingUserId = null;
}

async function saveAdminUser(event) {
    event.preventDefault();
    const userId = Number(elements.adminUserId.value || state.adminSettings.editingUserId || 0);
    if (!userId) return;
    const payload = {
        nome: elements.adminUserName.value.trim(),
        login: elements.adminUserLogin.value.trim(),
        tipo: elements.adminUserType.value,
        ativo: elements.adminUserActive.checked,
    };
    const password = elements.adminUserPassword.value.trim();
    if (password) payload.senha = password;
    try {
        await apiFetch(`/usuarios/${userId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        closeAdminUserModal();
        showToast("USUÁRIO ATUALIZADO.");
        await loadAdminSettingsUsers();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL ATUALIZAR O USUÁRIO.", true);
    }
}

async function loadAdminSettingsRules() {
    setAdminSettingsFeedback("CONSULTANDO REGRAS", "Carregando regras administrativas e compatibilidade...");
    try {
        const [rules, compatibility, homologation] = await Promise.all([
            apiFetch("/admin/intelligent-rules"),
            apiFetch("/admin/compatibility-status"),
            apiFetch("/admin/homologation-status"),
        ]);
        const ruleCount = Object.keys(rules?.rules || {}).length;
        setAdminSettingsFeedback("CONFIGURAÇÃO ADMINISTRATIVA", `
            <strong>${ruleCount} regra(s) carregada(s)</strong>
            <span>Compatibilidade: ${escapeHtml(String(compatibility?.status_geral || "-"))}</span>
            <span>Homologação: ${escapeHtml(String(homologation?.status_geral || "-"))}</span>
        `);
    } catch (error) {
        setAdminSettingsFeedback("FALHA NA CONSULTA", `<span>${escapeHtml(error.message || "Não foi possível consultar as regras.")}</span>`);
    }
}

async function loadAdminSettingsAudit() {
    setAdminSettingsFeedback("CONSULTANDO AUDITORIA", "Verificando o serviço de auditoria...");
    try {
        const status = await apiFetch("/admin/audit-health");
        setAdminSettingsFeedback("AUDITORIA DO SISTEMA", `
            <strong>${status?.healthy ? "AUDITORIA OPERACIONAL" : "AUDITORIA COM ALERTA"}</strong>
            <span>Falhas registradas: ${Number(status?.failure_count || 0)}</span>
            ${status?.last_failure_message ? `<span>Última falha: ${escapeHtml(status.last_failure_message)}</span>` : "<span>Nenhuma falha recente registrada.</span>"}
        `);
    } catch (error) {
        setAdminSettingsFeedback("FALHA NA CONSULTA", `<span>${escapeHtml(error.message || "Não foi possível consultar a auditoria.")}</span>`);
    }
}

function openAdminSettings() {
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE ACESSAR A SALA DE CONTROLE.", true);
        return;
    }
    elements.adminSettingsRoleBadge.textContent = String(state.user?.tipo || "ADMIN").toUpperCase();
    setAdminSettingsFeedback(state.adminSettings.feedbackTitle, state.adminSettings.feedbackHtml);
    setActiveScreen("adminSettings");
}

function openAdminSettingsAction(action) {
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE OPERAR AS CONFIGURAÇÕES.", true);
        return;
    }
    if (action === "users") loadAdminSettingsUsers();
    else if (action === "rules") loadAdminSettingsRules();
    else if (action === "audit") loadAdminSettingsAudit();
    else if (action === "backup") openAdminSettingsHomePanel("cloud-admin-panel");
    else if (action === "resets") openAdminSettingsHomePanel("admin-reset-panel");
    else if (action === "purchase-import") openAdminPurchaseImport();
}

function openAdminCatalogs() {
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE ACESSAR OS CADASTROS.", true);
        return;
    }
    setActiveScreen("adminCatalogs");
}

async function openAdminCatalogAction(action) {
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE OPERAR OS CADASTROS.", true);
        return;
    }
    if (action === "providers") await openPurchasesMenu({ focusProviders: true });
    else if (action === "checklist") await openChecklistCatalogMenu();
    else if (action === "employees") {
        await openRhAdminMenu();
        setRhAdminTab("employees");
    } else if (action === "users") {
        openAdminSettings();
        openAdminSettingsAction("users");
    } else if (action === "stock") await openMmpStockMenu();
}

function openAdminPurchaseImport() {
    if (!hasAdminAccess()) return;
    setAdminSettingsFeedback("MIGRAÇÃO HISTÓRICA DE COMPRAS", `
        <strong>CONTROLE RESTRITO AO ADMINISTRADOR</strong>
        <span>Use somente para migrar uma fonte histórica autorizada. O mesmo arquivo não será duplicado.</span>
        <div class="purchases-import-row">
            <input id="admin-purchases-import-file" type="file" accept=".xlsx">
            <button id="admin-purchases-import-button" class="secondary-button" type="button">IMPORTAR BASE HISTÓRICA</button>
        </div>
        <div id="admin-purchases-import-feedback">Aguardando arquivo autorizado.</div>
    `);
    document.getElementById("admin-purchases-import-button")?.addEventListener("click", submitPurchaseImport);
}

const PURCHASE_STATUS_LABELS = {
    SOLICITADA: "SOLICITADA",
    APROVADA: "APROVADA",
    AGUARDANDO_PC: "AGUARDANDO PC",
    PC_PARCIAL: "PC PARCIAL",
    AGUARDANDO_NF: "AGUARDANDO NF",
    EM_TRANSITO: "EM TRÂNSITO",
    PARCIALMENTE_RECEBIDA: "RECEBIMENTO PARCIAL",
    RECEBIDA: "RECEBIDA",
    CANCELADA: "CANCELADA",
};

function purchaseRequestItemStatus(row) {
    const requestStatus = String(row?.status || "SOLICITADA").toUpperCase();
    const items = Array.isArray(row?.items) ? row.items : [];
    const itemStatuses = items.map((item) => String(item?.status || "").toUpperCase());
    if (itemStatuses.some((status) => status === "AGUARDANDO_PC") && ["SOLICITADA", "APROVADA"].includes(requestStatus)) {
        return "AGUARDANDO_PC";
    }
    if (itemStatuses.some((status) => status === "PC_PARCIAL")) return "PC_PARCIAL";
    if (itemStatuses.length && itemStatuses.every((status) => status === "AGUARDANDO_NF")) return "AGUARDANDO_NF";
    return requestStatus;
}

function purchaseRequestIsProviderPreferred(row) {
    return Boolean(row?.supplier?.preferred || row?.provider?.preferred || row?.supplier_preferred || row?.provider_preferred);
}

function purchaseRequestPriorityRank(priority) {
    return { CRITICA: 0, ALTA: 1, MEDIA: 2, BAIXA: 3 }[String(priority || "MEDIA").toUpperCase()] ?? 4;
}

function purchaseRequestSupportsCurrentReceiving(row) {
    const items = Array.isArray(row?.items) ? row.items : [];
    return !items.length || (items.length === 1 && String(items[0]?.item_type || "").toUpperCase() === "MATERIAL");
}

function renderPurchaseRequests() {
    if (!elements.purchasesRequestList) return;
    const rows = Array.isArray(state.purchases.requests) ? state.purchases.requests : [];
    const query = String(elements.purchasesRequestSearch?.value || "").trim().toLocaleLowerCase("pt-BR");
    const statusFilter = String(elements.purchasesRequestStatus?.value || "TODOS").toUpperCase();
    const sortKey = String(elements.purchasesRequestSort?.value || "RECENTES").toUpperCase();
    const filtered = rows.filter((row) => {
        const itemStatus = purchaseRequestItemStatus(row);
        const matchesStatus = statusFilter === "TODOS" || itemStatus === statusFilter || (statusFilter === "AGUARDANDO_PC" && String(row?.status || "").toUpperCase() === "SOLICITADA");
        if (!matchesStatus) return false;
        if (!query) return true;
        const material = row?.material || {};
        const firstItem = (row?.items || [])[0] || {};
        const haystack = [
            row?.code, row?.sc_number, row?.module, row?.requester_raw, row?.equipment_raw,
            row?.supplier?.name, row?.supplier?.trade_name, material?.referencia, material?.descricao,
            firstItem?.description_raw, firstItem?.product_code_raw,
        ].filter(Boolean).join(" ").toLocaleLowerCase("pt-BR");
        return haystack.includes(query);
    }).sort((left, right) => {
        if (sortKey === "PRIORIDADE") {
            const priorityDelta = purchaseRequestPriorityRank(left?.priority) - purchaseRequestPriorityRank(right?.priority);
            if (priorityDelta) return priorityDelta;
        }
        if (sortKey === "PROVEDOR_PREFERENCIAL") {
            const preferredDelta = Number(purchaseRequestIsProviderPreferred(right)) - Number(purchaseRequestIsProviderPreferred(left));
            if (preferredDelta) return preferredDelta;
            const providerDelta = String(left?.supplier?.name || "").localeCompare(String(right?.supplier?.name || ""), "pt-BR");
            if (providerDelta) return providerDelta;
        }
        return Number(right?.id || 0) - Number(left?.id || 0);
    });

    if (elements.purchasesRequestsCount) {
        elements.purchasesRequestsCount.textContent = `${filtered.length} de ${rows.length} ${rows.length === 1 ? "solicitação" : "solicitações"}`;
    }
    if (!filtered.length) {
        elements.purchasesRequestList.innerHTML = `<article class="purchases-request-empty"><strong>${rows.length ? "NENHUMA SOLICITAÇÃO NESTE FILTRO" : "NENHUMA SOLICITAÇÃO DE COMPRA"}</strong><span>${rows.length ? "Ajuste a busca ou o status para consultar outra SC." : "As solicitações aparecerão aqui quando forem registradas."}</span></article>`;
        renderPurchaseRequestBoard([]);
        return;
    }
    elements.purchasesRequestList.innerHTML = filtered.map((row) => {
        const status = purchaseRequestItemStatus(row);
        const statusLabel = PURCHASE_STATUS_LABELS[status] || status.replaceAll("_", " ");
        const priority = String(row?.priority || "MEDIA").toUpperCase();
        const material = row?.material || {};
        const firstItem = (row?.items || [])[0] || {};
        const materialName = material?.descricao || firstItem?.description_raw || "Material não informado";
        const materialReference = material?.referencia || firstItem?.product_code_raw || "Sem referência";
        const supplierName = row?.supplier?.name || "Provedor ainda não definido";
        const preferred = purchaseRequestIsProviderPreferred(row);
        const quantity = row?.requested_quantity ?? firstItem?.quantity_requested ?? "-";
        const expectedDate = row?.expected_date ? formatManausDateTime(row.expected_date, { short: true }) : "Sem previsão";
        const canApprove = hasAdminAccess() && String(row?.status || "").toUpperCase() === "SOLICITADA";
        const canReceive = hasWashReportAccess() && purchaseRequestSupportsCurrentReceiving(row) && ["APROVADA", "EM_TRANSITO", "PARCIALMENTE_RECEBIDA"].includes(String(row?.status || "").toUpperCase());
        return `<article class="purchases-request-card">
            <header><div><span class="purchases-request-code">${escapeHtml(row?.sc_number || row?.code || "SC")}</span><strong>${escapeHtml(materialName)}</strong><em>${escapeHtml(materialReference)}</em></div><b class="purchases-request-status status-${status.toLowerCase()}">${escapeHtml(statusLabel)}</b></header>
            <div class="purchases-request-details"><span><small>MÓDULO</small>${escapeHtml(row?.module || "COMPRAS")}</span><span><small>QUANTIDADE</small>${escapeHtml(String(quantity))}</span><span><small>PRIORIDADE</small><b class="purchases-request-priority priority-${priority.toLowerCase()}">${escapeHtml(priority)}</b></span><span><small>PREVISÃO</small>${escapeHtml(expectedDate)}</span></div>
            <footer><span>${escapeHtml(supplierName)}${preferred ? " · PREFERENCIAL" : ""}</span><span>${escapeHtml(row?.requester_raw || "Solicitante não informado")}</span></footer>
            <div class="purchases-request-actions"><button class="secondary-button" type="button" data-purchase-open="${Number(row?.id || 0)}">ABRIR</button>${canApprove ? `<button class="secondary-button" type="button" data-purchase-approve="${Number(row?.id || 0)}">APROVAR</button>` : ""}${canReceive ? `<button class="primary-button" type="button" data-purchase-receive="${Number(row?.id || 0)}">RECEBER</button>` : ""}</div>
        </article>`;
    }).join("");
    renderPurchaseRequestBoard(filtered);
}

const PURCHASE_REQUEST_KANBAN_COLUMNS = [
    ["SOLICITADA", "SOLICITADAS", "Aguardando análise."],
    ["APROVADA", "APROVADAS", "Liberadas para montar PC."],
    ["AGUARDANDO_PC", "AGUARDANDO PC", "Sem pedido emitido."],
    ["PC_PARCIAL", "PC PARCIAL", "Pedido incompleto."],
    ["AGUARDANDO_NF", "AGUARDANDO NF", "PC sem nota fiscal."],
    ["EM_TRANSITO", "EM TRÂNSITO", "Compra em entrega."],
    ["PARCIALMENTE_RECEBIDA", "RECEBIMENTO PARCIAL", "Ainda há saldo."],
    ["RECEBIDA", "RECEBIDAS", "Processo concluído."],
];

function purchaseRequestKanbanCard(row) {
    const item = (row?.items || [])[0] || {};
    const material = row?.material || {};
    const description = material?.descricao || item?.description_raw || "Material não informado";
    const quantity = row?.requested_quantity ?? item?.quantity_requested ?? "-";
    const priority = String(row?.priority || "MEDIA").toUpperCase();
    const status = purchaseRequestItemStatus(row);
    return `<article class="purchases-kanban-card"><div><b>${escapeHtml(row?.sc_number || row?.code || "SC")}</b><strong>${escapeHtml(description)}</strong><small>${escapeHtml(row?.module || "COMPRAS")} · ${escapeHtml(String(quantity))} un. · ${escapeHtml(priority)}</small></div><button class="secondary-button" type="button" data-purchase-open="${Number(row?.id || 0)}">ABRIR SC</button></article>`;
}

function renderPurchaseRequestBoard(rows = state.purchases.requests || []) {
    if (!elements.purchasesRequestBoard) return;
    elements.purchasesRequestBoard.innerHTML = PURCHASE_REQUEST_KANBAN_COLUMNS.map(([key, title, helper]) => {
        const cards = rows.filter((row) => purchaseRequestItemStatus(row) === key).map(purchaseRequestKanbanCard);
        return purchaseKanbanColumnMarkup(key, title, helper, cards);
    }).join("");
}

function renderPurchaseMaterialOptions() {
    const materials = Array.isArray(state.materials) ? state.materials.filter((material) => material?.ativo !== false) : [];
    const options = materials.length
        ? `<option value="">Selecione um material</option>${materials.map((material) => `<option value="${Number(material.id)}">${escapeHtml(`${material.referencia || "SEM REF."} — ${material.descricao || "MATERIAL"}`)}</option>`).join("")}`
        : `<option value="">Nenhum material ativo encontrado</option>`;
    elements.purchaseRequestItems?.querySelectorAll(".purchase-request-item-material").forEach((select) => {
        const selected = select.value;
        select.innerHTML = options;
        if (selected) select.value = selected;
    });
}

async function loadPurchaseMaterials() {
    if (!Array.isArray(state.materials) || !state.materials.length) {
        state.materials = await apiFetch("/materiais?ativos=true");
    }
    renderPurchaseMaterialOptions();
}

function purchaseRequestItemMarkup(item = {}) {
    const materials = Array.isArray(state.materials) ? state.materials.filter((material) => material?.ativo !== false) : [];
    const options = materials.length
        ? `<option value="">Selecione um material</option>${materials.map((material) => `<option value="${Number(material.id)}" ${Number(item.material_id) === Number(material.id) ? "selected" : ""}>${escapeHtml(`${material.referencia || "SEM REF."} — ${material.descricao || "MATERIAL"}`)}</option>`).join("")}`
        : `<option value="">Carregando materiais...</option>`;
    const type = String(item.item_type || "MATERIAL").toUpperCase() === "SERVICO" ? "SERVICO" : "MATERIAL";
    return `<article class="purchase-request-item-row" data-item-type="${type}">
        <div class="purchase-request-item-row-header"><strong>ITEM</strong><button class="icon-button" type="button" data-purchase-remove-item="true">REMOVER</button></div>
        <label class="modal-field"><span>TIPO *</span><select class="purchase-request-item-type"><option value="MATERIAL" ${type === "MATERIAL" ? "selected" : ""}>MATERIAL</option><option value="SERVICO" ${type === "SERVICO" ? "selected" : ""}>SERVIÇO</option></select></label>
        <label class="modal-field purchase-request-item-material-field ${type === "SERVICO" ? "hidden" : ""}"><span>MATERIAL *</span><select class="purchase-request-item-material">${options}</select></label>
        <label class="modal-field purchase-request-item-service-field ${type === "MATERIAL" ? "hidden" : ""}"><span>DESCRIÇÃO DO SERVIÇO *</span><input class="purchase-request-item-service" maxlength="255" value="${escapeHtml(item.description_raw || "")}" placeholder="Ex.: reparo de bomba hidráulica"></label>
        <label class="modal-field"><span>QUANTIDADE *</span><input class="purchase-request-item-quantity" type="number" min="1" step="1" value="${Number(item.quantity_requested || 1)}" required></label>
        <label class="modal-field"><span>UNIDADE</span><input class="purchase-request-item-unit" maxlength="30" value="${escapeHtml(item.unit_of_measure || "UN")}" placeholder="UN, KIT..."></label>
        <label class="modal-field purchase-request-field-wide"><span>OBSERVAÇÃO DO ITEM</span><input class="purchase-request-item-notes" maxlength="500" value="${escapeHtml(item.notes || "")}" placeholder="Informação específica deste item"></label>
    </article>`;
}

function renderPurchaseRequestItems() {
    if (!elements.purchaseRequestItems) return;
    const rows = elements.purchaseRequestItems.querySelectorAll(".purchase-request-item-row");
    if (!rows.length) elements.purchaseRequestItems.innerHTML = purchaseRequestItemMarkup();
}

function addPurchaseRequestItem(item = {}) {
    if (!elements.purchaseRequestItems) return;
    elements.purchaseRequestItems.insertAdjacentHTML("beforeend", purchaseRequestItemMarkup(item));
}

function togglePurchaseRequestItemType(row) {
    const type = String(row.querySelector(".purchase-request-item-type")?.value || "MATERIAL").toUpperCase();
    row.dataset.itemType = type;
    row.querySelector(".purchase-request-item-material-field")?.classList.toggle("hidden", type !== "MATERIAL");
    row.querySelector(".purchase-request-item-service-field")?.classList.toggle("hidden", type !== "SERVICO");
}

async function openPurchaseRequestModal() {
    if (!hasWashReportAccess()) return;
    elements.purchaseRequestForm?.reset();
    if (elements.purchaseRequestScDate) elements.purchaseRequestScDate.value = formatDateInputValue(new Date());
    elements.purchaseRequestPriority && (elements.purchaseRequestPriority.value = "MEDIA");
    if (elements.purchaseRequestItems) elements.purchaseRequestItems.innerHTML = purchaseRequestItemMarkup();
    elements.purchaseRequestModal?.classList.remove("hidden");
    document.body.classList.add("modal-open");
    try {
        await loadPurchaseMaterials();
        renderPurchaseRequestItems();
        elements.purchaseRequestItems?.querySelector(".purchase-request-item-material")?.focus();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR OS MATERIAIS.", true);
    }
}

function closePurchaseRequestModal() {
    elements.purchaseRequestModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
}

async function submitPurchaseRequest(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const rows = [...(elements.purchaseRequestItems?.querySelectorAll(".purchase-request-item-row") || [])];
    if (!rows.length) { showToast("ADICIONE PELO MENOS UM ITEM.", true); return; }
    const items = [];
    for (const [index, row] of rows.entries()) {
        const itemType = String(row.querySelector(".purchase-request-item-type")?.value || "MATERIAL").toUpperCase();
        const quantity = Number(row.querySelector(".purchase-request-item-quantity")?.value || 0);
        if (!Number.isInteger(quantity) || quantity <= 0) { showToast(`INFORME UMA QUANTIDADE VÁLIDA NO ITEM ${index + 1}.`, true); return; }
        const item = { item_type: itemType, quantity, unit_of_measure: row.querySelector(".purchase-request-item-unit")?.value.trim() || "UN", notes: row.querySelector(".purchase-request-item-notes")?.value.trim() || null };
        if (itemType === "MATERIAL") {
            item.material_id = Number(row.querySelector(".purchase-request-item-material")?.value || 0);
            if (!item.material_id) { showToast(`SELECIONE O MATERIAL DO ITEM ${index + 1}.`, true); return; }
        } else {
            item.description_raw = row.querySelector(".purchase-request-item-service")?.value.trim() || "";
            if (!item.description_raw) { showToast(`INFORME A DESCRIÇÃO DO SERVIÇO NO ITEM ${index + 1}.`, true); return; }
        }
        items.push(item);
    }
    const submit = elements.purchaseRequestSubmit;
    if (submit) { submit.disabled = true; submit.textContent = "ABRINDO..."; }
    try {
        await apiFetch("/compras/solicitacoes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                items,
                sc_date: elements.purchaseRequestScDate?.value || null,
                external_quote_number: elements.purchaseRequestQuote?.value.trim() || null,
                requester_raw: elements.purchaseRequestRequester?.value.trim() || null,
                cost_center: elements.purchaseRequestCostCenter?.value.trim() || null,
                module: elements.purchaseRequestModule?.value.trim() || null,
                equipment_raw: elements.purchaseRequestEquipment?.value.trim() || null,
                work_order_number: elements.purchaseRequestWorkOrder?.value.trim() || null,
                priority: elements.purchaseRequestPriority?.value || "MEDIA",
                expected_date: elements.purchaseRequestExpectedDate?.value || null,
                observation: elements.purchaseRequestObservation?.value.trim() || null,
            }),
        });
        closePurchaseRequestModal();
        await loadPurchasesData();
        showToast("SOLICITAÇÃO DE COMPRA ABERTA.");
    } catch (error) {
        showToast(error.message || "FALHA AO ABRIR SOLICITAÇÃO.", true);
    } finally {
        if (submit) { submit.disabled = false; submit.textContent = "ABRIR SOLICITAÇÃO"; }
    }
}

function purchaseRequestById(id) {
    return (state.purchases.requests || []).find((row) => Number(row.id) === Number(id));
}

function renderPurchaseDetail(row) {
    if (!row || !elements.purchaseDetailContent) return;
    const status = purchaseRequestItemStatus(row);
    const remaining = Math.max(0, Number(row.requested_quantity || 0) - Number(row.received_quantity || 0));
    const material = row.material || {};
    if (elements.purchaseDetailTitle) elements.purchaseDetailTitle.textContent = row.sc_number || row.code || "Solicitação de compra";
    const receipts = Array.isArray(row.receipts) ? row.receipts : [];
    const receiptHistory = receipts.length ? receipts.map((receipt) => {
        const invoiceMatch = String(receipt.notes || "").match(/NOTA_FISCAL:\s*(\/\S+)/i);
        const note = String(receipt.notes || "").replace(/NOTA_FISCAL:\s*\/\S+/i, "").trim();
        const invoiceMeta = receipt.invoice_number ? `NF ${receipt.invoice_number}${receipt.invoice_series ? ` · Série ${receipt.invoice_series}` : ""}${receipt.invoice_date ? ` · ${formatManausDateTime(receipt.invoice_date, { short: true })}` : ""}${receipt.invoice_value !== null && receipt.invoice_value !== undefined ? ` · ${formatCurrency(receipt.invoice_value)}` : ""}` : "";
        return `<article class="purchase-receipt-history-item"><div><strong>${escapeHtml(formatManausDateTime(receipt.received_at, { short: true }) || "Recebimento")}</strong><span>${escapeHtml(String(receipt.quantity || 0))} unidade(s)${receipt.received_by?.nome ? ` · ${escapeHtml(receipt.received_by.nome)}` : ""}</span>${invoiceMeta ? `<em>${escapeHtml(invoiceMeta)}</em>` : ""}</div>${note ? `<p>${escapeHtml(note)}</p>` : ""}${invoiceMatch || receipt.invoice_file_path ? `<button class="secondary-button" type="button" data-purchase-file="${escapeHtml(receipt.invoice_file_path || invoiceMatch[1])}">ABRIR NOTA FISCAL</button>` : ""}</article>`;
    }).join("") : `<div class="purchase-receipt-history-empty">Nenhum recebimento registrado até o momento.</div>`;
    elements.purchaseDetailContent.innerHTML = `<div class="purchase-detail-grid"><span><small>MATERIAL</small><b>${escapeHtml(material.descricao || "Material não informado")}</b></span><span><small>STATUS</small><b class="purchases-request-status status-${status.toLowerCase()}">${escapeHtml(PURCHASE_STATUS_LABELS[status] || status)}</b></span><span><small>QUANTIDADE</small><b>${escapeHtml(String(row.requested_quantity ?? "-"))} solicitada(s)</b></span><span><small>RECEBIDO</small><b>${escapeHtml(String(row.received_quantity ?? 0))} | ${escapeHtml(String(remaining))} restante(s)</b></span><span><small>PRIORIDADE</small><b>${escapeHtml(row.priority || "MEDIA")}</b></span><span><small>PROVEDOR</small><b>${escapeHtml(row.supplier?.name || "Ainda não definido")}</b></span></div><p class="purchase-detail-observation">${escapeHtml(row.justification || row.observation || "Sem observação registrada.")}</p><section class="purchase-receipt-history"><header><div><span>RASTREABILIDADE</span><strong>HISTÓRICO DE RECEBIMENTOS</strong></div><em>${receipts.length} registro(s)</em></header><div class="purchase-receipt-history-list">${receiptHistory}</div></section>`;
    elements.purchaseDetailApprove?.classList.toggle("hidden", !(hasAdminAccess() && String(row.status || "").toUpperCase() === "SOLICITADA"));
    elements.purchaseDetailReceive?.classList.toggle("hidden", !(hasWashReportAccess() && purchaseRequestSupportsCurrentReceiving(row) && ["APROVADA", "EM_TRANSITO", "PARCIALMENTE_RECEBIDA"].includes(String(row.status || "").toUpperCase()) && remaining > 0));
}

async function openProtectedPurchaseFile(path) {
    if (!path) return;
    try {
        const response = await fetch(`${state.apiBaseUrl}${path}`, { headers: { Authorization: `Bearer ${state.token}` } });
        if (!response.ok) throw new Error("NOTA FISCAL NÃO DISPONÍVEL.");
        const objectUrl = URL.createObjectURL(await response.blob());
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.target = "_blank";
        anchor.rel = "noopener";
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) { showToast(error.message || "FALHA AO ABRIR NOTA FISCAL.", true); }
}

async function openPurchaseRequestDetails(id) {
    const row = purchaseRequestById(id);
    if (!row) return;
    state.purchases.selectedRequestId = Number(id);
    renderPurchaseDetail(row);
    elements.purchaseDetailModal?.classList.remove("hidden");
    document.body.classList.add("modal-open");
    try {
        const detail = await apiFetch(`/compras/solicitacoes/${Number(id)}`);
        state.purchases.requests = (state.purchases.requests || []).map((item) => Number(item.id) === Number(id) ? detail : item);
        renderPurchaseDetail(detail);
    } catch (error) {
        showToast(error.message || "DETALHES PARCIAIS DA SOLICITAÇÃO.", true);
    }
}

function closePurchaseDetailModal() {
    elements.purchaseDetailModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
    state.purchases.selectedRequestId = null;
}

async function approvePurchaseRequest(id) {
    if (!hasAdminAccess()) return;
    try {
        await apiFetch(`/compras/solicitacoes/${Number(id)}/aprovar`, { method: "POST" });
        closePurchaseDetailModal();
        await loadPurchasesData();
        showToast("SOLICITAÇÃO APROVADA.");
    } catch (error) { showToast(error.message || "FALHA AO APROVAR SOLICITAÇÃO.", true); }
}

function openPurchaseReceiveModal(id) {
    if (!hasWashReportAccess()) return;
    const row = purchaseRequestById(id);
    if (!row) return;
    const remaining = Math.max(0, Number(row.requested_quantity || 0) - Number(row.received_quantity || 0));
    elements.purchaseReceiveId.value = String(id);
    elements.purchaseReceiveQuantity.value = String(Math.max(1, remaining));
    elements.purchaseReceiveQuantity.max = String(remaining);
    elements.purchaseReceiveInvoiceNumber.value = "";
    elements.purchaseReceiveInvoiceSeries.value = "";
    elements.purchaseReceiveInvoiceDate.value = "";
    elements.purchaseReceiveInvoiceValue.value = "";
    elements.purchaseReceiveNotes.value = "";
    if (elements.purchaseReceiveInvoice) elements.purchaseReceiveInvoice.value = "";
    elements.purchaseReceiveHelp.textContent = `${row.sc_number || row.code || "SC"} — saldo disponível: ${remaining}.`;
    elements.purchaseReceiveModal?.classList.remove("hidden");
    document.body.classList.add("modal-open");
    elements.purchaseReceiveQuantity.focus();
}

function closePurchaseReceiveModal() {
    elements.purchaseReceiveModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
}

async function submitPurchaseReceive(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const id = Number(elements.purchaseReceiveId?.value || 0);
    const quantity = Number(elements.purchaseReceiveQuantity?.value || 0);
    if (!id || quantity < 1) { showToast("INFORME UMA QUANTIDADE VÁLIDA.", true); return; }
    try {
        const row = purchaseRequestById(id);
        const invoice = elements.purchaseReceiveInvoice?.files?.[0];
        let notes = elements.purchaseReceiveNotes?.value.trim() || "";
        let invoicePath = null;
        if (invoice) {
            invoicePath = await uploadEvidence(invoice, row?.sc_number || row?.code || `SC-${id}`, "NOTA_FISCAL", "nota_fiscal", "COMPRAS");
            notes = `${notes}${notes ? "\n" : ""}NOTA_FISCAL: ${invoicePath}`;
        }
        await apiFetch(`/compras/solicitacoes/${id}/recebimentos`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
            quantity,
            notes: notes || null,
            idempotency_key: `web-${id}-${Date.now()}`,
            invoice_number: elements.purchaseReceiveInvoiceNumber?.value.trim() || null,
            invoice_series: elements.purchaseReceiveInvoiceSeries?.value.trim() || null,
            invoice_date: elements.purchaseReceiveInvoiceDate?.value || null,
            invoice_value: elements.purchaseReceiveInvoiceValue?.value || null,
            invoice_file_path: invoicePath || null,
        }) });
        closePurchaseReceiveModal();
        closePurchaseDetailModal();
        await loadPurchasesData();
        showToast("RECEBIMENTO REGISTRADO.");
    } catch (error) { showToast(error.message || "FALHA AO REGISTRAR RECEBIMENTO.", true); }
}

function purchaseOrderPendingRows() {
    return (state.purchases.pendingPcItems || []).flatMap((group) => (group.items || []).map((item) => ({ ...item, ...group })));
}

function renderPurchaseOrderPending() {
    if (!elements.purchaseOrderPendingList) return;
    const rows = purchaseOrderPendingRows();
    elements.purchaseOrderForm?.classList.toggle("purchases-order-form-empty", !rows.length);
    if (elements.purchasesOrdersPendingCount) elements.purchasesOrdersPendingCount.textContent = `${rows.length} ${rows.length === 1 ? "item pendente" : "itens pendentes"}`;
    if (!rows.length) {
        elements.purchaseOrderPendingList.innerHTML = `<article class="purchases-request-empty"><strong>NENHUM ITEM AGUARDANDO PC</strong><span>Aprove uma SC para disponibilizar seus itens nesta etapa.</span></article>`;
        if (elements.purchaseOrderSubmit) elements.purchaseOrderSubmit.disabled = true;
        renderPurchaseOrderBoard([]);
        return;
    }
    if (elements.purchaseOrderSubmit) elements.purchaseOrderSubmit.disabled = false;
    elements.purchaseOrderPendingList.innerHTML = rows.map((item) => {
        const description = item.item_type === "SERVICO" ? item.description_raw : (item.material?.descricao || item.description_raw || "Material não informado");
        const reference = item.product_code_raw || item.material?.referencia || "Sem referência";
        const maxQuantity = Number(item.remaining_order_quantity || 0);
        return `<label class="purchase-order-pending-row"><input class="purchase-order-item-check" type="checkbox" data-purchase-order-item="${Number(item.id)}"><span class="purchase-order-pending-main"><b>${escapeHtml(item.sc_number || "SC")}</b><strong>${escapeHtml(description)}</strong><em>${escapeHtml(reference)} · ${escapeHtml(item.item_type || "ITEM")} · ${escapeHtml(item.module || "COMPRAS")}</em></span><span class="purchase-order-pending-balance"><small>PENDENTE</small><b>${escapeHtml(String(maxQuantity))}</b></span><input class="purchase-order-item-quantity" type="number" min="0.01" step="1" max="${maxQuantity}" value="${maxQuantity}" data-purchase-order-quantity="${Number(item.id)}" aria-label="Quantidade do item ${Number(item.id)}"></label>`;
    }).join("");
    renderPurchaseOrderBoard(rows);
}

function renderPurchaseOrderBoard(rows = purchaseOrderPendingRows()) {
    if (!elements.purchasesOrderBoard) return;
    const pendingCards = rows.map((item) => {
        const description = item.item_type === "SERVICO" ? item.description_raw : (item.material?.descricao || item.description_raw || "Material não informado");
        return `<article class="purchases-kanban-card"><div><b>${escapeHtml(item.sc_number || "SC")}</b><strong>${escapeHtml(description)}</strong><small>${escapeHtml(item.module || "COMPRAS")} · saldo ${escapeHtml(String(item.remaining_order_quantity || 0))}</small></div><span class="purchases-kanban-hint">SELECIONE NA LISTA PARA EMITIR</span></article>`;
    });
    const orderCards = (state.purchases.orders || []).map((order) => `<article class="purchases-kanban-card"><div><b>${escapeHtml(order.pc_number || "PC")}</b><strong>${escapeHtml(order.supplier_raw || "Provedor não informado")}</strong><small>${escapeHtml(order.status || "EMITIDO")} · ${(order.items || []).length} item(ns)</small></div><span class="purchases-kanban-hint">ABERTO</span></article>`);
    elements.purchasesOrderBoard.innerHTML = [
        purchaseKanbanColumnMarkup("AGUARDANDO_PC", "AGUARDANDO PC", "Itens aprovados para montar pedido.", pendingCards),
        purchaseKanbanColumnMarkup("EMITIDO", "PC EMITIDOS", "Pedidos já registrados.", orderCards),
    ].join("");
}

async function loadPurchaseOrdersData() {
    try {
        const [pending, orders] = await Promise.all([apiFetch("/compras/pedidos/pendentes"), apiFetch("/compras/pedidos")]);
        state.purchases.pendingPcItems = Array.isArray(pending) ? pending : [];
        state.purchases.orders = Array.isArray(orders) ? orders : [];
        renderPurchaseOrderPending();
        renderPurchaseOverview();
    } catch (error) {
        state.purchases.pendingPcItems = [];
        renderPurchaseOrderPending();
        showToast(error.message || "FALHA AO CARREGAR OS PEDIDOS DE COMPRA.", true);
    }
}

async function submitPurchaseOrder(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const selected = [...(elements.purchaseOrderPendingList?.querySelectorAll(".purchase-order-item-check:checked") || [])];
    if (!selected.length) { showToast("SELECIONE PELO MENOS UM ITEM PARA O PC.", true); return; }
    const items = [];
    for (const checkbox of selected) {
        const itemId = Number(checkbox.dataset.purchaseOrderItem || 0);
        const quantityInput = elements.purchaseOrderPendingList.querySelector(`[data-purchase-order-quantity="${itemId}"]`);
        const quantity = Number(quantityInput?.value || 0);
        const max = Number(quantityInput?.max || 0);
        if (!Number.isFinite(quantity) || quantity <= 0 || quantity > max) { showToast("A quantidade do PC deve respeitar o saldo pendente.", true); return; }
        items.push({ purchase_request_item_id: itemId, quantity_ordered: quantity });
    }
    const submit = elements.purchaseOrderSubmit;
    if (submit) { submit.disabled = true; submit.textContent = "EMITINDO..."; }
    try {
        await apiFetch("/compras/pedidos", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                pc_number: elements.purchaseOrderNumber?.value.trim() || null,
                pc_date: elements.purchaseOrderDate?.value || null,
                supplier_raw: elements.purchaseOrderProvider?.value.trim() || null,
                delivery_due_date: elements.purchaseOrderDeliveryDate?.value || null,
                total_value: elements.purchaseOrderTotal?.value || null,
                payment_terms: elements.purchaseOrderPaymentTerms?.value.trim() || null,
                notes: elements.purchaseOrderNotes?.value.trim() || null,
                items,
            }),
        });
        elements.purchaseOrderForm?.reset();
        if (elements.purchaseOrderDate) elements.purchaseOrderDate.value = formatDateInputValue(new Date());
        await loadPurchasesData();
        showToast("PC EMITIDO COM SUCESSO.");
    } catch (error) {
        showToast(error.message || "FALHA AO EMITIR PC.", true);
    } finally {
        if (submit) { submit.disabled = false; submit.textContent = "EMITIR PC SELECIONADO"; }
        renderPurchaseOrderPending();
    }
}

function purchaseInvoicePendingById(id) {
    return (state.purchases.pendingInvoices?.pending_nf || []).find((row) => Number(row.purchase_order_id) === Number(id));
}

function purchaseReceiptPendingById(id) {
    return (state.purchases.pendingInvoices?.pending_receipts || []).find((row) => Number(row.id) === Number(id));
}

function renderPurchaseInvoiceData() {
    const pendingNf = state.purchases.pendingInvoices?.pending_nf || [];
    const pendingReceipts = state.purchases.pendingInvoices?.pending_receipts || [];
    if (elements.purchasesInvoicesPendingCount) elements.purchasesInvoicesPendingCount.textContent = `${pendingNf.length} ${pendingNf.length === 1 ? "NF pendente" : "NFs pendentes"}`;
    if (elements.purchasesReceiptsPendingCount) elements.purchasesReceiptsPendingCount.textContent = `${pendingReceipts.length} ${pendingReceipts.length === 1 ? "item para receber" : "itens para receber"}`;
    if (elements.purchasesInvoicePendingList) {
        elements.purchasesInvoicePendingList.innerHTML = pendingNf.length ? pendingNf.map((order) => {
            const totalPending = (order.items || []).reduce((sum, item) => sum + Number(item.remaining_invoice_quantity || 0), 0);
            return `<article class="purchases-invoice-card"><header><div><span>${escapeHtml(order.pc_number || "PC")}</span><strong>${escapeHtml(order.supplier_raw || "Provedor não informado")}</strong></div><b class="purchases-invoice-balance">${escapeHtml(String(totalPending))} item(ns)</b></header><p>${(order.items || []).length} item(ns) aguardando faturamento.</p><button class="secondary-button" type="button" data-purchase-invoice-open="${Number(order.purchase_order_id)}">REGISTRAR NF</button></article>`;
        }).join("") : `<article class="purchases-invoice-empty"><strong>NENHUM PC AGUARDANDO NF</strong><span>Quando um PC for emitido, ele aparecerá aqui.</span></article>`;
    }
    if (elements.purchasesReceiptPendingList) {
        elements.purchasesReceiptPendingList.innerHTML = pendingReceipts.length ? pendingReceipts.map((item) => {
            const description = item.item_type === "SERVICO" ? item.description_raw : (item.material?.descricao || item.description_raw || "Material não informado");
            return `<article class="purchases-invoice-card"><header><div><span>${escapeHtml(item.invoice_number || "NF")} · ${escapeHtml(item.pc_number || "PC")}</span><strong>${escapeHtml(description)}</strong></div><b class="purchases-invoice-balance">${escapeHtml(String(item.remaining_receipt_quantity || 0))} pendente</b></header><p>${escapeHtml(item.sc_number || "SC")} · Faturado: ${escapeHtml(String(item.quantity_invoiced || 0))} · Recebido: ${escapeHtml(String(item.quantity_received || 0))}</p><button class="primary-button" type="button" data-purchase-invoice-receive="${Number(item.id)}">REGISTRAR ENTRADA</button></article>`;
        }).join("") : `<article class="purchases-invoice-empty"><strong>NENHUM ITEM AGUARDANDO RECEBIMENTO</strong><span>As entradas por NF aparecerão aqui para conferência.</span></article>`;
    }
    renderPurchaseInvoiceBoard(pendingNf, pendingReceipts);
}

function renderPurchaseInvoiceBoard(pendingNf = state.purchases.pendingInvoices?.pending_nf || [], pendingReceipts = state.purchases.pendingInvoices?.pending_receipts || []) {
    if (!elements.purchasesInvoiceBoard) return;
    const nfCards = pendingNf.map((order) => `<article class="purchases-kanban-card"><div><b>${escapeHtml(order.pc_number || "PC")}</b><strong>${escapeHtml(order.supplier_raw || "Provedor não informado")}</strong><small>${(order.items || []).length} item(ns) aguardando faturamento.</small></div><button class="secondary-button" type="button" data-purchase-invoice-open="${Number(order.purchase_order_id)}">REGISTRAR NF</button></article>`);
    const receiptCards = pendingReceipts.map((item) => {
        const description = item.item_type === "SERVICO" ? item.description_raw : (item.material?.descricao || item.description_raw || "Material não informado");
        return `<article class="purchases-kanban-card"><div><b>${escapeHtml(item.invoice_number || "NF")}</b><strong>${escapeHtml(description)}</strong><small>${escapeHtml(item.pc_number || "PC")} · saldo ${escapeHtml(String(item.remaining_receipt_quantity || 0))}</small></div><button class="primary-button" type="button" data-purchase-invoice-receive="${Number(item.id)}">REGISTRAR ENTRADA</button></article>`;
    });
    elements.purchasesInvoiceBoard.innerHTML = [
        purchaseKanbanColumnMarkup("AGUARDANDO_NF", "AGUARDANDO NF", "PC emitido sem nota.", nfCards),
        purchaseKanbanColumnMarkup("AGUARDANDO_RECEBIMENTO", "AGUARDANDO RECEBIMENTO", "NF registrada, aguardando entrada.", receiptCards),
        purchaseKanbanColumnMarkup("RECEBIDA", "CONCLUÍDOS", "Itens já recebidos.", []),
    ].join("");
}

async function loadPurchaseInvoiceData() {
    try {
        state.purchases.pendingInvoices = await apiFetch("/compras/notas/pendentes") || { pending_nf: [], pending_receipts: [] };
        renderPurchaseInvoiceData();
        renderPurchaseOverview();
    } catch (error) {
        state.purchases.pendingInvoices = { pending_nf: [], pending_receipts: [] };
        renderPurchaseInvoiceData();
        showToast(error.message || "FALHA AO CARREGAR AS NOTAS FISCAIS.", true);
    }
}

function openPurchaseInvoiceModal(purchaseOrder) {
    if (!hasWashReportAccess() || !purchaseOrder) return;
    elements.purchaseInvoiceForm?.reset();
    elements.purchaseInvoicePcId && (elements.purchaseInvoicePcId.value = String(purchaseOrder.purchase_order_id));
    if (elements.purchaseInvoiceDate) elements.purchaseInvoiceDate.value = formatDateInputValue(new Date());
    if (elements.purchaseInvoiceHelp) elements.purchaseInvoiceHelp.textContent = `${purchaseOrder.pc_number || "PC"} · ${purchaseOrder.supplier_raw || "Provedor não informado"}`;
    if (elements.purchaseInvoiceItems) {
        elements.purchaseInvoiceItems.innerHTML = (purchaseOrder.items || []).map((item) => {
            const description = item.item_type === "SERVICO" ? item.description_raw : (item.material?.descricao || item.description_raw || "Material não informado");
            const maxQuantity = Number(item.remaining_invoice_quantity || 0);
            return `<label class="purchase-invoice-item-row"><input class="purchase-invoice-item-check" type="checkbox" data-purchase-invoice-item="${Number(item.purchase_order_item_id)}"><span><b>${escapeHtml(item.sc_number || "SC")}</b><strong>${escapeHtml(description)}</strong><em>${escapeHtml(item.item_type || "ITEM")} · saldo do PC: ${escapeHtml(String(maxQuantity))}</em></span><input class="purchase-invoice-item-quantity" type="number" min="0.01" step="1" max="${maxQuantity}" value="${maxQuantity}" data-purchase-invoice-quantity="${Number(item.purchase_order_item_id)}" aria-label="Quantidade faturada"></label>`;
        }).join("");
    }
    elements.purchaseInvoiceModal?.classList.remove("hidden");
    elements.purchaseInvoiceNumber?.focus();
}

function closePurchaseInvoiceModal() {
    elements.purchaseInvoiceModal?.classList.add("hidden");
}

async function submitPurchaseInvoice(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const pc = purchaseInvoicePendingById(Number(elements.purchaseInvoicePcId?.value || 0));
    const selected = [...(elements.purchaseInvoiceItems?.querySelectorAll(".purchase-invoice-item-check:checked") || [])];
    if (!pc || !selected.length) { showToast("SELECIONE PELO MENOS UM ITEM DA NF.", true); return; }
    const items = [];
    for (const checkbox of selected) {
        const itemId = Number(checkbox.dataset.purchaseInvoiceItem || 0);
        const quantityInput = elements.purchaseInvoiceItems.querySelector(`[data-purchase-invoice-quantity="${itemId}"]`);
        const quantity = Number(quantityInput?.value || 0);
        const max = Number(quantityInput?.max || 0);
        if (!Number.isFinite(quantity) || quantity <= 0 || quantity > max) { showToast("A quantidade da NF deve respeitar o saldo do PC.", true); return; }
        items.push({ purchase_order_item_id: itemId, quantity_invoiced: quantity });
    }
    const submit = elements.purchaseInvoiceSubmit;
    if (submit) { submit.disabled = true; submit.textContent = "SALVANDO..."; }
    try {
        let filePath = null;
        const file = elements.purchaseInvoiceFile?.files?.[0];
        if (file) filePath = await uploadEvidence(file, pc.pc_number || "PC", "NOTA_FISCAL", "nota_fiscal", "COMPRAS");
        await apiFetch("/compras/notas", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                purchase_order_id: Number(pc.purchase_order_id),
                invoice_number: elements.purchaseInvoiceNumber?.value.trim() || null,
                series: elements.purchaseInvoiceSeries?.value.trim() || null,
                invoice_date: elements.purchaseInvoiceDate?.value || null,
                invoice_value: elements.purchaseInvoiceValue?.value || null,
                file_path: filePath,
                notes: elements.purchaseInvoiceNotes?.value.trim() || null,
                items,
            }),
        });
        closePurchaseInvoiceModal();
        await loadPurchasesData();
        showToast("NF VINCULADA AO PC COM SUCESSO.");
    } catch (error) {
        showToast(error.message || "FALHA AO REGISTRAR A NF.", true);
    } finally {
        if (submit) { submit.disabled = false; submit.textContent = "SALVAR NF"; }
    }
}

function openPurchaseInvoiceReceiveModal(invoiceItem) {
    if (!hasWashReportAccess() || !invoiceItem) return;
    state.purchases.selectedInvoiceId = Number(invoiceItem.invoice_id);
    state.purchases.selectedInvoiceItemId = Number(invoiceItem.id);
    if (elements.purchaseInvoiceReceiveId) elements.purchaseInvoiceReceiveId.value = String(invoiceItem.invoice_id);
    if (elements.purchaseInvoiceReceiveItemId) elements.purchaseInvoiceReceiveItemId.value = String(invoiceItem.id);
    if (elements.purchaseInvoiceReceiveQuantity) {
        elements.purchaseInvoiceReceiveQuantity.value = String(Math.max(1, Number(invoiceItem.remaining_receipt_quantity || 0)));
        elements.purchaseInvoiceReceiveQuantity.max = String(Number(invoiceItem.remaining_receipt_quantity || 0));
    }
    if (elements.purchaseInvoiceReceiveNotes) elements.purchaseInvoiceReceiveNotes.value = "";
    if (elements.purchaseInvoiceReceiveHelp) elements.purchaseInvoiceReceiveHelp.textContent = `${invoiceItem.invoice_number || "NF"} · ${invoiceItem.pc_number || "PC"} · saldo pendente: ${invoiceItem.remaining_receipt_quantity || 0}`;
    elements.purchaseInvoiceReceiveModal?.classList.remove("hidden");
    elements.purchaseInvoiceReceiveQuantity?.focus();
}

function closePurchaseInvoiceReceiveModal() {
    elements.purchaseInvoiceReceiveModal?.classList.add("hidden");
}

async function submitPurchaseInvoiceReceive(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const invoiceId = Number(elements.purchaseInvoiceReceiveId?.value || 0);
    const invoiceItemId = Number(elements.purchaseInvoiceReceiveItemId?.value || 0);
    const quantity = Number(elements.purchaseInvoiceReceiveQuantity?.value || 0);
    const max = Number(elements.purchaseInvoiceReceiveQuantity?.max || 0);
    if (!invoiceId || !invoiceItemId || !Number.isInteger(quantity) || quantity <= 0 || quantity > max) { showToast("Informe uma quantidade inteira dentro do saldo da NF.", true); return; }
    try {
        await apiFetch(`/compras/notas/${invoiceId}/recebimentos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ invoice_item_id: invoiceItemId, quantity_received: quantity, idempotency_key: `web-nf-${invoiceId}-${invoiceItemId}-${Date.now()}`, notes: elements.purchaseInvoiceReceiveNotes?.value.trim() || null }),
        });
        closePurchaseInvoiceReceiveModal();
        await loadPurchasesData();
        showToast("ENTRADA DA NF REGISTRADA.");
    } catch (error) {
        showToast(error.message || "FALHA AO REGISTRAR A ENTRADA.", true);
    }
}

function purchaseProcessStatusLabel(status) {
    return {
        AGUARDANDO_PC: "AGUARDANDO PC",
        PC_PARCIAL: "PC PARCIAL",
        AGUARDANDO_NF: "AGUARDANDO NF",
        AGUARDANDO_RECEBIMENTO: "AGUARDANDO RECEBIMENTO",
        PARCIALMENTE_RECEBIDA: "RECEBIMENTO PARCIAL",
        RECEBIDA: "RECEBIDA",
    }[status] || status || "SEM STATUS";
}

function renderPurchaseProcessCenter() {
    const data = state.purchases.processCenter || { summary: {}, items: [] };
    const summary = data.summary || {};
    const rows = data.items || [];
    if (elements.purchasesProcessCenterCount) elements.purchasesProcessCenterCount.textContent = `${rows.length} ${rows.length === 1 ? "item" : "itens"}`;
    if (elements.purchasesProcessPcCount) elements.purchasesProcessPcCount.textContent = String(summary.pending_pc || 0);
    if (elements.purchasesProcessNfCount) elements.purchasesProcessNfCount.textContent = String(summary.pending_nf || 0);
    if (elements.purchasesProcessReceiptCount) elements.purchasesProcessReceiptCount.textContent = String(summary.pending_receipt || 0);
    if (!elements.purchasesProcessList) return;
    if (!rows.length) {
        elements.purchasesProcessList.innerHTML = `<article class="purchases-process-empty"><strong>NENHUM ITEM ENCONTRADO</strong><span>Ajuste os filtros ou abra uma nova SC.</span></article>`;
        renderPurchaseProcessBoard();
        return;
    }
    elements.purchasesProcessList.innerHTML = rows.map((row) => {
        const description = row.item_type === "SERVICO" ? row.description_raw : (row.material?.descricao || row.description_raw || "Material não informado");
        const status = String(row.item_status || "").toLowerCase().replaceAll("_", "-");
        const actionLabel = { EMITIR_PC: "EMITIR PC", REGISTRAR_NF: "REGISTRAR NF", RECEBER_MATERIAL: "RECEBER", RECEBER_SALDO: "RECEBER SALDO", CONCLUIDO: "CONCLUÍDO" }[row.next_action] || "ABRIR SC";
        return `<article class="purchases-process-card"><div class="purchases-process-card-main"><header><span>${escapeHtml(row.sc_number || "SC")}</span><b class="purchases-process-status purchases-process-status-${escapeHtml(status)}">${escapeHtml(purchaseProcessStatusLabel(row.item_status))}</b></header><strong>${escapeHtml(description)}</strong><p>${escapeHtml(row.item_type || "ITEM")} · ${escapeHtml(row.module || "COMPRAS")} · ${escapeHtml(row.equipment_raw || "Equipamento não informado")}</p></div><div class="purchases-process-card-metrics"><span>SALDO</span><strong>${escapeHtml(String(row.remaining_quantity || 0))}</strong><small>Solicitado ${escapeHtml(String(row.requested_quantity || 0))} · Recebido ${escapeHtml(String(row.received_quantity || 0))}</small></div><button class="secondary-button" type="button" data-purchase-process-open="${Number(row.purchase_request_id)}">${escapeHtml(actionLabel)}</button></article>`;
    }).join("");
    renderPurchaseProcessBoard();
}

const PURCHASE_KANBAN_COLUMNS = [
    ["AGUARDANDO_PC", "AGUARDANDO PC", "Itens aprovados sem pedido."],
    ["PC_PARCIAL", "PC PARCIAL", "Pedido emitido parcialmente."],
    ["AGUARDANDO_NF", "AGUARDANDO NF", "PC sem nota fiscal."],
    ["AGUARDANDO_RECEBIMENTO", "AGUARDANDO RECEBIMENTO", "NF registrada, aguardando entrada."],
    ["PARCIALMENTE_RECEBIDA", "RECEBIMENTO PARCIAL", "Ainda existe saldo pendente."],
    ["RECEBIDA", "CONCLUÍDO", "Processo recebido."],
];

function purchaseKanbanColumnMarkup(key, title, helper, cards) {
    return `<section class="purchases-kanban-column purchases-kanban-${key.toLowerCase().replaceAll("_", "-")}"><header><div><span>${escapeHtml(title)}</span><small>${escapeHtml(helper)}</small></div><b>${cards.length}</b></header><div class="purchases-kanban-column-body">${cards.length ? cards.join("") : `<p class="purchases-kanban-empty">Nenhum item nesta etapa.</p>`}</div></section>`;
}

function purchaseProcessKanbanCard(row) {
    const description = row.item_type === "SERVICO" ? row.description_raw : (row.material?.descricao || row.description_raw || "Material não informado");
    const actionLabel = { EMITIR_PC: "EMITIR PC", REGISTRAR_NF: "REGISTRAR NF", RECEBER_MATERIAL: "RECEBER", RECEBER_SALDO: "RECEBER SALDO", CONCLUIDO: "CONCLUÍDO" }[row.next_action] || "ABRIR SC";
    return `<article class="purchases-kanban-card"><div><b>${escapeHtml(row.sc_number || "SC")}</b><strong>${escapeHtml(description)}</strong><small>${escapeHtml(row.module || "COMPRAS")} · saldo ${escapeHtml(String(row.remaining_quantity || 0))}</small></div><button class="secondary-button" type="button" data-purchase-process-open="${Number(row.purchase_request_id)}">${escapeHtml(actionLabel)}</button></article>`;
}

function renderPurchaseProcessBoard() {
    if (!elements.purchasesProcessBoard) return;
    const rows = state.purchases.processCenter?.items || [];
    elements.purchasesProcessBoard.innerHTML = PURCHASE_KANBAN_COLUMNS.map(([key, title, helper]) => {
        const cards = rows.filter((row) => String(row.item_status || "").toUpperCase() === key).map(purchaseProcessKanbanCard);
        return purchaseKanbanColumnMarkup(key, title, helper, cards);
    }).join("");
}

async function loadPurchaseProcessCenter() {
    const params = new URLSearchParams();
    const search = elements.purchasesProcessSearch?.value.trim();
    const status = elements.purchasesProcessStatus?.value || "TODOS";
    const itemType = elements.purchasesProcessType?.value || "TODOS";
    if (search) params.set("q", search);
    if (status !== "TODOS") params.set("status", status);
    if (itemType !== "TODOS") params.set("item_type", itemType);
    try {
        state.purchases.processCenter = await apiFetch(`/compras/central-processos${params.toString() ? `?${params.toString()}` : ""}`) || { summary: {}, items: [] };
        renderPurchaseProcessCenter();
    } catch (error) {
        state.purchases.processCenter = { summary: {}, items: [] };
        renderPurchaseProcessCenter();
        showToast(error.message || "FALHA AO CARREGAR A CENTRAL DE PROCESSOS.", true);
    }
}

function purchaseReportStatusLabel(status) {
    return purchaseProcessStatusLabel(status);
}

function renderPurchaseReportSummary() {
    const data = state.purchases.reportSummary || { summary: {}, by_status: {}, by_type: {}, by_provider: {} };
    const summary = data.summary || {};
    if (elements.purchasesReportMetrics) {
        const metrics = [
            ["PROCESSOS", summary.processes || 0],
            ["ITENS", summary.items || 0],
            ["SOLICITADO", summary.requested_quantity || 0],
            ["RECEBIDO", summary.received_quantity || 0],
            ["SALDO", summary.remaining_quantity || 0],
        ];
        elements.purchasesReportMetrics.innerHTML = metrics.map(([label, value]) => `<article><span>${label}</span><strong>${escapeHtml(String(value))}</strong></article>`).join("");
    }
    const renderList = (container, rows, formatter) => {
        if (!container) return;
        const entries = Object.entries(rows || {}).sort((left, right) => Number(right[1]?.items || right[1] || 0) - Number(left[1]?.items || left[1] || 0));
        container.innerHTML = entries.length ? entries.slice(0, 8).map(([label, value]) => formatter(label, value)).join("") : `<span class="purchases-report-empty">Sem dados no período.</span>`;
    };
    renderList(elements.purchasesReportStatusList, data.by_status, (label, value) => `<div><span>${escapeHtml(purchaseReportStatusLabel(label))}</span><b>${escapeHtml(String(value))}</b></div>`);
    renderList(elements.purchasesReportTypeList, data.by_type, (label, value) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(String(value.items || 0))} item(ns)</b></div>`);
    renderList(elements.purchasesReportProviderList, data.by_provider, (label, value) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(String(value))} PC(s)</b></div>`);
}

async function loadPurchaseReportSummary() {
    const params = new URLSearchParams();
    if (elements.purchasesReportDateFrom?.value) params.set("date_from", elements.purchasesReportDateFrom.value);
    if (elements.purchasesReportDateTo?.value) params.set("date_to", elements.purchasesReportDateTo.value);
    try {
        state.purchases.reportSummary = await apiFetch(`/compras/relatorios/resumo${params.toString() ? `?${params.toString()}` : ""}`) || { summary: {}, by_status: {}, by_type: {}, by_provider: {} };
        renderPurchaseReportSummary();
    } catch (error) {
        state.purchases.reportSummary = { summary: {}, by_status: {}, by_type: {}, by_provider: {} };
        renderPurchaseReportSummary();
        showToast(error.message || "FALHA AO CARREGAR O RELATÓRIO DE COMPRAS.", true);
    }
}

function purchaseReportQuery(format = "") {
    const params = new URLSearchParams();
    if (format) params.set("formato", format);
    if (elements.purchasesReportDateFrom?.value) params.set("date_from", elements.purchasesReportDateFrom.value);
    if (elements.purchasesReportDateTo?.value) params.set("date_to", elements.purchasesReportDateTo.value);
    return params.toString() ? `?${params.toString()}` : "";
}

async function exportPurchaseReport(format) {
    if (!hasWashReportAccess()) return;
    try {
        const extension = format === "PDF" ? "pdf" : "xlsx";
        const period = elements.purchasesReportDateFrom?.value || elements.purchasesReportDateTo?.value ? "-periodo" : "";
        await downloadAuthenticatedFile(`/compras/relatorios/exportar${purchaseReportQuery(format)}`, `relatorio-compras${period}.${extension}`);
        showToast(`RELATÓRIO DE COMPRAS EXPORTADO EM ${format}.`);
    } catch (error) {
        showToast(error.message || "FALHA AO EXPORTAR O RELATÓRIO.", true);
    }
}

function renderPurchaseReportSchedules() {
    const panel = elements.purchasesReportSchedulesPanel;
    if (!panel) return;
    const visible = hasAdminAccess();
    panel.classList.toggle("hidden", !visible);
    if (!visible || !elements.purchasesReportSchedulesList) return;
    const schedules = state.purchases.reportSchedules || [];
    elements.purchasesReportSchedulesList.innerHTML = schedules.length ? schedules.map((schedule) => {
        const active = Boolean(schedule.active);
        const nextRun = schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString("pt-BR") : "não definido";
        const format = String(schedule.export_format || "XLSX").toUpperCase();
        const frequency = String(schedule.frequency || "WEEKLY").toUpperCase() === "MONTHLY" ? "MENSAL" : "SEMANAL";
        return `<article class="purchases-report-schedule-card ${active ? "" : "is-inactive"}">
            <div><strong>${escapeHtml(schedule.name || "Relatório automático")}</strong><span>${frequency} · ${format} · ${schedule.period_days || 7} dias</span><small>Próxima execução: ${escapeHtml(nextRun)}</small></div>
            <div class="purchases-report-schedule-actions"><button class="secondary-button" type="button" data-purchase-report-run="${schedule.id}">EXECUTAR AGORA</button><button class="secondary-button" type="button" data-purchase-report-toggle="${schedule.id}" data-active="${active ? "false" : "true"}">${active ? "PAUSAR" : "ATIVAR"}</button></div>
        </article>`;
    }).join("") : `<span class="purchases-report-empty">Nenhum agendamento criado.</span>`;
}

async function loadPurchaseReportSchedules() {
    if (!hasAdminAccess()) {
        renderPurchaseReportSchedules();
        return;
    }
    try {
        state.purchases.reportSchedules = await apiFetch("/compras/relatorios/automaticos") || [];
    } catch (error) {
        state.purchases.reportSchedules = [];
        showToast(error.message || "FALHA AO CARREGAR AGENDAMENTOS.", true);
    }
    renderPurchaseReportSchedules();
}

async function submitPurchaseReportSchedule(event) {
    event.preventDefault();
    if (!hasAdminAccess()) return;
    const payload = {
        name: elements.purchasesReportScheduleName?.value?.trim(),
        frequency: elements.purchasesReportScheduleFrequency?.value,
        period_days: Number(elements.purchasesReportSchedulePeriodDays?.value || 7),
        export_format: elements.purchasesReportScheduleFormat?.value,
        next_run_at: elements.purchasesReportScheduleNextRun?.value || undefined,
    };
    try {
        await apiFetch("/compras/relatorios/automaticos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        elements.purchasesReportScheduleForm?.reset();
        if (elements.purchasesReportSchedulePeriodDays) elements.purchasesReportSchedulePeriodDays.value = "7";
        showToast("AGENDAMENTO CRIADO.");
        await loadPurchaseReportSchedules();
    } catch (error) {
        showToast(error.message || "FALHA AO CRIAR AGENDAMENTO.", true);
    }
}

async function executePurchaseReportSchedule(scheduleId) {
    try {
        const result = await apiFetch(`/compras/relatorios/automaticos/executar?schedule_id=${scheduleId}`, { method: "POST" });
        const run = result?.runs?.[0];
        showToast(run?.status === "CONCLUIDO" ? "RELATÓRIO AUTOMÁTICO GERADO." : "AGENDAMENTO PROCESSADO.");
        await loadPurchaseReportSchedules();
        if (run?.id) await downloadAuthenticatedFile(`/compras/relatorios/automaticos/runs/${run.id}/download`, run.filename || "relatorio-compras.xlsx");
    } catch (error) {
        showToast(error.message || "FALHA AO EXECUTAR AGENDAMENTO.", true);
    }
}

async function togglePurchaseReportSchedule(scheduleId, active) {
    try {
        await apiFetch(`/compras/relatorios/automaticos/${scheduleId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active }) });
        showToast(active ? "AGENDAMENTO ATIVADO." : "AGENDAMENTO PAUSADO.");
        await loadPurchaseReportSchedules();
    } catch (error) {
        showToast(error.message || "FALHA AO ATUALIZAR AGENDAMENTO.", true);
    }
}

function renderPurchaseOverview() {
    const rows = state.purchases.requests || [];
    const open = rows.filter((row) => !["RECEBIDA", "CANCELADA"].includes(String(row.status || "").toUpperCase()));
    const pendingPcCount = purchaseOrderPendingRows().length;
    const awaitingPc = pendingPcCount || rows.filter((row) => ["SOLICITADA", "AGUARDANDO_PC"].includes(String(row.status || "").toUpperCase())).length;
    const pendingInvoiceGroups = state.purchases.pendingInvoices?.pending_nf;
    const awaitingNf = Array.isArray(pendingInvoiceGroups)
        ? pendingInvoiceGroups
        : rows.filter((row) => ["EM_TRANSITO", "AGUARDANDO_NF"].includes(String(row.status || "").toUpperCase()));
    if (elements.purchasesOpenCount) elements.purchasesOpenCount.textContent = String(open.length);
    if (elements.purchasesAwaitingPcCount) elements.purchasesAwaitingPcCount.textContent = String(awaitingPc);
    if (elements.purchasesAwaitingNfCount) elements.purchasesAwaitingNfCount.textContent = String(awaitingNf.length);
    renderPurchaseRequests();
}

async function loadPurchasesData() {
    try {
        const requests = await apiFetch("/compras/solicitacoes");
        state.purchases.requests = requests || [];
        renderPurchaseOverview();
        await loadPurchaseOrdersData();
        await loadPurchaseInvoiceData();
        await loadPurchaseProcessCenter();
        await loadPurchaseReportSummary();
        await loadPurchaseReportSchedules();
    } catch (error) {
        showToast(error.message || "FALHA AO CARREGAR COMPRAS.", true);
    }
}

function resetPurchaseProviderForm() {
    state.purchases.editingProviderId = null;
    elements.purchasesProviderForm?.reset();
    if (elements.purchasesProviderActive) elements.purchasesProviderActive.checked = true;
    if (elements.purchasesProviderSubmit) elements.purchasesProviderSubmit.textContent = "CADASTRAR PROVEDOR";
    if (elements.purchasesProviderEditorTitle) elements.purchasesProviderEditorTitle.textContent = "NOVO PROVEDOR";
    elements.purchasesProviderEditor?.classList.add("hidden");
}

function openPurchaseProviderEditor(provider = null) {
    if (!hasAdminAccess()) return;
    if (provider) {
        editPurchaseProvider(provider);
        return;
    }
    resetPurchaseProviderForm();
    elements.purchasesProviderEditor?.classList.remove("hidden");
    elements.purchasesProviderEditorTitle && (elements.purchasesProviderEditorTitle.textContent = "NOVO PROVEDOR");
    elements.purchasesProviderCode?.focus({ preventScroll: true });
}

function renderPurchaseProviders() {
    if (!elements.purchasesProviderList || !hasAdminAccess()) return;
    const providers = state.purchases.providers || [];
    if (elements.purchasesProviderCount) elements.purchasesProviderCount.textContent = `${providers.length} ${providers.length === 1 ? "cadastrado" : "cadastrados"}`;
    if (!providers.length) {
        elements.purchasesProviderList.innerHTML = `<article class="purchases-provider-empty"><strong>NENHUM PROVEDOR CADASTRADO</strong><span>Comece pelo botão “+ NOVO PROVEDOR”.</span></article>`;
        return;
    }
    elements.purchasesProviderList.innerHTML = providers.map((provider) => {
        const contact = [provider.contact_name, provider.phone, provider.email].filter(Boolean).join(" | ") || "Contato não informado";
        return `<article class="purchases-provider-card ${provider.active === false ? "is-inactive" : ""}">
            <header><div><span>${escapeHtml(provider.code || "SEM CÓDIGO")}</span><strong>${escapeHtml(provider.name || "PROVEDOR")}</strong><em>${escapeHtml(provider.trade_name || provider.legal_name || "Nome comercial não informado")}</em></div><button class="secondary-button" type="button" data-purchase-provider-edit="${provider.id}">EDITAR</button></header>
            <p>${escapeHtml(contact)}</p>
            <div class="purchases-provider-badges"><b class="${provider.active === false ? "is-off" : "is-on"}">${provider.active === false ? "INATIVO" : "ATIVO"}</b><b class="${provider.homologated ? "is-approved" : "is-pending"}">${provider.homologated ? "HOMOLOGADO" : "PENDENTE"}</b>${provider.preferred ? '<b class="is-preferred">PREFERENCIAL</b>' : ""}</div>
        </article>`;
    }).join("");
}

async function loadPurchaseProviders() {
    if (!hasAdminAccess()) return;
    try {
        const providers = await apiFetch("/compras/provedores");
        state.purchases.providers = Array.isArray(providers) ? providers : [];
        renderPurchaseProviders();
    } catch (error) {
        renderStateCard(elements.purchasesProviderList, {
            title: "NÃO FOI POSSÍVEL CARREGAR OS PROVEDORES",
            message: error.message || "Tente novamente.",
            tone: "error",
        });
    }
}

function editPurchaseProvider(provider) {
    if (!hasAdminAccess() || !provider) return;
    state.purchases.editingProviderId = Number(provider.id);
    elements.purchasesProviderCode.value = provider.code || "";
    elements.purchasesProviderName.value = provider.name || "";
    elements.purchasesProviderLegalName.value = provider.legal_name || "";
    elements.purchasesProviderTradeName.value = provider.trade_name || "";
    elements.purchasesProviderTaxId.value = provider.tax_id || "";
    elements.purchasesProviderContact.value = provider.contact_name || "";
    elements.purchasesProviderEmail.value = provider.email || "";
    elements.purchasesProviderPhone.value = provider.phone || "";
    elements.purchasesProviderNotes.value = provider.notes || "";
    elements.purchasesProviderActive.checked = provider.active !== false;
    elements.purchasesProviderHomologated.checked = Boolean(provider.homologated);
    elements.purchasesProviderPreferred.checked = Boolean(provider.preferred);
    elements.purchasesProviderSubmit.textContent = "SALVAR PROVEDOR";
    elements.purchasesProviderEditorTitle && (elements.purchasesProviderEditorTitle.textContent = "EDITAR PROVEDOR");
    elements.purchasesProviderEditor?.classList.remove("hidden");
    elements.purchasesProviderPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitPurchaseProvider(event) {
    event.preventDefault();
    if (!hasAdminAccess()) {
        showToast("SOMENTE ADMIN PODE CADASTRAR PROVEDORES.", true);
        return;
    }
    const providerId = state.purchases.editingProviderId;
    const payload = {
        code: elements.purchasesProviderCode.value.trim(),
        name: elements.purchasesProviderName.value.trim(),
        legal_name: elements.purchasesProviderLegalName.value.trim(),
        trade_name: elements.purchasesProviderTradeName.value.trim(),
        tax_id: elements.purchasesProviderTaxId.value.trim(),
        contact_name: elements.purchasesProviderContact.value.trim(),
        email: elements.purchasesProviderEmail.value.trim(),
        phone: elements.purchasesProviderPhone.value.trim(),
        notes: elements.purchasesProviderNotes.value.trim(),
        active: elements.purchasesProviderActive.checked,
        homologated: elements.purchasesProviderHomologated.checked,
        preferred: elements.purchasesProviderPreferred.checked,
    };
    elements.purchasesProviderSubmit.disabled = true;
    try {
        await apiFetch(providerId ? `/compras/provedores/${providerId}` : "/compras/provedores", {
            method: providerId ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        resetPurchaseProviderForm();
        await loadPurchaseProviders();
        showToast(providerId ? "PROVEDOR ATUALIZADO." : "PROVEDOR CADASTRADO.");
    } catch (error) {
        showToast(error.message || "FALHA AO SALVAR PROVEDOR.", true);
    } finally {
        elements.purchasesProviderSubmit.disabled = false;
    }
}

async function submitPurchaseImport() {
    if (!hasAdminAccess()) { showToast("SOMENTE ADMIN PODE IMPORTAR A BASE HISTÓRICA.", true); return; }
    const fileInput = document.getElementById("admin-purchases-import-file");
    const importButton = document.getElementById("admin-purchases-import-button");
    const feedback = document.getElementById("admin-purchases-import-feedback");
    const file = fileInput?.files?.[0];
    if (!file) { showToast("SELECIONE A PLANILHA XLSX DE COMPRAS.", true); return; }
    const body = new FormData(); body.append("file", file);
    if (importButton) importButton.disabled = true;
    try {
        const result = await apiFetch("/compras/importacoes", { method: "POST", body });
        const reconciliation = result.reconciliation || {};
        if (feedback) feedback.innerHTML = `<strong>IMPORTAÇÃO ${escapeHtml(result.status || "CONCLUÍDA")}.</strong><span>${reconciliation.source_rows || 0} linhas | ${reconciliation.purchase_requests || 0} SCs | ${reconciliation.materials || 0} materiais | ${reconciliation.purchase_orders || 0} PCs.</span>`;
        showToast("HISTÓRICO DE COMPRAS IMPORTADO.");
    } catch (error) { showToast(error.message || "FALHA NA IMPORTAÇÃO.", true); }
    finally { if (importButton) importButton.disabled = false; }
}

async function loadMaterialPurchaseHistory() {
    const materialId = Number(elements.purchasesMaterialId?.value || 0);
    if (!materialId) { showToast("INFORME O ID DO MATERIAL.", true); return; }
    try {
        const result = await apiFetch(`/compras/materiais/${materialId}/historico`);
        state.purchases.materialHistory = result;
        const summary = result.summary || {};
        if (elements.purchasesMaterialHistory) {
            elements.purchasesMaterialHistory.innerHTML = `<strong>${escapeHtml(result.material?.referencia || "MATERIAL")} — ${escapeHtml(result.material?.descricao || "")}</strong><span>SCs: ${summary.purchase_requests || 0} | Solicitado: ${summary.requested_quantity || 0} | Recebido: ${summary.received_quantity || 0} | Em aberto: ${summary.open_quantity || 0}</span><div class="purchases-history-list">${(result.items || []).slice(0, 20).map((item) => `<article><b>${escapeHtml(item.purchase_request?.sc_number || "SC")}</b><span>${escapeHtml(item.purchase_request?.status || "-")} | ${item.quantity_requested || 0} un.</span><em>${escapeHtml(item.purchase_request?.module || "OUTROS")}</em></article>`).join("") || "Nenhuma solicitação encontrada."}</div>`;
        }
    } catch (error) { showToast(error.message || "MATERIAL SEM HISTÓRICO DE COMPRAS.", true); }
}

const PURCHASES_AREAS = new Set(["process", "requests", "orders", "invoices", "materials", "reports"]);
const PURCHASES_VIEWS = new Set(["QUADRO", "LISTA", "CARTOES"]);

function setPurchasesArea(area = "process") {
    const nextArea = PURCHASES_AREAS.has(area) ? area : "process";
    state.purchases.activeArea = nextArea;
    document.querySelectorAll("[data-purchases-area-section]").forEach((section) => {
        section.classList.toggle("purchases-area-hidden", section.dataset.purchasesAreaSection !== nextArea);
    });
    elements.purchasesWorkflowNav?.querySelectorAll("[data-purchases-area]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.purchasesArea === nextArea);
    });
}

function setPurchasesView(target, view) {
    if (!state.purchases.views || !Object.prototype.hasOwnProperty.call(state.purchases.views, target)) return;
    const nextView = PURCHASES_VIEWS.has(view) ? view : "CARTOES";
    state.purchases.views[target] = nextView;
    const listMap = {
        process: elements.purchasesProcessList,
        requests: elements.purchasesRequestList,
        orders: elements.purchaseOrderPendingList,
        invoices: document.querySelector(".purchases-invoice-columns"),
    };
    const boardMap = {
        process: elements.purchasesProcessBoard,
        requests: elements.purchasesRequestBoard,
        orders: elements.purchasesOrderBoard,
        invoices: elements.purchasesInvoiceBoard,
    };
    const list = listMap[target];
    const board = boardMap[target];
    board?.classList.toggle("hidden", nextView !== "QUADRO");
    list?.classList.toggle("hidden", nextView === "QUADRO");
    list?.classList.toggle("purchases-view-list", nextView === "LISTA");
    list?.classList.toggle("purchases-view-cards", nextView === "CARTOES");
    document.querySelector(`[data-purchases-view-target="${target}"]`)?.querySelectorAll("[data-purchases-view-option]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.purchasesViewOption === nextView);
    });
}

function applyPurchasesViews() {
    Object.entries(state.purchases.views || {}).forEach(([target, view]) => setPurchasesView(target, view));
}

async function openPurchasesMenu({ focusProviders = false, focusReports = false } = {}) {
    if (!hasWashReportAccess()) return;
    if (elements.purchasesRoleBadge) elements.purchasesRoleBadge.textContent = hasAdminAccess() ? "ADMINISTRAÇÃO" : "GESTÃO";
    if (elements.purchaseOrderDate && !elements.purchaseOrderDate.value) elements.purchaseOrderDate.value = formatDateInputValue(new Date());
    elements.purchasesProviderPanel?.classList.toggle("hidden", !hasAdminAccess());
    setActiveScreen("purchases");
    setPurchasesArea(focusReports ? "reports" : focusProviders ? "materials" : state.purchases.activeArea || "process");
    applyPurchasesViews();
    const loaders = [loadPurchasesData()];
    if (hasAdminAccess()) loaders.push(loadPurchaseProviders());
    await Promise.all(loaders);
    if (focusProviders && hasAdminAccess()) {
        elements.purchasesProviderPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
        openPurchaseProviderEditor();
    }
    if (focusReports) elements.purchasesReportsPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function mmpWarehouseByType(type) {
    return state.mmpStock.warehouses.find((warehouse) => String(warehouse.warehouse_type || "").toUpperCase() === type && warehouse.active !== false) || null;
}

function mmpQrImageUrl(qrCode) {
    return `https://quickchart.io/qr?size=140&text=${encodeURIComponent(qrCode)}`;
}

function renderMmpLocationOptions() {
    const locations = state.mmpStock.locations.filter((location) => location.active !== false);
    const options = locations.length ? locations.map((location) => `<option value="${location.id}">${escapeHtml(location.label)}</option>`).join("") : `<option value="">Crie uma prateleira primeiro</option>`;
    if (elements.mmpLocationWarehouse) {
        const mmp = mmpWarehouseByType("MMP");
        elements.mmpLocationWarehouse.innerHTML = mmp ? `<option value="${mmp.id}">${escapeHtml(mmp.name)}</option>` : `<option value="">Estoque MMP não configurado</option>`;
    }
    if (elements.mmpTransferLocation) elements.mmpTransferLocation.innerHTML = options;
}

function renderMmpMainStocks() {
    if (!elements.mmpMainStockList) return;
    if (!state.mmpStock.mainStocks.length) {
        elements.mmpMainStockList.innerHTML = `<article class="empty-state"><strong>SEM SALDO NO ARMAZÉM PRINCIPAL.</strong><span>Cadastre o armazém e distribua os materiais antes de transferir.</span></article>`;
        return;
    }
    elements.mmpMainStockList.innerHTML = state.mmpStock.mainStocks.map((stock) => {
        const material = stock.material || {};
        const available = Math.max(Number(stock.available_quantity || stock.quantity || 0), 0);
        return `<label class="mmp-main-stock-row"><input type="checkbox" data-mmp-transfer-material="${stock.material_id}" ${available ? "" : "disabled"}><span><strong>${escapeHtml(String(material.referencia || "-").toUpperCase())}</strong><em>${escapeHtml(String(material.descricao || "-"))}</em></span><b>${available} DISP.</b><input class="mmp-transfer-quantity" data-mmp-transfer-quantity="${stock.material_id}" type="number" min="1" max="${available}" value="1" disabled></label>`;
    }).join("");
    elements.mmpMainStockList.querySelectorAll("[data-mmp-transfer-material]").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            const materialId = checkbox.dataset.mmpTransferMaterial;
            const quantity = elements.mmpMainStockList.querySelector(`[data-mmp-transfer-quantity="${materialId}"]`);
            if (quantity) quantity.disabled = !checkbox.checked;
        });
    });
}

function renderMmpStockList() {
    const rows = state.mmpStock.mmpStocks || [];
    const total = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0);
    const low = rows.filter((row) => Number(row.quantity || 0) <= Number(row.material?.estoque_minimo || 0)).length;
    if (elements.mmpStockSummary) elements.mmpStockSummary.innerHTML = `<div><span>MATERIAIS</span><strong>${rows.length}</strong></div><div><span>UNIDADES</span><strong>${total}</strong></div><div><span>BAIXO ESTOQUE</span><strong>${low}</strong></div>`;
    if (!elements.mmpStockList) return;
    elements.mmpStockList.innerHTML = rows.length ? rows.map((stock) => {
        const material = stock.material || {};
        return `<article class="mmp-stock-card"><header><div><span>${escapeHtml(String(material.referencia || "MATERIAL").toUpperCase())}</span><strong>${escapeHtml(String(material.descricao || "-").toUpperCase())}</strong></div><b>${Number(stock.quantity || 0)} UN.</b></header><p>${escapeHtml(stock.location?.label || "SEM LOCAL")}</p><div class="mmp-stock-card-foot"><span>${escapeHtml(stock.qr_code || "SEM QR")}</span><button type="button" class="secondary-button" data-mmp-stock-lookup="${escapeHtml(stock.qr_code || "")}">ABRIR MATERIAL</button></div></article>`;
    }).join("") : `<article class="empty-state"><strong>ESTOQUE MMP VAZIO.</strong><span>O saldo transferido do Armazém Principal aparecerá aqui.</span></article>`;
    elements.mmpStockList.querySelectorAll("[data-mmp-stock-lookup]").forEach((button) => button.addEventListener("click", () => {
        if (elements.mmpQrCode) elements.mmpQrCode.value = button.dataset.mmpStockLookup || "";
        lookupMmpStock();
    }));
}

function renderMmpVehicles() {
    if (!elements.mmpIssueVehicle) return;
    const vehicles = (state.vehicles || []).filter((vehicle) => vehicle.ativo !== false);
    elements.mmpIssueVehicle.innerHTML = `<option value="">Selecione o equipamento</option>${vehicles.map((vehicle) => `<option value="${vehicle.id}">${escapeHtml(String(vehicle.frota || vehicle.placa || "EQUIPAMENTO"))} | ${escapeHtml(String(vehicle.modelo || "-"))}</option>`).join("")}`;
}

function renderMmpTransfers() {
    const rows = state.mmpStock.transfers || [];
    if (!elements.mmpTransferHistory) return;
    elements.mmpTransferHistory.innerHTML = rows.length ? rows.map((transfer) => `<article class="mmp-transfer-row"><strong>${escapeHtml(transfer.code || "TRANSFERÊNCIA")}</strong><span>${escapeHtml(transfer.source_warehouse?.name || "ARMAZÉM PRINCIPAL")} → ${escapeHtml(transfer.destination_warehouse?.name || "ESTOQUE MMP")}</span><em>${(transfer.items || []).length} material(is) | ${formatDateTime(transfer.created_at)}</em></article>`).join("") : "Nenhuma transferência registrada.";
}

async function loadMmpStockData() {
    try {
        state.mmpStock.warehouses = await apiFetch("/suprimentos/depositos");
        const principal = mmpWarehouseByType("PRINCIPAL");
        const mmp = mmpWarehouseByType("MMP");
        const [mainStocks, mmpStocks, locations, transfers] = await Promise.all([
            principal ? apiFetch(`/suprimentos/estoques?warehouse_id=${principal.id}`) : Promise.resolve([]),
            apiFetch("/suprimentos/mmp/saldos"),
            mmp ? apiFetch(`/suprimentos/locais?warehouse_id=${mmp.id}`) : Promise.resolve([]),
            apiFetch("/suprimentos/transferencias?limite=25"),
        ]);
        state.mmpStock.mainStocks = mainStocks || [];
        state.mmpStock.mmpStocks = mmpStocks || [];
        state.mmpStock.locations = locations || [];
        state.mmpStock.transfers = transfers || [];
        renderMmpLocationOptions();
        renderMmpMainStocks();
        renderMmpStockList();
        renderMmpTransfers();
        if (elements.mmpAdminFeedback) elements.mmpAdminFeedback.textContent = principal && mmp ? `${principal.name} e ${mmp.name} carregados.` : "Cadastre o Armazém Principal e o Estoque MMP para começar.";
    } catch (error) {
        if (elements.mmpAdminFeedback) elements.mmpAdminFeedback.textContent = error.message || "Não foi possível carregar os estoques.";
        showToast(error.message || "FALHA AO CARREGAR ESTOQUE MMP.", true);
    }
}

async function createMmpWarehouse(type) {
    const exists = mmpWarehouseByType(type);
    if (exists) {
        showToast(`${exists.name.toUpperCase()} JÁ ESTÁ CONFIGURADO.`);
        return;
    }
    const payload = type === "MMP" ? { code: "EST-MMP", name: "Estoque MMP", warehouse_type: "MMP" } : { code: "ARM-PRINCIPAL", name: "Armazém Principal", warehouse_type: "PRINCIPAL" };
    try {
        await apiFetch("/suprimentos/depositos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        showToast(`${payload.name.toUpperCase()} CRIADO.`);
        await loadMmpStockData();
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL CRIAR O ESTOQUE.", true); }
}

async function submitMmpLocation(event) {
    event.preventDefault();
    const warehouse = mmpWarehouseByType("MMP");
    if (!warehouse) { showToast("CRIE O ESTOQUE MMP PRIMEIRO.", true); return; }
    try {
        await apiFetch("/suprimentos/locais", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ warehouse_id: warehouse.id, shelf_code: elements.mmpLocationShelf.value.trim(), location_code: elements.mmpLocationCode.value.trim(), position_code: elements.mmpLocationPosition.value.trim() }) });
        elements.mmpLocationForm.reset(); showToast("LOCAL CRIADO."); await loadMmpStockData();
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL CRIAR O LOCAL.", true); }
}

async function submitMmpTransfer(event) {
    event.preventDefault();
    const locationId = Number(elements.mmpTransferLocation.value || 0);
    const items = Array.from(elements.mmpMainStockList.querySelectorAll("[data-mmp-transfer-material]:checked")).map((checkbox) => ({ material_id: Number(checkbox.dataset.mmpTransferMaterial), quantity: Number(elements.mmpMainStockList.querySelector(`[data-mmp-transfer-quantity="${checkbox.dataset.mmpTransferMaterial}"]`)?.value || 0), location_id: locationId })).filter((item) => item.quantity > 0);
    if (!locationId || !items.length) { showToast("SELECIONE OS MATERIAIS, AS QUANTIDADES E O LOCAL.", true); return; }
    try {
        const transfer = await apiFetch("/suprimentos/transferencias", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }) });
        const labels = (transfer.items || []).map((item) => `<div class="mmp-label-preview"><strong>${escapeHtml(String(item.material?.referencia || "MATERIAL"))} | ${escapeHtml(String(item.material?.descricao || ""))}</strong><img src="${mmpQrImageUrl(item.qr_code)}" alt="QR Code ${escapeHtml(item.qr_code)}"><span>${escapeHtml(item.qr_code)} | ${escapeHtml(item.location?.label || "")}</span></div>`).join("");
        if (elements.mmpAdminFeedback) elements.mmpAdminFeedback.innerHTML = `<strong>TRANSFERÊNCIA ${escapeHtml(transfer.code)} CONCLUÍDA.</strong><div class="mmp-label-list">${labels}</div>`;
        showToast("TRANSFERÊNCIA PARA O ESTOQUE MMP CONCLUÍDA."); await loadMmpStockData();
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL TRANSFERIR OS MATERIAIS.", true); }
}

async function lookupMmpStock() {
    const code = elements.mmpQrCode?.value?.trim() || "";
    if (!code) { showToast("INFORME OU BIPE O QR CODE DO MATERIAL.", true); return; }
    try {
        const stock = await apiFetch(`/suprimentos/mmp/qr/${encodeURIComponent(code)}`);
        state.mmpStock.selectedStock = stock;
        elements.mmpSelectedStock.innerHTML = `<strong>${escapeHtml(String(stock.material?.referencia || "MATERIAL"))} | ${escapeHtml(String(stock.material?.descricao || "").toUpperCase())}</strong><span>SALDO: ${Number(stock.quantity || 0)} | LOCAL: ${escapeHtml(stock.location?.label || "SEM LOCAL")}</span><em>${escapeHtml(stock.qr_code || code)}</em>`;
        elements.mmpIssueForm.classList.remove("hidden");
    } catch (error) { state.mmpStock.selectedStock = null; elements.mmpIssueForm.classList.add("hidden"); showToast(error.message || "MATERIAL MMP NÃO ENCONTRADO.", true); }
}

async function scanMmpQr() {
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices?.getUserMedia) { showToast("LEITURA POR CÂMERA INDISPONÍVEL. DIGITE O CÓDIGO DO QR.", true); return; }
    let stream;
    try {
        const detector = new BarcodeDetector({ formats: ["qr_code"] });
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        elements.mmpQrPreview.srcObject = stream; elements.mmpQrPreview.classList.remove("hidden"); await elements.mmpQrPreview.play();
        const deadline = Date.now() + 25000;
        while (Date.now() < deadline) {
            const codes = await detector.detect(elements.mmpQrPreview);
            if (codes.length) { elements.mmpQrCode.value = String(codes[0].rawValue || "").trim(); await lookupMmpStock(); return; }
            await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
        showToast("NENHUM QR DE MATERIAL IDENTIFICADO.", true);
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL ACESSAR A CÂMERA.", true); }
    finally { stream?.getTracks().forEach((track) => track.stop()); elements.mmpQrPreview.pause(); elements.mmpQrPreview.srcObject = null; elements.mmpQrPreview.classList.add("hidden"); }
}

async function submitMmpIssue(event) {
    event.preventDefault();
    if (!state.mmpStock.selectedStock) { showToast("CONSULTE O MATERIAL PELO QR CODE PRIMEIRO.", true); return; }
    try {
        await apiFetch("/suprimentos/mmp/saidas", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ qr_code: state.mmpStock.selectedStock.qr_code, quantity: Number(elements.mmpIssueQuantity.value || 0), vehicle_id: Number(elements.mmpIssueVehicle.value || 0), application: elements.mmpIssueApplication.value.trim() }) });
        showToast("SAÍDA DO ESTOQUE MMP REGISTRADA."); elements.mmpIssueForm.reset(); elements.mmpIssueForm.classList.add("hidden"); elements.mmpSelectedStock.textContent = "Saída registrada. Bipe o próximo material."; state.mmpStock.selectedStock = null; await loadMmpStockData();
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL REGISTRAR A SAÍDA.", true); }
}

async function openMmpStockMenu() {
    if (!hasMmpAccess()) { showToast("SEU PERFIL NÃO POSSUI ACESSO AO ESTOQUE MMP.", true); return; }
    const management = hasWashReportAccess();
    elements.mmpStockRoleBadge.textContent = management ? "ADMINISTRAÇÃO" : "OPERAÇÃO";
    elements.mmpAdminPanel.classList.toggle("hidden", !management);
    elements.mmpOperationPanel.classList.remove("hidden");
    renderMmpVehicles();
    setActiveScreen("mmpStock");
    await loadMmpStockData();
}

function rhAdminStatusLabel(status) {
    return String(status || "PRE_CADASTRO").replaceAll("_", " ");
}

function setRhAdminTab(tab) {
    const selected = ["overview", "employees", "operations", "reports"].includes(tab) ? tab : "overview";
    state.rhAdmin.tab = selected;
    elements.rhAdminTabs.forEach((button) => button.classList.toggle("is-active", button.dataset.rhAdminTab === selected));
    elements.rhAdminOverviewPanel.classList.toggle("hidden", selected !== "overview");
    elements.rhAdminEmployeesPanel.classList.toggle("hidden", selected !== "employees");
    elements.rhAdminOperationsPanel.classList.toggle("hidden", selected !== "operations");
    elements.rhAdminReportsPanel.classList.toggle("hidden", selected !== "reports");
}

function renderRhAdminOverview() {
    const overview = state.rhAdmin.overview || {};
    const employees = overview.employees || {};
    const attendance = overview.attendance || {};
    const alerts = Array.isArray(overview.alerts) ? overview.alerts : [];
    const alertSummary = overview.alert_summary || {};
    const cards = [
        ["COLABORADORES ATIVOS", employees.active || 0, "TOTAL EM ATIVIDADE"],
        ["ABSENTEÍSMO", `${Number(attendance.absenteeism_percent || 0).toFixed(2)}%`, "NO PERÍODO"],
        ["ALERTAS VENCIDOS", alertSummary.expired || 0, "DOCUMENTOS E TREINAMENTOS"],
        ["VENCENDO EM BREVE", alertSummary.expiring || 0, "ACOMPANHAR PRAZOS"],
    ];
    elements.rhAdminOverviewCards.innerHTML = cards.map(([label, value, hint]) => `
        <article class="rh-admin-summary-card"><span>${label}</span><strong>${escapeHtml(String(value))}</strong><em>${hint}</em></article>
    `).join("");
    elements.rhAdminAlertCount.textContent = `${alerts.length} alerta${alerts.length === 1 ? "" : "s"}`;
    elements.rhAdminAlertList.innerHTML = alerts.length
        ? alerts.slice(0, 8).map((alert) => `<div class="rh-admin-list-row"><strong>${escapeHtml(alert.kind || "ALERTA")}</strong><span>${escapeHtml((alert.employee || {}).full_name || "Colaborador não identificado")}</span><em>${escapeHtml(alert.status || "-")}</em></div>`).join("")
        : `<div class="rh-admin-empty">Nenhum alerta de vencimento no período.</div>`;
    const teams = Array.isArray(employees.by_team) ? employees.by_team : [];
    elements.rhAdminTeamList.innerHTML = teams.length
        ? teams.map((team) => `<div class="rh-admin-list-row"><strong>${escapeHtml(team.team_name || "Sem atividade")}</strong><span>${Number(team.total || 0)} colaborador(es)</span></div>`).join("")
        : `<div class="rh-admin-empty">Nenhum agrupamento disponível.</div>`;
}

async function loadRhAdminOverview() {
    elements.rhAdminOverviewCards.innerHTML = `<div class="rh-admin-loading">CARREGANDO INDICADORES...</div>`;
    try {
        state.rhAdmin.overview = await apiFetch("/rh/gestao");
        renderRhAdminOverview();
    } catch (error) {
        renderStateCard(elements.rhAdminOverviewCards, { title: "PAINEL INDISPONÍVEL", message: error.message || "Tente novamente.", tone: "error" });
        showToast(error.message || "FALHA AO CARREGAR PAINEL DE RH.", true);
    }
}

function filteredRhAdminEmployees() {
    const query = elements.rhAdminEmployeeSearch.value.trim().toLocaleLowerCase("pt-BR");
    const status = elements.rhAdminEmployeeStatus.value;
    return state.rhAdmin.employees.filter((employee) => {
        const searchable = `${employee.full_name || ""} ${employee.registration || ""} ${employee.team_name || ""}`.toLocaleLowerCase("pt-BR");
        return (!query || searchable.includes(query)) && (!status || employee.status === status);
    });
}

function renderRhAdminEmployees() {
    const employees = filteredRhAdminEmployees();
    elements.rhAdminEmployeesCounter.textContent = `${employees.length} de ${state.rhAdmin.employees.length} colaborador(es)`;
    if (!employees.length) {
        renderStateCard(elements.rhAdminEmployeesList, { title: "NENHUM COLABORADOR ENCONTRADO", message: "Ajuste os filtros ou cadastre um novo colaborador." });
        return;
    }
    elements.rhAdminEmployeesList.innerHTML = employees.map((employee) => `
        <article class="rh-admin-employee-row">
            <div class="rh-admin-employee-avatar">${escapeHtml((employee.full_name || "?").trim().slice(0, 1).toUpperCase())}</div>
            <div class="rh-admin-employee-main"><strong>${escapeHtml(employee.full_name || "Sem nome")}</strong><span>${escapeHtml(employee.registration || "Sem matrícula")} · ${escapeHtml(employee.function_name || "Sem função")}</span><small>${escapeHtml(employee.team_name || "Sem atividade")} · ${escapeHtml(employee.shift_name || "Sem turno")}</small></div>
            <em class="rh-admin-employee-status status-${String(employee.status || "").toLowerCase()}">${escapeHtml(rhAdminStatusLabel(employee.status))}</em>
            <button class="icon-button" type="button" data-rh-admin-edit-employee="${Number(employee.id)}">EDITAR</button>
        </article>
    `).join("");
}

async function loadRhAdminEmployees() {
    renderStateCard(elements.rhAdminEmployeesList, { title: "CARREGANDO COLABORADORES", message: "Consultando o cadastro funcional.", tone: "loading" });
    try {
        const rows = await apiFetch("/rh/colaboradores");
        state.rhAdmin.employees = Array.isArray(rows) ? rows : [];
        renderRhAdminEmployees();
    } catch (error) {
        renderStateCard(elements.rhAdminEmployeesList, { title: "CADASTRO INDISPONÍVEL", message: error.message || "Tente novamente.", tone: "error" });
        showToast(error.message || "FALHA AO CARREGAR COLABORADORES.", true);
    }
}

async function loadRhAdminLinkableUsers(selectedId = null) {
    const users = await apiFetch("/rh/colaboradores/usuarios-disponiveis");
    elements.rhAdminEmployeeUser.innerHTML = `<option value="">SEM LOGIN VINCULADO</option>${(Array.isArray(users) ? users : []).map((user) => `<option value="${Number(user.id)}">${escapeHtml(user.nome || user.login || "Usuário")} (${escapeHtml(user.login || "")})</option>`).join("")}`;
    elements.rhAdminEmployeeUser.value = selectedId ? String(selectedId) : "";
}

async function openRhAdminEmployeeModal(employee = null) {
    state.rhAdmin.editingEmployeeId = employee ? Number(employee.id) : null;
    state.rhAdmin.existingEmployeePhoto = employee?.photo_path || "";
    elements.rhAdminEmployeeModalTitle.textContent = employee ? "Editar colaborador" : "Novo colaborador";
    elements.rhAdminEmployeeRegistration.value = employee?.registration || "";
    elements.rhAdminEmployeeName.value = employee?.full_name || "";
    elements.rhAdminEmployeeFunction.value = employee?.function_name || "";
    elements.rhAdminEmployeeTeam.value = employee?.team_name || "";
    elements.rhAdminEmployeeShift.value = employee?.shift_name || "";
    elements.rhAdminEmployeeStatusField.value = employee?.status || "PRE_CADASTRO";
    elements.rhAdminEmployeeHiredOn.value = employee?.hired_on || "";
    elements.rhAdminEmployeeNotes.value = employee?.notes || "";
    elements.rhAdminEmployeePhoto.value = "";
    elements.rhAdminEmployeePhotoStatus.textContent = employee?.photo_path ? "Foto atual mantida se nenhuma nova for escolhida." : "Nenhuma foto nova selecionada.";
    elements.rhAdminEmployeeModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    try {
        await loadRhAdminLinkableUsers(employee?.user_id || null);
    } catch (error) {
        elements.rhAdminEmployeeUser.innerHTML = `<option value="">NÃO FOI POSSÍVEL CARREGAR LOGINS</option>`;
        showToast(error.message || "FALHA AO CARREGAR LOGINS DISPONÍVEIS.", true);
    }
    elements.rhAdminEmployeeRegistration.focus();
}

function closeRhAdminEmployeeModal() {
    elements.rhAdminEmployeeModal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    elements.rhAdminEmployeeForm.reset();
    state.rhAdmin.editingEmployeeId = null;
    state.rhAdmin.existingEmployeePhoto = "";
}

async function submitRhAdminEmployee(event) {
    event.preventDefault();
    if (!hasWashReportAccess()) return;
    const payload = {
        registration: elements.rhAdminEmployeeRegistration.value.trim(),
        full_name: elements.rhAdminEmployeeName.value.trim(),
        function_name: elements.rhAdminEmployeeFunction.value.trim(),
        team_name: elements.rhAdminEmployeeTeam.value.trim(),
        shift_name: elements.rhAdminEmployeeShift.value.trim(),
        status: elements.rhAdminEmployeeStatusField.value,
        hired_on: elements.rhAdminEmployeeHiredOn.value || null,
        user_id: elements.rhAdminEmployeeUser.value ? Number(elements.rhAdminEmployeeUser.value) : null,
        notes: elements.rhAdminEmployeeNotes.value.trim() || null,
        photo_path: state.rhAdmin.existingEmployeePhoto || null,
    };
    if (!payload.registration || !payload.full_name || !payload.function_name || !payload.team_name || !payload.shift_name) {
        showToast("PREENCHA OS CAMPOS OBRIGATÓRIOS.", true);
        return;
    }
    const photo = elements.rhAdminEmployeePhoto.files?.[0];
    const editingId = state.rhAdmin.editingEmployeeId;
    elements.rhAdminEmployeeSave.disabled = true;
    elements.rhAdminEmployeeSave.textContent = "SALVANDO...";
    try {
        if (photo) payload.photo_path = await uploadEvidence(photo, "RH", payload.full_name, "perfil", "COLABORADORES");
        await apiFetch(editingId ? `/rh/colaboradores/${editingId}` : "/rh/colaboradores", {
            method: editingId ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        closeRhAdminEmployeeModal();
        await Promise.all([loadRhAdminEmployees(), loadRhAdminOverview()]);
        showToast(editingId ? "COLABORADOR ATUALIZADO." : "COLABORADOR CADASTRADO.");
    } catch (error) {
        showToast(error.message || "FALHA AO SALVAR COLABORADOR.", true);
    } finally {
        elements.rhAdminEmployeeSave.disabled = false;
        elements.rhAdminEmployeeSave.textContent = "SALVAR COLABORADOR";
    }
}

async function openRhAdminMenu() {
    if (!hasWashReportAccess()) {
        showToast("SOMENTE ADMIN OU GESTOR PODE ACESSAR A GESTÃO DE RH.", true);
        return;
    }
    setActiveScreen("rhAdmin");
    setRhAdminTab("overview");
    elements.rhAdminRoleBadge.textContent = String(state.user?.tipo || "gestor").toUpperCase();
    await Promise.all([loadRhAdminOverview(), loadRhAdminEmployees()]);
}

async function openHrJourneyMenu() {
    setActiveScreen("hrJourney");
    elements.hrJourneyCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.hrJourneyList, {
        title: "CARREGANDO MINHA JORNADA",
        message: "Buscando apenas os dados vinculados ao seu login.",
        tone: "loading",
    });
    try {
        state.hrJourney = await apiFetch("/operacao-mobile/minha-jornada");
        localStorage.setItem(OFFLINE_HR_JOURNEY_KEY, JSON.stringify(state.hrJourney));
        renderHrJourney();
    } catch (error) {
        const cachedJourney = readJsonStorage(OFFLINE_HR_JOURNEY_KEY, null);
        if (cachedJourney && isOfflineError(error)) {
            state.hrJourney = cachedJourney;
            renderHrJourney();
            showToast("MINHA JORNADA OFFLINE CARREGADA. OS DADOS SÃO A ÚLTIMA CONSULTA SALVA.");
            return;
        }
        elements.hrJourneyCounter.textContent = "INDISPONÍVEL";
        renderStateCard(elements.hrJourneyList, {
            title: "JORNADA NÃO DISPONÍVEL",
            message: error.message || "Este login precisa ser vinculado ao cadastro de colaborador.",
            tone: "error",
        });
        showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR A JORNADA.", true);
    }
}

function renderHrJourney() {
    const journey = state.hrJourney || {};
    const employee = journey.employee || {};
    const attendance = journey.attendance || [];
    const trainingAlerts = journey.training_alerts || [];
    elements.hrJourneyCounter.textContent = employee.registration ? `${employee.registration} | ${employee.status || "-"}` : "SEM VÍNCULO";
    elements.hrJourneySummary.innerHTML = `
        <div>
            <strong>${escapeHtml(String(employee.full_name || "COLABORADOR").toUpperCase())}</strong>
            <span>${escapeHtml(String(employee.function_name || "FUNÇÃO NÃO INFORMADA").toUpperCase())} | ${escapeHtml(String(employee.team_name || "EQUIPE NÃO INFORMADA").toUpperCase())}</span>
        </div>
        <div class="progress-track" aria-hidden="true"><span style="width: 100%"></span></div>
        <span>TURNO: ${escapeHtml(String(employee.shift_name || "-").toUpperCase())} | BASE: ${escapeHtml(formatDate(journey.reference_date))}</span>
    `;
    const attendanceRows = attendance.length ? attendance.map((row) => `
        <article class="checklist-card">
            <div class="item-topline"><span>FREQ.</span><h3>${escapeHtml(String(row.occurrence_type || "-").toUpperCase())}</h3></div>
            <div class="activity-meta"><strong>${escapeHtml(formatDate(row.occurrence_date))}</strong><span>${row.delay_minutes ? `${Number(row.delay_minutes)} MIN DE ATRASO` : row.is_justified ? "JUSTIFICADO" : "REGISTRADO"}</span></div>
        </article>
    `).join("") : `<article class="empty-state"><strong>SEM FREQUÊNCIA RECENTE.</strong><span>CONSULTE O RH SE VOCÊ ESPERAVA UM LANÇAMENTO.</span></article>`;
    const trainingRows = trainingAlerts.length ? trainingAlerts.map((row) => `
        <article class="checklist-card">
            <div class="item-topline"><span>CURSO</span><h3>${escapeHtml(String(row.course_name || "TREINAMENTO").toUpperCase())}</h3></div>
            <div class="activity-meta"><strong>${escapeHtml(String(row.status || "-").toUpperCase())}</strong><span>VALIDADE: ${escapeHtml(formatDate(row.expires_on))}</span></div>
        </article>
    `).join("") : "";
    elements.hrJourneyList.innerHTML = `
        <section class="module-section"><div class="module-header"><div><span>FREQUÊNCIA</span><strong>ÚLTIMOS LANÇAMENTOS</strong></div><em>${attendance.length}</em></div>${attendanceRows}</section>
        <section class="module-section"><div class="module-header"><div><span>TREINAMENTOS</span><strong>ALERTAS DE VALIDADE</strong></div><em>${trainingAlerts.length}</em></div>${trainingRows || "<article class=\"empty-state\"><strong>NENHUM ALERTA PRÓXIMO.</strong><span>NÃO HÁ TREINAMENTO VENCIDO OU VENCENDO EM 30 DIAS.</span></article>"}</section>
    `;
}

function currentIsoWeekInput() {
    const reference = new Date();
    const utc = new Date(Date.UTC(reference.getFullYear(), reference.getMonth(), reference.getDate()));
    const day = utc.getUTCDay() || 7;
    utc.setUTCDate(utc.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
    const week = Math.ceil((((utc - yearStart) / 86400000) + 1) / 7);
    return `${utc.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function isoWeekToMonday(value) {
    const match = /^(\d{4})-W(\d{2})$/.exec(String(value || ""));
    if (!match) return "";
    const year = Number(match[1]);
    const week = Number(match[2]);
    const januaryFourth = new Date(Date.UTC(year, 0, 4));
    const weekday = januaryFourth.getUTCDay() || 7;
    januaryFourth.setUTCDate(januaryFourth.getUTCDate() - weekday + 1 + ((week - 1) * 7));
    return januaryFourth.toISOString().slice(0, 10);
}

async function openWeeklyDsrMenu() {
    if (!hasWashReportAccess()) {
        showToast("APENAS ADMIN OU GESTOR PODE LANÇAR DSR.", true);
        return;
    }
    if (!elements.weeklyDsrWeek.value) {
        elements.weeklyDsrWeek.value = currentIsoWeekInput();
    }
    setActiveScreen("weeklyDsr");
    await refreshWeeklyDsr();
}

async function refreshWeeklyDsr() {
    const weekStart = isoWeekToMonday(elements.weeklyDsrWeek?.value);
    if (!weekStart) {
        showToast("SELECIONE UMA SEMANA VÁLIDA.", true);
        return;
    }
    elements.weeklyDsrCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.weeklyDsrList, {
        title: "CARREGANDO DSR",
        message: "Buscando os colaboradores ativos e os registros desta semana.",
        tone: "loading",
    });
    try {
        const [employees, overview] = await Promise.all([
            apiFetch("/rh/colaboradores?situacao=ATIVO"),
            apiFetch(`/rh/dsr-semanal?semana=${weekStart}`),
        ]);
        state.weeklyDsr = { employees: employees || [], overview: overview || null };
        renderWeeklyDsr();
    } catch (error) {
        elements.weeklyDsrCounter.textContent = "INDISPONÍVEL";
        renderStateCard(elements.weeklyDsrList, {
            title: "DSR NÃO DISPONÍVEL",
            message: error.message || "Não foi possível carregar a semana.",
            tone: "error",
        });
        showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR A DSR.", true);
    }
}

function openScheduleTab(tab) {
    if (tab === "special") {
        openSpecialScheduleMenu();
        return;
    }
    openWeeklyDsrMenu();
}

function fillScheduleFilter(element, values, label) {
    if (!element) return;
    const selected = element.value;
    const options = [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))].sort((left, right) => left.localeCompare(right, "pt-BR"));
    element.innerHTML = `<option value="">${label}</option>${options.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
    element.value = options.includes(selected) ? selected : "";
}

function prepareScheduleFilters(prefix, employees) {
    const elementsByPrefix = {
        weekly: { team: elements.weeklyDsrTeam, shift: elements.weeklyDsrShift, functionName: elements.weeklyDsrFunction },
        special: { team: elements.specialScheduleTeam, shift: elements.specialScheduleShift, functionName: elements.specialScheduleFunction },
    }[prefix];
    if (!elementsByPrefix) return;
    fillScheduleFilter(elementsByPrefix.team, employees.map((employee) => employee.team_name), "TODOS OS TIMES");
    fillScheduleFilter(elementsByPrefix.shift, employees.map((employee) => employee.shift_name), "TODOS OS TURNOS");
    fillScheduleFilter(elementsByPrefix.functionName, employees.map((employee) => employee.function_name), "TODAS AS FUNÇÕES");
}

function scheduleEmployeeMatches(employee, prefix) {
    const filters = {
        weekly: { search: elements.weeklyDsrSearch, area: elements.weeklyDsrArea, team: elements.weeklyDsrTeam, shift: elements.weeklyDsrShift, functionName: elements.weeklyDsrFunction },
        special: { search: elements.specialScheduleSearch, area: elements.specialScheduleArea, team: elements.specialScheduleTeam, shift: elements.specialScheduleShift, functionName: elements.specialScheduleFunction },
    }[prefix];
    if (!filters) return true;
    const search = normalizeText(filters.search?.value);
    const area = absenteeismCategory(employee);
    return (!search || normalizeText(`${employee.full_name || ""} ${employee.registration || ""}`).includes(search))
        && (!filters.area?.value || filters.area.value === area)
        && (!filters.team?.value || filters.team.value === String(employee.team_name || ""))
        && (!filters.shift?.value || filters.shift.value === String(employee.shift_name || ""))
        && (!filters.functionName?.value || filters.functionName.value === String(employee.function_name || ""));
}

function sortScheduleEmployees(employees) {
    const categoryOrder = { ADM: 1, RTG: 2, LBS: 3, OUTROS: 4 };
    return [...employees].sort((left, right) => (categoryOrder[absenteeismCategory(left)] || 9) - (categoryOrder[absenteeismCategory(right)] || 9)
        || String(left.full_name || "").localeCompare(String(right.full_name || ""), "pt-BR"));
}

function renderWeeklyDsr() {
    const overview = state.weeklyDsr.overview || {};
    const employees = state.weeklyDsr.employees || [];
    const registeredIds = new Set((overview.records || []).map((row) => Number(row.employee_id)));
    const vacationIds = new Set((overview.vacation_employee_ids || []).map(Number));
    prepareScheduleFilters("weekly", employees);
    const filteredEmployees = sortScheduleEmployees(employees.filter((employee) => scheduleEmployeeMatches(employee, "weekly")));
    const eligible = filteredEmployees.filter((employee) => !vacationIds.has(Number(employee.id)));
    elements.weeklyDsrCounter.textContent = `${eligible.length} ELEGÍVEIS | ${registeredIds.size} JÁ REGISTRADOS`;
    elements.weeklyDsrSummary.innerHTML = `
        <div><strong>SEMANA DE ${escapeHtml(formatDate(overview.week_start))} A ${escapeHtml(formatDate(overview.week_end))}</strong><span>DSR SERÁ REGISTRADA NO DOMINGO: ${escapeHtml(formatDate(overview.dsr_date))}</span></div>
        <div class="progress-track" aria-hidden="true"><span style="width: 100%"></span></div>
        <span>FÉRIAS NO DOMINGO: ${vacationIds.size}. Estes colaboradores ficam bloqueados nesta semana.</span>
    `;
    const rows = filteredEmployees.map((employee) => {
        const id = Number(employee.id);
        const onVacation = vacationIds.has(id);
        const registered = registeredIds.has(id);
        const detail = onVacation ? "FÉRIAS — BLOQUEADO" : registered ? "DSR JÁ REGISTRADA" : "LANÇAR DSR";
        return `<tr class="schedule-table-row ${onVacation ? "is-blocked" : ""}">
            <td>${escapeHtml(absenteeismCategory(employee))}</td>
            <td><strong>${escapeHtml(String(employee.full_name || "COLABORADOR").toUpperCase())}</strong></td>
            <td>${escapeHtml(String(employee.registration || "SEM MATRÍCULA"))}</td>
            <td><strong>${escapeHtml(String(employee.function_name || "-"))}</strong><span>${escapeHtml(String(employee.shift_name || "-"))}</span></td>
            <td><span class="schedule-status ${onVacation ? "is-vacation" : registered ? "is-registered" : "is-open"}">${detail}</span></td>
            <td><input class="weekly-dsr-employee" type="checkbox" value="${id}" ${onVacation ? "disabled" : "checked"} aria-label="${escapeHtml(detail)}"></td>
        </tr>`;
    }).join("");
    elements.weeklyDsrList.innerHTML = rows ? `<div class="absenteeism-table-wrap schedule-table-wrap"><table class="absenteeism-table schedule-table"><thead><tr><th>ÁREA</th><th>COLABORADOR</th><th>MATRÍCULA</th><th>FUNÇÃO / TURNO</th><th>SITUAÇÃO DSR</th><th>LANÇAR</th></tr></thead><tbody>${rows}</tbody></table></div>` : "<article class=\"empty-state\"><strong>NENHUM COLABORADOR ENCONTRADO.</strong><span>AJUSTE OS FILTROS.</span></article>";
}

async function submitWeeklyDsr() {
    const weekStart = isoWeekToMonday(elements.weeklyDsrWeek?.value);
    const employeeIds = Array.from(document.querySelectorAll(".weekly-dsr-employee:checked")).map((input) => Number(input.value));
    if (!weekStart || !employeeIds.length) {
        showToast("SELECIONE A SEMANA E AO MENOS UM COLABORADOR.", true);
        return;
    }
    elements.weeklyDsrSaveButton.disabled = true;
    elements.weeklyDsrSaveButton.textContent = "SALVANDO...";
    try {
        const result = await apiFetch("/rh/dsr-semanal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ week_start: weekStart, employee_ids: employeeIds }),
        });
        showToast(`${Number(result.created?.length || 0)} DSR LANÇADA(S). ${Number(result.already_registered || 0)} JÁ EXISTIA(M).`);
        await refreshWeeklyDsr();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL SALVAR A DSR.", true);
    } finally {
        elements.weeklyDsrSaveButton.disabled = false;
        elements.weeklyDsrSaveButton.textContent = "SALVAR DSR DA SEMANA";
    }
}

function nextSundayInput() {
    const reference = new Date();
    const remainingDays = (7 - reference.getDay()) % 7 || 7;
    reference.setDate(reference.getDate() + remainingDays);
    return formatDateInputValue(reference);
}

function isoWeekStartForDate(value) {
    if (!value) return "";
    const reference = new Date(`${value}T12:00:00`);
    if (Number.isNaN(reference.getTime())) return "";
    const mondayOffset = (reference.getDay() + 6) % 7;
    reference.setDate(reference.getDate() - mondayOffset);
    return formatDateInputValue(reference);
}

function defaultDsrInputForSchedule(scheduleDate) {
    const reference = new Date(`${scheduleDate}T12:00:00`);
    if (Number.isNaN(reference.getTime())) return "";
    reference.setDate(reference.getDate() + 1);
    return formatDateInputValue(reference);
}

const WEEKDAY_NAMES_PT_BR = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];

function formatDateWithWeekday(value) {
    if (!value) return "-";
    const [year, month, day] = String(value).split("-").map(Number);
    if (![year, month, day].every(Number.isFinite)) return formatDate(value);
    const reference = new Date(year, month - 1, day, 12, 0, 0);
    return `${formatDate(value)} — ${WEEKDAY_NAMES_PT_BR[reference.getDay()]}`;
}

function closeSpecialScheduleHistory() {
    elements.specialScheduleHistoryModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
}

function renderSpecialScheduleHistory(rows) {
    const historyRows = [...(rows || [])].sort((left, right) => {
        const dateOrder = String(right.schedule_date || "").localeCompare(String(left.schedule_date || ""));
        return dateOrder || Number(right.id || 0) - Number(left.id || 0);
    });
    if (!historyRows.length) {
        renderStateCard(elements.specialScheduleHistoryList, {
            title: "NENHUMA ESCALA REGISTRADA",
            message: "Quando uma escala for salva, ela aparecerá aqui com a data e o dia da semana.",
            tone: "neutral",
            compact: true,
        });
        return;
    }
    const tableRows = historyRows.map((row) => {
        const employee = row.employee || {};
        const scheduleDate = row.schedule_date;
        const dsrDate = row.dsr_date;
        const status = String(row.status || "-").replaceAll("_", " ");
        return `<tr>
            <td><strong>${escapeHtml(formatDateWithWeekday(scheduleDate))}</strong></td>
            <td>${escapeHtml(String(row.schedule_type || "-").toUpperCase())}${row.holiday_name ? `<span>${escapeHtml(row.holiday_name)}</span>` : ""}</td>
            <td><strong>${escapeHtml(String(employee.full_name || "COLABORADOR").toUpperCase())}</strong><span>${escapeHtml(String(employee.registration || "-"))}</span></td>
            <td>${escapeHtml(absenteeismCategory(employee))}</td>
            <td><strong>${escapeHtml(String(status).toUpperCase())}</strong></td>
            <td>${dsrDate ? escapeHtml(formatDateWithWeekday(dsrDate)) : "NÃO SE APLICA"}</td>
        </tr>`;
    }).join("");
    elements.specialScheduleHistoryList.innerHTML = `<div class="absenteeism-table-wrap special-schedule-history-table-wrap"><table class="absenteeism-table special-schedule-history-table"><thead><tr><th>DATA DA ESCALA</th><th>TIPO</th><th>COLABORADOR</th><th>ÁREA</th><th>SITUAÇÃO</th><th>DSR PREVISTA</th></tr></thead><tbody>${tableRows}</tbody></table></div>`;
}

async function loadSpecialScheduleHistory() {
    const selectedDate = elements.specialScheduleHistoryDate?.value || "";
    const query = selectedDate ? `?data=${encodeURIComponent(selectedDate)}` : "";
    elements.specialScheduleHistoryLoad.disabled = true;
    elements.specialScheduleHistoryLoad.textContent = "CARREGANDO...";
    renderStateCard(elements.specialScheduleHistoryList, { title: "CARREGANDO HISTÓRICO", message: "Consultando as escalas salvas.", tone: "loading", compact: true });
    try {
        const rows = await apiFetch(`/rh/escalas-especiais${query}`);
        renderSpecialScheduleHistory(rows);
    } catch (error) {
        renderStateCard(elements.specialScheduleHistoryList, { title: "HISTÓRICO INDISPONÍVEL", message: error.message || "Não foi possível consultar o histórico.", tone: "error", compact: true });
        showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR O HISTÓRICO.", true);
    } finally {
        elements.specialScheduleHistoryLoad.disabled = false;
        elements.specialScheduleHistoryLoad.textContent = "CARREGAR HISTÓRICO";
    }
}

async function openSpecialScheduleHistory() {
    elements.specialScheduleHistoryModal?.classList.remove("hidden");
    document.body.classList.add("modal-open");
    await loadSpecialScheduleHistory();
}

async function exportSpecialSchedulePdf() {
    const date = elements.specialScheduleDate?.value || "";
    const type = elements.specialScheduleType?.value || "";
    const params = new URLSearchParams();
    if (date) params.set("data", date);
    if (type) params.set("tipo", type);
    const filename = `escala_${String(type || "historico").toLowerCase()}_${date || "historico"}.pdf`;
    elements.specialSchedulePdfButton.disabled = true;
    elements.specialSchedulePdfButton.textContent = "GERANDO PDF...";
    try {
        const response = await fetch(`${state.apiBaseUrl}/rh/escalas-especiais/pdf?${params}`, { headers: optionsLikeHeaders({ Accept: "application/pdf" }) });
        if (!response.ok) {
            let payload = {};
            try { payload = await response.json(); } catch { payload = {}; }
            throw new Error(payload.error || "NÃO FOI POSSÍVEL GERAR O PDF.");
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank", "noopener");
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60000);
        showToast("PDF DA ESCALA BAIXADO E ABERTO.");
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL EXPORTAR O PDF.", true);
    } finally {
        elements.specialSchedulePdfButton.disabled = false;
        elements.specialSchedulePdfButton.textContent = "EXPORTAR PDF";
    }
}

function toggleSpecialHolidayName() {
    const isHoliday = elements.specialScheduleType?.value === "FERIADO";
    const isSunday = !isHoliday;
    elements.specialScheduleHolidayLabel?.classList.toggle("hidden", !isHoliday);
    elements.specialScheduleHolidayName?.classList.toggle("hidden", !isHoliday);
    elements.specialScheduleDsrLabel?.classList.toggle("hidden", !isSunday);
    elements.specialScheduleDsrActions?.classList.toggle("hidden", !isSunday);
    if (!isHoliday && elements.specialScheduleHolidayName) {
        elements.specialScheduleHolidayName.value = "";
    }
}

async function openSpecialScheduleMenu() {
    if (!hasWashReportAccess()) {
        showToast("APENAS ADMIN OU GESTOR PODE LANÇAR ESCALA.", true);
        return;
    }
    if (!elements.specialScheduleDate.value) {
        elements.specialScheduleDate.value = nextSundayInput();
    }
    if (elements.specialScheduleType.value === "DOMINGO") elements.specialScheduleDate.min = elements.specialScheduleDate.max = nextSundayInput();
    if (elements.specialScheduleType.value === "DOMINGO" && !elements.specialScheduleDefaultDsr.value) {
        elements.specialScheduleDefaultDsr.value = defaultDsrInputForSchedule(elements.specialScheduleDate.value);
    }
    toggleSpecialHolidayName();
    setActiveScreen("specialSchedule");
    await refreshSpecialSchedule();
}

async function refreshSpecialSchedule() {
    const scheduleDate = elements.specialScheduleDate?.value;
    if (!scheduleDate) {
        showToast("INFORME A DATA DA ESCALA.", true);
        return;
    }
    if (elements.specialScheduleType.value === "DOMINGO" && !elements.specialScheduleDefaultDsr.value) {
        elements.specialScheduleDefaultDsr.value = defaultDsrInputForSchedule(scheduleDate);
    }
    elements.specialScheduleCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.specialScheduleList, {
        title: "CARREGANDO ESCALA",
        message: "Buscando colaboradores ativos e a escala já registrada nesta data.",
        tone: "loading",
    });
    try {
        const [employees, rows] = await Promise.all([
            apiFetch("/rh/colaboradores?situacao=ATIVO"),
            apiFetch(`/rh/escalas-especiais?data=${scheduleDate}`),
        ]);
        state.specialSchedule = { employees: employees || [], rows: rows || [] };
        renderSpecialSchedule();
    } catch (error) {
        elements.specialScheduleCounter.textContent = "INDISPONÍVEL";
        renderStateCard(elements.specialScheduleList, {
            title: "ESCALA NÃO DISPONÍVEL",
            message: error.message || "Não foi possível carregar a escala.",
            tone: "error",
        });
        showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR A ESCALA.", true);
    }
}

function renderSpecialSchedule() {
    const allEmployees = state.specialSchedule.employees || [];
    prepareScheduleFilters("special", allEmployees);
    const employees = sortScheduleEmployees(allEmployees.filter((employee) => scheduleEmployeeMatches(employee, "special")));
    const rows = state.specialSchedule.rows || [];
    const scheduleDate = elements.specialScheduleDate.value;
    const isSunday = elements.specialScheduleType.value === "DOMINGO";
    const defaultDsrDate = elements.specialScheduleDefaultDsr.value;
    const scheduledByEmployee = new Map(rows.map((row) => [Number(row.employee_id), row]));
    elements.specialScheduleCounter.textContent = `${employees.length} ATIVOS | ${rows.length} JÁ ESCALADOS`;
    const dsrSummary = isSunday
        ? `A DSR só será criada após confirmar a presença no domingo. Data prevista: ${escapeHtml(formatDateWithWeekday(defaultDsrDate))}.`
        : "Feriado não gera DSR neste fluxo. A escala ficará aguardando a confirmação de presença.";
    elements.specialScheduleSummary.innerHTML = `
        <div><strong>ESCALA: ${escapeHtml(formatDateWithWeekday(scheduleDate))} | ${escapeHtml(String(elements.specialScheduleType.value || "-").toUpperCase())}</strong><span>${dsrSummary}</span></div>
        <div class="progress-track" aria-hidden="true"><span style="width: 100%"></span></div>
        <span>${isSunday ? `SEMANA DA DSR PREVISTA: ${escapeHtml(formatDateWithWeekday(isoWeekStartForDate(defaultDsrDate)))}.` : "CONFIRME COMPARECIMENTO OU NÃO COMPARECIMENTO APÓS A ESCALA."}</span>
    `;
    const rowsHtml = employees.map((employee) => {
        const id = Number(employee.id);
        const schedule = scheduledByEmployee.get(id);
        const dsrDate = schedule?.dsr_date || defaultDsrDate || "";
        const weekStart = isoWeekStartForDate(dsrDate);
        const scheduled = Boolean(schedule);
        const status = String(schedule?.status || "").replaceAll("_", " ");
        const attendanceActions = scheduled && schedule.status === "ESCALADO" ? `<div class="special-schedule-result-actions"><button class="secondary-button" type="button" data-special-schedule-action="confirmar" data-schedule-id="${Number(schedule.id)}">COMPARECEU</button><button class="secondary-button" type="button" data-special-schedule-action="ausente" data-schedule-id="${Number(schedule.id)}">NÃO COMPARECEU</button></div>` : "";
        const choice = scheduled ? `ESCALA ${escapeHtml(status)}${isSunday ? ` | DSR: ${escapeHtml(formatDateWithWeekday(dsrDate))}` : ""}` : "INCLUIR NA ESCALA";
        return `<tr class="special-schedule-card schedule-table-row ${scheduled ? "is-blocked" : ""}" data-employee-id="${id}">
            <td>${escapeHtml(absenteeismCategory(employee))}</td>
            <td><strong>${escapeHtml(String(employee.full_name || "COLABORADOR").toUpperCase())}</strong></td>
            <td>${escapeHtml(String(employee.registration || "-"))}</td>
            <td><strong>${escapeHtml(String(employee.function_name || "-"))}</strong><span>${escapeHtml(String(employee.shift_name || employee.team_name || "-"))}</span></td>
            <td><span class="schedule-status ${scheduled ? "is-registered" : "is-open"}">${choice}</span></td>
            <td>${isSunday ? `<label class="schedule-dsr-inline">DSR <input class="special-schedule-dsr-date" type="date" value="${escapeHtml(dsrDate)}" ${scheduled ? "disabled" : ""}><small>SEMANA: <span class="special-schedule-week">${escapeHtml(formatDateWithWeekday(weekStart))}</span></small></label>` : "NÃO SE APLICA"}</td>
            <td>${scheduled ? attendanceActions : `<label class="schedule-select-row"><input class="special-schedule-employee" type="checkbox" aria-label="Selecionar ${escapeHtml(String(employee.full_name || "colaborador"))}"><span>SELECIONAR</span></label>`}</td>
        </tr>`;
    }).join("");
    elements.specialScheduleList.innerHTML = rowsHtml ? `<div class="absenteeism-table-wrap schedule-table-wrap"><table class="absenteeism-table schedule-table special-schedule-table"><thead><tr><th>ÁREA</th><th>COLABORADOR</th><th>MATRÍCULA</th><th>FUNÇÃO / TURNO</th><th>SITUAÇÃO</th><th>DSR PREVISTA</th><th>AÇÃO</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>` : "<article class=\"empty-state\"><strong>NENHUM COLABORADOR ENCONTRADO.</strong><span>AJUSTE OS FILTROS.</span></article>";
    updateSpecialScheduleSelectionSummary();
}

function updateSpecialScheduleSelectionSummary() {
    const checkboxes = Array.from(document.querySelectorAll(".special-schedule-employee"));
    const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
    checkboxes.forEach((checkbox) => {
        checkbox.closest(".special-schedule-card")?.classList.toggle("is-selected", checkbox.checked);
    });
    if (elements.specialScheduleSelectedCount) {
        elements.specialScheduleSelectedCount.textContent = `${selected} SELECIONADO${selected === 1 ? "" : "S"}`;
    }
    if (elements.specialScheduleSelectAll) {
        elements.specialScheduleSelectAll.disabled = !checkboxes.length;
        elements.specialScheduleSelectAll.checked = checkboxes.length > 0 && selected === checkboxes.length;
        elements.specialScheduleSelectAll.indeterminate = selected > 0 && selected < checkboxes.length;
    }
}

async function submitSpecialSchedule() {
    const scheduleDate = elements.specialScheduleDate?.value;
    const scheduleType = elements.specialScheduleType?.value;
    const holidayName = elements.specialScheduleHolidayName?.value.trim() || "";
    const isSunday = scheduleType === "DOMINGO";
    const entries = Array.from(document.querySelectorAll(".special-schedule-card")).flatMap((card) => {
        const checkbox = card.querySelector(".special-schedule-employee");
        const dsrDate = card.querySelector(".special-schedule-dsr-date")?.value;
        return checkbox?.checked ? [{ employee_id: Number(card.dataset.employeeId), ...(isSunday ? { dsr_date: dsrDate } : {}) }] : [];
    });
    if (!scheduleDate || !entries.length) {
        showToast("INFORME A DATA E SELECIONE AO MENOS UM COLABORADOR.", true);
        return;
    }
    if (scheduleType === "FERIADO" && !holidayName) {
        showToast("INFORME O NOME DO FERIADO.", true);
        return;
    }
    if (isSunday && entries.some((entry) => !entry.dsr_date)) {
        showToast("INFORME A DATA DA DSR PARA TODOS OS COLABORADORES SELECIONADOS.", true);
        return;
    }
    elements.specialScheduleSaveButton.disabled = true;
    elements.specialScheduleSaveButton.textContent = "SALVANDO...";
    try {
        const result = await apiFetch("/rh/escalas-especiais", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                schedule_date: scheduleDate,
                schedule_type: scheduleType,
                holiday_name: holidayName || null,
                entries,
            }),
        });
        showToast(`${Number(result.length || 0)} COLABORADOR(ES) ESCALADO(S). ${isSunday ? "A DSR SERÁ CRIADA APÓS CONFIRMAR PRESENÇA." : "FERIADO SEM DSR."}`);
        await refreshSpecialSchedule();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL SALVAR A ESCALA.", true);
    } finally {
        elements.specialScheduleSaveButton.disabled = false;
        elements.specialScheduleSaveButton.textContent = "SALVAR ESCALA E DSR";
    }
}

async function resolveSpecialSchedule(scheduleId, action) {
    const endpoint = action === "confirmar" ? "confirmar-presenca" : "nao-compareceu";
    try {
        const result = await apiFetch(`/rh/escalas-especiais/${scheduleId}/${endpoint}`, { method: "POST" });
        const status = String(result.status || "").replaceAll("_", " ");
        showToast(`ESCALA ATUALIZADA: ${status}.${result.dsr_attendance_record_id ? " DSR REGISTRADA." : ""}`);
        await refreshSpecialSchedule();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL ATUALIZAR A ESCALA.", true);
    }
}

const ABSENTEEISM_STATUSES = ["PRESENTE", "FALTA", "ATESTADO", "DSR", "FERIAS", "FOLGA", "AFASTADO", "CURSO", "SERVICO_EXTERNO"];

function absenteeismCategory(employee) {
    const notes = normalizeText(employee?.notes || "");
    const areaMatch = notes.match(/area de atuacao:\s*([a-z]+)/i);
    const area = areaMatch?.[1] || "";
    if (area === "pcm" || area === "adm") return "ADM";
    if (area === "rtg") return "RTG";
    if (area === "lbs") return "LBS";
    const team = normalizeText(employee?.team_name || "");
    if (team.includes("adm")) return "ADM";
    if (team.includes("rtg")) return "RTG";
    if (team.includes("lbs")) return "LBS";
    return "OUTROS";
}

function fillAbsenteeismFilter(element, values, label) {
    const selected = element.value;
    element.innerHTML = `<option value="">${label}</option>${[...new Set(values.filter(Boolean))].sort().map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
    element.value = selected;
}

async function openAbsenteeismMenu() {
    if (!hasWashReportAccess()) return showToast("APENAS ADMIN OU GESTOR PODE APURAR ABSENTEÍSMO.", true);
    if (!elements.absenteeismDate.value) elements.absenteeismDate.value = formatDateInputValue(new Date());
    fillAbsenteeismFilter(elements.absenteeismStatus, ABSENTEEISM_STATUSES, "TODOS OS STATUS");
    setActiveScreen("absenteeism");
    await refreshAbsenteeism();
}

async function refreshAbsenteeism() {
    const params = absenteeismQueryParams();
    [...params.keys()].forEach((key) => !params.get(key) && params.delete(key));
    elements.absenteeismCounter.textContent = "CARREGANDO...";
    try {
        const data = await apiFetch(`/rh/absenteismo-mobile?${params}`);
        state.absenteeism = data;
        const employees = data.rows.map((row) => row.employee || {});
        fillAbsenteeismFilter(elements.absenteeismShift, employees.map((row) => row.shift_name), "TODOS OS TURNOS");
        fillAbsenteeismFilter(elements.absenteeismSector, employees.map((row) => row.team_name), "TODAS AS ÁREAS");
        fillAbsenteeismFilter(elements.absenteeismFunction, employees.map((row) => row.function_name), "TODAS AS FUNÇÕES");
        renderAbsenteeism();
    } catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL CARREGAR O ABSENTEÍSMO.", true); }
}

function absenteeismQueryParams() {
    return new URLSearchParams({ data: elements.absenteeismDate.value, nome: elements.absenteeismName.value.trim(), matricula: elements.absenteeismRegistration.value.trim(), turno: elements.absenteeismShift.value, setor: elements.absenteeismSector.value, funcao: elements.absenteeismFunction.value, status: elements.absenteeismStatus.value });
}

function scheduleAbsenteeismRefresh() {
    window.clearTimeout(absenteeismFilterTimer);
    absenteeismFilterTimer = window.setTimeout(() => refreshAbsenteeism(), 220);
}

function addDaysToDateInput(value, days) {
    if (!value) return "";
    const date = new Date(`${value}T12:00:00`);
    date.setDate(date.getDate() + Math.max(0, Number(days || 1) - 1));
    return formatDateInputValue(date);
}

function closeAbsenteeismAtestadoModal(restore = true) {
    const pending = state.pendingAbsenteeismAtestado;
    if (restore && pending?.row && pending.target) {
        pending.target.value = pending.previousStatus;
        pending.row.dataset.status = pending.previousStatus;
        pending.row.dataset.awaitingAtestado = "false";
        pending.row.className = `absenteeism-row status-${pending.previousStatus.toLowerCase()}`;
        updateAbsenteeismPreview();
    }
    elements.absenteeismAtestadoModal?.classList.add("hidden");
    state.pendingAbsenteeismAtestado = null;
}

function openAbsenteeismAtestadoModal(row, target, previousStatus) {
    const employee = state.absenteeism.rows.find((item) => Number(item.employee?.id) === Number(row.dataset.employeeId))?.employee || {};
    state.pendingAbsenteeismAtestado = { row, target, previousStatus };
    elements.absenteeismAtestadoEmployee.textContent = `${employee.full_name || "Colaborador"} | Matrícula: ${employee.registration || "-"}`;
    elements.absenteeismAtestadoStart.value = elements.absenteeismDate.value;
    elements.absenteeismAtestadoDays.value = "1";
    elements.absenteeismAtestadoEnd.value = elements.absenteeismDate.value;
    elements.absenteeismAtestadoNotes.value = "";
    elements.absenteeismAtestadoModal.classList.remove("hidden");
    elements.absenteeismAtestadoDays.focus();
}

async function saveAbsenteeismAtestado(event) {
    event.preventDefault();
    const pending = state.pendingAbsenteeismAtestado;
    if (!pending) return;
    const start = elements.absenteeismAtestadoStart.value;
    const days = Math.min(366, Math.max(1, Number(elements.absenteeismAtestadoDays.value || 1)));
    try {
        await apiFetch("/rh/frequencia", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ employee_id: Number(pending.row.dataset.employeeId), occurrence_date: start, end_date: addDaysToDateInput(start, days), occurrence_type: "ATESTADO", notes: elements.absenteeismAtestadoNotes.value.trim() }) });
        closeAbsenteeismAtestadoModal(false);
        showToast(`ATESTADO REGISTRADO POR ${days} DIA(S).`);
        await refreshAbsenteeism();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL REGISTRAR O ATESTADO.", true);
    }
}

async function exportAbsenteeismPdf() {
    const params = absenteeismQueryParams();
    [...params.keys()].forEach((key) => !params.get(key) && params.delete(key));
    const date = elements.absenteeismDate.value || formatDateInputValue(new Date());
    const filename = `absenteismo_${date}.pdf`;
    try {
        elements.absenteeismPdfButton.disabled = true;
        const response = await fetch(`${state.apiBaseUrl}/rh/absenteismo-mobile/pdf?${params}`, { headers: optionsLikeHeaders({ Accept: "application/pdf" }) });
        if (!response.ok) throw new Error("NÃO FOI POSSÍVEL GERAR O PDF.");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank", "noopener");
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60000);
        showToast("RELATÓRIO DE ABSENTEÍSMO BAIXADO E ABERTO.");
    } catch (error) {
        if (error.name !== "AbortError") showToast(error.message || "NÃO FOI POSSÍVEL EXPORTAR O PDF.", true);
    } finally {
        elements.absenteeismPdfButton.disabled = false;
    }
}

function renderAbsenteeism() {
    const rows = state.absenteeism.rows || [], summary = state.absenteeism.summary || { by_type: {} };
    elements.absenteeismCounter.textContent = `${summary.total || 0} COLABORADORES`;
    elements.absenteeismSummary.innerHTML = ABSENTEEISM_STATUSES.map((status) => `<div><strong>${summary.by_type?.[status] || 0}</strong><span>${status.replaceAll("_", " ")}</span></div>`).join("");
    let area = "";
    const categoryOrder = { ADM: 1, RTG: 2, LBS: 3, OUTROS: 4 };
    const orderedRows = [...rows].sort((left, right) => {
        const leftCategory = absenteeismCategory(left.employee || {}), rightCategory = absenteeismCategory(right.employee || {});
        return (categoryOrder[leftCategory] || 9) - (categoryOrder[rightCategory] || 9) || String(left.employee?.full_name || "").localeCompare(String(right.employee?.full_name || ""), "pt-BR");
    });
    const tableRows = orderedRows.map((row) => {
        const employee = row.employee || {}, nextArea = absenteeismCategory(employee);
        const heading = nextArea !== area ? (area = nextArea, `<tr class="absenteeism-area-row"><th colspan="6">${escapeHtml(nextArea)}</th></tr>`) : "";
        const options = ABSENTEEISM_STATUSES.map((status) => `<option value="${status}" ${row.occurrence_type === status ? "selected" : ""}>${status.replaceAll("_", " ")}</option>`).join("");
        return `${heading}<tr class="absenteeism-row status-${String(row.occurrence_type).toLowerCase()}" data-employee-id="${Number(employee.id)}" data-vacation="${row.automatic_vacation}" data-status="${row.occurrence_type}" data-awaiting-atestado="false"><td class="absenteeism-area-cell">${escapeHtml(nextArea)}</td><td class="absenteeism-employee-cell"><strong>${escapeHtml(employee.full_name || "-")}</strong></td><td>${escapeHtml(employee.registration || "-")}</td><td><strong>${escapeHtml(employee.function_name || "-")}</strong><span>${escapeHtml(employee.shift_name || "-")}</span></td><td><select class="absenteeism-status status-${String(row.occurrence_type).toLowerCase()}" ${row.automatic_vacation ? "disabled" : ""}>${options}</select></td><td><input class="absenteeism-notes" value="${escapeHtml(row.notes || "")}" placeholder="Observação" ${row.automatic_vacation ? "disabled" : ""}></td></tr>`;
    }).join("");
    elements.absenteeismList.innerHTML = tableRows ? `<div class="absenteeism-table-wrap"><table class="absenteeism-table"><thead><tr><th>ÁREA</th><th>COLABORADOR</th><th>MATRÍCULA</th><th>FUNÇÃO / TURNO</th><th>STATUS DO DIA</th><th>OBSERVAÇÃO</th></tr></thead><tbody>${tableRows}</tbody></table></div>` : "<div class=\"empty-state\"><strong>SEM COLABORADORES.</strong><span>AJUSTE OS FILTROS.</span></div>";
}

function updateAbsenteeismPreview() {
    const totals = Object.fromEntries(ABSENTEEISM_STATUSES.map((status) => [status, 0]));
    document.querySelectorAll(".absenteeism-row").forEach((row) => {
        const status = row.querySelector(".absenteeism-status")?.value;
        if (status in totals) totals[status] += 1;
    });
    elements.absenteeismSummary.innerHTML = ABSENTEEISM_STATUSES.map((status) => `<div><strong>${totals[status]}</strong><span>${status.replaceAll("_", " ")}</span></div>`).join("");
}

async function saveAbsenteeism() {
    const entries = Array.from(document.querySelectorAll(".absenteeism-row")).filter((row) => row.dataset.vacation !== "true" && row.dataset.awaitingAtestado !== "true").map((row) => ({ employee_id: Number(row.dataset.employeeId), occurrence_type: row.querySelector(".absenteeism-status").value, notes: row.querySelector(".absenteeism-notes").value.trim() }));
    if (!entries.length) return showToast("NÃO HÁ REGISTROS MANUAIS PARA SALVAR.", true);
    elements.absenteeismSaveButton.disabled = true;
    try { const result = await apiFetch("/rh/absenteismo-mobile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ date: elements.absenteeismDate.value, entries }) }); showToast(`${result.saved} REGISTRO(S) SALVO(S).`); await refreshAbsenteeism(); }
    catch (error) { showToast(error.message || "NÃO FOI POSSÍVEL SALVAR.", true); }
    finally { elements.absenteeismSaveButton.disabled = false; }
}

const OPERATIONAL_STATUS_LABELS = {
    SEM_APONTAMENTO: "SEM APONTAMENTO",
    DISPONIVEL: "DISPONÍVEL",
    INDISPONIVEL: "INDISPONÍVEL",
    RESTRICAO: "COM RESTRIÇÃO",
    MANUTENCAO: "EM MANUTENÇÃO",
};

async function openAvailabilityMenu(options = {}) {
    state.focusedAvailabilityVehicleId = Number(options.vehicleId || state.selectedVehicle?.id || 0) || null;
    setActiveScreen("availability");
    elements.availabilityCounter.textContent = "CARREGANDO...";
    renderStateCard(elements.availabilityList, {
        title: "CARREGANDO EQUIPAMENTOS",
        message: "Buscando a situação operacional e as últimas leituras.",
        tone: "loading",
    });
    try {
        state.availabilityOverview = await apiFetch("/disponibilidade/visao");
        localStorage.setItem(OFFLINE_AVAILABILITY_KEY, JSON.stringify(state.availabilityOverview));
        renderAvailability();
    } catch (error) {
        const cachedOverview = readJsonStorage(OFFLINE_AVAILABILITY_KEY, null);
        if (cachedOverview) {
            state.availabilityOverview = cachedOverview;
            renderAvailability();
            showToast("DISPONIBILIDADE OFFLINE CARREGADA. O APONTAMENTO SERÁ SINCRONIZADO.");
            return;
        }
        elements.availabilityCounter.textContent = "FALHA";
        renderStateCard(elements.availabilityList, {
            title: "NÃO FOI POSSÍVEL CARREGAR A DISPONIBILIDADE",
            message: error.message || "Verifique a conexão e tente novamente.",
            tone: "error",
        });
        showToast(error.message, true);
    }
}

function renderAvailability() {
    const overview = state.availabilityOverview || { summary: {}, rows: [] };
    const rows = overview.rows || [];
    const visibleRows = filterAvailabilityRows(rows);
    const counts = availabilityCounts(visibleRows);
    const measured = visibleRows
        .map((row) => row.availability_percentage)
        .filter((value) => value !== null && value !== undefined)
        .map(Number);
    const average = measured.length ? measured.reduce((total, value) => total + value, 0) / measured.length : null;
    elements.availabilityCounter.textContent = visibleRows.length === rows.length
        ? `${rows.length} EQUIPAMENTO${rows.length === 1 ? "" : "S"}`
        : `${visibleRows.length} DE ${rows.length} EQUIPAMENTOS`;
    elements.availabilityFamilyTabs.forEach((button) => {
        const active = String(button.dataset.availabilityFamily || "TODOS").toUpperCase() === state.availabilityFilters.family;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
    });
    elements.availabilitySummary.innerHTML = `
        <article><span>DISPONÍVEIS</span><strong>${Number(counts.DISPONIVEL || 0)}</strong></article>
        <article><span>INDISPONÍVEIS</span><strong>${Number(counts.INDISPONIVEL || 0)}</strong></article>
        <article><span>RESTRIÇÃO</span><strong>${Number(counts.RESTRICAO || 0)}</strong></article>
        <article><span>MANUTENÇÃO</span><strong>${Number(counts.MANUTENCAO || 0)}</strong></article>
        <article><span>SEM APONTAMENTO</span><strong>${Number(counts.SEM_APONTAMENTO || 0)}</strong></article>
        <article><span>DISPONIBILIDADE MEDIDA</span><strong>${average == null ? "-" : `${Number(average).toFixed(2)}%`}</strong></article>
    `;
    elements.availabilityList.innerHTML = "";
    if (!visibleRows.length) {
        renderStateCard(elements.availabilityList, {
            title: rows.length ? "NENHUM EQUIPAMENTO NESTE FILTRO" : "NENHUM EQUIPAMENTO UNIFICADO",
            message: rows.length
                ? "Limpe os filtros ou selecione outro módulo para continuar."
                : "Cadastre o módulo do equipamento no Desktop antes do apontamento.",
        });
        return;
    }
    visibleRows.forEach((row) => elements.availabilityList.appendChild(makeAvailabilityCard(row)));
    if (state.focusedAvailabilityVehicleId) {
        const focusedCard = elements.availabilityList.querySelector(`[data-vehicle-id="${state.focusedAvailabilityVehicleId}"]`);
        focusedCard?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function availabilityFamilyKey(row) {
    const vehicle = row?.vehicle || {};
    return getVehicleFamilyKey({
        ...vehicle,
        family: row?.family || vehicle.family,
        family_name: row?.family?.name || vehicle.family_name,
    });
}

function filterAvailabilityRows(rows) {
    const search = normalizeText(state.availabilityFilters.search);
    const family = String(state.availabilityFilters.family || "TODOS").toUpperCase();
    const status = String(state.availabilityFilters.status || "").toUpperCase();
    const priority = { INDISPONIVEL: 0, MANUTENCAO: 1, RESTRICAO: 2, SEM_APONTAMENTO: 3, DISPONIVEL: 4 };
    return rows.filter((row) => {
        const vehicle = row.vehicle || {};
        const operationalStatus = String(vehicle.operational_state?.operational_status || "SEM_APONTAMENTO").toUpperCase();
        const haystack = normalizeText([
            vehicle.frota,
            vehicle.placa,
            vehicle.modelo,
            vehicle.tipo,
            row.family?.name,
            row.location?.full_name,
        ].join(" "));
        return (!search || haystack.includes(search))
            && (family === "TODOS" || availabilityFamilyKey(row) === family)
            && (!status || operationalStatus === status);
    }).sort((left, right) => {
        const leftStatus = String(left.vehicle?.operational_state?.operational_status || "SEM_APONTAMENTO").toUpperCase();
        const rightStatus = String(right.vehicle?.operational_state?.operational_status || "SEM_APONTAMENTO").toUpperCase();
        const statusDifference = (priority[leftStatus] ?? 9) - (priority[rightStatus] ?? 9);
        if (statusDifference) return statusDifference;
        return String(left.vehicle?.frota || left.vehicle?.placa || "").localeCompare(
            String(right.vehicle?.frota || right.vehicle?.placa || ""),
            "pt-BR",
            { numeric: true, sensitivity: "base" },
        );
    });
}

function availabilityCounts(rows) {
    const counts = { DISPONIVEL: 0, INDISPONIVEL: 0, RESTRICAO: 0, MANUTENCAO: 0, SEM_APONTAMENTO: 0 };
    rows.forEach((row) => {
        const status = String(row.vehicle?.operational_state?.operational_status || "SEM_APONTAMENTO").toUpperCase();
        counts[status] = Number(counts[status] || 0) + 1;
    });
    return counts;
}

function makeAvailabilityCard(row) {
    const vehicle = row.vehicle || {};
    const operationalState = vehicle.operational_state || {};
    const status = operationalState.operational_status || "SEM_APONTAMENTO";
    const card = document.createElement("article");
    card.dataset.vehicleId = String(vehicle.id || "");
    card.className = `availability-card status-${status.toLowerCase()}`;
    card.innerHTML = `
        <header>
            <div>
                <span>${escapeHtml(row.location?.full_name || "SEM LOCAL DEFINIDO")}</span>
                <strong>${escapeHtml(vehicle.frota || vehicle.placa || "EQUIPAMENTO")}</strong>
                <em>${escapeHtml(row.family?.name || vehicle.tipo || "SEM FAMÍLIA")}</em>
            </div>
            <b>${escapeHtml(OPERATIONAL_STATUS_LABELS[status] || status)}</b>
        </header>
        <div class="availability-reading">
            <span>ÚLTIMO HORÍMETRO</span>
            <strong>${operationalState.latest_hourmeter == null ? "SEM LEITURA" : `${Number(operationalState.latest_hourmeter).toFixed(2)} h`}</strong>
            <small>${operationalState.latest_hourmeter_at ? formatManausDateTime(operationalState.latest_hourmeter_at) : ""}</small>
        </div>
        <details class="availability-action-panel availability-action-status">
            <summary><span>01</span><div><strong>ATUALIZAR SITUAÇÃO</strong><small>Informe a condição observada agora.</small></div></summary>
            <div class="availability-form-grid">
                <label><span>NOVA SITUAÇÃO</span>
                    <select class="availability-status">
                        <option value="DISPONIVEL">DISPONÍVEL</option>
                        <option value="INDISPONIVEL">INDISPONÍVEL</option>
                        <option value="RESTRICAO">COM RESTRIÇÃO</option>
                        <option value="MANUTENCAO">EM MANUTENÇÃO</option>
                    </select>
                </label>
                <label><span>MOTIVO / CONDIÇÃO</span><input class="availability-reason" maxlength="255" placeholder="Obrigatório fora da condição disponível"></label>
                <label><span>EVIDÊNCIA DO STATUS</span><input class="availability-status-photo" type="file" accept="image/*" capture="environment"></label>
                <button class="primary-button availability-status-save" type="button">SALVAR SITUAÇÃO</button>
            </div>
        </details>
        <details class="availability-action-panel availability-action-hourmeter">
            <summary><span>02</span><div><strong>REGISTRAR HORÍMETRO</strong><small>Digite a leitura mostrada no painel.</small></div></summary>
            <div class="availability-form-grid hourmeter-form">
                <label><span>NOVA LEITURA</span><input class="availability-hourmeter" type="number" min="0" step="0.01" inputmode="decimal" placeholder="Ex.: 1250,50"></label>
                <label><span>OBSERVAÇÃO</span><input class="availability-hourmeter-notes" maxlength="255" placeholder="Opcional"></label>
                <label><span>FOTO DO PAINEL</span><input class="availability-hourmeter-photo" type="file" accept="image/*" capture="environment"></label>
                <button class="primary-button availability-hourmeter-save" type="button">REGISTRAR HORÍMETRO</button>
            </div>
        </details>
    `;
    card.querySelector(".availability-status").value = status === "SEM_APONTAMENTO" ? "DISPONIVEL" : status;
    card.querySelector(".availability-status-save").addEventListener("click", () => submitOperationalStatus(card, vehicle));
    card.querySelector(".availability-hourmeter-save").addEventListener("click", () => submitHourmeter(card, vehicle));
    card.querySelectorAll(".availability-action-panel").forEach((panel) => {
        panel.addEventListener("toggle", () => {
            if (!panel.open) return;
            card.querySelectorAll(".availability-action-panel").forEach((other) => {
                if (other !== panel) other.open = false;
            });
        });
    });
    return card;
}

async function submitOperationalStatus(card, vehicle) {
    const button = card.querySelector(".availability-status-save");
    const status = card.querySelector(".availability-status").value;
    const reason = card.querySelector(".availability-reason").value.trim();
    const file = card.querySelector(".availability-status-photo").files?.[0];
    if (status !== "DISPONIVEL" && !reason) {
        showToast("INFORME O MOTIVO DESTA SITUAÇÃO.", true);
        return;
    }
    button.disabled = true;
    button.textContent = "SALVANDO...";
    try {
        const evidencePath = file
            ? await uploadEvidence(file, vehicle.frota || "EQUIPAMENTO", "STATUS OPERACIONAL", "status_operacional", "DISPONIBILIDADE")
            : null;
        await apiFetch(`/equipamentos/${vehicle.id}/status-operacional`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status, reason, evidence_path: evidencePath }),
        });
        showToast("SITUAÇÃO OPERACIONAL ATUALIZADA.");
        await openAvailabilityMenu();
    } catch (error) {
        button.disabled = false;
        button.textContent = "SALVAR SITUAÇÃO";
        showToast(error.message, true);
    }
}

async function submitHourmeter(card, vehicle) {
    const button = card.querySelector(".availability-hourmeter-save");
    const reading = card.querySelector(".availability-hourmeter").value;
    const notes = card.querySelector(".availability-hourmeter-notes").value.trim();
    const file = card.querySelector(".availability-hourmeter-photo").files?.[0];
    if (reading === "" || Number(reading) < 0) {
        showToast("INFORME UMA LEITURA DE HORÍMETRO VÁLIDA.", true);
        return;
    }
    button.disabled = true;
    button.textContent = "REGISTRANDO...";
    try {
        const result = await submitMobileOperation("HORIMETRO", {
            vehicle_id: vehicle.id, reading: Number(reading), notes, recorded_at: new Date().toISOString(),
        }, file ? {
            file, field: "evidence_path", vehicleLabel: vehicle.frota || "EQUIPAMENTO",
            itemLabel: "HORÍMETRO", kind: "horimetro", folder: "DISPONIBILIDADE",
        } : null);
        if (result.queued) {
            showToast("HORÍMETRO SALVO NO APARELHO PARA SINCRONIZAR.");
        } else {
            showToast("HORÍMETRO REGISTRADO.");
            await openAvailabilityMenu({ vehicleId: vehicle.id });
        }
    } catch (error) {
        button.disabled = false;
        button.textContent = "REGISTRAR HORÍMETRO";
        showToast(error.message, true);
    }
}

async function openEmergenciesMenu() {
    setActiveScreen("emergencies");
    elements.emergencyVehicle.innerHTML = state.vehicles.filter((vehicle) => vehicle.ativo !== false)
        .map((vehicle) => `<option value="${vehicle.id}">${escapeHtml(vehicle.frota || vehicle.placa || vehicle.modelo)}</option>`).join("");
    if (state.selectedVehicle?.id) {
        elements.emergencyVehicle.value = String(state.selectedVehicle.id);
    }
    try {
        state.emergencies = await apiFetch("/emergenciais");
        localStorage.setItem(OFFLINE_EMERGENCIES_KEY, JSON.stringify(state.emergencies));
        renderEmergencies();
    } catch (error) {
        const cachedEmergencies = readJsonStorage(OFFLINE_EMERGENCIES_KEY, null);
        if (cachedEmergencies) {
            state.emergencies = cachedEmergencies;
            renderEmergencies();
            showToast("EMERGENCIAIS OFFLINE CARREGADOS. AS ETAPAS SERÃO SINCRONIZADAS.");
            return;
        }
        renderStateCard(elements.emergenciesList, { title: "FALHA AO CARREGAR", message: error.message, tone: "error" });
    }
}

function renderEmergencies() {
    const rows = state.emergencies || [];
    elements.emergenciesCounter.textContent = `${rows.length} OCORRÊNCIA${rows.length === 1 ? "" : "S"}`;
    elements.emergenciesList.innerHTML = "";
    if (!rows.length) {
        return renderStateCard(elements.emergenciesList, { title: "SEM EMERGENCIAIS", message: "Nenhuma ocorrência aberta ou atribuída a você." });
    }
    rows.forEach((row) => elements.emergenciesList.appendChild(makeEmergencyCard(row)));
}

function makeEmergencyCard(emergency) {
    const vehicle = emergency.vehicle || {};
    const order = emergency.work_order || {};
    const execution = emergency.execution || {};
    const card = document.createElement("article");
    card.className = `emergency-card severity-${String(emergency.severity || "baixa").toLowerCase()}`;
    let action = `<div class="emergency-waiting">AGUARDANDO TRIAGEM E GERAÇÃO DA OS NO DESKTOP.</div>`;
    if (order.id && !execution.repair_started_at) {
        action = `<div class="emergency-action"><textarea class="emergency-diagnosis" placeholder="DIAGNÓSTICO OBRIGATÓRIO"></textarea><input class="emergency-before-photo" type="file" accept="image/*" capture="environment"><button class="primary-button emergency-start" type="button">INICIAR REPARO</button></div>`;
    } else if (order.id && !execution.repair_completed_at) {
        action = `<div class="emergency-action"><textarea class="emergency-service" placeholder="SERVIÇO EXECUTADO"></textarea><input class="emergency-after-photo" type="file" accept="image/*" capture="environment"><button class="primary-button emergency-complete" type="button">CONCLUIR REPARO</button></div>`;
    } else if (order.id && execution.test_result !== "APROVADO") {
        action = `<div class="emergency-action"><select class="emergency-test-result"><option value="APROVADO">TESTE APROVADO</option><option value="REPROVADO">TESTE REPROVADO</option></select><textarea class="emergency-test-notes" placeholder="OBSERVAÇÃO DO TESTE"></textarea><input class="emergency-test-photo" type="file" accept="image/*" capture="environment"><button class="primary-button emergency-test" type="button">REGISTRAR TESTE</button></div>`;
    } else if (order.id && execution.release_status !== "LIBERADO") {
        action = `<button class="primary-button emergency-release" type="button">LIBERAR EQUIPAMENTO</button>`;
    } else if (execution.release_status === "LIBERADO") {
        action = `<div class="emergency-released">EQUIPAMENTO LIBERADO APÓS TESTE APROVADO.</div>`;
    }
    card.innerHTML = `<header><div><span>${escapeHtml(emergency.event_number || "EMERGENCIAL")}</span><strong>${escapeHtml(vehicle.frota || vehicle.placa || "EQUIPAMENTO")}</strong><em>${escapeHtml(emergency.title || "")}</em></div><b>${escapeHtml(emergency.severity || "-")}</b></header><div class="emergency-meta"><span>${escapeHtml(emergency.status || "-")}</span><span>${emergency.equipment_stopped ? "EQUIPAMENTO PARADO" : "SEM PARADA"}</span><span>${escapeHtml(order.order_number || "SEM OS")}</span></div><p>${escapeHtml(emergency.description || "")}</p>${action}`;
    card.querySelector(".emergency-start")?.addEventListener("click", () => startEmergencyWorkOrder(card, emergency));
    card.querySelector(".emergency-complete")?.addEventListener("click", () => completeEmergencyRepair(card, emergency));
    card.querySelector(".emergency-test")?.addEventListener("click", () => testEmergencyWorkOrder(card, emergency));
    card.querySelector(".emergency-release")?.addEventListener("click", () => releaseEmergencyWorkOrder(emergency));
    return card;
}

async function submitEmergency(event) {
    event.preventDefault();
    elements.emergencySubmit.disabled = true;
    try {
        const vehicleId = Number(elements.emergencyVehicle.value);
        const vehicle = state.vehicles.find((row) => Number(row.id) === vehicleId) || {};
        const file = elements.emergencyEvidence.files?.[0];
        const result = await submitMobileOperation("EMERGENCIA", {
            vehicle_id: vehicleId, severity: elements.emergencySeverity.value,
            equipment_stopped: elements.emergencyStopped.checked, title: elements.emergencyTitle.value.trim(),
            description: elements.emergencyDescription.value.trim(), location: elements.emergencyLocation.value.trim(),
            opened_at: new Date().toISOString(),
        }, file ? {
            file, field: "evidence_path", vehicleLabel: vehicle.frota || "EQUIPAMENTO",
            itemLabel: elements.emergencyTitle.value, kind: "emergencial", folder: "EMERGENCIAIS",
        } : null);
        elements.emergencyCreateForm.reset();
        if (result.queued) {
            showToast("EMERGÊNCIA SALVA NO APARELHO PARA SINCRONIZAR.");
        } else {
            showToast("EMERGÊNCIA REGISTRADA E ENVIADA PARA TRIAGEM.");
            await openEmergenciesMenu();
        }
    } catch (error) { showToast(error.message, true); }
    finally { elements.emergencySubmit.disabled = false; }
}

async function startEmergencyWorkOrder(card, emergency) {
    const diagnosis = card.querySelector(".emergency-diagnosis").value.trim();
    if (!diagnosis) return showToast("INFORME O DIAGNÓSTICO.", true);
    try {
        const file = card.querySelector(".emergency-before-photo").files?.[0];
        const result = await submitMobileOperation("OS_INICIAR", {
            work_order_id: emergency.work_order_id, diagnosis,
        }, file ? {
            file, field: "before_evidence_path", vehicleLabel: emergency.vehicle?.frota || "EQUIPAMENTO",
            itemLabel: emergency.title, kind: "os_antes", folder: "EMERGENCIAIS",
        } : null);
        if (result.queued) showToast("INÍCIO DA OS SALVO NO APARELHO PARA SINCRONIZAR.");
        else await openEmergenciesMenu();
    } catch (error) { showToast(error.message, true); }
}

async function completeEmergencyRepair(card, emergency) {
    const service = card.querySelector(".emergency-service").value.trim();
    const file = card.querySelector(".emergency-after-photo").files?.[0];
    if (!service || !file) return showToast("INFORME O SERVIÇO E A FOTO POSTERIOR.", true);
    try {
        const result = await submitMobileOperation("OS_CONCLUIR", {
            work_order_id: emergency.work_order_id, service_performed: service,
        }, {
            file, field: "after_evidence_path", vehicleLabel: emergency.vehicle?.frota || "EQUIPAMENTO",
            itemLabel: emergency.title, kind: "os_depois", folder: "EMERGENCIAIS",
        });
        if (result.queued) showToast("CONCLUSÃO DA OS SALVA NO APARELHO PARA SINCRONIZAR.");
        else await openEmergenciesMenu();
    } catch (error) { showToast(error.message, true); }
}

async function testEmergencyWorkOrder(card, emergency) {
    const result = card.querySelector(".emergency-test-result").value;
    const notes = card.querySelector(".emergency-test-notes").value.trim();
    if (result === "REPROVADO" && !notes) return showToast("INFORME O MOTIVO DA REPROVAÇÃO.", true);
    try {
        const file = card.querySelector(".emergency-test-photo").files?.[0];
        const synced = await submitMobileOperation("OS_TESTAR", {
            work_order_id: emergency.work_order_id, test_result: result, test_notes: notes,
        }, file ? {
            file, field: "test_evidence_path", vehicleLabel: emergency.vehicle?.frota || "EQUIPAMENTO",
            itemLabel: emergency.title, kind: "os_teste", folder: "EMERGENCIAIS",
        } : null);
        if (synced.queued) showToast("TESTE DA OS SALVO NO APARELHO PARA SINCRONIZAR.");
        else await openEmergenciesMenu();
    } catch (error) { showToast(error.message, true); }
}

async function releaseEmergencyWorkOrder(emergency) {
    try {
        const result = await submitMobileOperation("OS_LIBERAR", { work_order_id: emergency.work_order_id });
        if (result.queued) showToast("LIBERAÇÃO DA OS SALVA NO APARELHO PARA SINCRONIZAR.");
        else {
            showToast("EQUIPAMENTO LIBERADO E DISPONIBILIDADE RESTAURADA.");
            await openEmergenciesMenu();
        }
    } catch (error) { showToast(error.message, true); }
}

async function openTechnicalLibraryMenu() {
    setActiveScreen("technicalLibrary");
    const vehicles = state.vehicles.filter((vehicle) => vehicle.ativo !== false);
    elements.technicalLibraryVehicle.innerHTML = vehicles.map((vehicle) =>
        `<option value="${vehicle.id}">${escapeHtml(vehicle.frota || vehicle.placa || vehicle.modelo)}</option>`
    ).join("");
    if (!vehicles.length) {
        renderStateCard(elements.technicalLibraryList, { title: "SEM EQUIPAMENTOS", message: "Nenhum equipamento ativo disponível para consulta." });
        return;
    }
    await loadTechnicalLibraryDocuments();
}

async function loadTechnicalLibraryDocuments() {
    const vehicleId = Number(elements.technicalLibraryVehicle.value);
    renderStateCard(elements.technicalLibraryList, { title: "CARREGANDO DOCUMENTOS", message: "Buscando a biblioteca técnica do equipamento.", tone: "loading" });
    try {
        state.technicalDocuments = await apiFetch(`/biblioteca-tecnica?vehicle_id=${vehicleId}`);
        renderTechnicalLibraryDocuments();
    } catch (error) {
        renderStateCard(elements.technicalLibraryList, { title: "FALHA AO CARREGAR", message: error.message, tone: "error" });
        showToast(error.message, true);
    }
}

function renderTechnicalLibraryDocuments() {
    const rows = state.technicalDocuments || [];
    elements.technicalLibraryList.innerHTML = "";
    if (!rows.length) {
        renderStateCard(elements.technicalLibraryList, { title: "SEM DOCUMENTOS", message: "A gestão ainda não vinculou documentos técnicos a este equipamento ou módulo." });
        return;
    }
    rows.forEach((documentRow) => {
        const card = document.createElement("article");
        card.className = "technical-library-card";
        card.innerHTML = `<header><div><span>${escapeHtml(documentRow.code || "DOCUMENTO")}</span><strong>${escapeHtml(documentRow.title || "")}</strong><em>${escapeHtml(documentRow.document_type || "-")} | REV. ${escapeHtml(documentRow.revision || "-")}</em></div><b>${escapeHtml(documentRow.effective_status || documentRow.status || "-")}</b></header><p>${escapeHtml(documentRow.description || "Sem descrição adicional.")}</p><button class="primary-button" type="button">ABRIR DOCUMENTO</button>`;
        card.querySelector("button").addEventListener("click", () => openTechnicalDocument(documentRow));
        elements.technicalLibraryList.appendChild(card);
    });
}

async function openTechnicalDocument(documentRow) {
    try {
        const response = await fetch(`${state.apiBaseUrl}${documentRow.file_path}`, { headers: { Authorization: `Bearer ${state.token}` } });
        if (!response.ok) throw new Error("Não foi possível abrir o documento.");
        const url = URL.createObjectURL(await response.blob());
        window.open(url, "_blank", "noopener");
        window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) { showToast(error.message, true); }
}

async function openTechnicalInspectionsMenu() {
    setActiveScreen("technicalInspections");
    elements.technicalInspectionForm.innerHTML = "";
    elements.technicalInspectionTemplateInfo.innerHTML = "CARREGANDO MODELOS TÉCNICOS...";
    try {
        const templates = await apiFetch("/inspecoes-tecnicas/modelos");
        state.technicalInspectionTemplates = templates || [];
        localStorage.setItem(OFFLINE_INSPECTION_TEMPLATES_KEY, JSON.stringify(state.technicalInspectionTemplates));
    } catch (error) {
        const cached = readJsonStorage(OFFLINE_INSPECTION_TEMPLATES_KEY, []);
        if (!cached.length) {
            renderStateCard(elements.technicalInspectionForm, {
                title: "MODELOS INDISPONÍVEIS", message: error.message, tone: "error",
            });
            return;
        }
        state.technicalInspectionTemplates = cached;
        showToast("USANDO MODELOS SALVOS NO APARELHO.");
    }
    renderTechnicalInspectionSelectors();
}

function renderTechnicalInspectionSelectors() {
    const familyIds = new Set(state.technicalInspectionTemplates.map((item) => Number(item.family_id)));
    const vehicles = state.vehicles.filter((vehicle) => vehicle.ativo !== false && familyIds.has(Number(vehicle.family_id)));
    elements.technicalInspectionVehicle.innerHTML = vehicles.map((vehicle) =>
        `<option value="${vehicle.id}">${escapeHtml(vehicle.frota || vehicle.placa || vehicle.modelo)}</option>`
    ).join("");
    if (!vehicles.length) {
        elements.technicalInspectionTemplate.innerHTML = "";
        renderStateCard(elements.technicalInspectionForm, {
            title: "SEM EQUIPAMENTOS COM MODELO PUBLICADO",
            message: "Publique um template para o módulo no Desktop.",
        });
        return;
    }
    renderTechnicalInspectionTemplateOptions();
}

function renderTechnicalInspectionTemplateOptions() {
    const vehicleId = Number(elements.technicalInspectionVehicle.value);
    const vehicle = state.vehicles.find((item) => Number(item.id) === vehicleId);
    const templates = state.technicalInspectionTemplates.filter(
        (template) => Number(template.family_id) === Number(vehicle?.family_id)
    );
    elements.technicalInspectionTemplate.innerHTML = templates.map((template) =>
        `<option value="${template.id}">${escapeHtml(template.name)} | V${template.version}</option>`
    ).join("");
    renderTechnicalInspectionForm();
}

function renderTechnicalInspectionForm() {
    const templateId = Number(elements.technicalInspectionTemplate.value);
    const template = state.technicalInspectionTemplates.find((item) => Number(item.id) === templateId);
    elements.technicalInspectionForm.innerHTML = "";
    if (!template) {
        return;
    }
    elements.technicalInspectionTemplateInfo.innerHTML = `
        <div><strong>${escapeHtml(template.name)} | V${template.version}</strong>
        <span>${escapeHtml(template.instructions || "Siga os itens na ordem publicada.")}</span></div>
    `;
    (template.items || []).filter((item) => item.active !== false).forEach((item) => {
        const card = document.createElement("article");
        card.className = "technical-inspection-item";
        card.dataset.itemId = item.id;
        card.dataset.responseType = item.response_type;
        let control = "";
        if (item.response_type === "STATUS") {
            control = `<select class="technical-response"><option value="">SELECIONE</option><option value="OK">OK</option><option value="NC">NÃO CONFORME</option><option value="NA">NÃO SE APLICA</option></select>`;
        } else if (item.response_type === "NUMERO") {
            control = `<input class="technical-number" type="number" step="0.01" inputmode="decimal" placeholder="VALOR ${escapeHtml(item.unit || "")}">`;
        } else {
            control = `<input class="technical-text" type="text" placeholder="INFORME A RESPOSTA">`;
        }
        card.innerHTML = `
            <header><span>${escapeHtml(item.category || "INSPEÇÃO")}</span><strong>${escapeHtml(item.label)}</strong></header>
            ${control}
            <textarea class="technical-observation" placeholder="OBSERVAÇÃO ${item.response_type === "STATUS" ? "(OBRIGATÓRIA EM NC)" : "OPCIONAL"}"></textarea>
            ${item.response_type === "STATUS" ? `<label class="evidence-input"><span>EVIDÊNCIA DE NC</span><input class="technical-evidence" type="file" accept="image/*" capture="environment"><em>${item.evidence_on_nc ? "OBRIGATÓRIA EM NÃO CONFORMIDADE" : "OPCIONAL"}</em></label>` : ""}
        `;
        elements.technicalInspectionForm.appendChild(card);
    });
}

async function collectTechnicalInspectionDraft() {
    const vehicleId = Number(elements.technicalInspectionVehicle.value);
    const templateId = Number(elements.technicalInspectionTemplate.value);
    const template = state.technicalInspectionTemplates.find((item) => Number(item.id) === templateId);
    const vehicle = state.vehicles.find((item) => Number(item.id) === vehicleId);
    const templateItems = new Map((template?.items || []).map((item) => [Number(item.id), item]));
    const items = [];
    for (const card of elements.technicalInspectionForm.querySelectorAll(".technical-inspection-item")) {
        const templateItemId = Number(card.dataset.itemId);
        const definition = templateItems.get(templateItemId) || {};
        const responseType = card.dataset.responseType;
        const status = card.querySelector(".technical-response")?.value || null;
        const valueText = card.querySelector(".technical-text")?.value.trim() || null;
        const numberRaw = card.querySelector(".technical-number")?.value;
        const observation = card.querySelector(".technical-observation")?.value.trim() || null;
        const evidenceFile = card.querySelector(".technical-evidence")?.files?.[0] || null;
        if (definition.required && responseType === "STATUS" && !status) throw new Error(`RESPONDA: ${definition.label}.`);
        if (definition.required && responseType === "TEXTO" && !valueText) throw new Error(`RESPONDA: ${definition.label}.`);
        if (definition.required && responseType === "NUMERO" && numberRaw === "") throw new Error(`INFORME O VALOR: ${definition.label}.`);
        if (status === "NC" && !observation) throw new Error(`INFORME A OBSERVAÇÃO: ${definition.label}.`);
        if (status === "NC" && definition.evidence_on_nc && !evidenceFile) throw new Error(`ANEXE A EVIDÊNCIA: ${definition.label}.`);
        items.push({
            template_item_id: templateItemId, item_label: definition.label,
            status, value_text: valueText,
            value_number: numberRaw === "" || numberRaw == null ? null : Number(numberRaw),
            observation, evidence_file: evidenceFile,
        });
    }
    return {
        id: createQueueId(), template_id: templateId, vehicle_id: vehicleId,
        vehicle: { frota: vehicle?.frota || vehicle?.placa || "EQUIPAMENTO" },
        template: { name: template?.name || "INSPEÇÃO TÉCNICA" },
        general_notes: elements.technicalInspectionGeneralNotes.value.trim(), items,
        queuedAt: new Date().toISOString(), status: "PENDENTE",
    };
}

async function sendTechnicalInspectionDraft(draft) {
    const items = [];
    for (const item of draft.items) {
        let evidencePath = item.evidence_path || null;
        if (item.evidence_file) {
            evidencePath = await uploadEvidence(
                item.evidence_file, draft.vehicle.frota, item.item_label,
                "inspecao_tecnica_nc", "INSPECOES_TECNICAS"
            );
        }
        const { evidence_file, item_label, ...payload } = item;
        items.push({ ...payload, evidence_path: evidencePath });
    }
    return apiFetch("/inspecoes-tecnicas/execucoes", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            template_id: draft.template_id, vehicle_id: draft.vehicle_id,
            general_notes: draft.general_notes, items,
        }),
    });
}

async function submitTechnicalInspection() {
    elements.technicalInspectionSubmit.disabled = true;
    try {
        const draft = await collectTechnicalInspectionDraft();
        if (!navigator.onLine) {
            await withOfflineStore(INSPECTION_QUEUE_STORE, "readwrite", (store) => store.put(draft));
            showToast("INSPEÇÃO SALVA NO APARELHO PARA SINCRONIZAR.");
            setActiveScreen("home");
            return;
        }
        await sendTechnicalInspectionDraft(draft);
        showToast("INSPEÇÃO TÉCNICA CONCLUÍDA.");
        setActiveScreen("home");
    } catch (error) {
        showToast(error.message, true);
    } finally {
        elements.technicalInspectionSubmit.disabled = false;
    }
}

async function syncPendingTechnicalInspections() {
    if (!state.token || !navigator.onLine) return;
    const queue = await withOfflineStore(INSPECTION_QUEUE_STORE, "readonly", (store) => new Promise((resolve, reject) => {
        const request = store.getAll(); request.onsuccess = () => resolve(request.result || []); request.onerror = () => reject(request.error);
    }));
    for (const draft of queue) {
        try {
            await sendTechnicalInspectionDraft(draft);
            await withOfflineStore(INSPECTION_QUEUE_STORE, "readwrite", (store) => store.delete(draft.id));
        } catch (error) {
            if (isOfflineError(error)) break;
        }
    }
}

async function loadNonConformityHubData() {
    const [macro, micro, checklistRows, mechanicRows, materials] = await Promise.all([
        apiFetch("/relatorios/macro"),
        apiFetch("/relatorios/micro"),
        apiFetch(`/nao_conformidades?status=${encodeURIComponent(state.ncChecklistStatus)}`),
        apiFetch(`/mecanico/nao_conformidades?status=${encodeURIComponent(state.ncMechanicStatus)}`),
        apiFetch("/materiais?ativos=true"),
    ]);
    state.nonConformityMacro = macro || [];
    state.nonConformityMicro = micro || [];
    state.nonConformityChecklist = checklistRows || [];
    state.nonConformityMechanic = mechanicRows || [];
    state.materials = materials || state.materials || [];
}

async function loadMaintenanceOverview() {
    const family = state.maintenanceFamilyFilter && state.maintenanceFamilyFilter !== "TODOS"
        ? `&familia=${encodeURIComponent(state.maintenanceFamilyFilter.toLowerCase())}`
        : "";
    state.maintenanceOverview = await apiFetch(`/manutencao/visao?ano=${state.maintenanceYear}&mes=${state.maintenanceMonth}${family}&excluir_checklist=true`);
}

function maintenanceOfflineCacheKey() {
    const family = String(state.maintenanceFamilyFilter || "TODOS").toUpperCase();
    return family === "TODOS" ? OFFLINE_MAINTENANCE_KEY : `${OFFLINE_MAINTENANCE_KEY}:${family.toLowerCase()}`;
}

async function loadChecklistHistory() {
    const params = new URLSearchParams();
    if (state.checklistHistory.dataInicio) {
        params.set("data_inicio", state.checklistHistory.dataInicio);
    }
    if (state.checklistHistory.dataFim) {
        params.set("data_fim", state.checklistHistory.dataFim);
    }

    const path = params.toString()
        ? `/checklist/historico-matriz?${params.toString()}`
        : "/checklist/historico-matriz";
    const data = await apiFetch(path);

    state.checklistHistory.columns = Array.isArray(data?.columns) ? data.columns : [];
    state.checklistHistory.rows = Array.isArray(data?.rows) ? data.rows : [];

    if (data?.periodo?.inicio) {
        state.checklistHistory.dataInicio = data.periodo.inicio;
    }
    if (data?.periodo?.fim) {
        state.checklistHistory.dataFim = data.periodo.fim;
    }

    renderChecklistHistory();
}

function normalizeHistorySearch(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toUpperCase();
}

function historyRowMatchesEquipmentSearch(row) {
    const search = normalizeHistorySearch(state.checklistHistory.equipmentSearch);
    if (!search) {
        return true;
    }
    const haystack = normalizeHistorySearch([
        row.frota,
        row.placa,
        row.modelo,
        row.descricao,
    ].join(" "));
    return haystack.includes(search);
}

function historyRowMatchesFamily(row) {
    const selectedFamily = normalizeText(state.checklistHistory.tipo).toUpperCase();
    const vehicle = state.vehicles.find((item) => Number(item.id) === Number(row.vehicle_id));
    const family = getVehicleFamilyKey(vehicle || { tipo: row.tipo });
    return Boolean(family) && (!selectedFamily || family === selectedFamily);
}

function compareChecklistHistoryRows(left, right) {
    const sortKey = state.checklistHistory.sortKey || "frota";
    const direction = state.checklistHistory.sortDirection === "desc" ? -1 : 1;

    if (sortKey === "count") {
        const leftValue = Number(left.checklist_count || 0);
        const rightValue = Number(right.checklist_count || 0);
        if (leftValue !== rightValue) {
            return (leftValue - rightValue) * direction;
        }
    } else if (sortKey.startsWith("date:")) {
        const columnIndex = Number(sortKey.split(":")[1]);
        const leftValue = normalizeHistorySearch((left.cells || [])[columnIndex] || "");
        const rightValue = normalizeHistorySearch((right.cells || [])[columnIndex] || "");
        const compare = leftValue.localeCompare(rightValue, "pt-BR", { numeric: true, sensitivity: "base" });
        if (compare !== 0) {
            return compare * direction;
        }
    } else {
        const leftValue = normalizeHistorySearch(left.frota || "");
        const rightValue = normalizeHistorySearch(right.frota || "");
        const compare = leftValue.localeCompare(rightValue, "pt-BR", { numeric: true, sensitivity: "base" });
        if (compare !== 0) {
            return compare * direction;
        }
    }

    return normalizeHistorySearch(left.frota || "").localeCompare(
        normalizeHistorySearch(right.frota || ""),
        "pt-BR",
        { numeric: true, sensitivity: "base" }
    );
}

function getVisibleChecklistHistoryRows() {
    return [...(state.checklistHistory.rows || [])]
        .filter(historyRowMatchesEquipmentSearch)
        .filter(historyRowMatchesFamily)
        .sort(compareChecklistHistoryRows);
}

function makeChecklistHistorySortHeader(label, sortKey, extraClass = "") {
    const isActive = state.checklistHistory.sortKey === sortKey;
    const direction = isActive ? state.checklistHistory.sortDirection : "";
    const indicator = direction === "asc" ? "▲" : direction === "desc" ? "▼" : "";
    return `
        <th class="${extraClass} history-sort-header ${isActive ? "active" : ""}" data-history-sort="${escapeHtml(sortKey)}">
            <button type="button">
                <span>${escapeHtml(label)}</span>
                <em>${indicator}</em>
            </button>
        </th>
    `;
}

function renderChecklistHistory() {
    if (!elements.checklistHistoryTableWrap || !elements.checklistHistoryCounter) {
        return;
    }

    const columns = state.checklistHistory.columns || [];
    const rows = getVisibleChecklistHistoryRows();

    elements.checklistHistoryCounter.textContent = `${rows.length} FROTAS`;
    if (elements.checklistHistoryEquipmentSearch) {
        elements.checklistHistoryEquipmentSearch.value = state.checklistHistory.equipmentSearch || "";
    }
    if (elements.checklistHistoryStartDate) {
        elements.checklistHistoryStartDate.value = state.checklistHistory.dataInicio || "";
    }
    if (elements.checklistHistoryEndDate) {
        elements.checklistHistoryEndDate.value = state.checklistHistory.dataFim || "";
    }
    if (elements.checklistHistoryTypeFilter) {
        elements.checklistHistoryTypeFilter.value = state.checklistHistory.tipo || "";
    }

    if (!columns.length) {
        if (elements.checklistHistorySummaryCard) {
            elements.checklistHistorySummaryCard.innerHTML = "";
        }
        elements.checklistHistoryTableWrap.innerHTML = `
            <article class="empty-state">
                <strong>SEM DATAS PARA O PERÍODO SELECIONADO.</strong>
                <span>AJUSTE O FILTRO DE DATA PARA VISUALIZAR O HISTÓRICO.</span>
            </article>
        `;
        return;
    }

    if (!rows.length) {
        if (elements.checklistHistorySummaryCard) {
            elements.checklistHistorySummaryCard.innerHTML = "";
        }
        elements.checklistHistoryTableWrap.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA FROTA ENCONTRADA NESTE FILTRO.</strong>
                <span>AJUSTE O MÓDULO OU O PERÍODO.</span>
            </article>
        `;
        return;
    }

    const totalChecklists = rows.reduce((total, row) => total + Number(row.checklist_count || 0), 0);
    const periodLabel = state.checklistHistory.dataInicio && state.checklistHistory.dataFim
        ? `${formatDate(state.checklistHistory.dataInicio)} A ${formatDate(state.checklistHistory.dataFim)}`
        : "PERÍODO NÃO INFORMADO";

    const headerColumns = columns
        .map((column, index) => makeChecklistHistorySortHeader(String(column.label || "-"), `date:${index}`))
        .join("");
    const bodyRows = rows
        .map((row) => {
            const cellValues = (row.cells || [])
                .map((value) => `<td>${value ? escapeHtml(String(value)) : ""}</td>`)
                .join("");
            const checklistCount = Number(row.checklist_count || 0);
            const vehicleId = String(row.vehicle_id || "");
            const isExpanded = vehicleId && vehicleId === String(state.checklistHistory.expandedVehicleId || "");
            return `
                <tr class="${isExpanded ? "history-row-selected" : ""}">
                    <th class="history-vehicle-cell" data-vehicle-id="${escapeHtml(vehicleId)}" title="Toque para expandir/recolher">
                        <strong>${escapeHtml(String(row.frota || "-"))}</strong>
                        <span>${escapeHtml(String(row.placa || "-").toUpperCase())}</span>
                        ${row.modelo || row.descricao ? `<small>${escapeHtml(String(row.modelo || row.descricao || "-").toUpperCase())}</small>` : ""}
                    </th>
                    <td class="history-count-cell">${checklistCount}</td>
                    ${cellValues}
                </tr>
            `;
        })
        .join("");

    elements.checklistHistoryTableWrap.classList.toggle("history-expanded", Boolean(state.checklistHistory.expandedVehicleId));
    if (elements.checklistHistorySummaryCard) {
        elements.checklistHistorySummaryCard.innerHTML = `
        <section class="history-summary">
            <article>
                <span>PERIODO</span>
                <strong>${escapeHtml(periodLabel)}</strong>
            </article>
            <article>
                <span>DATAS NA MATRIZ</span>
                <strong>${columns.length} DIA${columns.length === 1 ? "" : "S"}</strong>
            </article>
            <article>
                <span>CHECKLISTS NO FILTRO</span>
                <strong>${totalChecklists} REGISTRO${totalChecklists === 1 ? "" : "S"}</strong>
            </article>
        </section>
        <p class="history-caption">Toque na frota para expandir a leitura da linha e acompanhe o total pelo campo Nº.</p>
        `;
    }
    elements.checklistHistoryTableWrap.innerHTML = `
        <table class="history-table">
            <thead>
                <tr>
                    ${makeChecklistHistorySortHeader("FROTA", "frota", "history-frota-header")}
                    ${makeChecklistHistorySortHeader("Nº", "count", "history-count-header")}
                    ${headerColumns}
                </tr>
            </thead>
            <tbody>
                ${bodyRows}
            </tbody>
        </table>
    `;
    bindChecklistHistoryExpansion();
    bindChecklistHistorySorting();
}

function bindChecklistHistoryExpansion() {
    elements.checklistHistoryTableWrap.querySelectorAll(".history-vehicle-cell").forEach((cell) => {
        cell.addEventListener("click", () => {
            const vehicleId = String(cell.dataset.vehicleId || "");
            const nextVehicleId = state.checklistHistory.expandedVehicleId === vehicleId ? "" : vehicleId;
            state.checklistHistory.expandedVehicleId = nextVehicleId;
            elements.checklistHistoryTableWrap.classList.toggle("history-expanded", Boolean(nextVehicleId));
            elements.checklistHistoryTableWrap.querySelectorAll("tbody tr").forEach((row) => {
                row.classList.remove("history-row-selected");
            });
            if (nextVehicleId) {
                cell.closest("tr")?.classList.add("history-row-selected");
            }
        });
    });
}

function bindChecklistHistorySorting() {
    elements.checklistHistoryTableWrap.querySelectorAll("[data-history-sort]").forEach((header) => {
        header.addEventListener("click", () => {
            const sortKey = String(header.dataset.historySort || "frota");
            if (state.checklistHistory.sortKey === sortKey) {
                state.checklistHistory.sortDirection = state.checklistHistory.sortDirection === "asc" ? "desc" : "asc";
            } else {
                state.checklistHistory.sortKey = sortKey;
                state.checklistHistory.sortDirection = "asc";
            }
            state.checklistHistory.expandedVehicleId = "";
            renderChecklistHistory();
        });
    });
}

async function applyChecklistHistoryFilters() {
    const type = elements.checklistHistoryTypeFilter?.value || "";
    const startDate = elements.checklistHistoryStartDate?.value || "";
    const endDate = elements.checklistHistoryEndDate?.value || "";

    if (startDate && endDate && endDate < startDate) {
        showToast("A DATA FINAL DEVE SER MAIOR OU IGUAL À DATA INICIAL.", true);
        return;
    }

    state.checklistHistory.tipo = type;
    state.checklistHistory.dataInicio = startDate;
    state.checklistHistory.dataFim = endDate;

    try {
        await loadChecklistHistory();
    } catch (error) {
        showToast(error.message, true);
    }
}

function scheduleChecklistHistoryFilters() {
    if (checklistHistoryFilterTimer) {
        window.clearTimeout(checklistHistoryFilterTimer);
    }
    checklistHistoryFilterTimer = window.setTimeout(() => {
        applyChecklistHistoryFilters();
    }, 350);
}

function updateChecklistHistoryEquipmentSearch() {
    state.checklistHistory.equipmentSearch = elements.checklistHistoryEquipmentSearch?.value || "";
    state.checklistHistory.expandedVehicleId = "";
    renderChecklistHistory();
}

function renderNonConformities() {
    if (!elements.nonConformitiesSummary) {
        return;
    }
    const detailMode = Boolean(state.selectedNonConformityItem);
    const checklistOpen = state.nonConformityMacro.reduce((total, row) => total + Number(row.abertas || 0), 0);
    const checklistResolved = state.nonConformityMacro.reduce((total, row) => total + Number(row.resolvidas || 0), 0);
    const mechanicOpen = state.nonConformityMechanic.filter((row) => !row.resolvido).length;
    const mechanicResolved = state.nonConformityMechanic.filter((row) => row.resolvido).length;
    const openTotal = checklistOpen + mechanicOpen;
    const resolvedTotal = checklistResolved + mechanicResolved;
    const overallTotal = openTotal + resolvedTotal;
    const resolvedPercent = overallTotal ? Math.round((resolvedTotal / overallTotal) * 100) : 0;

    elements.nonConformitiesSummary.innerHTML = `
        <div>
            <strong>${checklistOpen} ABERTAS DE CHECKLIST</strong>
            <span>${checklistResolved} RESOLVIDAS</span>
        </div>
        <div>
            <strong>${mechanicOpen} INTERNAS ABERTAS</strong>
            <span>${mechanicResolved} RESOLVIDAS</span>
        </div>
        <div>
            <strong>${openTotal} PENDENCIAS ATIVAS</strong>
            <span>${resolvedTotal} CONCLUIDAS NO PAINEL</span>
        </div>
        <div>
            <strong>${resolvedPercent}% DE RESOLUCAO</strong>
            <span>${state.nonConformityChecklist.length + state.nonConformityMechanic.length} REGISTROS NO FILTRO</span>
        </div>
        <div class="progress-track" aria-hidden="true">
            <span style="width:${Math.min(100, Math.max(0, resolvedPercent))}%"></span>
        </div>
        <span class="progress-hint">Priorize os blocos macro e micro para localizar reincidencia antes de abrir cada registro.</span>
    `;

    screens.nonConformities?.classList.toggle("nc-detail-mode", detailMode);
    if (elements.nonConformitiesBackButton) {
        elements.nonConformitiesBackButton.textContent = detailMode ? "VOLTAR" : "MENU";
    }
    elements.nonConformitiesSummary.classList.toggle("hidden", detailMode);
    elements.nonConformitiesTotalToolbar?.classList.toggle("hidden", detailMode);
    elements.nonConformitiesFilterSection?.classList.toggle("hidden", detailMode);
    elements.nonConformitiesMechanicSection?.classList.toggle("hidden", detailMode);

    elements.nonConformitiesCounter.textContent = `${openTotal} ABERTAS`;
    elements.nonConformitiesMacroCounter.textContent = `${state.nonConformityMacro.length} ITENS`;
    elements.nonConformitiesChecklistCounter.textContent = `${filterChecklistNonConformitiesBySelectedItem(state.nonConformityChecklist).length} REGISTROS`;
    elements.nonConformitiesMechanicCounter.textContent = `${state.nonConformityMechanic.length} REGISTROS`;

    elements.ncChecklistFilterOpen?.classList.toggle("active", state.ncChecklistStatus === "abertas");
    elements.ncChecklistFilterClosed?.classList.toggle("active", state.ncChecklistStatus === "resolvidas");
    elements.ncMechanicFilterOpen?.classList.toggle("active", state.ncMechanicStatus === "abertas");
    elements.ncMechanicFilterClosed?.classList.toggle("active", state.ncMechanicStatus === "resolvidas");

    renderNonConformityReports();
    renderChecklistNonConformities();
    renderMechanicNonConformities();
}

function renderNonConformityReports() {
    const macroRows = state.nonConformityMacro || [];
    const selectedItem = state.selectedNonConformityItem;

    elements.nonConformitiesMicroList.innerHTML = "";

    if (!macroRows.length) {
        elements.nonConformitiesMacroList.innerHTML = `
            <article class="empty-state compact">
                <strong>SEM NÃO CONFORMIDADES NO FILTRO.</strong>
                <span>AS NÃO CONFORMIDADES DO CHECKLIST APARECERÃO AQUI.</span>
            </article>
        `;
    } else {
        elements.nonConformitiesMacroList.innerHTML = `
            <article class="list-toolbar">
                <strong>TIPOS DE NÃO CONFORMIDADE</strong>
                <span>TOQUE PARA ABRIR</span>
            </article>
            <div class="nc-grid">
                ${macroRows.map((row) => `
                    <article class="nc-report-row ${selectedItem === row.item_nome ? "is-selected" : ""}" data-nc-filter-item="${escapeHtml(row.item_nome || "")}">
                        <div>
                            <strong>${escapeHtml(String(row.item_nome || "-").toUpperCase())}</strong>
                            <span>${Number(row.abertas || 0)} ABERTAS | ${Number(row.resolvidas || 0)} RESOLVIDAS</span>
                        </div>
                        <em>${Number(row.total_nc || 0)} NÃO CONFORMIDADES</em>
                        ${selectedItem === row.item_nome ? `
                            <div class="nc-report-filter">
                                <span>FILTRO APLICADO NESTE TIPO DE NÃO CONFORMIDADE.</span>
                                <button type="button" class="nc-report-action" data-nc-clear-filter="true">LIMPAR</button>
                            </div>
                        ` : ""}
                    </article>
                `).join("")}
            </div>
        `;
        elements.nonConformitiesMacroList.querySelectorAll("[data-nc-filter-item]").forEach((rowElement) => {
            rowElement.addEventListener("click", (event) => {
                if (event.target instanceof HTMLElement && event.target.closest("[data-nc-clear-filter]")) {
                    state.selectedNonConformityItem = "";
                } else {
                    state.selectedNonConformityItem = rowElement.dataset.ncFilterItem || "";
                }
                renderNonConformities();
            });
        });
    }
}

function renderChecklistNonConformities() {
    if (!state.selectedNonConformityItem) {
        elements.nonConformitiesChecklistList.innerHTML = `
            <article class="empty-state compact">
                <strong>SELECIONE UMA NÃO CONFORMIDADE ACIMA.</strong>
                <span>TOQUE EM UM TIPO PARA ABRIR A TELA PRÓPRIA COM OS REGISTROS.</span>
            </article>
        `;
        return;
    }
    const rows = filterChecklistNonConformitiesBySelectedItem(state.nonConformityChecklist || []);
    elements.nonConformitiesChecklistList.innerHTML = "";

    if (!rows.length) {
        elements.nonConformitiesChecklistList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA NÃO CONFORMIDADE DE CHECKLIST NESTE FILTRO.</strong>
                <span>ALTERE O STATUS OU AGUARDE NOVOS REGISTROS.</span>
            </article>
        `;
        return;
    }

    if (state.selectedNonConformityItem) {
        elements.nonConformitiesChecklistList.innerHTML = `
            <article class="nc-section-filter">
                <div>
                    <span>NÃO CONFORMIDADE</span>
                    <strong>${escapeHtml(String(state.selectedNonConformityItem).toUpperCase())}</strong>
                </div>
                <button type="button" data-nc-clear-filter="true">VOLTAR</button>
            </article>
        `;
        elements.nonConformitiesChecklistList.querySelector("[data-nc-clear-filter]")?.addEventListener("click", () => {
            state.selectedNonConformityItem = "";
            renderNonConformities();
        });
    }

    rows.forEach((row, index) => {
        elements.nonConformitiesChecklistList.appendChild(makeChecklistNonConformityCard(row, index + 1));
    });
}

function filterChecklistNonConformitiesBySelectedItem(rows) {
    const selected = normalizeText(state.selectedNonConformityItem || "");
    if (!selected) {
        return rows;
    }
    return rows.filter((row) => {
        const principal = normalizeText(row.item_principal || "");
        const itemName = normalizeText(row.item_nome || "");
        const labelBase = normalizeText(String(row.item_label || "").split(" - ")[0] || "");
        return [principal, itemName, labelBase].includes(selected);
    });
}

function renderMechanicNonConformities() {
    const rows = state.nonConformityMechanic || [];
    elements.nonConformitiesMechanicList.innerHTML = "";

    if (!rows.length) {
        elements.nonConformitiesMechanicList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA NÃO CONFORMIDADE INTERNA NESTE FILTRO.</strong>
                <span>ABRA UMA NOVA NÃO CONFORMIDADE INTERNA NO FORMULÁRIO ACIMA.</span>
            </article>
        `;
        return;
    }

    rows.forEach((row, index) => {
        elements.nonConformitiesMechanicList.appendChild(makeMechanicNonConformityCard(row, index + 1));
    });
}

function renderMaintenance() {
    if (!elements.maintenanceList || !elements.maintenanceCounter) {
        return;
    }

    const overview = state.maintenanceOverview || { resumo: {}, cronograma: { days: [] }, programacoes: [] };
    const resumo = overview.resumo || {};
    const days = maintenanceOverviewDays(overview);
    const selectedDay = ensureSelectedMaintenanceDate(days);
    const selectedItems = filterMaintenanceItemsForMobile(selectedDay?.items || []);
    const selectedDayLabel = selectedDay?.date ? formatDate(selectedDay.date) : "SEM DIA";
    const familyLabel = state.maintenanceFamilyFilter === "TODOS" ? "RTG E LBS" : state.maintenanceFamilyFilter;
    const familyItems = filterMaintenanceItemsByFamily(days.flatMap((day) => day.items || []));
    const visibleSummary = buildMaintenanceFamilySummary(resumo, familyItems);

    updateMaintenanceFamilyTabs();
    elements.maintenanceCounter.textContent = `${Number(visibleSummary.programados || visibleSummary.itens || 0)} PROGRAMADOS · ${familyLabel}`;
    elements.maintenanceMonthTitle.textContent = String(overview.periodo?.rotulo || `${state.maintenanceMonth}/${state.maintenanceYear}`).toUpperCase();
    screens.maintenance.querySelector(".list-toolbar span").textContent = `${familyLabel} | ${selectedDayLabel} | ${selectedItems.length} SERVIÇO${selectedItems.length === 1 ? "" : "S"} NO DIA SELECIONADO.`;
    renderMaintenanceSummary(visibleSummary);
    renderMaintenanceDashboard(days);
    renderMaintenanceCalendar(days);
    renderMaintenanceDayPanel(selectedDay);
    elements.maintenanceList.innerHTML = "";

    if (!selectedItems.length) {
        elements.maintenanceList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA MANUTENÇÃO PROGRAMADA PARA ESTE DIA.</strong>
                <span>AGUARDE NOVA PROGRAMACAO ENVIADA PELO DESKTOP.</span>
            </article>
        `;
        return;
    }

    selectedItems.forEach((item, index) => {
        elements.maintenanceList.appendChild(makeMaintenanceItemCard(item, index + 1));
    });
}

function maintenanceOverviewDays(overview = state.maintenanceOverview) {
    return (overview?.cronograma?.days || []).map((day) => ({
        ...day,
        items: (day.items || []).filter((item) => String(item.schedule?.source_type || item.source_type || "").toUpperCase() !== "CHECKLIST_NC"),
    }));
}

function renderPlanning() {
    if (!elements.planningList || !elements.planningCounter) return;
    const overview = state.maintenanceOverview || { resumo: {}, cronograma: { days: [] } };
    const items = maintenanceOverviewDays(overview).flatMap((day) => (day.items || []).map((item) => ({
        ...item,
        planning_date: item.scheduled_date || day.date,
    })));
    const filter = state.planningStatusFilter || "ABERTAS";
    const visibleItems = items.filter((item) => {
        const stage = maintenanceKanbanStage(item);
        if (filter === "BLOQUEADAS") return stage === "BLOQUEADO";
        if (filter === "CONCLUIDAS") return stage === "CONCLUIDO";
        if (filter === "ABERTAS") return stage !== "CONCLUIDO" && String(item.status || "").toUpperCase() !== "CANCELADO";
        return true;
    });
    const openCount = items.filter((item) => maintenanceKanbanStage(item) !== "CONCLUIDO").length;
    const blockedCount = items.filter((item) => maintenanceKanbanStage(item) === "BLOQUEADO").length;
    const completedCount = items.filter((item) => maintenanceKanbanStage(item) === "CONCLUIDO").length;
    elements.planningCounter.textContent = `${visibleItems.length} ITEM${visibleItems.length === 1 ? "" : "S"} NO BACKLOG`;
    elements.planningPeriodLabel.textContent = "SOMENTE PROGRAMAÇÕES DE MANUTENÇÃO · CHECKLIST SEPARADO";
    elements.planningMonthTitle.textContent = String(overview.periodo?.rotulo || `${state.maintenanceMonth}/${state.maintenanceYear}`).toUpperCase();
    elements.planningSummary.innerHTML = `
        <div><strong>${openCount} ABERTAS</strong><span>Itens disponíveis para organização.</span></div>
        <div><strong>${blockedCount} BLOQUEADAS</strong><span>Aguardando material ou condição.</span></div>
        <div><strong>${completedCount} CONCLUÍDAS</strong><span>Execuções registradas.</span></div>
        <span class="progress-hint">A área operacional executa no Kanban. Aqui, a gestão organiza datas e prioridades.</span>
    `;
    elements.planningFilterButtons?.forEach((button) => {
        const active = String(button.dataset.planningFilter || "") === filter;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
    });
    elements.planningList.innerHTML = "";
    if (!visibleItems.length) {
        elements.planningList.innerHTML = `<article class="empty-state"><strong>NENHUM ITEM NESTE FILTRO.</strong><span>As ocorrências de Checklist ficam no módulo próprio.</span></article>`;
        return;
    }
    visibleItems.forEach((item, index) => {
        const vehicle = item.vehicle || {};
        const schedule = item.schedule || {};
        const workOrder = item.work_order || {};
        const stage = maintenanceKanbanStage(item);
        const card = document.createElement("article");
        card.className = "planning-item-card";
        card.innerHTML = `
            <div class="item-topline"><span>${String(index + 1).padStart(2, "0")}</span><h3>${escapeHtml(String(schedule.title || item.item_name || "PROGRAMAÇÃO").toUpperCase())}</h3></div>
            <div class="planning-item-grid">
                <span><strong>EQUIPAMENTO</strong>${escapeHtml(String(vehicle.frota || vehicle.placa || "-").toUpperCase())} · ${escapeHtml(maintenanceFamilyKey(item) || "MÓDULO")}</span>
                <span><strong>OS</strong>${escapeHtml(String(workOrder.order_number || "-").toUpperCase())}</span>
                <span><strong>ETAPA</strong>${escapeHtml(stage.replaceAll("_", " "))}</span>
                <span><strong>RESPONSÁVEL</strong>${escapeHtml(String(schedule.assigned_mechanic?.nome || item.assigned_mechanic?.nome || "SEM RESPONSÁVEL").toUpperCase())}</span>
            </div>
            ${stage !== "CONCLUIDO" ? `<div class="planning-reprogram-row"><label><span>NOVA DATA</span><input type="date" class="maintenance-reprogram-date" value="${escapeHtml(item.planning_date || "")}"></label><button type="button" class="secondary-button maintenance-reprogram-button">REPROGRAMAR ITEM</button></div>` : `<span class="nc-resolved-flag">CONCLUÍDO</span>`}
        `;
        card.querySelector(".maintenance-reprogram-button")?.addEventListener("click", () => reprogramMaintenanceItem(card, item));
        elements.planningList.appendChild(card);
    });
}

function maintenanceKanbanStage(item) {
    const itemStatus = String(item?.status || "PENDENTE").toUpperCase();
    const scheduleStatus = String(item?.schedule?.status || "").toUpperCase();
    if (itemStatus === "INSTALADO") return "CONCLUIDO";
    if (itemStatus === "AGUARDANDO_MATERIAL" || scheduleStatus === "AGUARDANDO_MATERIAL" || !maintenanceItemCanInstall(item)) return "BLOQUEADO";
    if (scheduleStatus === "EM_EXECUCAO") return "EM_EXECUCAO";
    if (["PROGRAMADO", "REPROGRAMADO"].includes(itemStatus) || ["PROGRAMADA", "REPROGRAMADA"].includes(scheduleStatus)) return "PROGRAMADO";
    return "PLANEJADO";
}

function maintenanceDashboardStatus(item) {
    const stage = maintenanceKanbanStage(item);
    const scheduledDate = String(item?.kanban_date || item?.scheduled_date || "");
    if (stage !== "CONCLUIDO" && stage !== "BLOQUEADO" && scheduledDate && scheduledDate < getManausDateKey()) {
        return "ATRASADO";
    }
    return stage;
}

function maintenanceDashboardStatusMeta(status) {
    const items = {
        PLANEJADO: { label: "PLANEJADO", tone: "planned" },
        PROGRAMADO: { label: "PROGRAMADO", tone: "scheduled" },
        EM_EXECUCAO: { label: "EM EXECUÇÃO", tone: "progress" },
        BLOQUEADO: { label: "BLOQUEADO", tone: "blocked" },
        ATRASADO: { label: "ATRASADO", tone: "overdue" },
        CONCLUIDO: { label: "CONCLUÍDO", tone: "completed" },
    };
    return items[status] || items.PLANEJADO;
}

function maintenanceDashboardItems(days) {
    const filter = state.maintenanceDashboardFilter || "TODOS";
    const stageOrder = { ATRASADO: 0, BLOQUEADO: 1, EM_EXECUCAO: 2, PROGRAMADO: 3, PLANEJADO: 4, CONCLUIDO: 5 };
    const items = filterMaintenanceItemsByFamily(days.flatMap((day) => (day.items || []).map((item) => ({
        ...item,
        kanban_date: item.scheduled_date || day.date,
    }))));
    return items
        .filter((item) => filter === "TODOS" || maintenanceDashboardStatus(item) === filter)
        .sort((left, right) => {
            const toneDifference = (stageOrder[maintenanceDashboardStatus(left)] || 9) - (stageOrder[maintenanceDashboardStatus(right)] || 9);
            if (toneDifference) return toneDifference;
            return String(left.kanban_date || "9999-12-31").localeCompare(String(right.kanban_date || "9999-12-31"));
        });
}

function maintenanceDashboardCounts(days) {
    const allItems = filterMaintenanceItemsByFamily(days.flatMap((day) => (day.items || []).map((item) => ({
        ...item,
        kanban_date: item.scheduled_date || day.date,
    }))));
    return allItems.reduce((counts, item) => {
        counts.TODOS += 1;
        const status = maintenanceDashboardStatus(item);
        counts[status] = (counts[status] || 0) + 1;
        return counts;
    }, { TODOS: 0, PLANEJADO: 0, PROGRAMADO: 0, EM_EXECUCAO: 0, BLOQUEADO: 0, ATRASADO: 0, CONCLUIDO: 0 });
}

function renderMaintenanceDashboard(days) {
    const view = state.maintenanceDashboardView || "KANBAN";
    const items = maintenanceDashboardItems(days);
    const counts = maintenanceDashboardCounts(days);
    elements.maintenanceViewButtons.forEach((button) => {
        const active = button.dataset.maintenanceView === view;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
    });
    elements.maintenanceDashboardFilterButtons.forEach((button) => {
        const filter = button.dataset.maintenanceDashboardFilter || "TODOS";
        const active = filter === state.maintenanceDashboardFilter;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        const count = button.querySelector("b");
        if (count) count.textContent = String(counts[filter] || 0);
    });
    elements.maintenanceKanban?.classList.toggle("hidden", view !== "KANBAN");
    elements.maintenanceTableWrap?.classList.toggle("hidden", view !== "TABLE");
    elements.maintenanceCards?.classList.toggle("hidden", view !== "CARDS");
    renderMaintenanceKanban(items);
    renderMaintenanceTable(items);
    renderMaintenanceCards(items);
}

function maintenanceDashboardAction(item) {
    if (maintenanceKanbanStage(item) === "CONCLUIDO") return "";
    return `<button type="button" class="secondary-button maintenance-dashboard-open" data-maintenance-date="${escapeHtml(item.kanban_date || "")}" data-maintenance-filter="${maintenanceKanbanStage(item) === "BLOQUEADO" ? "AGUARDANDO_MATERIAL" : "ABERTAS"}">ABRIR</button>`;
}

function bindMaintenanceDashboardActions(container) {
    container?.querySelectorAll(".maintenance-dashboard-open").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedMaintenanceDate = button.dataset.maintenanceDate || "";
            state.maintenanceStatusFilter = button.dataset.maintenanceFilter || "ABERTAS";
            renderMaintenance();
            elements.maintenanceList?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });
}

function renderMaintenanceKanban(items) {
    if (!elements.maintenanceKanban) return;
    const columns = [
        { key: "PLANEJADO", label: "PLANEJADO", hint: "Ainda precisa ser organizado." },
        { key: "PROGRAMADO", label: "PROGRAMADO", hint: "Já tem data para execução." },
        { key: "EM_EXECUCAO", label: "EM EXECUÇÃO", hint: "A equipe já iniciou." },
        { key: "BLOQUEADO", label: "BLOQUEADO", hint: "Material ou condição impede a execução." },
        { key: "CONCLUIDO", label: "CONCLUÍDO", hint: "Execução registrada." },
    ];
    const grouped = new Map(columns.map((column) => [column.key, []]));
    items.forEach((item) => grouped.get(maintenanceKanbanStage(item))?.push(item));
    elements.maintenanceKanban.innerHTML = columns.map((column) => {
        const rows = grouped.get(column.key) || [];
        return `
            <section class="maintenance-kanban-column maintenance-kanban-${column.key.toLowerCase().replaceAll("_", "-")}" data-kanban-column="${column.key}">
                <header><div><strong>${column.label}</strong><span>${column.hint}</span></div><b>${rows.length}</b></header>
                <div class="maintenance-kanban-items">
                    ${rows.length ? rows.map((item) => {
                        const vehicle = item.vehicle || {};
                        const schedule = item.schedule || {};
                        const workOrder = item.work_order || {};
                        const title = schedule.title || item.item_name || "MANUTENÇÃO";
                        const status = maintenanceDashboardStatusMeta(maintenanceDashboardStatus(item));
                        const date = item.kanban_date ? formatDateTime(`${item.kanban_date}T00:00:00`) : "SEM DATA";
                        const open = column.key !== "CONCLUIDO";
                        return `<article class="maintenance-kanban-card maintenance-status-${status.tone}">
                            <strong>${escapeHtml(String(title).toUpperCase())}</strong>
                            <span>${escapeHtml(String(vehicle.frota || vehicle.placa || "EQUIPAMENTO").toUpperCase())} · ${escapeHtml(maintenanceFamilyKey(item) || "MÓDULO")}</span>
                            <span>OS ${escapeHtml(String(workOrder.order_number || "-").toUpperCase())} · ${escapeHtml(status.label)}</span>
                            <small>${escapeHtml(date)}</small>
                            ${open ? maintenanceDashboardAction(item) : ""}
                        </article>`;
                    }).join("") : `<p class="maintenance-kanban-empty">NENHUM SERVIÇO NESTA ETAPA.</p>`}
                </div>
            </section>
        `;
    }).join("");
    bindMaintenanceDashboardActions(elements.maintenanceKanban);
}

function renderMaintenanceTable(items) {
    if (!elements.maintenanceTableBody) return;
    if (!items.length) {
        elements.maintenanceTableBody.innerHTML = `<tr><td colspan="8" class="maintenance-dashboard-empty">NENHUMA MANUTENÇÃO NESTE FILTRO.</td></tr>`;
        return;
    }
    elements.maintenanceTableBody.innerHTML = items.map((item) => {
        const vehicle = item.vehicle || {};
        const schedule = item.schedule || {};
        const workOrder = item.work_order || {};
        const mechanic = item.assigned_mechanic || schedule.assigned_mechanic || {};
        const status = maintenanceDashboardStatusMeta(maintenanceDashboardStatus(item));
        return `<tr class="maintenance-status-${status.tone}">
            <td><strong>${escapeHtml(String(workOrder.order_number || "-").toUpperCase())}</strong></td>
            <td><strong>${escapeHtml(String(schedule.title || item.item_name || "MANUTENÇÃO").toUpperCase())}</strong></td>
            <td>${escapeHtml(String(vehicle.frota || vehicle.placa || "EQUIPAMENTO").toUpperCase())}</td>
            <td>${escapeHtml(maintenanceFamilyKey(item) || "-")}</td>
            <td>${escapeHtml(String(mechanic.nome || "SEM RESPONSÁVEL").toUpperCase())}</td>
            <td>${item.kanban_date ? formatDate(item.kanban_date) : "SEM DATA"}</td>
            <td><span class="maintenance-status-pill maintenance-status-${status.tone}">${status.label}</span></td>
            <td>${maintenanceDashboardAction(item) || "-"}</td>
        </tr>`;
    }).join("");
    bindMaintenanceDashboardActions(elements.maintenanceTableBody);
}

function renderMaintenanceCards(items) {
    if (!elements.maintenanceCards) return;
    if (!items.length) {
        elements.maintenanceCards.innerHTML = `<article class="maintenance-dashboard-empty">NENHUMA MANUTENÇÃO NESTE FILTRO.</article>`;
        return;
    }
    elements.maintenanceCards.innerHTML = items.map((item) => {
        const vehicle = item.vehicle || {};
        const schedule = item.schedule || {};
        const workOrder = item.work_order || {};
        const mechanic = item.assigned_mechanic || schedule.assigned_mechanic || {};
        const status = maintenanceDashboardStatusMeta(maintenanceDashboardStatus(item));
        return `<article class="maintenance-dashboard-card maintenance-status-${status.tone}">
            <div><strong>OS ${escapeHtml(String(workOrder.order_number || "-").toUpperCase())}</strong><span class="maintenance-status-pill maintenance-status-${status.tone}">${status.label}</span></div>
            <h3>${escapeHtml(String(schedule.title || item.item_name || "MANUTENÇÃO").toUpperCase())}</h3>
            <p><b>EQUIPAMENTO</b>${escapeHtml(String(vehicle.frota || vehicle.placa || "EQUIPAMENTO").toUpperCase())} · ${escapeHtml(maintenanceFamilyKey(item) || "MÓDULO")}</p>
            <p><b>RESPONSÁVEL</b>${escapeHtml(String(mechanic.nome || "SEM RESPONSÁVEL").toUpperCase())}</p>
            <p><b>DATA</b>${item.kanban_date ? formatDate(item.kanban_date) : "SEM DATA"}</p>
            ${maintenanceDashboardAction(item)}
        </article>`;
    }).join("");
    bindMaintenanceDashboardActions(elements.maintenanceCards);
}

function updateMaintenanceFamilyTabs() {
    elements.maintenanceFamilyTabs?.forEach((button) => {
        const active = String(button.dataset.maintenanceFamily || "TODOS").toUpperCase() === state.maintenanceFamilyFilter;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
    });
}

function maintenanceFamilyKey(item) {
    const vehicle = item?.vehicle || {};
    const family = getVehicleFamilyKey({
        ...vehicle,
        family_name: vehicle.family_name || item?.family_name || item?.familia_veiculo,
        tipo: vehicle.tipo || item?.tipo || item?.family_code,
    });
    if (family) return family;
    const raw = normalizeText(vehicle.family?.code || vehicle.family?.name || item?.family_code || item?.family_name || item?.familia_veiculo);
    if (raw.includes("rtg")) return "RTG";
    if (raw.includes("lbs")) return "LBS";
    return "";
}

function filterMaintenanceItemsByFamily(items) {
    const family = String(state.maintenanceFamilyFilter || "TODOS").toUpperCase();
    if (family === "TODOS") return items;
    return items.filter((item) => maintenanceFamilyKey(item) === family);
}

function buildMaintenanceFamilySummary(resumo, familyItems) {
    if (state.maintenanceFamilyFilter === "TODOS") return resumo;
    const openStatuses = new Set(["PENDENTE", "PROGRAMADO", "REPROGRAMADO"]);
    const pending = familyItems.filter((item) => openStatuses.has(String(item.status || "").toUpperCase())).length;
    const installed = familyItems.filter((item) => String(item.status || "").toUpperCase() === "INSTALADO").length;
    const notExecuted = familyItems.filter((item) => String(item.status || "").toUpperCase() === "NAO_EXECUTADO").length;
    const blocked = familyItems.filter((item) => String(item.status || "").toUpperCase() === "AGUARDANDO_MATERIAL").length;
    const total = familyItems.length;
    return {
        ...resumo,
        itens: total,
        programados: total,
        pendentes: pending,
        instalados: installed,
        nao_executados: notExecuted,
        aguardando_material: blocked,
        percentual_conclusao: total ? Math.round((installed / total) * 100) : 0,
    };
}

function renderMaintenanceSummary(resumo) {
    if (!elements.maintenanceSummary) {
        return;
    }
    const percent = Number(resumo.percentual_conclusao || 0);
    const openOrders = Number(resumo.os_abertas || 0);
    const overdueOrders = Number(resumo.os_atrasadas || 0);
    const blockedOrders = Number(resumo.os_bloqueadas || 0);
    const completedOrders = Number(resumo.os_concluidas || 0);
    const totalBlockers = Number((state.maintenanceOverview?.bloqueios || []).length || 0);
    const oldestOpenOrders = state.maintenanceOverview?.backlog_prioritario?.os_mais_antigas || [];
    elements.maintenanceSummary.innerHTML = `
        <div>
            <strong>${Number(resumo.pendentes || 0)} PENDENTES</strong>
            <span>${Number(resumo.instalados || 0)} INSTALADOS</span>
        </div>
        <div>
            <strong>${Number(resumo.nao_executados || 0)} NÃO EXECUTADOS</strong>
            <span>${Number(resumo.aguardando_material || 0)} AGUARDANDO MATERIAL</span>
        </div>
        <div>
            <strong>${percent}% CONCLUIDO</strong>
            <span>${Number(resumo.dias_utilizados || 0)} DIAS UTILIZADOS</span>
        </div>
        <div>
            <strong>${openOrders} OS ABERTAS</strong>
            <span>${overdueOrders} ATRASADAS | ${blockedOrders} BLOQUEADAS | ${completedOrders} CONCLUÍDAS</span>
        </div>
        <div class="progress-track" aria-hidden="true">
            <span style="width:${Math.min(100, Math.max(0, percent))}%"></span>
        </div>
        <span class="progress-hint">CAPACIDADE MEDIA ${Number(resumo.capacidade_media || 0)} | BLOQUEIOS ATIVOS ${totalBlockers} | ACOMPANHE O DIA SELECIONADO PARA EXECUTAR E REPROGRAMAR.</span>
        <div class="nc-meta-list">
            <strong>PRIORIDADE DO BACKLOG: 5 OS ABERTAS MAIS ANTIGAS</strong>
            ${oldestOpenOrders.length ? oldestOpenOrders.map((order, index) => `
                <span>${index + 1}. ${escapeHtml(String(order.order_number || "OS").toUpperCase())} | ${escapeHtml(String(order.vehicle_label || "EQUIPAMENTO").toUpperCase())} | ${Number(order.age_days || 0)} DIA(S) | ${escapeHtml(String(order.status || "-").replace(/_/g, " "))}</span>
            `).join("") : "<span>SEM OS ABERTAS NO RECORTE ATUAL.</span>"}
        </div>
    `;
}

function ensureSelectedMaintenanceDate(days) {
    const selected = days.find((day) => day.date === state.selectedMaintenanceDate);
    if (selected && (state.maintenanceFamilyFilter === "TODOS" || filterMaintenanceItemsByFamily(selected.items || []).length)) {
        return selected;
    }
    const today = getManausDateParts();
    const todayKey = formatDateKey(today.year, today.month, today.day);
    const firstDayWithItems = days.find((day) => filterMaintenanceItemsByFamily(day.items || []).length);
    if (today.year === state.maintenanceYear && today.month === state.maintenanceMonth) {
        state.selectedMaintenanceDate = todayKey;
    } else {
        state.selectedMaintenanceDate = firstDayWithItems?.date || formatDateKey(state.maintenanceYear, state.maintenanceMonth, 1);
    }
    return days.find((day) => day.date === state.selectedMaintenanceDate) || {
        date: state.selectedMaintenanceDate,
        day: Number(state.selectedMaintenanceDate.slice(-2)),
        items: [],
    };
}

function renderMaintenanceCalendar(days) {
    if (!elements.maintenanceCalendar) {
        return;
    }
    const daysByDate = new Map(days.map((day) => [day.date, day]));
    const firstWeekday = new Date(state.maintenanceYear, state.maintenanceMonth - 1, 1).getDay();
    const totalDays = new Date(state.maintenanceYear, state.maintenanceMonth, 0).getDate();
    const todayKey = getManausDateKey();
    elements.maintenanceCalendar.innerHTML = "";

    for (let index = 0; index < firstWeekday; index += 1) {
        const filler = document.createElement("span");
        filler.className = "wash-day empty";
        filler.setAttribute("aria-hidden", "true");
        elements.maintenanceCalendar.appendChild(filler);
    }

    for (let dayNumber = 1; dayNumber <= totalDays; dayNumber += 1) {
        const dateKey = formatDateKey(state.maintenanceYear, state.maintenanceMonth, dayNumber);
        const day = daysByDate.get(dateKey) || { date: dateKey, day: dayNumber, items: [] };
        const familyItems = filterMaintenanceItemsByFamily(day.items || []);
        elements.maintenanceCalendar.appendChild(makeMaintenanceDayButton({ ...day, items: familyItems, total: familyItems.length }, dateKey === todayKey));
    }
}

function makeMaintenanceDayButton(day, isToday) {
    const total = Number(day.total || (day.items || []).length || 0);
    const pending = Number(day.pendentes || 0);
    const installed = Number(day.instalados || 0);
    const button = document.createElement("button");
    button.type = "button";
    button.className = [
        "wash-day",
        total ? "has-items" : "no-items",
        day.date === state.selectedMaintenanceDate ? "active" : "",
        isToday ? "today" : "",
        total > 0 && pending === 0 ? "done" : "",
    ].filter(Boolean).join(" ");
    button.innerHTML = `
        <strong>${String(day.day || Number(day.date.slice(-2))).padStart(2, "0")}</strong>
        <span>${total ? `${total} SERV.` : "SEM"}</span>
        ${pending ? `<em>${pending} PEND.</em>` : installed ? `<em>${installed} OK</em>` : ""}
    `;
    button.addEventListener("click", () => {
        state.selectedMaintenanceDate = day.date;
        renderMaintenance();
    });
    return button;
}

function renderMaintenanceDayPanel(day) {
    if (!elements.maintenanceDayPanel) {
        return;
    }
    const selectedDay = day || { date: state.selectedMaintenanceDate, items: [] };
    const familyItems = filterMaintenanceItemsByFamily(selectedDay.items || []);
    const total = familyItems.length;
    const pending = familyItems.filter((item) => ["PENDENTE", "PROGRAMADO", "REPROGRAMADO"].includes(String(item.status || "").toUpperCase())).length;
    const installed = familyItems.filter((item) => String(item.status || "").toUpperCase() === "INSTALADO").length;
    const notExecuted = familyItems.filter((item) => String(item.status || "").toUpperCase() === "NAO_EXECUTADO").length;
    const filter = state.maintenanceStatusFilter || "ABERTAS";
    elements.maintenanceDayPanel.innerHTML = `
        <section class="wash-day-summary maintenance-focus">
            <div>
                <span>DIA SELECIONADO</span>
                <strong>${formatDate(selectedDay.date)}</strong>
            </div>
            <div>
                <span>SERVIÇOS</span>
                <strong>${total}</strong>
            </div>
            <div>
                <span>PENDENTES</span>
                <strong>${pending}</strong>
            </div>
            <div>
                <span>CONCLUIDOS</span>
                <strong>${installed}</strong>
            </div>
        </section>
        <section class="wash-shift-tabs" role="tablist" aria-label="Filtro do painel do mecânico">
            <button type="button" class="wash-shift-tab ${filter === "ABERTAS" ? "active" : ""}" data-maint-filter="ABERTAS">ABERTAS</button>
            <button type="button" class="wash-shift-tab ${filter === "ATRASADAS" ? "active" : ""}" data-maint-filter="ATRASADAS">ATRASADAS</button>
            <button type="button" class="wash-shift-tab ${filter === "AGUARDANDO_MATERIAL" ? "active" : ""}" data-maint-filter="AGUARDANDO_MATERIAL">BLOQUEADAS</button>
            <button type="button" class="wash-shift-tab ${filter === "CONCLUIDAS" ? "active" : ""}" data-maint-filter="CONCLUIDAS">CONCLUÍDAS</button>
        </section>
        <p class="section-caption">NÃO EXECUTADOS NO DIA: ${notExecuted}. Use os cards abaixo para instalar, justificar ou reprogramar.</p>
    `;
    elements.maintenanceDayPanel.querySelectorAll("[data-maint-filter]").forEach((button) => {
        button.addEventListener("click", () => {
            state.maintenanceStatusFilter = button.dataset.maintFilter || "ABERTAS";
            renderMaintenance();
        });
    });
}

function filterMaintenanceItemsForMobile(items) {
    const filter = state.maintenanceStatusFilter || "ABERTAS";
    const todayKey = getManausDateKey();
    const openStatuses = new Set(["PENDENTE", "PROGRAMADO", "REPROGRAMADO"]);
    items = filterMaintenanceItemsByFamily(items);
    if (filter === "ABERTAS") {
        return items.filter((item) => openStatuses.has(String(item.status || "").toUpperCase()));
    }
    if (filter === "ATRASADAS") {
        return items.filter((item) => {
            const status = String(item.status || "").toUpperCase();
            const scheduled = String(item.scheduled_date || "");
            return openStatuses.has(status) && scheduled && scheduled < todayKey;
        });
    }
    if (filter === "AGUARDANDO_MATERIAL") {
        return items.filter((item) => String(item.status || "").toUpperCase() === "AGUARDANDO_MATERIAL");
    }
    if (filter === "CONCLUIDAS") {
        return items.filter((item) => String(item.status || "").toUpperCase() === "INSTALADO");
    }
    return items;
}

function maintenanceItemCanInstall(item) {
    const materials = item.schedule?.materiais || [];
    if (!materials.length) {
        return { allowed: true, reason: "" };
    }

    for (const link of materials) {
        const stock = Number(link.material?.quantidade_estoque || 0);
        const required = Number(link.quantity_per_vehicle || 1);
        const materialStatus = String(link.status || "").toUpperCase();
        if (materialStatus === "AGUARDANDO_MATERIAL" || materialStatus === "EM_COMPRAS") {
            return {
                allowed: false,
                reason: `${String(link.material?.referencia || link.material?.descricao || "MATERIAL").toUpperCase()} AGUARDANDO MATERIAL.`,
            };
        }
        if (stock < required) {
            return {
                allowed: false,
                reason: `${String(link.material?.referencia || link.material?.descricao || "MATERIAL").toUpperCase()} SEM SALDO (${stock}/${required}).`,
            };
        }
    }

    return { allowed: true, reason: "" };
}

function makeMaintenanceItemCard(item, index) {
    const vehicle = item.vehicle || {};
    const schedule = item.schedule || {};
    const workOrder = item.work_order || {};
    const materials = schedule.materiais || [];
    const packageLabel = String(schedule.package_reference_label || "").trim();
    const blockerSummary = schedule.bloqueios_resumo || {};
    const photoAfter = item.photo_after ? makeAbsoluteUrl(item.photo_after) : "";
    const status = String(item.status || "PENDENTE").toUpperCase();
    const canExecute = maintenanceItemCanInstall(item);
    const pendingMobileUpdate = state.pendingMaintenanceItemIds.has(Number(item.id));
    const card = document.createElement("article");
    card.className = "checklist-card activity-item-card maintenance-item-card";
    card.dataset.itemId = item.id;
    card.dataset.scheduleId = item.schedule_id;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(schedule.title || item.item_name || "PROGRAMACAO DE MANUTENCAO").toUpperCase())}</h3>
        </div>
        <div class="activity-meta">
            <strong>OS ${escapeHtml(String(workOrder.order_number || "-").toUpperCase())}</strong>
            <span>${escapeHtml(String(workOrder.status || status).replace(/_/g, " "))}</span>
        </div>
        <div class="activity-meta">
            <strong>${escapeHtml(String(vehicle.frota || "EQUIPAMENTO").toUpperCase())} | ${escapeHtml(String(vehicle.placa || "-").toUpperCase())}</strong>
            <span>${escapeHtml(maintenanceFamilyKey(item) || "MÓDULO NÃO INFORMADO")} · ${escapeHtml(String(vehicle.modelo || "-").toUpperCase())}</span>
        </div>
        <div class="nc-meta-list">
            <span>DATA PROGRAMADA: ${item.scheduled_date ? formatDateTime(`${item.scheduled_date}T00:00:00`) : "SEM DATA"}</span>
            <span>STATUS: ${escapeHtml(status.replace(/_/g, " "))}</span>
            <span>PROGRAMAÇÃO: ${escapeHtml(String(schedule.status || "-").replace(/_/g, " "))}</span>
            ${packageLabel ? `<span>${escapeHtml(packageLabel.toUpperCase())}</span>` : ""}
            ${schedule.assigned_mechanic ? `<span>MECÂNICO: ${escapeHtml(String(schedule.assigned_mechanic.nome || "").toUpperCase())}</span>` : ""}
        </div>
        ${(Number(blockerSummary.materiais_bloqueados || 0) || Number(blockerSummary.ordens_bloqueadas || 0) || blockerSummary.sem_responsavel) ? `
            <div class="nc-meta-list">
                ${Number(blockerSummary.materiais_bloqueados || 0) ? `<span>PEÇAS BLOQUEANDO: ${Number(blockerSummary.materiais_bloqueados || 0)}</span>` : ""}
                ${Number(blockerSummary.ordens_bloqueadas || 0) ? `<span>OS BLOQUEADAS: ${Number(blockerSummary.ordens_bloqueadas || 0)}</span>` : ""}
                ${blockerSummary.sem_responsavel ? `<span>SEM RESPONSÁVEL DEFINIDO</span>` : ""}
            </div>
        ` : ""}
        ${materials.length ? `
            <div class="nc-meta-list">
                ${materials.map((link) => {
                    const material = link.material || {};
                    return `<span>MATERIAL: ${escapeHtml(String(material.referencia || "-").toUpperCase())} | ${escapeHtml(String(material.descricao || "-").toUpperCase())} | ESTOQUE ${Number(material.quantidade_estoque || 0)} | NECESSÁRIO ${Number(link.quantity_required || 0)} | RESERVADO ${Number(link.quantity_reserved || 0)} | ${escapeHtml(String(link.status || "").replace(/_/g, " "))}</span>`;
                }).join("")}
            </div>
        ` : `
            <div class="nc-meta-list">
                <span>SEM MATERIAL VINCULADO NESTA PROGRAMAÇÃO.</span>
            </div>
        `}
        ${item.observation ? `<div class="nc-meta-list"><span>OBSERVAÇÃO: ${escapeHtml(item.observation)}</span></div>` : ""}
        ${pendingMobileUpdate ? `<span class="maintenance-flag">ATUALIZAÇÃO SALVA NO APARELHO. AGUARDANDO SINCRONIZAÇÃO.</span>` : ""}
        ${status !== "INSTALADO" && !canExecute.allowed ? `<span class="maintenance-flag">AGUARDANDO MATERIAL / BLOQUEIO</span>` : ""}
        ${workOrder.id ? `<button type="button" class="share-button maintenance-pdf-button">EXPORTAR PDF DA OS</button>` : ""}
        ${status === "INSTALADO" ? `
            <span class="nc-resolved-flag">INSTALADO</span>
            ${item.executed_by ? `<div class="nc-meta-list"><span>EXECUTADO POR: ${escapeHtml(String(item.executed_by.nome || "").toUpperCase())}</span><span>EXECUÇÃO EM: ${formatDateTime(item.executed_at)}</span></div>` : ""}
            ${item.not_executed_reason ? `<div class="nc-meta-list"><span>MOTIVO ANTERIOR: ${escapeHtml(item.not_executed_reason)}</span></div>` : ""}
            ${photoAfter ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    ${buildProtectedImageMarkup(photoAfter, "Foto depois da manutenção")}
                </figure>
            ` : ""}
        ` : `
            <div class="nc-resolve-form">
                <label>
                    <span>PARECER TÉCNICO</span>
                    <textarea class="maintenance-observation" placeholder="DESCREVA A EXECUÇÃO, PENDÊNCIA OU CONDIÇÃO ENCONTRADA">${escapeHtml(item.observation || "")}</textarea>
                </label>
                <label>
                    <span>MOTIVO PARA NÃO EXECUTAR</span>
                    <textarea class="maintenance-not-executed" placeholder="INFORME O MOTIVO, SE NÃO FOR POSSÍVEL CONCLUIR AGORA"></textarea>
                </label>
                <label class="evidence-input">
                    <span>FOTO DEPOIS</span>
                    <strong>EVIDÊNCIA OPCIONAL</strong>
                    <input type="file" class="maintenance-after-photo" accept="image/*" capture="environment">
                    <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.</em>
                </label>
                <img class="photo-preview maintenance-after-preview" alt="Prévia da foto depois">
                ${!canExecute.allowed ? `<div class="nc-meta-list"><span>INSTALAÇÃO BLOQUEADA: ${escapeHtml(canExecute.reason)}</span></div>` : ""}
                <div class="status-group activity-status-group" role="group" aria-label="Ações da manutenção">
                    <button type="button" class="status-button ok maintenance-execute-button"${canExecute.allowed && !pendingMobileUpdate ? "" : " disabled"}>INSTALAR</button>
                    <button type="button" class="status-button nc maintenance-not-executed-button"${pendingMobileUpdate ? " disabled" : ""}>NÃO EXECUTADO</button>
                </div>
                ${hasWashReportAccess() && !pendingMobileUpdate ? `
                    <div class="maintenance-reprogram-box">
                        <label>
                            <span>REPROGRAMAR DATA</span>
                            <input type="date" class="maintenance-reprogram-date" value="${escapeHtml(item.scheduled_date || "")}">
                        </label>
                        <button type="button" class="share-button maintenance-reprogram-button">REPROGRAMAR</button>
                    </div>
                ` : ""}
            </div>
        `}
    `;

    if (status !== "INSTALADO") {
        const fileInput = card.querySelector(".maintenance-after-photo");
        const preview = card.querySelector(".maintenance-after-preview");
        fileInput?.addEventListener("change", () => bindPhotoPreview(fileInput, preview));
        if (!pendingMobileUpdate) {
            card.querySelector(".maintenance-execute-button")?.addEventListener("click", () => submitMaintenanceItem(card, item, "INSTALADO"));
            card.querySelector(".maintenance-not-executed-button")?.addEventListener("click", () => submitMaintenanceItem(card, item, "NAO_EXECUTADO"));
        }
        card.querySelector(".maintenance-reprogram-button")?.addEventListener("click", () => reprogramMaintenanceItem(card, item));
    }
    card.querySelector(".maintenance-pdf-button")?.addEventListener("click", () => exportMaintenanceWorkOrderPdf(item));
    hydrateProtectedImages(card);
    attachCollapsibleCard(card);
    return card;
}

async function exportMaintenanceWorkOrderPdf(item) {
    const workOrder = item.work_order || {};
    const workOrderId = Number(workOrder.id || 0);
    if (!workOrderId) {
        showToast("OS NÃO DISPONÍVEL NESTE ITEM.", true);
        return;
    }
    try {
        await downloadAuthenticatedFile(
            `/manutencao/os/${workOrderId}/pdf`,
            `ordem_servico_${String(workOrder.order_number || workOrderId).toLowerCase().replace(/[^a-z0-9_-]/g, "_")}.pdf`
        );
        showToast("PDF DA OS BAIXADO COM SUCESSO.");
    } catch (error) {
        showToast(error.message || "FALHA AO EXPORTAR PDF DA OS.", true);
    }
}

async function reprogramMaintenanceItem(card, item) {
    const button = card.querySelector(".maintenance-reprogram-button");
    const scheduledDate = card.querySelector(".maintenance-reprogram-date")?.value || "";
    if (!scheduledDate) {
        showToast("INFORME A NOVA DATA DO CRONOGRAMA.", true);
        return;
    }
    button.disabled = true;
    button.textContent = "SALVANDO...";
    try {
        await apiFetch(`/manutencao/itens/${item.id}/reprogramar`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scheduled_date: scheduledDate }),
        });
        state.selectedMaintenanceDate = scheduledDate;
        await loadMaintenanceOverview();
        if (screens.planning && !screens.planning.classList.contains("hidden")) renderPlanning();
        else renderMaintenance();
        showToast("MANUTENÇÃO REPROGRAMADA.");
    } catch (error) {
        showToast(error.message || "FALHA AO REPROGRAMAR A MANUTENÇÃO.", true);
    } finally {
        button.disabled = false;
        button.textContent = "REPROGRAMAR";
    }
}

async function submitMaintenanceItem(card, item, newStatus) {
    const button = newStatus === "INSTALADO"
        ? card.querySelector(".maintenance-execute-button")
        : card.querySelector(".maintenance-not-executed-button");
    if (!button) {
        return;
    }

    const canExecute = maintenanceItemCanInstall(item);
    if (newStatus === "INSTALADO" && !canExecute.allowed) {
        showToast(canExecute.reason || "SEM SALDO PARA CONCLUIR A INSTALACAO.", true);
        return;
    }

    const afterFile = card.querySelector(".maintenance-after-photo")?.files?.[0];
    const observation = card.querySelector(".maintenance-observation")?.value?.trim() || "";
    const notExecutedReason = card.querySelector(".maintenance-not-executed")?.value?.trim() || "";

    if (newStatus === "NAO_EXECUTADO" && !notExecutedReason) {
        showToast("INFORME O MOTIVO PARA MARCAR COMO NÃO EXECUTADO.", true);
        return;
    }

    button.disabled = true;
    button.textContent = "SALVANDO...";
    try {
        const vehicleName = item.vehicle?.frota || item.vehicle?.placa || "EQUIPAMENTO";
        const itemName = item.schedule?.title || item.item_name || "MANUTENCAO";
        const result = await submitMobileOperation(
            "MANUTENCAO_ATUALIZAR_ITEM",
            {
                maintenance_item_id: item.id,
                vehicle_id: item.vehicle_id,
                status: newStatus,
                observation,
                not_executed_reason: notExecutedReason,
                photo_after: afterFile ? "" : (item.photo_after || ""),
            },
            afterFile ? {
                file: afterFile,
                field: "photo_after",
                vehicleLabel: vehicleName,
                itemLabel: itemName,
                kind: "manutencao_depois",
                folder: "MANUTENCAO",
            } : null,
        );

        if (result.queued) {
            state.pendingMaintenanceItemIds.add(Number(item.id));
            renderMaintenance();
            showToast("MANUTENÇÃO SALVA NO APARELHO. SERÁ ENVIADA QUANDO A CONEXÃO VOLTAR.");
            return;
        }

        await loadMaintenanceOverview();
        renderMaintenance();
        showToast(newStatus === "INSTALADO" ? "INSTALAÇÃO REGISTRADA." : "MANUTENÇÃO MARCADA COMO NÃO EXECUTADA.");
    } catch (error) {
        showToast(error.message || "FALHA AO SALVAR A MANUTENÇÃO.", true);
    } finally {
        button.disabled = false;
        button.textContent = newStatus === "INSTALADO" ? "INSTALAR" : "NÃO EXECUTADO";
    }
}

function makeChecklistNonConformityCard(item, index) {
    const vehicle = item.veiculo || {};
    const itemLabel = nonConformityLabel(item);
    const beforePhoto = item.foto_antes ? makeAbsoluteUrl(item.foto_antes) : "";
    const afterPhoto = item.foto_depois ? makeAbsoluteUrl(item.foto_depois) : "";
    const isResolved = Boolean(item.resolvido);
    const card = document.createElement("article");
    card.className = "checklist-card";
    card.dataset.itemId = item.id;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(itemLabel || "NÃO CONFORMIDADE").toUpperCase())}</h3>
        </div>
        <div class="activity-meta">
            <strong>${escapeHtml(String(vehicle.frota || "-").toUpperCase())} | ${escapeHtml(String(vehicle.placa || "-").toUpperCase())}</strong>
            <span>${escapeHtml(String(vehicle.modelo || "-").toUpperCase())}</span>
        </div>
        <div class="nc-meta-list">
            <span>ABERTA EM: ${formatDateTime(item.created_at)}</span>
            <span>ABERTA POR: ${escapeHtml(item.usuario?.nome || "-")}</span>
            ${isResolved ? `<span>RESOLVIDA EM: ${formatDateTime(item.data_resolucao)}</span>` : ""}
        </div>
        <div class="nc-photo-grid">
            ${beforePhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO ANTES</figcaption>
                    ${buildProtectedImageMarkup(beforePhoto, "Foto antes da não conformidade")}
                </figure>
            ` : ""}
            ${afterPhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    ${buildProtectedImageMarkup(afterPhoto, "Foto depois da não conformidade")}
                </figure>
            ` : ""}
        </div>
        ${isResolved ? `
            <span class="nc-resolved-flag">RESOLVIDA</span>
            <div class="nc-meta-list">
                <span>CÓDIGO DA PEÇA: ${escapeHtml(item.codigo_peca || "-")}</span>
                <span>DESCRIÇÃO: ${escapeHtml(item.descricao_peca || "-")}</span>
            </div>
        ` : `
            <div class="nc-resolve-form">
                <label>
                    <span>PECA CADASTRADA</span>
                    <select class="nc-material">${buildMaterialOptions(vehicle.tipo)}</select>
                </label>
                <label>
                    <span>QUANTIDADE DA PECA</span>
                    <input type="number" class="nc-quantity" min="1" step="1" value="1">
                </label>
                <label>
                    <span>OBSERVAÇÃO DA RESOLUÇÃO</span>
                    <textarea class="nc-observation" placeholder="DESCREVA O QUE FOI FEITO"></textarea>
                </label>
                <label class="evidence-input">
                    <span>EVIDÊNCIA DEPOIS</span>
                    <strong>FOTO DEPOIS DA CORRECAO</strong>
                    <input type="file" class="nc-after-photo" accept="image/*" capture="environment">
                    <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.</em>
                </label>
                <img class="photo-preview nc-after-preview" alt="Previa da foto depois">
                <button type="button" class="primary-button nc-resolve-button">SALVAR RESOLUCAO</button>
            </div>
        `}
    `;

    if (!isResolved) {
        const fileInput = card.querySelector(".nc-after-photo");
        const preview = card.querySelector(".nc-after-preview");
        fileInput?.addEventListener("change", () => bindPhotoPreview(fileInput, preview));
        card.querySelector(".nc-resolve-button")?.addEventListener("click", () => resolveChecklistNonConformity(card, item));
    }
    hydrateProtectedImages(card);
    attachCollapsibleCard(card);
    return card;
}

function nonConformityLabel(item) {
    return item?.item_label || item?.item_nome || "";
}

function makeMechanicNonConformityCard(item, index) {
    const beforePhoto = item.foto_antes ? makeAbsoluteUrl(item.foto_antes) : "";
    const afterPhoto = item.foto_depois ? makeAbsoluteUrl(item.foto_depois) : "";
    const isResolved = Boolean(item.resolvido);
    const card = document.createElement("article");
    card.className = "checklist-card";
    card.dataset.itemId = item.id;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(item.item_nome || "NÃO CONFORMIDADE INTERNA").toUpperCase())}</h3>
        </div>
        <div class="activity-meta">
            <strong>${escapeHtml(String(item.veiculo_referencia || "SEM REFERÊNCIA").toUpperCase())}</strong>
            <span>ABERTA POR ${escapeHtml(String(item.created_by?.nome || "-").toUpperCase())}</span>
        </div>
        <div class="nc-meta-list">
            <span>ABERTA EM: ${formatDateTime(item.created_at)}</span>
            ${item.observacao ? `<span>DETALHE: ${escapeHtml(item.observacao)}</span>` : ""}
            ${isResolved ? `<span>RESOLVIDA EM: ${formatDateTime(item.data_resolucao)}</span>` : ""}
        </div>
        <div class="nc-photo-grid">
            ${beforePhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO ANTES</figcaption>
                    ${buildProtectedImageMarkup(beforePhoto, "Foto antes da não conformidade interna")}
                </figure>
            ` : ""}
            ${afterPhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    ${buildProtectedImageMarkup(afterPhoto, "Foto depois da não conformidade interna")}
                </figure>
            ` : ""}
        </div>
        ${isResolved ? `
            <span class="nc-resolved-flag">RESOLVIDA</span>
            <div class="nc-meta-list">
                <span>CÓDIGO DA PEÇA: ${escapeHtml(item.codigo_peca || "-")}</span>
                <span>DESCRIÇÃO: ${escapeHtml(item.descricao_peca || "-")}</span>
            </div>
        ` : `
            <div class="nc-resolve-form">
                <label>
                    <span>PECA CADASTRADA</span>
                    <select class="nc-material">${buildMaterialOptions("")}</select>
                </label>
                <label>
                    <span>QUANTIDADE DA PECA</span>
                    <input type="number" class="nc-quantity" min="1" step="1" value="1">
                </label>
                <label>
                    <span>OBSERVAÇÃO DA RESOLUÇÃO</span>
                    <textarea class="nc-observation" placeholder="DESCREVA O QUE FOI FEITO"></textarea>
                </label>
                <label class="evidence-input">
                    <span>EVIDÊNCIA DEPOIS</span>
                    <strong>FOTO DEPOIS DA CORRECAO</strong>
                    <input type="file" class="nc-after-photo" accept="image/*" capture="environment">
                    <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.</em>
                </label>
                <img class="photo-preview nc-after-preview" alt="Previa da foto depois">
                <button type="button" class="primary-button nc-resolve-button">SALVAR RESOLUCAO</button>
            </div>
        `}
    `;

    if (!isResolved) {
        const fileInput = card.querySelector(".nc-after-photo");
        const preview = card.querySelector(".nc-after-preview");
        fileInput?.addEventListener("change", () => bindPhotoPreview(fileInput, preview));
        card.querySelector(".nc-resolve-button")?.addEventListener("click", () => resolveMechanicNonConformity(card, item));
    }
    hydrateProtectedImages(card);
    attachCollapsibleCard(card);
    return card;
}

function buildMaterialOptions(vehicleType = "") {
    const normalizedType = normalizeText(vehicleType);
    const materials = (state.materials || []).filter((material) => {
        const applyType = normalizeText(material.aplicacao_tipo || "");
        if (!normalizedType) {
            return material.ativo !== false;
        }
        return material.ativo !== false && (applyType === "ambos" || applyType === normalizedType);
    });
    if (!materials.length) {
        return `<option value="">Nenhuma peça cadastrada ativa</option>`;
    }
    const options = [`<option value="">Selecione a peça cadastrada</option>`];
    materials.forEach((material) => {
        const label = `${material.referencia || "-"} | ${material.descricao || "-"}`;
        options.push(`<option value="${material.id}">${escapeHtml(label.toUpperCase())}</option>`);
    });
    return options.join("");
}

async function resolveChecklistNonConformity(card, item) {
    const materialId = Number(card.querySelector(".nc-material")?.value || 0);
    if (!materialId) {
        showToast("SELECIONE A PECA CADASTRADA PARA RESOLVER.", true);
        return;
    }

    const fileInput = card.querySelector(".nc-after-photo");
    const file = fileInput?.files?.[0];
    if (!file && !item.foto_depois) {
        showToast("ANEXE A FOTO DEPOIS PARA FINALIZAR A NÃO CONFORMIDADE.", true);
        return;
    }

    const button = card.querySelector(".nc-resolve-button");
    button.disabled = true;
    button.textContent = "SALVANDO...";
    try {
        const vehicle = item.veiculo || {};
        const afterPhotoPath = file
            ? await uploadEvidence(file, vehicle.frota || vehicle.placa || "EQUIPAMENTO", item.item_nome || "NAO_CONFORMIDADE", "nc_depois", "NAO_CONFORMIDADES")
            : item.foto_depois;
        const quantity = Number(card.querySelector(".nc-quantity")?.value || 1);
        await apiFetch(`/nao_conformidade/${item.id}/resolver`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                material_id: materialId,
                quantidade_material: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
                observacao: card.querySelector(".nc-observation")?.value?.trim() || "",
                foto_depois: afterPhotoPath || "",
            }),
        });
        await loadNonConformityHubData();
        renderNonConformities();
        showToast("NÃO CONFORMIDADE DO CHECKLIST RESOLVIDA.");
    } catch (error) {
        showToast(error.message || "FALHA AO RESOLVER A NÃO CONFORMIDADE.", true);
    } finally {
        button.disabled = false;
        button.textContent = "SALVAR RESOLUCAO";
    }
}

async function resolveMechanicNonConformity(card, item) {
    const materialId = Number(card.querySelector(".nc-material")?.value || 0);
    if (!materialId) {
        showToast("SELECIONE A PECA CADASTRADA PARA RESOLVER.", true);
        return;
    }

    const fileInput = card.querySelector(".nc-after-photo");
    const file = fileInput?.files?.[0];
    if (!file && !item.foto_depois) {
        showToast("ANEXE A FOTO DEPOIS PARA FINALIZAR A NÃO CONFORMIDADE INTERNA.", true);
        return;
    }

    const button = card.querySelector(".nc-resolve-button");
    button.disabled = true;
    button.textContent = "SALVANDO...";
    try {
        const afterPhotoPath = file
            ? await uploadEvidence(file, item.veiculo_referencia || "EQUIPAMENTO", item.item_nome || "NAO_CONFORMIDADE_INTERNA", "nc_mecanico_depois", "NAO_CONFORMIDADES")
            : item.foto_depois;
        const quantity = Number(card.querySelector(".nc-quantity")?.value || 1);
        await apiFetch(`/mecanico/nao_conformidades/${item.id}/resolver`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                material_id: materialId,
                quantidade_material: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
                observacao_resolucao: card.querySelector(".nc-observation")?.value?.trim() || "",
                foto_depois: afterPhotoPath || "",
            }),
        });
        await loadNonConformityHubData();
        renderNonConformities();
        showToast("NÃO CONFORMIDADE INTERNA RESOLVIDA.");
    } catch (error) {
        showToast(error.message || "FALHA AO RESOLVER A NÃO CONFORMIDADE INTERNA.", true);
    } finally {
        button.disabled = false;
        button.textContent = "SALVAR RESOLUCAO";
    }
}

async function createMechanicNonConformity(event) {
    event.preventDefault();
    if (!elements.mechanicNcCreateForm) {
        return;
    }
    const itemName = elements.mechanicNcItemName?.value?.trim() || "";
    if (!itemName) {
        showToast("INFORME O NOME DA NÃO CONFORMIDADE INTERNA.", true);
        return;
    }

    const beforeFile = elements.mechanicNcBeforePhoto?.files?.[0];
    if (!beforeFile) {
        showToast("ANEXE A FOTO ANTES PARA ABRIR A NÃO CONFORMIDADE INTERNA.", true);
        return;
    }

    const createButton = document.getElementById("mechanic-nc-create-button");
    if (createButton) {
        createButton.disabled = true;
        createButton.textContent = "ABRINDO...";
    }
    try {
        const beforePhotoPath = await uploadEvidence(
            beforeFile,
            elements.mechanicNcVehicle?.value?.trim() || "SEM_REFERENCIA",
            itemName,
            "nc_mecanico_antes",
            "NAO_CONFORMIDADES",
        );
        await apiFetch("/mecanico/nao_conformidades", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                veiculo_referencia: elements.mechanicNcVehicle?.value?.trim() || "",
                item_nome: itemName,
                observacao: elements.mechanicNcObservation?.value?.trim() || "",
                foto_antes: beforePhotoPath,
            }),
        });
        elements.mechanicNcCreateForm.reset();
        clearPreview(elements.mechanicNcBeforePreview);
        updateEvidenceInputState(elements.mechanicNcBeforePhoto);
        await loadNonConformityHubData();
        renderNonConformities();
        showToast("NÃO CONFORMIDADE INTERNA ABERTA COM SUCESSO.");
    } catch (error) {
        showToast(error.message || "FALHA AO ABRIR A NÃO CONFORMIDADE INTERNA.", true);
    } finally {
        if (createButton) {
            createButton.disabled = false;
            createButton.textContent = "ABRIR NÃO CONFORMIDADE INTERNA";
        }
    }
}

function bindPhotoPreview(fileInput, previewElement) {
    if (!fileInput || !previewElement) {
        return;
    }
    const file = fileInput.files?.[0];
    if (!file) {
        clearPreview(previewElement);
        updateEvidenceInputState(fileInput);
        return;
    }
    if (previewElement.dataset.objectUrl) {
        URL.revokeObjectURL(previewElement.dataset.objectUrl);
    }
    const objectUrl = URL.createObjectURL(file);
    previewElement.dataset.objectUrl = objectUrl;
    previewElement.src = objectUrl;
    previewElement.classList.add("visible");
    previewElement.dataset.zoomLabel = previewElement.alt || "PRÉVIA DA EVIDÊNCIA";
    updateEvidenceInputState(fileInput);
}

function clearPreview(previewElement) {
    if (!previewElement) {
        return;
    }
    previewElement.classList.remove("visible");
    previewElement.removeAttribute("src");
    if (previewElement.dataset.objectUrl) {
        URL.revokeObjectURL(previewElement.dataset.objectUrl);
        delete previewElement.dataset.objectUrl;
    }
    delete previewElement.dataset.zoomLabel;
}

function openPhotoViewer(sourceUrl, label = "Visualização ampliada da evidência") {
    if (!elements.photoViewerModal || !elements.photoViewerImage || !sourceUrl) {
        return;
    }
    photoViewerFocusOrigin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    elements.photoViewerImage.src = sourceUrl;
    elements.photoViewerImage.alt = label;
    elements.photoViewerModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
}

function closePhotoViewer() {
    if (!elements.photoViewerModal || elements.photoViewerModal.classList.contains("hidden")) {
        return;
    }
    elements.photoViewerModal.classList.add("hidden");
    if (elements.photoViewerImage) {
        elements.photoViewerImage.removeAttribute("src");
        elements.photoViewerImage.alt = "Visualização ampliada da evidência";
    }
    document.body.classList.remove("modal-open");
    if (photoViewerFocusOrigin && document.contains(photoViewerFocusOrigin)) {
        photoViewerFocusOrigin.focus();
    }
    photoViewerFocusOrigin = null;
}

function setPullRefreshDistance(distance, label = "PUXE PARA ATUALIZAR") {
    if (!elements.mobileShell || !elements.pullRefreshIndicator) {
        return;
    }
    elements.mobileShell.style.setProperty("--pull-distance", `${distance}px`);
    elements.pullRefreshIndicator.textContent = label;
}

function resetPullRefresh() {
    if (!elements.mobileShell) {
        return;
    }
    pullRefresh.active = false;
    pullRefresh.armed = false;
    pullRefresh.distance = 0;
    elements.mobileShell.classList.remove("is-pulling", "pull-refresh-ready", "pull-refresh-loading");
    setPullRefreshDistance(0, "PUXE PARA ATUALIZAR");
}

function triggerPullRefresh() {
    if (!elements.mobileShell || pullRefresh.refreshing) {
        return;
    }
    pullRefresh.refreshing = true;
    elements.mobileShell.classList.remove("is-pulling", "pull-refresh-ready");
    elements.mobileShell.classList.add("pull-refresh-loading");
    setPullRefreshDistance(64, "ATUALIZANDO...");
    window.setTimeout(() => {
        window.location.reload();
    }, 180);
}

function initPullToRefresh() {
    if (!elements.mobileShell) {
        return;
    }

    elements.mobileShell.addEventListener("touchstart", (event) => {
        if (document.body.classList.contains("modal-open") || pullRefresh.refreshing) {
            return;
        }
        if (event.touches.length !== 1 || elements.mobileShell.scrollTop > 0) {
            pullRefresh.active = false;
            return;
        }
        pullRefresh.active = true;
        pullRefresh.armed = false;
        pullRefresh.startY = event.touches[0].clientY;
        pullRefresh.distance = 0;
    }, { passive: true });

    elements.mobileShell.addEventListener("touchmove", (event) => {
        if (!pullRefresh.active || document.body.classList.contains("modal-open")) {
            return;
        }
        const deltaY = event.touches[0].clientY - pullRefresh.startY;
        if (deltaY <= 0 || elements.mobileShell.scrollTop > 0) {
            resetPullRefresh();
            return;
        }
        event.preventDefault();
        pullRefresh.distance = Math.min(PULL_REFRESH_MAX_PX, Math.round(deltaY * 0.42));
        pullRefresh.armed = pullRefresh.distance >= PULL_REFRESH_TRIGGER_PX;
        elements.mobileShell.classList.add("is-pulling");
        elements.mobileShell.classList.toggle("pull-refresh-ready", pullRefresh.armed);
        setPullRefreshDistance(
            pullRefresh.distance,
            pullRefresh.armed ? "SOLTE PARA ATUALIZAR" : "PUXE PARA ATUALIZAR"
        );
    }, { passive: false });

    const finishPullGesture = () => {
        if (!pullRefresh.active) {
            return;
        }
        const shouldRefresh = pullRefresh.armed;
        resetPullRefresh();
        if (shouldRefresh) {
            triggerPullRefresh();
        }
    };

    elements.mobileShell.addEventListener("touchend", finishPullGesture);
    elements.mobileShell.addEventListener("touchcancel", resetPullRefresh);
}

function attachCollapsibleCard(card, options = {}) {
    if (!card) {
        return;
    }
    const summarySelectors = options.summarySelectors || [".item-topline", ".activity-meta"];
    const summaryNodes = summarySelectors
        .map((selector) => card.querySelector(selector))
        .filter((node) => node && node.parentElement === card);
    if (!summaryNodes.length) {
        return;
    }

    const detailNodes = Array.from(card.children).filter((node) => !summaryNodes.includes(node));
    if (!detailNodes.length) {
        return;
    }

    const toggleButton = document.createElement("button");
    toggleButton.type = "button";
    toggleButton.className = "card-toggle-header";

    const summaryWrap = document.createElement("div");
    summaryWrap.className = "card-toggle-summary";
    summaryNodes.forEach((node) => summaryWrap.appendChild(node));

    const indicator = document.createElement("span");
    indicator.className = "card-toggle-indicator";

    const detailWrap = document.createElement("div");
    detailWrap.className = "card-toggle-content";
    detailNodes.forEach((node) => detailWrap.appendChild(node));

    toggleButton.appendChild(summaryWrap);
    toggleButton.appendChild(indicator);

    const defaultExpanded = Boolean(options.defaultExpanded);
    const setExpanded = (expanded) => {
        detailWrap.hidden = !expanded;
        toggleButton.setAttribute("aria-expanded", expanded ? "true" : "false");
        indicator.textContent = expanded ? "OCULTAR DETALHES" : "VER DETALHES";
        card.classList.toggle("card-collapsible-open", expanded);
    };

    toggleButton.addEventListener("click", () => {
        setExpanded(detailWrap.hidden);
    });

    card.classList.add("card-collapsible");
    while (card.firstChild) {
        card.removeChild(card.firstChild);
    }
    card.appendChild(toggleButton);
    card.appendChild(detailWrap);
    setExpanded(defaultExpanded);
}

function formatDateTime(value) {
    return formatManausDateTime(value);
}

function normalizeCatalog(catalog) {
    return Object.fromEntries(
        Object.entries(catalog || {}).map(([vehicleType, rows]) => [
            vehicleType,
            (rows || []).map((row, index) => {
                if (typeof row === "string") {
                    return {
                        id: null,
                        item_nome: row,
                        foto_path: "",
                        position: index + 1,
                        module: classifyModule(row),
                    };
                }
                return {
                    ...row,
                    item_nome: row.item_nome,
                    foto_path: row.foto_path || "",
                    position: row.position || index + 1,
                    module: row.module || classifyModule(row.item_nome),
                };
            }),
        ]),
    );
}

function cacheOfflineReferenceData() {
    localStorage.setItem(OFFLINE_VEHICLES_KEY, JSON.stringify(state.vehicles));
    localStorage.setItem(OFFLINE_CATALOG_KEY, JSON.stringify(state.catalog));
}

function loadOfflineReferenceData() {
    const cachedVehicles = readJsonStorage(OFFLINE_VEHICLES_KEY, null);
    const cachedCatalog = readJsonStorage(OFFLINE_CATALOG_KEY, null);
    if (!cachedVehicles || !cachedCatalog) {
        return false;
    }
    state.vehicles = cachedVehicles.filter((vehicle) => isPortEquipment(vehicle));
    state.catalog = cachedCatalog;
    return true;
}

function openOfflineDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(CHECKLIST_QUEUE_STORE)) {
                const store = db.createObjectStore(CHECKLIST_QUEUE_STORE, { keyPath: "id" });
                store.createIndex("status", "status", { unique: false });
                store.createIndex("queuedAt", "queuedAt", { unique: false });
            }
            if (!db.objectStoreNames.contains(CHECKLIST_DRAFT_STORE)) {
                const store = db.createObjectStore(CHECKLIST_DRAFT_STORE, { keyPath: "vehicleId" });
                store.createIndex("updatedAt", "updatedAt", { unique: false });
            }
            if (!db.objectStoreNames.contains(INSPECTION_QUEUE_STORE)) {
                const store = db.createObjectStore(INSPECTION_QUEUE_STORE, { keyPath: "id" });
                store.createIndex("queuedAt", "queuedAt", { unique: false });
            }
            if (!db.objectStoreNames.contains(MOBILE_OPERATION_QUEUE_STORE)) {
                const store = db.createObjectStore(MOBILE_OPERATION_QUEUE_STORE, { keyPath: "id" });
                store.createIndex("status", "status", { unique: false });
                store.createIndex("queuedAt", "queuedAt", { unique: false });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function withOfflineStore(storeName, mode, action) {
    const db = await openOfflineDb();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(storeName, mode);
        const store = transaction.objectStore(storeName);
        const result = action(store);
        transaction.oncomplete = () => {
            db.close();
            resolve(result);
        };
        transaction.onerror = () => {
            db.close();
            reject(transaction.error);
        };
    });
}

async function withChecklistQueueStore(mode, action) {
    return withOfflineStore(CHECKLIST_QUEUE_STORE, mode, action);
}

async function addChecklistToQueue(draft, reason = "SEM CONEXÃO") {
    const queued = {
        ...draft,
        id: createQueueId(),
        type: "CHECKLIST",
        status: "PENDENTE",
        attempts: 0,
        lastError: reason,
        queuedAt: new Date().toISOString(),
        apiBaseUrl: state.apiBaseUrl,
        userLogin: state.user?.login || "",
    };
    await withChecklistQueueStore("readwrite", (store) => store.put(queued));
    await refreshSyncQueuePanel();
    return queued;
}

async function getChecklistQueue() {
    return withChecklistQueueStore("readonly", (store) => {
        const request = store.getAll();
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    });
}

async function updateChecklistQueueItem(item) {
    await withChecklistQueueStore("readwrite", (store) => store.put(item));
}

async function deleteChecklistQueueItem(id) {
    await withChecklistQueueStore("readwrite", (store) => store.delete(id));
}

async function getMobileOperationQueue() {
    return withOfflineStore(MOBILE_OPERATION_QUEUE_STORE, "readonly", (store) => {
        const request = store.getAll();
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    });
}

async function refreshPendingMaintenanceItemIds() {
    const queue = await getMobileOperationQueue();
    state.pendingMaintenanceItemIds = new Set(
        queue
            .filter((item) => item.operationType === "MANUTENCAO_ATUALIZAR_ITEM" && ["PENDENTE", "ERRO", "ENVIANDO"].includes(item.status))
            .map((item) => Number(item.payload?.maintenance_item_id || 0))
            .filter(Boolean),
    );
}

async function updateMobileOperationQueueItem(item) {
    await withOfflineStore(MOBILE_OPERATION_QUEUE_STORE, "readwrite", (store) => store.put(item));
}

async function deleteMobileOperationQueueItem(id) {
    await withOfflineStore(MOBILE_OPERATION_QUEUE_STORE, "readwrite", (store) => store.delete(id));
}

async function submitMobileOperation(operationType, payload, evidence = null) {
    const draft = {
        id: createQueueId(), type: "OPERACAO_MOBILE", operationType, payload, evidence,
        status: "PENDENTE", attempts: 0, lastError: "", queuedAt: new Date().toISOString(),
        occurredAt: new Date().toISOString(),
        userLogin: state.user?.login || "",
    };
    if (!navigator.onLine) {
        await updateMobileOperationQueueItem(draft);
        await refreshSyncQueuePanel();
        return { queued: true };
    }
    try {
        const response = await sendMobileOperationDraft(draft);
        return { queued: false, response };
    } catch (error) {
        if (!isOfflineError(error)) throw error;
        draft.lastError = error.message || "SEM CONEXÃO";
        await updateMobileOperationQueueItem(draft);
        await refreshSyncQueuePanel();
        return { queued: true };
    }
}

async function sendMobileOperationDraft(draft) {
    const payload = { ...(draft.payload || {}) };
    if (draft.evidence?.file) {
        payload[draft.evidence.field] = await uploadEvidence(
            draft.evidence.file, draft.evidence.vehicleLabel, draft.evidence.itemLabel,
            draft.evidence.kind, draft.evidence.folder,
        );
    }
    return apiFetch("/operacao-mobile/sincronizar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            operation_id: draft.id, operation_type: draft.operationType, payload,
            occurred_at: draft.occurredAt || draft.queuedAt,
        }),
    });
}

async function syncPendingMobileOperations({ silent = true } = {}) {
    if (!state.token || !navigator.onLine) return;
    const queue = await getMobileOperationQueue();
    const pending = queue.filter((item) => item.status === "PENDENTE" || item.status === "ERRO");
    let synced = 0;
    for (const item of pending) {
        const current = { ...item, status: "ENVIANDO", attempts: (item.attempts || 0) + 1, lastError: "" };
        await updateMobileOperationQueueItem(current);
        try {
            await sendMobileOperationDraft(current);
            await deleteMobileOperationQueueItem(current.id);
            synced += 1;
        } catch (error) {
            const conflict = error.status === 409;
            await updateMobileOperationQueueItem({
                ...current, status: conflict ? "CONFLITO" : "ERRO",
                lastError: error.message || "FALHA AO SINCRONIZAR.",
            });
            if (isOfflineError(error)) break;
        }
    }
    await refreshSyncQueuePanel();
    await refreshPendingMaintenanceItemIds();
    if (!screens.maintenance.classList.contains("hidden")) renderMaintenance();
    if (synced && !silent) showToast(`${synced} OPERAÇÃO(ÕES) MOBILE SINCRONIZADA(S).`);
}

function createQueueId() {
    if (crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function saveChecklistDraftNow() {
    if (!state.selectedVehicle || screens.checklist.classList.contains("hidden")) {
        return;
    }

    const items = Array.from(document.querySelectorAll(".checklist-item-card")).map((card) => {
        const file = card.querySelector("input[type='file']")?.files?.[0] || null;
        const textarea = card.querySelector("textarea");
        return {
            item_nome: card.dataset.itemName,
            item_principal: card.dataset.itemPrincipal || card.dataset.itemName,
            parte: card.dataset.itemPart || "",
            tipo_agrupamento: card.dataset.groupingType || "simples",
            module: card.dataset.module,
            status: card.dataset.status || "",
            observacao: textarea?.value || "",
            foto_antes_file: file,
            foto_antes_name: file?.name || "",
        };
    });

    const draft = {
        vehicleId: state.selectedVehicle.id,
        vehicle: {
            id: state.selectedVehicle.id,
            frota: state.selectedVehicle.frota,
            placa: state.selectedVehicle.placa,
            modelo: state.selectedVehicle.modelo,
            tipo: state.selectedVehicle.tipo,
        },
        currentModule: state.currentModule,
        items,
        updatedAt: new Date().toISOString(),
    };

    await withOfflineStore(CHECKLIST_DRAFT_STORE, "readwrite", (store) => store.put(draft));
    state.currentChecklistDraftUpdatedAt = draft.updatedAt;
    state.currentChecklistDraftRestored = false;
    localStorage.setItem(ACTIVE_CHECKLIST_DRAFT_KEY, String(state.selectedVehicle.id));
    updateProgress();
}

function scheduleChecklistDraftSave() {
    window.clearTimeout(scheduleChecklistDraftSave.timeoutId);
    scheduleChecklistDraftSave.timeoutId = window.setTimeout(() => {
        saveChecklistDraftNow().catch(() => {});
    }, 250);
}

async function getChecklistDraft(vehicleId) {
    return withOfflineStore(CHECKLIST_DRAFT_STORE, "readonly", (store) => {
        const request = store.get(Number(vehicleId));
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    });
}

async function getActiveChecklistDraft() {
    const vehicleId = localStorage.getItem(ACTIVE_CHECKLIST_DRAFT_KEY);
    if (!vehicleId) {
        return null;
    }
    return getChecklistDraft(vehicleId);
}

async function deleteChecklistDraft(vehicleId) {
    await withOfflineStore(CHECKLIST_DRAFT_STORE, "readwrite", (store) => store.delete(Number(vehicleId)));
    if (localStorage.getItem(ACTIVE_CHECKLIST_DRAFT_KEY) === String(vehicleId)) {
        localStorage.removeItem(ACTIVE_CHECKLIST_DRAFT_KEY);
    }
}

async function restoreActiveChecklistDraft() {
    const draft = await getActiveChecklistDraft().catch(() => null);
    if (!draft?.vehicleId) {
        return false;
    }
    const vehicle = state.vehicles.find((item) => Number(item.id) === Number(draft.vehicleId));
    if (!vehicle) {
        localStorage.removeItem(ACTIVE_CHECKLIST_DRAFT_KEY);
        return false;
    }
    const vehicleLabel = vehicle.frota || draft.vehicle?.frota || "equipamento";
    const updatedAtLabel = formatDateTimeShort(draft.updatedAt);
    const shouldRestore = window.confirm(
        updatedAtLabel
            ? `Deseja voltar para o checklist do ${vehicleLabel} salvo em ${updatedAtLabel}?`
            : `Deseja voltar para o checklist do ${vehicleLabel}?`
    );
    if (!shouldRestore) {
        localStorage.removeItem(ACTIVE_CHECKLIST_DRAFT_KEY);
        showToast("RETORNO AUTOMÁTICO DO CHECKLIST CANCELADO.");
        return false;
    }
    await selectVehicle(vehicle, { restoreDraft: true });
    showToast("CHECKLIST EM ANDAMENTO RESTAURADO.");
    return true;
}

async function restoreChecklistDraft(vehicleId) {
    const draft = await getChecklistDraft(vehicleId).catch(() => null);
    if (!draft?.items?.length) {
        state.currentChecklistDraftUpdatedAt = "";
        state.currentChecklistDraftRestored = false;
        return false;
    }
    const itemsByName = new Map(draft.items.map((item) => [normalizeText(item.item_nome), item]));

    document.querySelectorAll(".checklist-item-card").forEach((card) => {
        const saved = itemsByName.get(normalizeText(card.dataset.itemName));
        if (!saved) {
            return;
        }
        const status = saved.status || "";
        const statusButtons = card.querySelectorAll(".status-button");
        statusButtons.forEach((button) => button.classList.toggle("active", button.dataset.status === status));
        card.dataset.status = status;
        card.classList.toggle("has-nc", status === "NC");
        card.querySelector(".nc-fields")?.classList.toggle("visible", status === "NC");
        const textarea = card.querySelector("textarea");
        if (textarea) {
            textarea.value = saved.observacao || "";
        }
        if (saved.foto_antes_file) {
            const fileInput = card.querySelector("input[type='file']");
            const preview = card.querySelector(".photo-preview");
            const evidenceBox = fileInput?.closest(".evidence-input");
            const hint = evidenceBox?.querySelector("em");
            try {
                const transfer = new DataTransfer();
                transfer.items.add(saved.foto_antes_file);
                fileInput.files = transfer.files;
                fileInput.dataset.restoredFile = "true";
            } catch {
                fileInput.dataset.restoredFile = "true";
            }
            if (preview) {
                if (preview.dataset.objectUrl) {
                    URL.revokeObjectURL(preview.dataset.objectUrl);
                }
                const objectUrl = URL.createObjectURL(saved.foto_antes_file);
                preview.dataset.objectUrl = objectUrl;
                preview.src = objectUrl;
                preview.classList.add("visible");
                preview.dataset.zoomLabel = preview.alt || "PRÉVIA DA EVIDÊNCIA ANEXADA";
            }
            evidenceBox?.classList.add("has-file");
            if (hint) {
                hint.textContent = "EVIDÊNCIA RESTAURADA. TOQUE NA FOTO PARA AMPLIAR.";
                hint.classList.add("ok");
            }
        }
    });

    state.currentModule = draft.currentModule || "TODOS";
    state.currentChecklistDraftUpdatedAt = draft.updatedAt || "";
    state.currentChecklistDraftRestored = true;
    applyChecklistModuleFilter(state.currentModule);
    updateProgress();
    localStorage.setItem(ACTIVE_CHECKLIST_DRAFT_KEY, String(vehicleId));
    return true;
}

async function refreshSyncQueuePanel() {
    if (!elements.syncPanel) {
        return;
    }

    try {
        const [checklists, mobileOperations] = await Promise.all([getChecklistQueue(), getMobileOperationQueue()]);
        const visibleItems = [...checklists, ...mobileOperations]
            .filter((item) => item.status !== "SINCRONIZADO")
            .sort((a, b) => String(a.queuedAt || "").localeCompare(String(b.queuedAt || "")));

        elements.syncPanel.classList.toggle("hidden", visibleItems.length === 0);
        const conflicts = visibleItems.filter((item) => item.status === "CONFLITO").length;
        elements.syncCounter.textContent = `${visibleItems.length} OPERAÇÃO(ÕES) PENDENTE(S)${conflicts ? ` | ${conflicts} CONFLITO(S)` : ""}`;
        elements.syncList.innerHTML = visibleItems.slice(0, 4).map((item) => `
            <article class="sync-row ${item.status === "ERRO" || item.status === "CONFLITO" ? "error" : ""}">
                <div>
                    <strong>${escapeHtml(item.vehicle?.frota || item.evidence?.vehicleLabel || item.operationType || "EQUIPAMENTO")}</strong>
                    <span>${formatDateTime(item.queuedAt)} | ${escapeHtml(item.operationType || item.type || "CHECKLIST")}${item.lastError ? ` | ${escapeHtml(item.lastError)}` : ""}</span>
                </div>
                <em>${escapeHtml(item.status || "PENDENTE")}</em>
            </article>
        `).join("");
    } catch (error) {
        elements.syncPanel.classList.add("hidden");
    }
}

async function syncPendingChecklists({ silent = false } = {}) {
    if (!state.token || !navigator.onLine) {
        if (!silent) {
            showToast("SEM CONEXÃO PARA SINCRONIZAR.", true);
        }
        return;
    }

    const queue = await getChecklistQueue();
    const pending = queue.filter((item) => item.status === "PENDENTE" || item.status === "ERRO");
    if (!pending.length) {
        await refreshSyncQueuePanel();
        if (!silent) {
            showToast("NÃO HÁ CHECKLIST PENDENTE PARA SINCRONIZAR.");
        }
        return;
    }

    let synced = 0;
    for (const item of pending) {
        const current = {
            ...item,
            status: "ENVIANDO",
            attempts: (item.attempts || 0) + 1,
            lastError: "",
        };
        await updateChecklistQueueItem(current);
        await refreshSyncQueuePanel();

        try {
            await sendChecklistDraft(current);
            await deleteChecklistQueueItem(current.id);
            synced += 1;
        } catch (error) {
            await updateChecklistQueueItem({
                ...current,
                status: "ERRO",
                lastError: error.message || "FALHA AO SINCRONIZAR.",
            });
            if (isOfflineError(error)) {
                break;
            }
        }
    }

    await refreshSyncQueuePanel();
    if (synced) {
        renderHome();
        showToast(`${synced} CHECKLIST${synced === 1 ? "" : "S"} SINCRONIZADO${synced === 1 ? "" : "S"}.`);
    } else if (!silent) {
        showToast("NÃO FOI POSSÍVEL SINCRONIZAR A FILA.", true);
    }
}

function isOfflineError(error) {
    return !navigator.onLine || error?.name === "TypeError" || /fetch|network|conex/i.test(error?.message || "");
}

function renderVehicles() {
    const query = normalizeText(elements.vehicleSearch.value);
    const familyFilter = normalizeText(state.vehicleFamilyFilter).toUpperCase();
    const familyCounts = { LBS: 0, RTG: 0, SPREADER: 0 };
    state.vehicles.forEach((vehicle) => {
        const familyKey = getVehicleFamilyKey(vehicle);
        if (familyKey) familyCounts[familyKey] += 1;
    });
    Object.entries(familyCounts).forEach(([familyKey, count]) => {
        const countElement = elements.vehicleFamilyCounts[familyKey];
        if (countElement) countElement.textContent = String(count);
    });
    elements.vehicleFamilyCards.forEach((card) => {
        const isActive = normalizeText(card.dataset.vehicleFamily).toUpperCase() === familyFilter;
        card.classList.toggle("is-active", isActive);
        card.setAttribute("aria-pressed", String(isActive));
    });
    const filteredVehicles = state.vehicles.filter((vehicle) => {
        const matchesFamily = !familyFilter || getVehicleFamilyKey(vehicle) === familyFilter;
        const familyName = vehicle.family?.name || "";
        const locationName = vehicle.operational_location?.full_name || vehicle.local || "";
        const searchable = normalizeText(
            `${vehicle.frota} ${vehicle.nome || ""} ${vehicle.referencia || ""} ${vehicle.reference || ""} ${vehicle.placa} ${vehicle.modelo} ${vehicle.tipo} ${familyName} ${vehicle.serial_number || ""} ${vehicle.manufacturer || ""} ${vehicle.descricao || ""} ${locationName}`
        );
        return matchesFamily && (!query || searchable.includes(query));
    });

    elements.vehiclesList.classList.toggle("hidden", !query);
    elements.vehiclesList.setAttribute("aria-hidden", String(!query));

    elements.userSummary.innerHTML = `
        <div>
            <span>USUÁRIO</span>
            <strong>${escapeHtml(state.user.nome)}</strong>
        </div>
        <div>
            <span>PERFIL</span>
            <strong>${escapeHtml(String(state.user.tipo || "").toUpperCase())}</strong>
        </div>
        <div>
            <span>STATUS</span>
            <strong>${navigator.onLine ? "ONLINE" : "OFFLINE"}</strong>
        </div>
    `;

    elements.vehicleCounter.textContent = `${filteredVehicles.length} ATIVOS`;
    elements.vehiclesList.innerHTML = "";

    if (!filteredVehicles.length) {
        const hasQuery = Boolean(query);
        elements.vehiclesList.innerHTML = `
            <article class="empty-state">
                <strong>${hasQuery ? "NENHUM EQUIPAMENTO LOCALIZADO NESTA BUSCA." : "NENHUM EQUIPAMENTO ATIVO ENCONTRADO."}</strong>
                <span>${hasQuery ? "AJUSTE O TERMO DIGITADO OU LIMPE A BUSCA PARA VER TODA A FROTA." : "ATUALIZE O CADASTRO NO DESKTOP OU AJUSTE A BUSCA."}</span>
            </article>
        `;
        return;
    }

    filteredVehicles.forEach((vehicle) => {
        elements.vehiclesList.appendChild(makeVehicleCard(vehicle));
    });
}

function getVehicleFamilyKey(vehicle) {
    const familyName = normalizeText(vehicle?.family?.name || vehicle?.tipo || vehicle?.family_name || "");
    if (familyName.includes("spreader")) return "SPREADER";
    if (familyName.includes("rtg")) return "RTG";
    if (familyName.includes("lbs")) return "LBS";
    return "";
}

function isPortEquipment(vehicle) {
    return PORT_EQUIPMENT_FAMILIES.has(getVehicleFamilyKey(vehicle));
}

function toggleAssetAccessPanel(forceOpen = null) {
    if (!elements.assetAccessPanel || !elements.assetAccessToggle) return;
    const nfcSupported = "NDEFReader" in window;
    if (elements.scanAssetNfcButton) {
        elements.scanAssetNfcButton.disabled = !nfcSupported;
        elements.scanAssetNfcButton.textContent = nfcSupported ? "LER NFC" : "NFC INDISPONÍVEL";
        elements.scanAssetNfcButton.title = nfcSupported
            ? "Ler uma etiqueta NFC neste aparelho"
            : "NFC não é compatível neste navegador ou aparelho";
    }
    const isOpen = forceOpen === null
        ? elements.assetAccessPanel.classList.contains("hidden")
        : Boolean(forceOpen);
    elements.assetAccessPanel.classList.toggle("hidden", !isOpen);
    elements.assetAccessToggle.setAttribute("aria-expanded", String(isOpen));
    elements.assetAccessToggle.textContent = isOpen ? "FECHAR ACESSO POR ETIQUETA" : "ACESSAR ATIVO POR ETIQUETA";
}

function makeVehicleCard(vehicle) {
    const familyName = vehicle.family?.name || vehicle.tipo || "-";
    const locationName = vehicle.operational_location?.full_name || vehicle.local || "SEM LOCAL";
    const parentEquipment = vehicle.active_link?.parent_equipment;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "vehicle-card";
    card.innerHTML = `
        <span class="vehicle-type">${escapeHtml(String(familyName).toUpperCase())}</span>
        <strong>${escapeHtml(vehicle.frota || "-")}</strong>
        <span>${escapeHtml(String(vehicle.modelo || "MODELO NÃO INFORMADO").toUpperCase())}</span>
        <small>SÉRIE ${escapeHtml(vehicle.serial_number || "-")} | ${escapeHtml(String(locationName).toUpperCase())}</small>
        <small>CRITICIDADE ${escapeHtml(vehicle.criticality || "MEDIA")}${parentEquipment ? ` | ${escapeHtml(vehicle.active_link.link_type || "VÍNCULO")} ${escapeHtml(parentEquipment.frota || "-")}` : ""}</small>
        <small>ETIQUETA MOBILE ${escapeHtml(vehicle.mobile_access_code || `CF-ATIVO-${String(vehicle.id || "").padStart(6, "0")}`)}</small>
    `;
    card.addEventListener("click", () => selectVehicle(vehicle));
    return card;
}

function renderVehicleFamilyScreen() {
    const familyFilter = normalizeText(state.vehicleFamilyFilter).toUpperCase();
    const familyLabel = familyFilter === "SPREADER" ? "SPREADERS" : familyFilter || "MÓDULO";
    const filteredVehicles = state.vehicles.filter((vehicle) => getVehicleFamilyKey(vehicle) === familyFilter);
    elements.vehicleFamilyTitle.textContent = familyLabel;
    elements.vehicleFamilyScreenCounter.textContent = `${filteredVehicles.length} EQUIPAMENTO${filteredVehicles.length === 1 ? "" : "S"}`;
    elements.vehicleFamilyScreenList.innerHTML = "";
    if (!filteredVehicles.length) {
        elements.vehicleFamilyScreenList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUM EQUIPAMENTO ATIVO NESTE MÓDULO.</strong>
                <span>ATUALIZE O CADASTRO OU VOLTE PARA ESCOLHER OUTRO MÓDULO.</span>
            </article>
        `;
        return;
    }
    filteredVehicles.forEach((vehicle) => {
        elements.vehicleFamilyScreenList.appendChild(makeVehicleCard(vehicle));
    });
}

async function openMobileAssetByCode(rawCode) {
    const accessCode = normalizeMobileAssetCode(rawCode);
    if (!accessCode) {
        throw new Error("INFORME OU LEIA O CÓDIGO DA ETIQUETA.");
    }
    const cachedVehicle = state.vehicles.find((item) => (
        String(item.mobile_access_code || `CF-ATIVO-${String(item.id || "").padStart(6, "0")}`).toUpperCase() === accessCode
    ));
    const data = navigator.onLine
        ? await apiFetch(`/operacao-mobile/ativos/${encodeURIComponent(accessCode)}`)
        : cachedVehicle ? { access_code: accessCode, vehicle: cachedVehicle } : null;
    if (!data) throw new Error("ATIVO NÃO ESTÁ NO CACHE DESTE APARELHO. CONECTE PARA CARREGÁ-LO.");
    const vehicle = data.vehicle;
    if (!isPortEquipment(vehicle)) {
        throw new Error("ESTE ATIVO NÃO FAZ PARTE DO CHECKLIST PORTUÁRIO. USE LBS, RTG OU SPREADER.");
    }
    const index = state.vehicles.findIndex((item) => Number(item.id) === Number(vehicle.id));
    if (index >= 0) state.vehicles[index] = vehicle;
    else state.vehicles.push(vehicle);
    if (elements.assetAccessCode) elements.assetAccessCode.value = data.access_code || accessCode;
    const openedChecklist = await selectVehicle(vehicle);
    if (!openedChecklist) await openAvailabilityMenu({ vehicleId: vehicle.id });
}

function normalizeMobileAssetCode(rawCode) {
    const raw = String(rawCode || "").trim();
    if (!raw) return "";
    try {
        const fromUrl = new URL(raw, window.location.href).searchParams.get("ativo");
        return String(fromUrl || raw).trim().toUpperCase();
    } catch {
        return raw.toUpperCase();
    }
}

async function openMobileAssetFromInput() {
    try {
        await openMobileAssetByCode(elements.assetAccessCode?.value);
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL ABRIR O ATIVO.", true);
    }
}

async function scanMobileAssetQr() {
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices?.getUserMedia) {
        showToast("LEITURA POR CÂMERA NÃO É COMPATÍVEL NESTE NAVEGADOR. DIGITE O CÓDIGO DA ETIQUETA.", true);
        return;
    }
    let stream;
    try {
        const detector = new BarcodeDetector({ formats: ["qr_code"] });
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        elements.assetQrPreview.srcObject = stream;
        elements.assetQrPreview.classList.remove("hidden");
        await elements.assetQrPreview.play();
        const deadline = Date.now() + 25000;
        while (Date.now() < deadline) {
            const codes = await detector.detect(elements.assetQrPreview);
            if (codes.length) {
                const code = String(codes[0].rawValue || "").trim();
                if (elements.assetAccessCode) elements.assetAccessCode.value = code;
                await openMobileAssetByCode(code);
                return;
            }
            await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
        showToast("NENHUM QR FOI IDENTIFICADO. APROXIME A CÂMERA DA ETIQUETA.", true);
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL ACESSAR A CÂMERA.", true);
    } finally {
        stream?.getTracks().forEach((track) => track.stop());
        if (elements.assetQrPreview) {
            elements.assetQrPreview.pause();
            elements.assetQrPreview.srcObject = null;
            elements.assetQrPreview.classList.add("hidden");
        }
    }
}

async function scanMobileAssetNfc() {
    if (!("NDEFReader" in window)) {
        showToast("NFC NÃO É COMPATÍVEL NESTE NAVEGADOR. USE QR OU DIGITE O CÓDIGO.", true);
        return;
    }
    try {
        const reader = new NDEFReader();
        await reader.scan();
        showToast("APROXIME A ETIQUETA NFC DO APARELHO.");
        reader.addEventListener("reading", async (event) => {
            const record = event.message.records.find((item) => item.recordType === "text" || item.recordType === "url");
            if (!record) {
                showToast("A ETIQUETA NFC NÃO POSSUI O CÓDIGO DO ATIVO.", true);
                return;
            }
            const value = new TextDecoder(record.encoding || "utf-8").decode(record.data);
            const code = normalizeMobileAssetCode(value);
            if (elements.assetAccessCode) elements.assetAccessCode.value = code;
            try {
                await openMobileAssetByCode(code);
            } catch (error) {
                showToast(error.message || "NÃO FOI POSSÍVEL ABRIR O ATIVO.", true);
            }
        }, { once: true });
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL LER A ETIQUETA NFC.", true);
    }
}

function renderActivities() {
    const openActivities = state.activities.filter((activity) => activity.status === "ABERTA");
    elements.activityCounter.textContent = `${openActivities.length} ABERTAS`;
    elements.activitiesList.innerHTML = "";

    if (!openActivities.length) {
        elements.activitiesList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA INSPEÇÃO ABERTA.</strong>
                <span>AS INSPEÇÕES DE CONFERÊNCIA CRIADAS NO DESKTOP APARECERÃO AQUI.</span>
            </article>
        `;
        return;
    }

    openActivities.forEach((activity) => {
        const resumo = activity.resumo || {};
        const card = document.createElement("button");
        card.type = "button";
        card.className = "activity-card";
        card.innerHTML = `
            <span class="vehicle-type">${escapeHtml(activity.tipo_equipamento || "-")}</span>
            <strong>${escapeHtml(String(activity.titulo || activity.item_nome || "INSPEÇÃO").toUpperCase())}</strong>
            <span>${escapeHtml(String(activity.item_nome || "-").toUpperCase())}</span>
            <small>${resumo.pendentes || 0} PENDENTES | ${resumo.instalados || 0} CONFORMES | ${resumo.nao_instalados || 0} NÃO CONFORMES${activity.assigned_mechanic ? ` | DIRECIONADO: ${escapeHtml(String(activity.assigned_mechanic.nome || "").toUpperCase())}` : ""}</small>
        `;
        card.addEventListener("click", () => selectActivity(activity.id));
        elements.activitiesList.appendChild(card);
    });
}

function formatActivityStatusLabel(status) {
    const normalized = String(status || "PENDENTE").toUpperCase();
    if (normalized === "INSTALADO") {
        return "CONFORME";
    }
    if (normalized === "NAO_INSTALADO") {
        return "NÃO CONFORME";
    }
    if (normalized === "PENDENTE") {
        return "PENDENTE";
    }
    return normalized.replaceAll("_", " ");
}

async function selectActivity(activityId) {
    try {
        state.selectedActivity = await apiFetch(`/atividades/${activityId}`);
        renderActivityDetail();
        setActiveScreen("activityDetail");
    } catch (error) {
        showToast(error.message, true);
    }
}

function renderActivityDetail() {
    const activity = state.selectedActivity;
    const items = activity.itens || [];
    const resumo = activity.resumo || {};
    elements.activityTitle.textContent = String(activity.titulo || activity.item_nome || "INSPEÇÃO").toUpperCase();
    elements.activitySummary.innerHTML = `
        <div>
            <strong>${escapeHtml(String(activity.item_nome || "-").toUpperCase())}</strong>
            <span>${resumo.pendentes || 0} PENDENTES | ${resumo.instalados || 0} CONFORMES | ${resumo.nao_instalados || 0} NÃO CONFORMES</span>
        </div>
        <div class="progress-track" aria-hidden="true">
            <span style="width:${items.length ? Math.round(((items.length - (resumo.pendentes || 0)) / items.length) * 100) : 0}%"></span>
        </div>
    `;
    elements.activityItemsList.innerHTML = "";

    items.forEach((item, index) => {
        elements.activityItemsList.appendChild(makeActivityItemCard(activity, item, index + 1));
    });
}

function makeActivityItemCard(activity, item, index) {
    const vehicle = item.veiculo || {};
    const canShare = item.status_execucao && item.status_execucao !== "PENDENTE";
    const beforePath = item.foto_origem || item.foto_antes || "";
    const afterPath = item.foto_resolucao || item.foto_depois || "";
    const beforePhoto = beforePath ? makeAbsoluteUrl(beforePath) : "";
    const afterPhoto = afterPath ? makeAbsoluteUrl(afterPath) : "";
    const originLocked = Boolean(item.foto_origem_bloqueada);
    const card = document.createElement("article");
    card.className = "checklist-card activity-item-card";
    card.dataset.activityId = activity.id;
    card.dataset.itemId = item.id;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(vehicle.frota || "EQUIPAMENTO").toUpperCase())} - ${escapeHtml(String(vehicle.modelo || "").toUpperCase())}</h3>
        </div>
        <div class="activity-meta">
            <strong>STATUS ATUAL: ${escapeHtml(formatActivityStatusLabel(item.status_execucao || "PENDENTE"))}</strong>
            <span>PLACA ${escapeHtml(vehicle.placa || "-")}</span>
        </div>
        <div class="status-group activity-status-group" role="group" aria-label="Status da inspeção">
            <button type="button" class="status-button ok" data-status="INSTALADO">CONFORME</button>
            <button type="button" class="status-button nc" data-status="NAO_INSTALADO">NÃO CONFORME</button>
            <button type="button" class="status-button" data-status="PENDENTE">PENDENTE</button>
        </div>
        <label>
            <span>OBSERVAÇÃO DA INSPEÇÃO</span>
            <textarea placeholder="DESCREVA A CONFERÊNCIA, PENDÊNCIA OU RESTRIÇÃO">${escapeHtml(item.observacao || "")}</textarea>
        </label>
        <label class="evidence-input">
            <span>EVIDÊNCIA ANTES</span>
            <strong>FOTO DE ORIGEM DA CONFERÊNCIA</strong>
            <input type="file" data-photo="before" accept="image/*" capture="environment">
            <em>${item.foto_antes ? "FOTO DE ORIGEM JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM."}</em>
        </label>
        <img class="photo-preview before-preview" alt="PRÉVIA DA EVIDÊNCIA ANTES">
        <label class="evidence-input">
            <span>EVIDÊNCIA DA CONFERÊNCIA</span>
            <strong>FOTO DA CONFERÊNCIA</strong>
            <input type="file" data-photo="after" accept="image/*" capture="environment">
            <em>${item.foto_depois ? "FOTO DA CONFERÊNCIA JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM."}</em>
        </label>
        <img class="photo-preview after-preview" alt="PRÉVIA DA EVIDÊNCIA DEPOIS">
        <button type="button" class="primary-button activity-save-button">SALVAR CONFERÊNCIA</button>
        ${canShare ? `<button type="button" class="share-button activity-share-button">COMPARTILHAR NO WHATSAPP</button>` : ""}
    `;

    const beforeInput = card.querySelector("input[data-photo='before']");
    const beforeHint = beforeInput?.closest(".evidence-input")?.querySelector("em");
    const beforePreview = card.querySelector(".before-preview");
    if (beforeHint) {
        beforeHint.textContent = beforePath ? "FOTO DE ORIGEM JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.";
    }
    if (beforeInput && originLocked) {
        beforeInput.disabled = true;
    }
    if (beforePreview && beforePhoto) {
        beforePreview.src = beforePhoto;
        beforePreview.classList.add("visible");
    }

    const afterInput = card.querySelector("input[data-photo='after']");
    const afterHint = afterInput?.closest(".evidence-input")?.querySelector("em");
    const afterPreview = card.querySelector(".after-preview");
    if (afterHint) {
        afterHint.textContent = afterPath ? "FOTO DA CONFERÊNCIA JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.";
    }
    if (afterPreview && afterPhoto) {
        afterPreview.src = afterPhoto;
        afterPreview.classList.add("visible");
    }

    const statusButtons = card.querySelectorAll(".activity-status-group .status-button");
    statusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            statusButtons.forEach((statusButton) => statusButton.classList.remove("active"));
            button.classList.add("active");
            card.dataset.status = button.dataset.status;
        });
    });
    card.dataset.status = String(item.status_execucao || "PENDENTE").toUpperCase();
    statusButtons.forEach((statusButton) => {
        if (statusButton.dataset.status === card.dataset.status) {
            statusButton.classList.add("active");
        }
    });

    card.querySelectorAll("input[type='file']").forEach((input) => {
        input.addEventListener("change", () => previewFile(input, card));
    });
    card.querySelector(".activity-save-button").addEventListener("click", () => submitActivityItem(card, activity, item));
    card.querySelector(".activity-share-button")?.addEventListener("click", () => shareActivityItem(activity, item));
    attachCollapsibleCard(card);
    return card;
}

function previewFile(input, card) {
    const [file] = input.files;
    const preview = card.querySelector(input.dataset.photo === "before" ? ".before-preview" : ".after-preview");
    if (!file) {
        preview.classList.remove("visible");
        preview.removeAttribute("src");
        if (preview.dataset.objectUrl) {
            URL.revokeObjectURL(preview.dataset.objectUrl);
            delete preview.dataset.objectUrl;
        }
        return;
    }
    if (preview.dataset.objectUrl) {
        URL.revokeObjectURL(preview.dataset.objectUrl);
    }
    const objectUrl = URL.createObjectURL(file);
    preview.dataset.objectUrl = objectUrl;
    preview.src = objectUrl;
    preview.classList.add("visible");
}

async function submitActivityItem(card, activity, item) {
    const vehicle = item.veiculo || {};
    const status = card.dataset.status || String(item.status_execucao || "PENDENTE").toUpperCase();
    const currentBeforePath = item.foto_origem || item.foto_antes;
    const currentAfterPath = item.foto_resolucao || item.foto_depois;

    const saveButton = card.querySelector(".activity-save-button");
    saveButton.disabled = true;
    saveButton.textContent = "SALVANDO...";

    try {
        const beforeFile = card.querySelector("input[data-photo='before']").files[0];
        const afterFile = card.querySelector("input[data-photo='after']").files[0];
        const payload = {
            status_execucao: status,
            observacao: card.querySelector("textarea").value.trim(),
        };

        if (beforeFile) {
            payload.foto_antes = await uploadEvidence(beforeFile, vehicle.frota || "EQUIPAMENTO", activity.item_nome || "INSPECAO", "inspecao_origem", "INSPECOES");
        } else if (currentBeforePath) {
            payload.foto_antes = currentBeforePath;
        }
        if (afterFile) {
            payload.foto_depois = await uploadEvidence(afterFile, vehicle.frota || "EQUIPAMENTO", activity.item_nome || "INSPECAO", "inspecao_conferencia", "INSPECOES");
        } else if (currentAfterPath) {
            payload.foto_depois = currentAfterPath;
        }

        state.selectedActivity = await apiFetch(`/atividades/${activity.id}/itens/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        renderActivityDetail();
        showToast("INSPEÇÃO ATUALIZADA COM SUCESSO.");
    } catch (error) {
        showToast(error.message, true);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = "SALVAR CONFERÊNCIA";
    }
}

function getWashScheduleItems() {
    const days = state.washOverview?.cronograma?.days || [];
    return days.flatMap((day) => [
        ...(day.morning || []).map((item) => ({ ...item, scheduled_date: item.scheduled_date || day.date, scheduled_shift: item.scheduled_shift || "MANHA" })),
        ...(day.afternoon || []).map((item) => ({ ...item, scheduled_date: item.scheduled_date || day.date, scheduled_shift: item.scheduled_shift || "TARDE" })),
    ]);
}


async function submitWashEvidence(card, item) {
    const status = card.dataset.status;
    if (!status) {
        showToast("SELECIONE LAVADO OU NÃO LEVADO.", true);
        return;
    }

    const saveButton = card.querySelector(".wash-save-button");
    saveButton.disabled = true;
    saveButton.textContent = "SALVANDO...";

    try {
        const notes = card.querySelector(".wash-notes").value.trim();
        if (status === "NAO_LEVADO") {
            await apiFetch("/lavagens/cronograma/decisao", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    queue_item_id: item.queue_item_id,
                    data: item.scheduled_date,
                    turno: item.scheduled_shift || "MANHA",
                    motivo: notes || "VEÍCULO NÃO LEVADO PARA LAVAGEM.",
                }),
            });
        } else {
            const file = card.querySelector("input[type='file']").files[0];
            let fotoPath = "";
            if (file) {
                fotoPath = await uploadEvidence(file, item.referencia || "EQUIPAMENTO", "LAVAGEM", "lavagem_cronograma", "LAVAGENS");
            }
            const trailer = card.querySelector(".wash-trailer")?.value || "";
            await apiFetch("/lavagens/registrar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    queue_item_id: item.queue_item_id,
                    wash_date: `${item.scheduled_date}T${(item.scheduled_shift || "MANHA") === "MANHA" ? "08:00:00" : "14:00:00"}`,
                    local: card.querySelector(".wash-location").value.trim(),
                    valor: hasWashReportAccess() && !trailer ? item.valor_sugerido : null,
                    carreta: trailer,
                    tipo_equipamento: inferWashCategoryForMobile(item, trailer),
                    turno: item.scheduled_shift || "MANHA",
                    observacao: notes,
                    foto_path: fotoPath,
                }),
            });
        }

        await loadWashOverview();
        renderHome();
        renderWashes();
        showToast("PARECER DA LAVAGEM ATUALIZADO COM SUCESSO.");
    } catch (error) {
        showToast(error.message, true);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = "SALVAR PARECER";
    }
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
}

function getActiveTrailers() {
    return state.washOverview?.carretas || [];
}

function isTerbergReference(reference) {
    const normalized = String(reference || "").trim().toUpperCase();
    if (normalized.startsWith("TB")) {
        return true;
    }
    if (!/^\d+$/.test(normalized)) {
        return false;
    }
    const number = Number(normalized);
    return number >= 2301 && number <= 2310;
}

function canAttachTrailerToWash(item) {
    const reference = String(item.referencia || "").trim().toUpperCase();
    return String(item.tipo || "").toLowerCase() === "cavalo" || reference.startsWith("CV") || isTerbergReference(reference);
}

function inferWashCategoryForMobile(item, trailer) {
    if (trailer) {
        return "CONJUNTO";
    }
    if (canAttachTrailerToWash(item)) {
        return isTerbergReference(item.referencia) ? "TERBERG" : "CAVALO";
    }
    return item.categoria_lavagem || item.categoria_sugerida || "CAVALO";
}

function getWashValueForCategory(category, fallback = null) {
    const values = state.washOverview?.tabela_valores || [];
    const match = values.find((item) => String(item.categoria || "").toUpperCase() === String(category || "").toUpperCase());
    return match?.valor_unitario ?? match?.valor ?? fallback;
}

function formatCurrency(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "-";
    }
    return number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function buildPhotoShareText(title, lines, photoPath) {
    const photoUrl = photoPath ? makeAbsoluteUrl(photoPath) : "";
    return [
        title,
        ...lines.filter(Boolean),
        photoUrl ? `Foto: ${photoUrl}` : "",
    ].filter(Boolean).join("\n");
}

async function shareText(title, message) {
    if (navigator.share) {
        try {
            await navigator.share({ title, text: message });
            return;
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
        }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank", "noopener");
}

function shareActivityItem(activity, item) {
    const vehicle = item.veiculo || {};
    const photoPath = item.foto_depois || item.foto_antes || "";
    const title = "CF - inspecao";
    const message = buildPhotoShareText(title, [
        `Inspeção: ${activity.item_nome || activity.titulo || "-"}`,
        `Equipamento: ${vehicle.frota || "-"} | Placa: ${vehicle.placa || "-"}`,
        `Status: ${formatActivityStatusLabel(item.status_execucao || "-")}`,
        item.observacao ? `Observação: ${item.observacao}` : "",
    ], photoPath);
    shareText(title, message);
}

function shareWashItem(item) {
    const title = "CF - lavagem";
    const message = buildPhotoShareText(title, [
        `Equipamento: ${item.referencia || "-"}`,
        `Data: ${formatDate(item.scheduled_date)} | Turno: ${item.scheduled_shift || "-"}`,
        `Status: ${item.status_rotulo || item.status_execucao || "LAVADO"}`,
        `Tipo: ${item.categoria_lavagem || item.categoria_sugerida || "-"}`,
        item.carreta ? `Carreta: ${item.carreta}` : "",
    ], item.foto_path || "");
    shareText(title, message);
}

function buildTrailerOptions(selectedTrailer = "") {
    const trailers = getActiveTrailers();
    const selected = String(selectedTrailer || "");
    const options = [
        `<option value=""${selected ? "" : " selected"}>Sem carreta (mantem cavalo sozinho)</option>`,
    ];
    if (!trailers.length) {
        options.push("<option value=\"\" disabled>Nenhuma carreta cadastrada</option>");
        return options.join("");
    }
    trailers.forEach((trailer) => {
        const value = String(trailer.frota || "");
        const label = `${trailer.frota || "-"} | ${trailer.placa || "-"}`;
        options.push(`<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(label)}</option>`);
    });
    return options.join("");
}

function updateWashCategoryPreview(card, item) {
    const trailer = card.querySelector(".wash-trailer")?.value || "";
    const category = inferWashCategoryForMobile(item, trailer);
    const value = getWashValueForCategory(category, item.valor_sugerido);
    const preview = card.querySelector(".wash-category-preview");
    if (!preview) {
        return;
    }
    preview.textContent = trailer
        ? `COM CARRETA: ${category}${hasWashReportAccess() ? ` | VALOR ${formatCurrency(value)}` : ""}`
        : `${category} SOZINHO${hasWashReportAccess() ? ` | VALOR ${formatCurrency(value)}` : ""}`;
}

function renderWashes() {
    const scheduleItems = getWashScheduleItems();
    const pendingItems = scheduleItems.filter((item) => item.status_execucao !== "LAVADO");
    const days = state.washOverview?.cronograma?.days || [];
    const period = state.washOverview?.periodo || {};

    elements.washCounter.textContent = `${pendingItems.length} PROGRAMADOS`;
    screens.washes.querySelector(".list-toolbar span").textContent = "ESCOLHA O DIA NO CALENDARIO E REGISTRE O PARECER SEM ALTERAR A TABELA DE LAVAGEM.";
    elements.washMonthTitle.textContent = String(period.rotulo || `${state.washMonth}/${state.washYear}`).toUpperCase();
    elements.washReportPanel?.classList.toggle("hidden", !hasWashReportAccess());
    elements.washesList.innerHTML = "";
    ensureSelectedWashDate(days);
    renderWashCalendar(days);
    renderWashDayPanel(days);
}

function ensureSelectedWashDate(days) {
    if (days.find((day) => day.date === state.selectedWashDate)) {
        return;
    }

    const today = getManausDateParts();
    const todayKey = formatDateKey(today.year, today.month, today.day);
    const todayHasSchedule = days.find((day) => day.date === todayKey);
    const firstDayWithItems = days.find((day) => [...(day.morning || []), ...(day.afternoon || [])].length);

    if (today.year === state.washYear && today.month === state.washMonth) {
        state.selectedWashDate = todayHasSchedule?.date || todayKey;
        return;
    }

    state.selectedWashDate = firstDayWithItems?.date || formatDateKey(state.washYear, state.washMonth, 1);
}

function renderWashCalendar(days) {
    const daysByDate = new Map(days.map((day) => [day.date, day]));
    const firstWeekday = new Date(state.washYear, state.washMonth - 1, 1).getDay();
    const totalDays = new Date(state.washYear, state.washMonth, 0).getDate();
    const todayKey = getManausDateKey();

    elements.washCalendar.innerHTML = "";

    for (let index = 0; index < firstWeekday; index += 1) {
        const filler = document.createElement("span");
        filler.className = "wash-day empty";
        filler.setAttribute("aria-hidden", "true");
        elements.washCalendar.appendChild(filler);
    }

    for (let dayNumber = 1; dayNumber <= totalDays; dayNumber += 1) {
        const dateKey = formatDateKey(state.washYear, state.washMonth, dayNumber);
        const day = daysByDate.get(dateKey) || { date: dateKey, day: dayNumber, morning: [], afternoon: [] };
        elements.washCalendar.appendChild(makeWashDayButton(day, dateKey === todayKey));
    }
}

function makeWashDayButton(day, isToday) {
    const button = document.createElement("button");
    const summary = summarizeWashDay(day);
    const isSelected = day.date === state.selectedWashDate;
    button.type = "button";
    button.className = [
        "wash-day",
        summary.total ? "has-items" : "no-items",
        isSelected ? "active" : "",
        isToday ? "today" : "",
        day.blocked ? "blocked" : "",
        summary.pending === 0 && summary.total > 0 ? "done" : "",
    ].filter(Boolean).join(" ");
    button.innerHTML = `
        <strong>${String(day.day || Number(day.date.slice(-2))).padStart(2, "0")}</strong>
        <span>${summary.total ? `${summary.total} PROG.` : "SEM"}</span>
        ${summary.pending ? `<em>${summary.pending} PEND.</em>` : ""}
    `;
    button.addEventListener("click", () => {
        state.selectedWashDate = day.date;
        renderWashes();
    });
    return button;
}

function renderWashDayPanel(days) {
    const selectedDay = days.find((day) => day.date === state.selectedWashDate) || {
        date: state.selectedWashDate,
        morning: [],
        afternoon: [],
    };
    const morningItems = selectedDay.morning || [];
    const afternoonItems = selectedDay.afternoon || [];
    if (state.selectedWashShiftTab !== "TODOS" && state.selectedWashShiftTab !== "MANHA" && state.selectedWashShiftTab !== "TARDE") {
        state.selectedWashShiftTab = "TODOS";
    }
    if (state.selectedWashShiftTab === "MANHA" && morningItems.length === 0 && afternoonItems.length > 0) {
        state.selectedWashShiftTab = "TARDE";
    }
    if (state.selectedWashShiftTab === "TARDE" && afternoonItems.length === 0 && morningItems.length > 0) {
        state.selectedWashShiftTab = "MANHA";
    }
    const summary = summarizeWashDay(selectedDay);

    elements.washDayPanel.innerHTML = `
        <section class="wash-day-summary">
            <div>
                <span>DIA SELECIONADO</span>
                <strong>${formatDate(selectedDay.date)}</strong>
            </div>
            <div>
                <span>STATUS</span>
                <strong>${summary.pending} PENDENTES</strong>
            </div>
        </section>
        <section class="wash-shift-tabs" role="tablist" aria-label="Filtro por turno">
            <button type="button" class="wash-shift-tab ${state.selectedWashShiftTab === "TODOS" ? "active" : ""}" data-shift="TODOS">TODOS</button>
            <button type="button" class="wash-shift-tab ${state.selectedWashShiftTab === "MANHA" ? "active" : ""}" data-shift="MANHA">MANHÃ</button>
            <button type="button" class="wash-shift-tab ${state.selectedWashShiftTab === "TARDE" ? "active" : ""}" data-shift="TARDE">TARDE</button>
        </section>
    `;
    elements.washDayPanel.querySelectorAll(".wash-shift-tab").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedWashShiftTab = button.dataset.shift || "TODOS";
            renderWashDayPanel(days);
        });
    });
    elements.washesList.innerHTML = "";

    if (!summary.total) {
        elements.washesList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA LAVAGEM PROGRAMADA PARA ESTE DIA.</strong>
                <span>USE AS SETAS DO MÊS OU TOQUE EM UM DIA COM PROGRAMAÇÃO.</span>
            </article>
        `;
        return;
    }

    const activeShift = state.selectedWashShiftTab || "TODOS";
    if (activeShift === "TODOS" || activeShift === "MANHA") {
        renderWashShift("MANHÃ", morningItems);
    }
    if (activeShift === "TODOS" || activeShift === "TARDE") {
        renderWashShift("TARDE", afternoonItems);
    }
}

function renderWashShift(title, items) {
    const section = document.createElement("section");
    section.className = "wash-shift-section";
    section.innerHTML = `
        <div class="wash-shift-title">
            <strong>${title}</strong>
            <span>${items.length} VEÍCULO${items.length === 1 ? "" : "S"}</span>
        </div>
    `;

    if (!items.length) {
        section.innerHTML += `<article class="empty-state compact"><strong>SEM VEÍCULOS NESTE TURNO.</strong></article>`;
        elements.washesList.appendChild(section);
        return;
    }

    items.forEach((item, index) => {
        section.appendChild(makeWashCard(item, index + 1));
    });
    elements.washesList.appendChild(section);
}

function summarizeWashDay(day) {
    const items = [...(day.morning || []), ...(day.afternoon || [])];
    return {
        total: items.length,
        pending: items.filter((item) => item.status_execucao === "PENDENTE").length,
        washed: items.filter((item) => item.status_execucao === "LAVADO").length,
        notTaken: items.filter((item) => item.status_execucao === "NAO_CUMPRIDO" || item.status_execucao === "NAO_LEVADO").length,
    };
}

function formatDateKey(year, month, day) {
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

async function changeWashMonth(delta) {
    const date = new Date(state.washYear, state.washMonth - 1 + delta, 1);
    state.washYear = date.getFullYear();
    state.washMonth = date.getMonth() + 1;
    state.selectedWashDate = "";

    try {
        await loadWashOverview();
        renderHome();
        renderWashes();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function changeMaintenanceMonth(delta) {
    const date = new Date(state.maintenanceYear, state.maintenanceMonth - 1 + delta, 1);
    state.maintenanceYear = date.getFullYear();
    state.maintenanceMonth = date.getMonth() + 1;
    state.selectedMaintenanceDate = "";

    try {
        await loadMaintenanceOverview();
        if (screens.planning && !screens.planning.classList.contains("hidden")) renderPlanning();
        else renderMaintenance();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function exportWashMonthPdf() {
    if (!hasWashReportAccess()) {
        showToast("SOMENTE GESTOR OU ADMINISTRADOR PODE EXPORTAR O RELATÓRIO.", true);
        return;
    }

    const button = elements.washExportPdfButton;
    const filename = `relatorio_lavagens_${state.washYear}_${String(state.washMonth).padStart(2, "0")}.pdf`;
    try {
        if (button) {
            button.disabled = true;
            button.textContent = "GERANDO";
        }
        await downloadAuthorizedFile(`/lavagens/relatorio/pdf?ano=${state.washYear}&mes=${state.washMonth}`, filename);
        showToast("RELATÓRIO DE LAVAGEM GERADO.");
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL GERAR O RELATÓRIO.", true);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "PDF";
        }
    }
}

function makeWashCard(item, index) {
    const status = item.status_execucao || "PENDENTE";
    const isWashed = status === "LAVADO";
    const isNotTaken = status === "NAO_CUMPRIDO" || status === "NAO_LEVADO";
    const statusLabel = isWashed ? "LAVADO" : isNotTaken ? "NÃO LEVADO" : "PENDENTE";
    const evidenceUrl = item.foto_path ? makeAbsoluteUrl(item.foto_path) : "";
    const showTrailerField = canAttachTrailerToWash(item);
    const card = document.createElement("article");
    card.className = `checklist-card wash-card wash-status-${status.toLowerCase().replace(/_/g, "-")}`;
    card.dataset.queueItemId = item.queue_item_id;
    card.dataset.scheduledDate = item.scheduled_date;
    card.dataset.shift = item.scheduled_shift || "MANHA";
    card.dataset.category = item.categoria_lavagem || item.categoria_sugerida || "CAVALO";
    card.dataset.value = item.valor_sugerido || "";
    if (isNotTaken) {
        card.dataset.status = "NAO_LEVADO";
    }

    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(item.referencia || "EQUIPAMENTO").toUpperCase())}</h3>
        </div>
        <div class="activity-meta wash-meta">
            <strong>${formatDate(item.scheduled_date)} | ${escapeHtml(String(item.scheduled_shift || "-").toUpperCase())}</strong>
            <span>${escapeHtml(String(item.modelo || "-").toUpperCase())} | ${escapeHtml(String(item.placa || "-").toUpperCase())}</span>
            <em>${statusLabel}</em>
        </div>
        ${isWashed ? `
            <div class="wash-closed">
                <strong>PARECER JÁ REGISTRADO COMO LAVADO.</strong>
                <span>${escapeHtml(String(item.categoria_lavagem || "-").toUpperCase())}</span>
            </div>
            ${evidenceUrl ? buildProtectedImageMarkup(evidenceUrl, "EVIDÊNCIA DA LAVAGEM", { className: "photo-preview", showWhenLoaded: true }) : ""}
            <button type="button" class="share-button wash-share-button">COMPARTILHAR NO WHATSAPP</button>
        ` : `
            <div class="status-group activity-status-group" role="group" aria-label="Status da lavagem">
                <button type="button" class="status-button ok" data-status="LAVADO">LAVADO</button>
                <button type="button" class="status-button nc ${isNotTaken ? "active" : ""}" data-status="NAO_LEVADO">NÃO LEVADO</button>
            </div>
            <label>
                <span>LOCAL DA LAVAGEM</span>
                <input type="text" class="wash-location" placeholder="INFORME O LOCAL">
            </label>
            <label>
                <span>OBSERVAÇÃO / MOTIVO</span>
                <textarea class="wash-notes" placeholder="DESCREVA A EVIDÊNCIA OU O MOTIVO DE NÃO TER SIDO LEVADO">${escapeHtml(item.status_motivo || "")}</textarea>
            </label>
            ${showTrailerField ? `
                <label class="wash-trailer-field">
                    <span>CARRETA ATRELADA</span>
                    <select class="wash-trailer">
                        ${buildTrailerOptions(item.carreta || "")}
                    </select>
                    <em class="wash-category-preview"></em>
                </label>
            ` : ""}
            <label class="evidence-input">
                <span>EVIDÊNCIA DA LAVAGEM</span>
                <strong>FOTO DO VEÍCULO LEVADO / LAVADO</strong>
                <input type="file" accept="image/*" capture="environment">
                <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.</em>
            </label>
            <img class="photo-preview" alt="PRÉVIA DA EVIDÊNCIA DA LAVAGEM">
            <button type="button" class="primary-button wash-save-button">SALVAR PARECER</button>
        `}
    `;

    if (isWashed) {
        card.querySelector(".wash-share-button")?.addEventListener("click", () => shareWashItem(item));
        hydrateProtectedImages(card);
        attachCollapsibleCard(card);
        return card;
    }

    const statusButtons = card.querySelectorAll(".activity-status-group .status-button");
    statusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            statusButtons.forEach((statusButton) => statusButton.classList.remove("active"));
            button.classList.add("active");
            card.dataset.status = button.dataset.status;
        });
    });

    const trailerSelect = card.querySelector(".wash-trailer");
    if (trailerSelect) {
        trailerSelect.addEventListener("change", () => updateWashCategoryPreview(card, item));
        updateWashCategoryPreview(card, item);
    }

    const fileInput = card.querySelector("input[type='file']");
    fileInput.addEventListener("change", () => {
        const [file] = fileInput.files;
        const preview = card.querySelector(".photo-preview");
        if (!file) {
            preview.classList.remove("visible");
            preview.removeAttribute("src");
            return;
        }
        const reader = new FileReader();
        reader.onload = (event) => {
            preview.src = event.target.result;
            preview.classList.add("visible");
        };
        reader.readAsDataURL(file);
    });

    card.querySelector(".wash-save-button").addEventListener("click", () => submitWashEvidence(card, item));
    hydrateProtectedImages(card);
    attachCollapsibleCard(card);
    return card;
}

async function selectVehicle(vehicle, options = {}) {
    state.selectedVehicle = vehicle;
    state.currentModule = "TODOS";
    state.currentChecklistDraftUpdatedAt = "";
    state.currentChecklistDraftRestored = false;
    const items = state.catalog[vehicle.tipo] || [];
    if (!items.length) {
        showToast(`CHECKLIST DE ${String(vehicle.family?.name || vehicle.tipo || "EQUIPAMENTO").toUpperCase()} SERÁ CONFIGURADO NA FASE 3.`);
        return false;
    }
    const modules = buildModules(items);

    elements.checklistTitle.textContent = `${vehicle.frota} - ${vehicle.modelo}`;
    elements.checklistSubtitle.textContent = `${items.length} ITENS OBRIGATÓRIOS PARA ${String(vehicle.tipo || "").toUpperCase()}.`;
    elements.checklistForm.innerHTML = "";

    renderModuleTabs(modules);
    renderChecklistModules(modules);
    updateProgress();
    setActiveScreen("checklist");
    if (options.restoreDraft) {
        await restoreChecklistDraft(vehicle.id);
    } else {
        await restoreChecklistDraft(vehicle.id);
        localStorage.setItem(ACTIVE_CHECKLIST_DRAFT_KEY, String(vehicle.id));
        scheduleChecklistDraftSave();
    }
    return true;
}

function buildModules(items) {
    const grouped = new Map(MODULE_ORDER.map((moduleName) => [moduleName, []]));
    items.forEach((item) => {
        const moduleName = item.module || classifyModule(item.item_nome);
        if (!grouped.has(moduleName)) {
            grouped.set(moduleName, []);
        }
        grouped.get(moduleName).push(item);
    });

    return Array.from(grouped.entries())
        .map(([name, moduleItems]) => ({ name, items: moduleItems }))
        .filter((module) => module.items.length);
}

function renderModuleTabs(modules) {
    elements.moduleTabs.innerHTML = "";
    const allButton = makeModuleButton("TODOS", modules.reduce((total, module) => total + module.items.length, 0));
    elements.moduleTabs.appendChild(allButton);
    modules.forEach((module) => {
        elements.moduleTabs.appendChild(makeModuleButton(module.name, module.items.length));
    });
}

function makeModuleButton(moduleName, total) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "module-tab";
    button.classList.toggle("active", state.currentModule === moduleName);
    button.innerHTML = `<span>${escapeHtml(moduleName)}</span><strong>${total}</strong>`;
    button.addEventListener("click", () => {
        applyChecklistModuleFilter(moduleName);
        scheduleChecklistDraftSave();
    });
    return button;
}

function applyChecklistModuleFilter(moduleName) {
    state.currentModule = moduleName;
    document.querySelectorAll(".module-tab").forEach((item) => {
        const label = item.querySelector("span")?.textContent || "";
        item.classList.toggle("active", label === moduleName);
    });
    document.querySelectorAll(".module-section").forEach((section) => {
        section.classList.toggle("hidden-by-filter", moduleName !== "TODOS" && section.dataset.module !== moduleName);
    });
}

function getChecklistCards() {
    return Array.from(document.querySelectorAll(".checklist-item-card"));
}

function focusChecklistCard(card, { focusSelector = "", smooth = true } = {}) {
    if (!card) {
        return;
    }
    card.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "center" });
    const target = focusSelector ? card.querySelector(focusSelector) : null;
    const focusable = target || card.querySelector(".status-button") || card;
    if (focusable?.focus) {
        window.setTimeout(() => focusable.focus(), smooth ? 220 : 0);
    }
}

function findNextChecklistCard(currentCard, predicate) {
    const cards = getChecklistCards();
    const currentIndex = cards.indexOf(currentCard);
    if (currentIndex < 0) {
        return null;
    }
    for (let index = currentIndex + 1; index < cards.length; index += 1) {
        if (!predicate || predicate(cards[index])) {
            return cards[index];
        }
    }
    return null;
}

function updateEvidenceInputState(fileInput, { restoredName = "" } = {}) {
    const evidenceBox = fileInput?.closest(".evidence-input");
    const hint = evidenceBox?.querySelector("em");
    if (!evidenceBox || !hint) {
        return;
    }
    const file = fileInput?.files?.[0];
    const restored = fileInput?.dataset?.restoredFile === "true";
    if (file || restored) {
        evidenceBox.classList.add("has-file");
        hint.textContent = restored && !file
            ? "EVIDÊNCIA RESTAURADA. TOQUE NA FOTO PARA AMPLIAR."
            : "EVIDÊNCIA ANEXADA. TOQUE NA FOTO PARA AMPLIAR.";
        hint.classList.add("ok");
        return;
    }
    evidenceBox.classList.remove("has-file");
    hint.textContent = "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM";
    hint.classList.remove("ok");
}

function renderChecklistModules(modules) {
    elements.checklistForm.innerHTML = "";
    let globalIndex = 0;

    modules.forEach((module) => {
        const displayGroups = groupChecklistItemsForDisplay(module.items);
        const section = document.createElement("section");
        section.className = "module-section";
        section.dataset.module = module.name;
        section.innerHTML = `
            <div class="module-header">
                <div>
                    <span>MÓDULO</span>
                    <strong>${escapeHtml(module.name)}</strong>
                </div>
                <em>${module.items.length} ITENS</em>
            </div>
        `;

        displayGroups.forEach((displayGroup) => {
            globalIndex += 1;
            if (displayGroup.items.length > 1) {
                section.appendChild(makeChecklistGroup(displayGroup, module.name, globalIndex));
                return;
            }
            section.appendChild(makeChecklistCard(displayGroup.items[0], module.name, globalIndex));
        });

        elements.checklistForm.appendChild(section);
    });
}

function groupChecklistItemsForDisplay(items) {
    const groups = [];
    const groupedByKey = new Map();

    items.forEach((item) => {
        const grouping = item.agrupamento || {};
        const groupingType = grouping.tipo_agrupamento || "simples";
        const parentItem = grouping.item_principal || item.item_nome;
        if (groupingType === "simples") {
            groups.push({
                key: `simples:${item.item_nome}`,
                itemPrincipal: item.item_nome,
                tipoAgrupamento: "simples",
                items: [item],
            });
            return;
        }

        const key = `${groupingType}:${parentItem}`;
        if (!groupedByKey.has(key)) {
            const group = {
                key,
                itemPrincipal: parentItem,
                tipoAgrupamento: groupingType,
                items: [],
            };
            groupedByKey.set(key, group);
            groups.push(group);
        }
        groupedByKey.get(key).items.push(item);
    });

    return groups;
}

function makeChecklistGroup(displayGroup, moduleName, index) {
    const group = document.createElement("article");
    group.className = "checklist-group-card";
    group.dataset.itemPrincipal = displayGroup.itemPrincipal;
    group.dataset.groupingType = displayGroup.tipoAgrupamento;
    group.innerHTML = `
        <div class="checklist-group-header">
            <span>${String(index).padStart(2, "0")}</span>
            <div>
                <strong>${escapeHtml(displayGroup.itemPrincipal)}</strong>
                <em>${displayGroup.items.length} PARTES PARA AVALIAR</em>
            </div>
        </div>
        <div class="checklist-group-items"></div>
    `;

    const wrap = group.querySelector(".checklist-group-items");
    displayGroup.items.forEach((item) => {
        wrap.appendChild(makeChecklistCard(item, moduleName, index, { compactPart: true }));
    });
    return group;
}

function makeChecklistCard(item, moduleName, index, options = {}) {
    const itemName = item.item_nome;
    const grouping = item.agrupamento || {};
    const itemPrincipal = grouping.item_principal || itemName;
    const itemPart = grouping.parte || "";
    const groupingType = grouping.tipo_agrupamento || "simples";
    const title = options.compactPart && itemPart ? itemPart : itemName;
    const itemPhotoUrl = item.foto_path ? makeAbsoluteUrl(item.foto_path) : "";
    const card = document.createElement("article");
    card.className = "checklist-card checklist-item-card";
    card.classList.toggle("checklist-part-card", Boolean(options.compactPart));
    card.dataset.itemName = itemName;
    card.dataset.itemPrincipal = itemPrincipal;
    card.dataset.itemPart = itemPart;
    card.dataset.groupingType = groupingType;
    card.dataset.module = moduleName;
    card.innerHTML = `
        <div class="item-topline">
            <span>${options.compactPart ? "•" : String(index).padStart(2, "0")}</span>
            <div>
                <h3>${escapeHtml(title)}</h3>
                ${options.compactPart ? `<em>${escapeHtml(itemName)}</em>` : ""}
            </div>
        </div>
        ${itemPhotoUrl ? `
            <figure class="reference-photo">
                <figcaption>FOTO DE REFERÊNCIA DO ITEM</figcaption>
                ${buildProtectedImageMarkup(itemPhotoUrl, `FOTO DE REFERÊNCIA DO ITEM ${itemName}`)}
            </figure>
        ` : ""}
        <div class="status-group" role="group" aria-label="Status do item">
            <button type="button" class="status-button ok" data-status="OK">OK</button>
            <button type="button" class="status-button nc" data-status="NC">NÃO CONFORMIDADE</button>
        </div>
        <div class="nc-fields">
            <label>
                    <span>OBSERVAÇÃO DA NÃO CONFORMIDADE</span>
                    <textarea placeholder="DESCREVA A FALHA ENCONTRADA"></textarea>
            </label>
            <label class="evidence-input">
                <span>TIPO DA FOTO ANEXADA</span>
                <strong>EVIDÊNCIA DA NÃO CONFORMIDADE</strong>
                <span class="camera-trigger" tabindex="0"><span class="camera-trigger-icon" aria-hidden="true"></span><span>CÂMERA</span></span>
                <input class="camera-input" type="file" accept="image/*" capture="environment">
                <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM</em>
            </label>
            <img class="photo-preview" alt="PRÉVIA DA EVIDÊNCIA ANEXADA">
        </div>
    `;

    const statusButtons = card.querySelectorAll(".status-button");
    const ncFields = card.querySelector(".nc-fields");
    const fileInput = card.querySelector("input[type='file']");
    const preview = card.querySelector(".photo-preview");
    const textarea = card.querySelector("textarea");

    statusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const previousStatus = card.dataset.status || "";
            statusButtons.forEach((statusButton) => statusButton.classList.remove("active"));
            button.classList.add("active");
            card.dataset.status = button.dataset.status;
            card.classList.toggle("has-nc", button.dataset.status === "NC");
            ncFields.classList.toggle("visible", button.dataset.status === "NC");
            updateProgress();
            scheduleChecklistDraftSave();
            if (button.dataset.status === "NC") {
                window.setTimeout(() => {
                    textarea?.focus();
                    card.scrollIntoView({ behavior: "smooth", block: "center" });
                }, 160);
                return;
            }
            if (button.dataset.status === "OK" && previousStatus !== "OK") {
                const nextPendingCard = findNextChecklistCard(card, (candidate) => !candidate.dataset.status);
                if (nextPendingCard) {
                    focusChecklistCard(nextPendingCard, { focusSelector: ".status-button" });
                }
            }
        });
    });

    textarea?.addEventListener("input", scheduleChecklistDraftSave);
    textarea?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            focusChecklistCard(card, { focusSelector: ".camera-trigger" });
        }
    });

    fileInput.addEventListener("change", () => {
        const [file] = fileInput.files;
        if (!file) {
            preview.classList.remove("visible");
            preview.removeAttribute("src");
            if (preview.dataset.objectUrl) {
                URL.revokeObjectURL(preview.dataset.objectUrl);
                delete preview.dataset.objectUrl;
            }
            delete fileInput.dataset.restoredFile;
            updateEvidenceInputState(fileInput);
            return;
        }
        if (preview.dataset.objectUrl) {
            URL.revokeObjectURL(preview.dataset.objectUrl);
        }
        const objectUrl = URL.createObjectURL(file);
        preview.dataset.objectUrl = objectUrl;
        preview.src = objectUrl;
        preview.classList.add("visible");
        preview.dataset.zoomLabel = preview.alt || "PRÉVIA DA EVIDÊNCIA ANEXADA";
        delete fileInput.dataset.restoredFile;
        updateEvidenceInputState(fileInput);
        scheduleChecklistDraftSave();
        const nextPendingCard = findNextChecklistCard(card, (candidate) => !candidate.dataset.status);
        if (nextPendingCard) {
            focusChecklistCard(nextPendingCard, { focusSelector: ".status-button" });
        }
    });

    updateEvidenceInputState(fileInput);
    hydrateProtectedImages(card);
    return card;
}

function updateProgress() {
    const cards = getChecklistCards();
    const total = cards.length;
    const done = cards.filter((card) => card.dataset.status).length;
    const nc = cards.filter((card) => card.dataset.status === "NC").length;
    const percent = total ? Math.round((done / total) * 100) : 0;
    const remaining = Math.max(total - done, 0);
    const nextPendingCard = cards.find((card) => !card.dataset.status);
    const nextPendingLabel = nextPendingCard ? checklistCardLabel(nextPendingCard) : "";

    elements.checklistProgress.textContent = `${done} DE ${total} AVALIADOS | ${nc} NÃO CONFORMIDADES`;
    elements.progressBar.style.width = `${percent}%`;
    if (!total) {
        elements.checklistSubtitle.textContent = "CARREGANDO ITENS DO CHECKLIST.";
        return;
    }
    if (remaining > 0) {
        const draftLabel = state.currentChecklistDraftUpdatedAt
            ? ` RASCUNHO ${state.currentChecklistDraftRestored ? "RESTAURADO" : "SALVO"} AS ${formatDateTimeShort(state.currentChecklistDraftUpdatedAt)}.`
            : "";
        elements.checklistSubtitle.textContent = `FALTAM ${remaining} ITENS. PROXIMO: ${String(nextPendingLabel || "CONTINUE O PREENCHIMENTO").toUpperCase()}.${draftLabel}`;
        return;
    }
    elements.checklistSubtitle.textContent = nc
        ? `CHECKLIST PREENCHIDO. REVISE AS ${nc} NÃO CONFORMIDADE${nc === 1 ? "" : "S"} E ENVIE QUANDO ESTIVER PRONTO.`
        : "CHECKLIST COMPLETO. TUDO PREENCHIDO E PRONTO PARA ENVIO.";
}

function resetChecklistCardState(card) {
    card.dataset.status = "";
    card.classList.remove("has-nc");
    card.querySelectorAll(".status-button").forEach((button) => button.classList.remove("active"));
    card.querySelector(".nc-fields")?.classList.remove("visible");

    const textarea = card.querySelector("textarea");
    if (textarea) {
        textarea.value = "";
    }

    const fileInput = card.querySelector("input[type='file']");
    if (fileInput) {
        fileInput.value = "";
        delete fileInput.dataset.restoredFile;
        updateEvidenceInputState(fileInput);
    }

    const preview = card.querySelector(".photo-preview");
    if (preview) {
        preview.classList.remove("visible");
        preview.removeAttribute("src");
        if (preview.dataset.objectUrl) {
            URL.revokeObjectURL(preview.dataset.objectUrl);
            delete preview.dataset.objectUrl;
        }
    }
}

async function resetChecklist() {
    if (!state.selectedVehicle) {
        showToast("SELECIONE UM EQUIPAMENTO ANTES DE RESETAR.", true);
        return;
    }

    const vehicleLabel = state.selectedVehicle?.frota || "EQUIPAMENTO";
    const shouldReset = window.confirm(`Deseja resetar o checklist do ${vehicleLabel}?`);
    if (!shouldReset) {
        return;
    }

    Array.from(document.querySelectorAll(".checklist-item-card")).forEach((card) => {
        resetChecklistCardState(card);
    });

    applyChecklistModuleFilter("TODOS");

    await deleteChecklistDraft(state.selectedVehicle.id).catch(() => {});
    updateProgress();
    showToast("CHECKLIST RESETADO.");
}

function findChecklistIssue() {
    const cards = Array.from(document.querySelectorAll(".checklist-item-card"));
    for (const card of cards) {
        const itemLabel = checklistCardLabel(card);
        if (!card.dataset.status) {
            return {
                card,
                message: `SELECIONE OK OU NÃO CONFORMIDADE PARA ${itemLabel}.`,
            };
        }
        if (card.dataset.status === "NC") {
            const textarea = card.querySelector("textarea");
            const fileInput = card.querySelector("input[type='file']");
            const storedDraftFile = fileInput?.dataset?.restoredFile === "true";
            if (!textarea?.value?.trim()) {
                return {
                    card,
                    focusTarget: textarea,
                    message: `INFORME A OBSERVAÇÃO PARA ${itemLabel}.`,
                };
            }
            if (!fileInput?.files?.[0] && !storedDraftFile) {
                return {
                    card,
                    focusTarget: fileInput,
                    message: `ANEXE A EVIDÊNCIA DA NÃO CONFORMIDADE PARA ${itemLabel}.`,
                };
            }
        }
    }
    return null;
}

function checklistCardLabel(card) {
    const itemPrincipal = card?.dataset?.itemPrincipal || card?.dataset?.itemName || "ITEM";
    const itemPart = card?.dataset?.itemPart || "";
    return itemPart ? `${itemPrincipal} - ${itemPart}` : itemPrincipal;
}

function revealChecklistIssue(issue) {
    if (!issue?.card) {
        return;
    }
    const card = issue.card;
    if (card.dataset.module) {
        applyChecklistModuleFilter(card.dataset.module);
    }
    card.classList.add("card-attention");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
        card.classList.remove("card-attention");
    }, 1800);
    const target = issue.focusTarget || card.querySelector(".status-button") || card;
    if (target?.focus) {
        window.setTimeout(() => target.focus(), 250);
    }
}

function classifyModule(itemName) {
    const name = normalizeText(itemName);
    if (includesAny(name, ["farol", "lanterna", "luz", "seta", "pisca", "milha", "posicao"])) {
        return "ILUMINAÇÃO";
    }
    if (includesAny(name, ["painel", "botao", "anomalia", "indicador", "buzina", "cinto", "banco", "ar-condicionado", "parabrisa", "limpador", "retrovisor"])) {
        return "CABINE E PAINEL";
    }
    if (includesAny(name, ["bateria", "oleo", "fluido", "filtro", "radiador", "vazamento", "escapamento", "arla", "tanque", "combustivel", "liquido"])) {
        return "MOTOR E FLUIDOS";
    }
    if (includesAny(name, ["freio", "suspensao", "amortecedor", "pneu", "roda", "parafuso", "eixo", "cubo", "mangueira", "valvula"])) {
        return "FREIOS E RODAGEM";
    }
    if (includesAny(name, ["chassi", "pino rei", "quinta", "trava", "engate", "pe de apoio"])) {
        return "ACOPLAMENTO E ESTRUTURA";
    }
    if (includesAny(name, ["paralamas", "escada", "logo", "frontal", "grade", "parachoque", "placa", "tampa", "protecao", "slides"])) {
        return "EXTERNO E ACESSOS";
    }
    if (includesAny(name, ["extintor", "emergencia", "seguranca"])) {
        return "SEGURANÇA OPERACIONAL";
    }
    return "OUTROS";
}

function includesAny(text, terms) {
    return terms.some((term) => text.includes(normalizeText(term)));
}

function normalizeText(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function makeAbsoluteUrl(path) {
    if (!path) {
        return "";
    }
    if (path.startsWith("http://") || path.startsWith("https://")) {
        return path;
    }
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return `${state.apiBaseUrl}${normalizedPath}`;
}

function buildProtectedImageMarkup(sourceUrl, alt, { className = "", showWhenLoaded = false } = {}) {
    if (!sourceUrl) {
        return "";
    }
    const classAttribute = className ? ` class="${className}"` : "";
    const visibilityAttribute = showWhenLoaded ? ' data-show-when-loaded="true"' : "";
    return `<img${classAttribute} data-protected-src="${escapeHtml(sourceUrl)}"${visibilityAttribute} alt="${escapeHtml(alt)}">`;
}

async function loadProtectedImage(imageElement) {
    if (!(imageElement instanceof HTMLImageElement)) {
        return;
    }
    const sourceUrl = imageElement.dataset.protectedSrc || "";
    if (!sourceUrl) {
        return;
    }

    try {
        const response = await fetch(sourceUrl, {
            headers: {
                Authorization: state.token ? `Bearer ${state.token}` : "",
            },
        });
        if (!response.ok) {
            throw new Error(`Falha ao carregar imagem: ${response.status}`);
        }
        const blob = await response.blob();
        if (imageElement.dataset.objectUrl) {
            URL.revokeObjectURL(imageElement.dataset.objectUrl);
        }
        const objectUrl = URL.createObjectURL(blob);
        imageElement.dataset.objectUrl = objectUrl;
        imageElement.src = objectUrl;
        if (imageElement.dataset.showWhenLoaded === "true" || imageElement.classList.contains("photo-preview")) {
            imageElement.classList.add("visible");
        }
        imageElement.dataset.zoomLabel = imageElement.alt || "VISUALIZAÇÃO AMPLIADA DA EVIDÊNCIA";
        imageElement.classList.remove("photo-load-error");
    } catch {
        imageElement.classList.add("photo-load-error");
        if (imageElement.classList.contains("photo-preview")) {
            imageElement.classList.remove("visible");
        }
    }
}

function hydrateProtectedImages(container = document) {
    if (!container?.querySelectorAll) {
        return;
    }
    container.querySelectorAll("img[data-protected-src]").forEach((imageElement) => {
        if (imageElement.dataset.imageHydrated === "true") {
            return;
        }
        imageElement.dataset.imageHydrated = "true";
        void loadProtectedImage(imageElement);
    });
}

async function uploadImage(file, itemName, moduleName) {
    return uploadEvidence(file, state.selectedVehicle.frota, itemName, "evidencia_nc", moduleName);
}

async function prepareImageForUpload(file) {
    if (!file || !file.type.startsWith("image/")) {
        return file;
    }
    const maxSide = 1280;
    const quality = 0.72;
    try {
        const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
        const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
        const width = Math.max(1, Math.round(bitmap.width * scale));
        const height = Math.max(1, Math.round(bitmap.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d", { alpha: false });
        context.drawImage(bitmap, 0, 0, width, height);
        bitmap.close?.();
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
        if (!blob) {
            return file;
        }
        const originalName = file.name.replace(/\.[^.]+$/, "");
        return new File([blob], `${originalName || "foto"}-compactada.jpg`, {
            type: "image/jpeg",
            lastModified: Date.now(),
        });
    } catch {
        return file;
    }
}

async function uploadEvidence(file, vehicleName, itemName, photoType, moduleName) {
    const uploadFile = await prepareImageForUpload(file);
    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("vehicle", vehicleName);
    formData.append("item", itemName);
    formData.append("module", moduleName);
    formData.append("tipo_foto", photoType);
    formData.append("user", state.user.login);

    const response = await fetch(`${state.apiBaseUrl}/upload`, {
        method: "POST",
        headers: {
            Authorization: `Bearer ${state.token}`,
        },
        body: formData,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || (Object.prototype.hasOwnProperty.call(body, "success") && body.success === false)) {
        throw new Error(body.error || `FALHA AO ENVIAR IMAGEM DO ITEM ${itemName}.`);
    }
    const payload = Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    return payload.path;
}

async function collectChecklistDraft() {
    if (!state.selectedVehicle) {
        throw new Error("SELECIONE UM EQUIPAMENTO ANTES DE ENVIAR.");
    }

    const cards = Array.from(document.querySelectorAll(".checklist-item-card"));
    const itens = [];
    const storedDraft = await getChecklistDraft(state.selectedVehicle.id).catch(() => null);
    const storedItems = new Map((storedDraft?.items || []).map((item) => [normalizeText(item.item_nome), item]));

    for (const card of cards) {
        const status = card.dataset.status;
        const itemLabel = checklistCardLabel(card);
        if (!status) {
            throw new Error(`SELECIONE OK OU NÃO CONFORMIDADE PARA ${itemLabel}.`);
        }

        const item = {
            item_nome: card.dataset.itemName,
            item_principal: card.dataset.itemPrincipal || card.dataset.itemName,
            parte: card.dataset.itemPart || "",
            tipo_agrupamento: card.dataset.groupingType || "simples",
            module: card.dataset.module,
            status,
        };

        if (status === "NC") {
            const textarea = card.querySelector("textarea");
            const fileInput = card.querySelector("input[type='file']");
            const restoredItem = storedItems.get(normalizeText(card.dataset.itemName));
            const file = fileInput.files[0] || restoredItem?.foto_antes_file;

            if (!textarea.value.trim()) {
                throw new Error(`INFORME A OBSERVAÇÃO PARA ${itemLabel}.`);
            }
            if (!file) {
                throw new Error(`ANEXE A EVIDÊNCIA DA NÃO CONFORMIDADE PARA ${itemLabel}.`);
            }

            item.observacao = textarea.value.trim();
            item.foto_antes_file = file;
            item.foto_antes_name = file.name;
        }

        itens.push(item);
    }

    return {
        vehicle: {
            id: state.selectedVehicle.id,
            frota: state.selectedVehicle.frota,
            placa: state.selectedVehicle.placa,
            modelo: state.selectedVehicle.modelo,
            tipo: state.selectedVehicle.tipo,
        },
        itens,
        createdAt: new Date().toISOString(),
    };
}

async function sendChecklistDraft(draft) {
    const itens = [];
    for (const draftItem of draft.itens) {
        const item = {
            item_nome: draftItem.item_nome,
            item_principal: draftItem.item_principal || draftItem.item_nome,
            parte: draftItem.parte || "",
            tipo_agrupamento: draftItem.tipo_agrupamento || "simples",
            status: draftItem.status,
        };

        if (draftItem.status === "NC") {
            item.observacao = draftItem.observacao || "";
            if (draftItem.foto_antes) {
                item.foto_antes = draftItem.foto_antes;
            } else if (draftItem.foto_antes_file) {
                item.foto_antes = await uploadEvidence(
                    draftItem.foto_antes_file,
                    draft.vehicle.frota || "EQUIPAMENTO",
                    draftItem.item_nome,
                    "evidencia_nc",
                    draftItem.module || classifyModule(draftItem.item_nome),
                );
            }
        }
        itens.push(item);
    }

    return apiFetch("/checklist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            vehicle_id: draft.vehicle.id,
            itens,
        }),
    });
}

function showChecklistSuccess(draft, result = null, queued = false) {
    const totalNc = result?.total_nc || draft.itens.filter((item) => item.status === "NC").length;
    const when = result?.created_at || draft.createdAt;
    elements.successSummary.innerHTML = `
        <strong>${escapeHtml(draft.vehicle.frota)}</strong>
        <span>${queued ? "SALVO OFFLINE EM" : "ENVIADO EM"} ${formatDateTime(when)}</span>
        <span>NÃO CONFORMIDADES REGISTRADAS: ${totalNc}</span>
        ${queued ? "<span>SERÁ SINCRONIZADO AUTOMATICAMENTE QUANDO A CONEXÃO VOLTAR.</span>" : ""}
    `;
    deleteChecklistDraft(draft.vehicle.id).catch(() => {});
    setActiveScreen("success");
}

async function submitChecklist() {
    const issue = findChecklistIssue();
    if (issue) {
        revealChecklistIssue(issue);
        showToast(issue.message, true);
        return;
    }

    elements.submitChecklist.disabled = true;
    elements.submitChecklist.textContent = "ENVIANDO...";

    try {
        const draft = await collectChecklistDraft();

        if (!navigator.onLine) {
            await addChecklistToQueue(draft, "CHECKLIST SALVO SEM CONEXÃO.");
            showChecklistSuccess(draft, null, true);
            showToast("CHECKLIST SALVO OFFLINE.");
            return;
        }

        try {
            const result = await sendChecklistDraft(draft);
            showChecklistSuccess(draft, result, false);
            showToast("CHECKLIST ENVIADO COM SUCESSO.");
            syncPendingChecklists({ silent: true });
        } catch (error) {
            if (!isOfflineError(error)) {
                throw error;
            }
            await addChecklistToQueue(draft, "FALHA DE CONEXÃO NO ENVIO.");
            showChecklistSuccess(draft, null, true);
            showToast("CONEXÃO FALHOU. CHECKLIST FICOU NA FILA OFFLINE.");
        }
    } catch (error) {
        showToast(error.message, true);
    } finally {
        elements.submitChecklist.disabled = false;
        elements.submitChecklist.textContent = "ENVIAR CHECKLIST";
    }
}

async function logout() {
    try {
        if (state.token) {
            await apiFetch("/logout", { method: "POST" });
        }
    } catch (error) {
        console.warn("Falha ao registrar logout:", error);
    }
    state.token = "";
    state.user = null;
    state.selectedVehicle = null;
    if (sessionInactivityTimer) {
        window.clearTimeout(sessionInactivityTimer);
        sessionInactivityTimer = null;
    }
    closePasswordResetModal();
    clearSession();
    setLoginStatus("");
    resetLoginControls();
    setActiveScreen("login");
}

function resetPasswordModalFields() {
    if (elements.passwordChangeForm) {
        elements.passwordChangeForm.reset();
    }
}

function openPasswordResetModal() {
    if (!elements.passwordModal) {
        showToast("TELA DE SENHA INDISPONIVEL.", true);
        return;
    }
    passwordModalFocusOrigin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    resetPasswordModalFields();
    elements.passwordModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    window.setTimeout(() => {
        elements.passwordCurrentInput?.focus();
    }, 0);
}

function closePasswordResetModal() {
    if (!elements.passwordModal || elements.passwordModal.classList.contains("hidden")) {
        return;
    }
    elements.passwordModal.classList.add("hidden");
    document.body.classList.remove("modal-open");
    resetPasswordModalFields();
    if (passwordModalFocusOrigin && document.contains(passwordModalFocusOrigin)) {
        passwordModalFocusOrigin.focus();
    }
    passwordModalFocusOrigin = null;
}

function requestPasswordReset() {
    openPasswordResetModal();
}

function openResetRequestModal() {
    elements.resetRequestLogin.value = document.getElementById("login")?.value || "";
    elements.resetRequestModal?.classList.remove("hidden");
    document.body.classList.add("modal-open");
    elements.resetRequestLogin?.focus();
}

function closeResetRequestModal() {
    elements.resetRequestModal?.classList.add("hidden");
    if (elements.firstAccessModal?.classList.contains("hidden") && elements.passwordModal?.classList.contains("hidden")) {
        document.body.classList.remove("modal-open");
    }
}

async function submitResetRequest(event) {
    event.preventDefault();
    const loginValue = elements.resetRequestLogin?.value?.trim() || "";
    if (!loginValue) return;
    try {
        await fetchWithTimeout(`${state.apiBaseUrl}/auth/reset-solicitacoes`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ login: loginValue }),
        }, 15000);
        closeResetRequestModal();
        setLoginStatus("Solicitação enviada ao administrador.");
        showToast("SOLICITAÇÃO ENVIADA.");
    } catch (error) {
        setLoginStatus(error.message || "Não foi possível solicitar o reset.", true);
    }
}

function openFirstAccessModal() {
    if (!elements.firstAccessModal) return;
    elements.firstAccessModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    document.body.classList.add("first-access-only");
    elements.firstAccessStatus.textContent = "";
    resetFirstAccessPhoto();
    clearFirstAccessSignature();
}

function stopFirstAccessCamera() {
    state.firstAccessCameraStream?.getTracks().forEach((track) => track.stop());
    state.firstAccessCameraStream = null;
    if (elements.firstAccessCameraVideo) elements.firstAccessCameraVideo.srcObject = null;
    elements.firstAccessCameraPanel?.classList.add("hidden");
    elements.firstAccessCameraOpen?.classList.remove("hidden");
}

function resetFirstAccessPhoto() {
    stopFirstAccessCamera();
    state.firstAccessPhotoFile = null;
    if (elements.firstAccessPhoto) elements.firstAccessPhoto.value = "";
    elements.firstAccessPhotoPreview?.classList.add("hidden");
    elements.firstAccessPhotoFile?.classList.remove("hidden");
    if (elements.firstAccessPhotoPreviewImage) {
        if (elements.firstAccessPhotoPreviewImage.dataset.previewUrl) URL.revokeObjectURL(elements.firstAccessPhotoPreviewImage.dataset.previewUrl);
        delete elements.firstAccessPhotoPreviewImage.dataset.previewUrl;
        elements.firstAccessPhotoPreviewImage.removeAttribute("src");
    }
}

function showFirstAccessPhoto(file) {
    if (!file) return;
    state.firstAccessPhotoFile = file;
    const previewUrl = URL.createObjectURL(file);
    if (elements.firstAccessPhotoPreviewImage.dataset.previewUrl) URL.revokeObjectURL(elements.firstAccessPhotoPreviewImage.dataset.previewUrl);
    elements.firstAccessPhotoPreviewImage.dataset.previewUrl = previewUrl;
    elements.firstAccessPhotoPreviewImage.src = previewUrl;
    elements.firstAccessPhotoPreview?.classList.remove("hidden");
    elements.firstAccessCameraOpen?.classList.add("hidden");
    elements.firstAccessPhotoFile?.classList.add("hidden");
}

async function openFirstAccessCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
        elements.firstAccessPhoto?.click();
        return;
    }
    try {
        stopFirstAccessCamera();
        state.firstAccessCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "user" }, width: { ideal: 1280 }, height: { ideal: 1280 } }, audio: false });
        elements.firstAccessCameraVideo.srcObject = state.firstAccessCameraStream;
        elements.firstAccessCameraPanel?.classList.remove("hidden");
        elements.firstAccessCameraOpen?.classList.add("hidden");
    } catch (error) {
        elements.firstAccessPhoto?.click();
        showToast("A câmera não foi liberada. Escolha ou tire a foto pelo recurso do aparelho.", true);
    }
}

async function captureFirstAccessPhoto() {
    const video = elements.firstAccessCameraVideo;
    if (!video?.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.translate(canvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (blob) showFirstAccessPhoto(new File([blob], "foto-perfil.jpg", { type: "image/jpeg" }));
    stopFirstAccessCamera();
}

function clearFirstAccessSignature() {
    const canvas = elements.firstAccessSignature;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = "#0b56b5";
    context.lineWidth = 3;
    context.lineCap = "round";
}

function signatureDataUrl() {
    const canvas = elements.firstAccessSignature;
    if (!canvas) return "";
    const pixels = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    let ink = false;
    for (let index = 0; index < pixels.length; index += 4) {
        if (pixels[index] < 240 || pixels[index + 1] < 240 || pixels[index + 2] < 240) { ink = true; break; }
    }
    return ink ? canvas.toDataURL("image/png") : "";
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function submitFirstAccess() {
    const photo = state.firstAccessPhotoFile || elements.firstAccessPhoto?.files?.[0];
    const signature = signatureDataUrl();
    if (!photo) { elements.firstAccessStatus.textContent = "Tire uma foto para continuar."; return; }
    if (!signature) { elements.firstAccessStatus.textContent = "Faça sua assinatura no quadro."; return; }
    elements.firstAccessSubmit.disabled = true;
    elements.firstAccessStatus.textContent = "SALVANDO...";
    try {
        const photoDataUrl = await readFileAsDataUrl(photo);
        await apiFetch("/usuarios/me/primeiro-acesso", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ foto_data_url: photoDataUrl, assinatura_data_url: signature }),
        });
        state.welcomePhotoData = photoDataUrl;
        state.justCompletedFirstAccess = true;
        stopFirstAccessCamera();
        state.firstAccessRequired = false;
        if (state.user) { state.user.first_access_required = false; saveSession(state.token, state.user); }
        elements.firstAccessModal.classList.add("hidden");
        document.body.classList.remove("first-access-only");
        document.body.classList.remove("modal-open");
        await enterAuthenticatedApp();
    } catch (error) {
        elements.firstAccessStatus.textContent = error.message || "Não foi possível concluir o primeiro acesso.";
    } finally { elements.firstAccessSubmit.disabled = false; }
}

function maybeOpenWelcomeModal() {
    if (!state.justCompletedFirstAccess || !elements.welcomeModal) return;
    const name = String(state.user?.nome || "COLABORADOR").trim();
    const firstName = name.split(/\s+/)[0] || "COLABORADOR";
    elements.welcomeMessage.textContent = `${firstName}, seu acesso foi confirmado. Estamos felizes em ter você no sistema.`;
    elements.welcomeInitials.textContent = firstName.slice(0, 2).toUpperCase();
    if (state.welcomePhotoData) {
        elements.welcomePhoto.src = state.welcomePhotoData;
        elements.welcomePhotoWrap.classList.add("has-photo");
    }
    elements.welcomeModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    state.justCompletedFirstAccess = false;
}

function closeWelcomeModal() {
    elements.welcomeModal?.classList.add("hidden");
    document.body.classList.remove("modal-open");
}

function backToLoginFromFirstAccess() {
    stopFirstAccessCamera();
    elements.firstAccessModal?.classList.add("hidden");
    document.body.classList.remove("first-access-only", "modal-open");
    state.token = "";
    state.user = null;
    state.firstAccessRequired = false;
    state.justCompletedFirstAccess = false;
    clearSession();
    resetLoginControls();
    setActiveScreen("login");
    setLoginStatus("Acesso cancelado. Informe o usuário e a senha para entrar novamente.", true);
}

async function submitPasswordReset(event) {
    event.preventDefault();

    const currentPassword = elements.passwordCurrentInput?.value || "";
    const newPassword = elements.passwordNewInput?.value || "";
    const confirmPassword = elements.passwordConfirmInput?.value || "";

    if (!currentPassword) {
        showToast("INFORME A SENHA ATUAL.", true);
        elements.passwordCurrentInput?.focus();
        return;
    }
    if (!newPassword) {
        showToast("INFORME A NOVA SENHA.", true);
        elements.passwordNewInput?.focus();
        return;
    }
    if (!confirmPassword) {
        showToast("CONFIRME A NOVA SENHA.", true);
        elements.passwordConfirmInput?.focus();
        return;
    }
    if (newPassword !== confirmPassword) {
        showToast("AS SENHAS NÃO CONFEREM.", true);
        elements.passwordConfirmInput?.focus();
        return;
    }

    if (elements.passwordChangeSubmit) {
        elements.passwordChangeSubmit.disabled = true;
        elements.passwordChangeSubmit.textContent = "SALVANDO...";
    }
    if (elements.passwordChangeCancel) {
        elements.passwordChangeCancel.disabled = true;
    }

    try {
        await apiFetch("/usuarios/me/senha", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                senha_atual: currentPassword,
                nova_senha: newPassword,
            }),
        });
        showToast("SENHA ATUALIZADA COM SUCESSO.");
        closePasswordResetModal();
    } catch (error) {
        showToast(error.message || "NÃO FOI POSSÍVEL ATUALIZAR A SENHA.", true);
    } finally {
        if (elements.passwordChangeSubmit) {
            elements.passwordChangeSubmit.disabled = false;
            elements.passwordChangeSubmit.textContent = "Salvar senha";
        }
        if (elements.passwordChangeCancel) {
            elements.passwordChangeCancel.disabled = false;
        }
    }
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function on(element, eventName, handler) {
    if (element) {
        element.addEventListener(eventName, handler);
    }
}

on(elements.topbarHomeButton, "click", () => {
    closeTopbarNavigation();
    renderHome();
    setActiveScreen("home");
});
on(elements.themeToggleButton, "click", toggleTheme);
on(elements.topbarMobileToggle, "click", () => {
    closeTopbarSettingsMenu();
    const open = !elements.topbarNavigation?.classList.contains("is-open");
    elements.topbarNavigation?.classList.toggle("is-open", open);
    elements.topbarMobileToggle?.setAttribute("aria-expanded", String(open));
    if (!open) setTopbarModuleOpen("", false);
});
on(elements.topbarLogoutButton, "click", logout);
on(elements.adminUserForm, "submit", saveAdminUser);
on(elements.adminUserCancel, "click", closeAdminUserModal);
on(elements.adminUserModal, "click", (event) => {
    if (event.target?.dataset?.closeAdminUser === "true") closeAdminUserModal();
});
on(elements.adminSettingsFeedbackContent, "click", (event) => {
    const button = event.target.closest("[data-admin-user-edit]");
    if (button) openAdminUserModal(Number(button.dataset.adminUserEdit));
});
elements.topbarModuleTriggers.forEach((trigger) => on(trigger, "click", () => {
    closeTopbarSettingsMenu();
    const moduleKey = trigger.dataset.topbarModuleTrigger || "";
    const module = trigger.closest(".topbar-module");
    setTopbarModuleOpen(moduleKey, !module?.classList.contains("is-open"));
}));
elements.topbarActionButtons.forEach((button) => on(button, "click", () => openTopbarAction(button.dataset.topbarAction)));
document.addEventListener("click", (event) => {
    if (appTopbar && !appTopbar.contains(event.target)) {
        closeTopbarNavigation();
        return;
    }
    if (!elements.topbarSettingsMenu?.contains(event.target) && event.target !== elements.topbarUserSettingsButton) {
        closeTopbarSettingsMenu();
    }
    if (!elements.topbarNotificationsMenu?.contains(event.target) && event.target !== elements.topbarNotificationsButton) {
        closeTopbarNotificationsMenu();
    }
});

on(elements.loginForm, "submit", async (event) => {
    event.preventDefault();
    await handleLoginSubmit();
});

async function handleLoginSubmit() {
    state.apiBaseUrl = elements.apiBaseUrl.value.replace(/\/$/, "");
    localStorage.setItem("apiBaseUrl", state.apiBaseUrl);
    elements.loginButton.disabled = true;
    elements.loginButton.textContent = "Entrando...";

    try {
        await login({
            login: document.getElementById("login").value.trim().toLowerCase(),
            senha: document.getElementById("password").value,
        });
        await enterAuthenticatedApp();
        showToast("LOGIN REALIZADO COM SUCESSO.");
    } catch (error) {
        setLoginStatus(`Erro de acesso: ${error.message}`, true);
        showToast(error.message, true);
    } finally {
        elements.loginButton.disabled = false;
        elements.loginButton.textContent = "Entrar";
    }
}

on(elements.loginButton, "click", handleLoginSubmit);
on(elements.forgotPasswordButton, "click", openResetRequestModal);
on(elements.resetRequestForm, "submit", submitResetRequest);
on(elements.resetRequestClose, "click", closeResetRequestModal);
on(elements.resetRequestModal, "click", (event) => {
    if (event.target?.dataset?.closeResetRequest === "true") closeResetRequestModal();
});
on(elements.firstAccessClear, "click", clearFirstAccessSignature);
on(elements.firstAccessBack, "click", backToLoginFromFirstAccess);
on(elements.firstAccessCameraOpen, "click", openFirstAccessCamera);
on(elements.firstAccessCameraCapture, "click", captureFirstAccessPhoto);
on(elements.firstAccessPhotoFile, "click", () => elements.firstAccessPhoto?.click());
on(elements.firstAccessPhoto, "change", () => showFirstAccessPhoto(elements.firstAccessPhoto.files?.[0]));
on(elements.firstAccessPhotoRetake, "click", resetFirstAccessPhoto);
on(elements.firstAccessSubmit, "click", submitFirstAccess);
on(elements.welcomeStart, "click", closeWelcomeModal);

if (elements.firstAccessSignature) {
    const canvas = elements.firstAccessSignature;
    let drawing = false;
    const point = (event) => {
        const rect = canvas.getBoundingClientRect();
        return { x: (event.clientX - rect.left) * canvas.width / rect.width, y: (event.clientY - rect.top) * canvas.height / rect.height };
    };
    canvas.addEventListener("pointerdown", (event) => { drawing = true; canvas.setPointerCapture(event.pointerId); const p = point(event); canvas.getContext("2d").beginPath(); canvas.getContext("2d").moveTo(p.x, p.y); });
    canvas.addEventListener("pointermove", (event) => { if (!drawing) return; const p = point(event); const context = canvas.getContext("2d"); context.lineTo(p.x, p.y); context.stroke(); });
    ["pointerup", "pointercancel", "pointerleave"].forEach((name) => canvas.addEventListener(name, () => { drawing = false; }));
    clearFirstAccessSignature();
}
on(elements.vehicleSearch, "input", () => {
    if (normalizeText(elements.vehicleSearch.value)) {
        state.vehicleFamilyFilter = "";
    }
    renderVehicles();
});
on(elements.assetAccessToggle, "click", () => toggleAssetAccessPanel());
elements.vehicleFamilyCards.forEach((card) => {
    on(card, "click", () => {
        const family = String(card.dataset.vehicleFamily || "").toUpperCase();
        state.vehicleFamilyFilter = state.vehicleFamilyFilter === family ? "" : family;
        renderVehicleFamilyScreen();
        setActiveScreen("vehicleFamily");
    });
});
on(elements.openChecklistMenu, "click", openChecklistMenu);
on(elements.openChecklistHistoryMenu, "click", openChecklistHistoryMenu);
on(elements.openChecklistCatalogMenu, "click", openChecklistCatalogMenu);
on(elements.checklistCatalogNewButton, "click", () => openChecklistCatalogModal());
on(elements.checklistCatalogSearch, "input", () => {
    state.checklistCatalogAdmin.filters.search = elements.checklistCatalogSearch.value;
    renderChecklistCatalogAdmin();
});
on(elements.checklistCatalogTypeFilter, "change", () => {
    state.checklistCatalogAdmin.filters.type = elements.checklistCatalogTypeFilter.value;
    renderChecklistCatalogAdmin();
});
on(elements.checklistCatalogActiveFilter, "change", () => {
    state.checklistCatalogAdmin.filters.active = elements.checklistCatalogActiveFilter.value;
    renderChecklistCatalogAdmin();
});
on(elements.checklistCatalogClearFilters, "click", () => {
    state.checklistCatalogAdmin.filters = { search: "", type: "", active: "true" };
    elements.checklistCatalogSearch.value = "";
    elements.checklistCatalogTypeFilter.value = "";
    elements.checklistCatalogActiveFilter.value = "true";
    renderChecklistCatalogAdmin();
});
on(elements.checklistCatalogGroupType, "change", syncChecklistCatalogGroupingFields);
on(elements.checklistCatalogForm, "submit", submitChecklistCatalogItem);
on(elements.checklistCatalogCancel, "click", closeChecklistCatalogModal);
on(elements.checklistCatalogModal, "click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeChecklistCatalog === "true") {
        closeChecklistCatalogModal();
    }
});
on(elements.checklistCatalogList, "click", (event) => {
    const button = event.target instanceof HTMLElement
        ? event.target.closest("[data-checklist-catalog-action]")
        : null;
    if (!button) return;
    const itemId = Number(button.dataset.checklistCatalogId || 0);
    const item = state.checklistCatalogAdmin.items.find((entry) => Number(entry.id) === itemId);
    if (!item) return;
    if (button.dataset.checklistCatalogAction === "edit") openChecklistCatalogModal(item);
    if (button.dataset.checklistCatalogAction === "activate") changeChecklistCatalogItemStatus(item, true);
    if (button.dataset.checklistCatalogAction === "inactivate") changeChecklistCatalogItemStatus(item, false);
});
on(elements.openActivitiesMenu, "click", openActivitiesMenu);
on(elements.openWashesMenu, "click", openWashesMenu);
on(elements.openNonConformitiesMenu, "click", openNonConformitiesMenu);
on(elements.openMaintenanceMenu, "click", openMaintenanceMenu);
on(elements.openPlanningMenu, "click", openPlanningMenu);
on(elements.openPreventivesMenu, "click", openPreventivesMenu);
on(elements.openAvailabilityMenu, "click", openAvailabilityMenu);
on(elements.availabilitySearch, "input", () => {
    state.availabilityFilters.search = elements.availabilitySearch.value;
    renderAvailability();
});
on(elements.availabilityStatusFilter, "change", () => {
    state.availabilityFilters.status = elements.availabilityStatusFilter.value;
    renderAvailability();
});
elements.availabilityFamilyTabs.forEach((button) => {
    on(button, "click", () => {
        state.availabilityFilters.family = String(button.dataset.availabilityFamily || "TODOS").toUpperCase();
        renderAvailability();
    });
});
on(elements.availabilityClearFilters, "click", () => {
    state.availabilityFilters = { search: "", family: "TODOS", status: "" };
    elements.availabilitySearch.value = "";
    elements.availabilityStatusFilter.value = "";
    renderAvailability();
});
on(elements.openTechnicalInspectionsMenu, "click", openTechnicalInspectionsMenu);
on(elements.openEmergenciesMenu, "click", openEmergenciesMenu);
on(elements.openTechnicalLibraryMenu, "click", openTechnicalLibraryMenu);
on(elements.openMaintenanceDashboardMenu, "click", () => {
    window.location.href = "./dashboard-manutencao/";
});
on(elements.openHrJourneyMenu, "click", openHrJourneyMenu);
on(elements.openRhAdminMenu, "click", openRhAdminMenu);
on(elements.openAdminSettingsMenu, "click", openAdminSettings);
on(elements.openAdminCatalogsMenu, "click", openAdminCatalogs);
on(elements.openMmpStockMenu, "click", openMmpStockMenu);
on(elements.openPurchasesMenu, "click", openPurchasesMenu);
on(elements.openPurchasesReportsMenu, "click", () => openModuleReports("purchases"));
on(elements.openEquipmentReportsMenu, "click", () => openModuleReports("equipment"));
on(elements.openMaintenanceReportsMenu, "click", () => openModuleReports("maintenance"));
on(elements.moduleReportsList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-module-report-action]") : null;
    if (button) openModuleReportAction(button.dataset.moduleReportAction);
});
elements.rhAdminTabs.forEach((button) => on(button, "click", () => setRhAdminTab(button.dataset.rhAdminTab)));
on(elements.rhAdminRefreshOverview, "click", loadRhAdminOverview);
on(elements.rhAdminNewEmployee, "click", () => openRhAdminEmployeeModal());
on(elements.rhAdminRefreshEmployees, "click", loadRhAdminEmployees);
on(elements.rhAdminEmployeeSearch, "input", renderRhAdminEmployees);
on(elements.rhAdminEmployeeStatus, "change", renderRhAdminEmployees);
on(elements.rhAdminEmployeeForm, "submit", submitRhAdminEmployee);
on(elements.rhAdminEmployeeCancel, "click", closeRhAdminEmployeeModal);
on(elements.rhAdminEmployeeModal, "click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeRhAdminEmployee === "true") closeRhAdminEmployeeModal();
});
on(elements.adminSettingsGrid, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-admin-settings-action]") : null;
    if (button) openAdminSettingsAction(button.dataset.adminSettingsAction);
});
on(elements.adminCatalogsGrid, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-admin-catalog-action]") : null;
    if (button) openAdminCatalogAction(button.dataset.adminCatalogAction);
});
on(elements.rhAdminEmployeesList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-rh-admin-edit-employee]") : null;
    if (!button) return;
    const employee = state.rhAdmin.employees.find((row) => Number(row.id) === Number(button.dataset.rhAdminEditEmployee));
    if (employee) openRhAdminEmployeeModal(employee);
});
document.querySelectorAll("[data-rh-admin-open]").forEach((button) => on(button, "click", () => {
    const target = button.dataset.rhAdminOpen;
    if (target === "overview") {
        setRhAdminTab("overview");
    } else if (target === "attendance") {
        showToast("A EDIÇÃO DE FREQUÊNCIA SERÁ CONECTADA NA PRÓXIMA ETAPA.");
    } else if (target === "absenteeism") {
        openAbsenteeismMenu();
    } else if (target === "schedule") {
        openSpecialScheduleMenu();
    }
}));
on(elements.openWeeklyDsrMenu, "click", openWeeklyDsrMenu);
on(elements.openSpecialScheduleMenu, "click", openSpecialScheduleMenu);
on(elements.openAbsenteeismMenu, "click", openAbsenteeismMenu);
on(elements.emergencyCreateForm, "submit", submitEmergency);
on(elements.washPrevMonth, "click", () => changeWashMonth(-1));
on(elements.washNextMonth, "click", () => changeWashMonth(1));
on(elements.washExportPdfButton, "click", exportWashMonthPdf);
on(elements.maintenancePrevMonth, "click", () => changeMaintenanceMonth(-1));
on(elements.maintenanceNextMonth, "click", () => changeMaintenanceMonth(1));
elements.maintenanceViewButtons.forEach((button) => {
    on(button, "click", () => {
        state.maintenanceDashboardView = button.dataset.maintenanceView || "KANBAN";
        renderMaintenance();
    });
});
elements.maintenanceDashboardFilterButtons.forEach((button) => {
    on(button, "click", () => {
        state.maintenanceDashboardFilter = button.dataset.maintenanceDashboardFilter || "TODOS";
        renderMaintenance();
    });
});
elements.maintenanceFamilyTabs.forEach((button) => {
    on(button, "click", async () => {
        state.maintenanceFamilyFilter = String(button.dataset.maintenanceFamily || "TODOS").toUpperCase();
        state.selectedMaintenanceDate = "";
        if (state.token && navigator.onLine) {
            try {
                await loadMaintenanceOverview();
                localStorage.setItem(maintenanceOfflineCacheKey(), JSON.stringify(state.maintenanceOverview));
            } catch (error) {
                showToast(`FILTRO ${state.maintenanceFamilyFilter} APLICADO LOCALMENTE: ${error.message || "sem conexão"}.`, true);
            }
        }
        renderMaintenance();
    });
});
on(elements.syncNowButton, "click", async () => {
    await syncPendingChecklists({ silent: false });
    await syncPendingMobileOperations({ silent: false });
});
on(elements.openAssetCodeButton, "click", openMobileAssetFromInput);
on(elements.assetAccessCode, "keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        openMobileAssetFromInput();
    }
});
on(elements.scanAssetQrButton, "click", scanMobileAssetQr);
on(elements.scanAssetNfcButton, "click", scanMobileAssetNfc);
on(elements.cloudBackupButton, "click", createCloudBackup);
on(elements.homeLogoutButton, "click", logout);
on(elements.topbarUserSettingsButton, "click", (event) => {
    event.stopPropagation();
    toggleTopbarSettingsMenu();
});
on(elements.topbarNotificationsButton, "click", (event) => {
    event.stopPropagation();
    toggleTopbarNotificationsMenu();
});
on(elements.topbarNotificationsMarkRead, "click", markInternalNotificationsRead);
on(elements.topbarNotificationsClear, "click", clearInternalNotifications);
on(elements.topbarNotificationsOriginFilter, "change", updateNotificationFilters);
on(elements.topbarNotificationsPriorityFilter, "change", updateNotificationFilters);
on(elements.topbarNotificationsFromFilter, "change", updateNotificationFilters);
on(elements.topbarNotificationsToFilter, "change", updateNotificationFilters);
on(elements.topbarNotificationsResetFilters, "click", clearNotificationFilters);
on(elements.topbarSettingsMenu, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-settings-action]") : null;
    if (button) openTopbarSettingsAction(button.dataset.settingsAction || "");
});
on(elements.topbarLanguageSelect, "change", () => {
    applyLanguage(elements.topbarLanguageSelect.value);
    showToast(elements.topbarLanguageSelect.value === "en-US" ? "IDIOMA ENGLISH SELECIONADO. TRADUÇÃO EM PREPARAÇÃO." : "IDIOMA PORTUGUÊS (BRASIL) SELECIONADO.");
});
on(elements.passwordChangeForm, "submit", submitPasswordReset);
on(elements.passwordChangeCancel, "click", closePasswordResetModal);
on(elements.passwordModal, "click", (event) => {
    if (event.target?.dataset?.closePasswordModal === "true") {
        closePasswordResetModal();
    }
});
on(elements.photoViewerModal, "click", (event) => {
    if (event.target?.dataset?.closePhotoViewer === "true") {
        closePhotoViewer();
    }
});
on(elements.vehiclesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.activitiesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.washesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.checklistHistoryBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.checklistCatalogBackButton, "click", () => {
    closeChecklistCatalogModal();
    renderHome();
    setActiveScreen("home");
});
on(elements.checklistHistoryEquipmentSearch, "input", updateChecklistHistoryEquipmentSearch);
on(elements.checklistHistoryTypeFilter, "change", scheduleChecklistHistoryFilters);
on(elements.checklistHistoryStartDate, "change", scheduleChecklistHistoryFilters);
on(elements.checklistHistoryEndDate, "change", scheduleChecklistHistoryFilters);
on(elements.maintenanceBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.planningBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.planningPrevMonth, "click", () => changeMaintenanceMonth(-1));
on(elements.planningNextMonth, "click", () => changeMaintenanceMonth(1));
on(elements.planningRefreshButton, "click", openPlanningMenu);
elements.planningFilterButtons.forEach((button) => on(button, "click", () => {
    state.planningStatusFilter = String(button.dataset.planningFilter || "ABERTAS");
    renderPlanning();
}));
on(elements.preventivesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.hrJourneyBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.rhAdminBackButton, "click", () => {
    closeRhAdminEmployeeModal();
    renderHome();
    setActiveScreen("home");
});
on(elements.adminSettingsBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.mmpStockBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.purchasesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.purchasesWorkflowNav, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchases-area]") : null;
    if (button) setPurchasesArea(button.dataset.purchasesArea);
});
document.querySelectorAll("[data-purchases-view-target] [data-purchases-view-option]").forEach((button) => {
    button.addEventListener("click", () => setPurchasesView(button.closest("[data-purchases-view-target]")?.dataset.purchasesViewTarget, button.dataset.purchasesViewOption));
});
on(elements.adminCatalogsBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.purchasesProviderForm, "submit", submitPurchaseProvider);
on(elements.purchasesProviderNew, "click", () => openPurchaseProviderEditor());
on(elements.purchasesProviderCancel, "click", resetPurchaseProviderForm);
on(elements.purchasesProviderList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-provider-edit]") : null;
    if (!button) return;
    const provider = state.purchases.providers.find((row) => Number(row.id) === Number(button.dataset.purchaseProviderEdit));
    if (provider) editPurchaseProvider(provider);
});
on(elements.purchasesMaterialHistoryButton, "click", loadMaterialPurchaseHistory);
on(elements.purchasesRequestSearch, "input", renderPurchaseRequests);
on(elements.purchasesRequestStatus, "change", renderPurchaseRequests);
on(elements.purchasesRequestSort, "change", renderPurchaseRequests);
on(elements.purchasesRequestNew, "click", openPurchaseRequestModal);
on(elements.purchaseRequestAddItem, "click", () => addPurchaseRequestItem());
on(elements.purchaseRequestItems, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-remove-item]") : null;
    if (!button) return;
    const rows = elements.purchaseRequestItems.querySelectorAll(".purchase-request-item-row");
    if (rows.length <= 1) { showToast("A SC precisa manter pelo menos um item.", true); return; }
    button.closest(".purchase-request-item-row")?.remove();
});
on(elements.purchaseRequestItems, "change", (event) => {
    const select = event.target instanceof HTMLElement ? event.target.closest(".purchase-request-item-type") : null;
    if (select) togglePurchaseRequestItemType(select.closest(".purchase-request-item-row"));
});
on(elements.purchasesRequestList, "click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const openButton = target?.closest("[data-purchase-open]");
    const approveButton = target?.closest("[data-purchase-approve]");
    const receiveButton = target?.closest("[data-purchase-receive]");
    if (openButton) openPurchaseRequestDetails(Number(openButton.dataset.purchaseOpen));
    else if (approveButton) approvePurchaseRequest(Number(approveButton.dataset.purchaseApprove));
    else if (receiveButton) openPurchaseReceiveModal(Number(receiveButton.dataset.purchaseReceive));
});
on(elements.purchasesRequestBoard, "click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const openButton = target?.closest("[data-purchase-open]");
    if (openButton) openPurchaseRequestDetails(Number(openButton.dataset.purchaseOpen));
});
on(elements.purchaseRequestForm, "submit", submitPurchaseRequest);
on(elements.purchaseOrderForm, "submit", submitPurchaseOrder);
on(elements.purchasesOrdersRefresh, "click", loadPurchaseOrdersData);
on(elements.purchasesInvoicesRefresh, "click", loadPurchaseInvoiceData);
on(elements.purchasesInvoicePendingList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-invoice-open]") : null;
    if (button) openPurchaseInvoiceModal(purchaseInvoicePendingById(Number(button.dataset.purchaseInvoiceOpen)));
});
on(elements.purchasesInvoiceBoard, "click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const invoiceButton = target?.closest("[data-purchase-invoice-open]");
    const receiveButton = target?.closest("[data-purchase-invoice-receive]");
    if (invoiceButton) openPurchaseInvoiceModal(purchaseInvoicePendingById(Number(invoiceButton.dataset.purchaseInvoiceOpen)));
    else if (receiveButton) openPurchaseInvoiceReceiveModal(purchaseReceiptPendingById(Number(receiveButton.dataset.purchaseInvoiceReceive)));
});
on(elements.purchasesReceiptPendingList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-invoice-receive]") : null;
    if (button) openPurchaseInvoiceReceiveModal(purchaseReceiptPendingById(Number(button.dataset.purchaseInvoiceReceive)));
});
on(elements.purchaseInvoiceForm, "submit", submitPurchaseInvoice);
on(elements.purchaseInvoiceCancel, "click", closePurchaseInvoiceModal);
on(elements.purchaseInvoiceModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closePurchaseInvoice === "true") closePurchaseInvoiceModal(); });
on(elements.purchaseInvoiceReceiveForm, "submit", submitPurchaseInvoiceReceive);
on(elements.purchaseInvoiceReceiveCancel, "click", closePurchaseInvoiceReceiveModal);
on(elements.purchaseInvoiceReceiveModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closePurchaseInvoiceReceive === "true") closePurchaseInvoiceReceiveModal(); });
on(elements.purchasesProcessCenterRefresh, "click", loadPurchaseProcessCenter);
on(elements.purchasesProcessSearch, "change", loadPurchaseProcessCenter);
on(elements.purchasesProcessStatus, "change", loadPurchaseProcessCenter);
on(elements.purchasesProcessType, "change", loadPurchaseProcessCenter);
on(elements.purchasesProcessList, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-process-open]") : null;
    if (button) openPurchaseRequestDetails(Number(button.dataset.purchaseProcessOpen));
});
on(elements.purchasesProcessBoard, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-process-open]") : null;
    if (button) openPurchaseRequestDetails(Number(button.dataset.purchaseProcessOpen));
});
on(elements.purchasesReportRefresh, "click", loadPurchaseReportSummary);
on(elements.purchasesReportExportPdf, "click", () => exportPurchaseReport("PDF"));
on(elements.purchasesReportExportXlsx, "click", () => exportPurchaseReport("XLSX"));
on(elements.purchasesReportScheduleForm, "submit", submitPurchaseReportSchedule);
on(elements.purchasesReportSchedulesList, "click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    const runButton = target?.closest("[data-purchase-report-run]");
    const toggleButton = target?.closest("[data-purchase-report-toggle]");
    if (runButton) executePurchaseReportSchedule(Number(runButton.dataset.purchaseReportRun));
    else if (toggleButton) togglePurchaseReportSchedule(Number(toggleButton.dataset.purchaseReportToggle), toggleButton.dataset.active === "true");
});
on(elements.purchaseRequestCancel, "click", closePurchaseRequestModal);
on(elements.purchaseRequestModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closePurchaseRequest === "true") closePurchaseRequestModal(); });
on(elements.purchaseDetailClose, "click", closePurchaseDetailModal);
on(elements.purchaseDetailApprove, "click", () => approvePurchaseRequest(state.purchases.selectedRequestId));
on(elements.purchaseDetailReceive, "click", () => openPurchaseReceiveModal(state.purchases.selectedRequestId));
on(elements.purchaseDetailContent, "click", (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("[data-purchase-file]") : null;
    if (button) openProtectedPurchaseFile(button.dataset.purchaseFile);
});
on(elements.purchaseDetailModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closePurchaseDetail === "true") closePurchaseDetailModal(); });
on(elements.purchaseReceiveForm, "submit", submitPurchaseReceive);
on(elements.purchaseReceiveCancel, "click", closePurchaseReceiveModal);
on(elements.purchaseReceiveModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closePurchaseReceive === "true") closePurchaseReceiveModal(); });
on(elements.mmpCreatePrincipalButton, "click", () => createMmpWarehouse("PRINCIPAL"));
on(elements.mmpCreateWarehouseButton, "click", () => createMmpWarehouse("MMP"));
on(elements.mmpLocationForm, "submit", submitMmpLocation);
on(elements.mmpTransferForm, "submit", submitMmpTransfer);
on(elements.mmpLookupButton, "click", lookupMmpStock);
on(elements.mmpQrCode, "keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); lookupMmpStock(); } });
on(elements.mmpScanQrButton, "click", scanMmpQr);
on(elements.mmpIssueForm, "submit", submitMmpIssue);
on(elements.mmpRefreshButton, "click", loadMmpStockData);
on(elements.moduleReportsBackButton, "click", () => {
    state.moduleReports = "";
    renderHome();
    setActiveScreen("home");
});
on(elements.weeklyDsrBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.weeklyDsrRefreshButton, "click", refreshWeeklyDsr);
on(elements.weeklyDsrSaveButton, "click", submitWeeklyDsr);
on(elements.weeklyDsrSearch, "input", renderWeeklyDsr);
on(elements.weeklyDsrArea, "change", renderWeeklyDsr);
on(elements.weeklyDsrTeam, "change", renderWeeklyDsr);
on(elements.weeklyDsrShift, "change", renderWeeklyDsr);
on(elements.weeklyDsrFunction, "change", renderWeeklyDsr);
on(elements.specialScheduleBackButton, "click", () => {
    closeSpecialScheduleHistory();
    renderHome();
    setActiveScreen("home");
});
on(elements.specialScheduleType, "change", () => {
    toggleSpecialHolidayName();
    if (state.specialSchedule.employees.length) {
        renderSpecialSchedule();
    }
});
on(elements.specialScheduleDate, "change", () => {
    if (elements.specialScheduleType.value === "DOMINGO") {
        elements.specialScheduleDefaultDsr.value = defaultDsrInputForSchedule(elements.specialScheduleDate.value);
    }
});
on(elements.specialScheduleRefreshButton, "click", refreshSpecialSchedule);
on(elements.specialScheduleSaveButton, "click", submitSpecialSchedule);
on(elements.specialScheduleSearch, "input", renderSpecialSchedule);
on(elements.specialScheduleArea, "change", renderSpecialSchedule);
on(elements.specialScheduleTeam, "change", renderSpecialSchedule);
on(elements.specialScheduleShift, "change", renderSpecialSchedule);
on(elements.specialScheduleFunction, "change", renderSpecialSchedule);
on(elements.specialScheduleHistoryButton, "click", openSpecialScheduleHistory);
on(elements.specialSchedulePdfButton, "click", exportSpecialSchedulePdf);
on(elements.specialScheduleHistoryLoad, "click", loadSpecialScheduleHistory);
on(elements.specialScheduleHistoryClose, "click", closeSpecialScheduleHistory);
on(elements.specialScheduleHistoryModal, "click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeSpecialScheduleHistory === "true") closeSpecialScheduleHistory();
});
on(elements.specialScheduleSelectAll, "change", (event) => {
    document.querySelectorAll(".special-schedule-employee").forEach((checkbox) => { checkbox.checked = event.target.checked; });
    updateSpecialScheduleSelectionSummary();
});
on(elements.specialScheduleList, "change", (event) => {
    if (event.target instanceof HTMLInputElement && event.target.classList.contains("special-schedule-employee")) {
        updateSpecialScheduleSelectionSummary();
    }
});
document.querySelectorAll(".schedule-tab").forEach((tab) => on(tab, "click", () => openScheduleTab(tab.dataset.scheduleTab)));
on(elements.absenteeismBackButton, "click", () => { renderHome(); setActiveScreen("home"); });
on(elements.absenteeismDate, "change", refreshAbsenteeism);
on(elements.absenteeismName, "input", scheduleAbsenteeismRefresh);
on(elements.absenteeismRegistration, "input", scheduleAbsenteeismRefresh);
on(elements.absenteeismShift, "change", refreshAbsenteeism);
on(elements.absenteeismSector, "change", refreshAbsenteeism);
on(elements.absenteeismFunction, "change", refreshAbsenteeism);
on(elements.absenteeismStatus, "change", refreshAbsenteeism);
on(elements.absenteeismPdfButton, "click", exportAbsenteeismPdf);
on(elements.absenteeismSaveButton, "click", saveAbsenteeism);
on(elements.absenteeismList, "change", (event) => {
    const target = event.target;
    if (target instanceof HTMLSelectElement && target.classList.contains("absenteeism-status")) {
        const row = target.closest(".absenteeism-row");
        const previousStatus = row.dataset.status || "PRESENTE";
        row.dataset.status = target.value;
        target.className = `absenteeism-status status-${target.value.toLowerCase()}`;
        if (target.value === "ATESTADO") {
            row.dataset.awaitingAtestado = "true";
            openAbsenteeismAtestadoModal(row, target, previousStatus);
            return;
        }
        row.className = `absenteeism-row status-${target.value.toLowerCase()}`;
        row.dataset.awaitingAtestado = "false";
        updateAbsenteeismPreview();
    }
});
on(elements.absenteeismAtestadoForm, "submit", saveAbsenteeismAtestado);
on(elements.absenteeismAtestadoCancel, "click", () => closeAbsenteeismAtestadoModal(true));
on(elements.absenteeismAtestadoStart, "change", () => { elements.absenteeismAtestadoEnd.value = addDaysToDateInput(elements.absenteeismAtestadoStart.value, elements.absenteeismAtestadoDays.value); });
on(elements.absenteeismAtestadoDays, "input", () => { elements.absenteeismAtestadoEnd.value = addDaysToDateInput(elements.absenteeismAtestadoStart.value, elements.absenteeismAtestadoDays.value); });
on(elements.absenteeismAtestadoModal, "click", (event) => { if (event.target instanceof HTMLElement && event.target.dataset.closeAbsenteeismAtestado === "true") closeAbsenteeismAtestadoModal(true); });
on(elements.specialScheduleList, "change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.classList.contains("special-schedule-dsr-date")) {
        return;
    }
    const week = target.closest(".special-schedule-card")?.querySelector(".special-schedule-week");
    if (week) {
        week.textContent = formatDate(isoWeekStartForDate(target.value));
    }
});
on(elements.specialScheduleList, "click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
        return;
    }
    const action = target.dataset.specialScheduleAction;
    const scheduleId = Number(target.dataset.scheduleId || 0);
    if (action && scheduleId) {
        resolveSpecialSchedule(scheduleId, action);
    }
});
on(elements.availabilityBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.emergenciesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.technicalLibraryBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.technicalLibraryVehicle, "change", loadTechnicalLibraryDocuments);
on(elements.technicalInspectionsBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.technicalInspectionVehicle, "change", renderTechnicalInspectionTemplateOptions);
on(elements.technicalInspectionTemplate, "change", renderTechnicalInspectionForm);
on(elements.technicalInspectionSubmit, "click", submitTechnicalInspection);
on(elements.nonConformitiesBackButton, "click", () => {
    if (state.selectedNonConformityItem) {
        state.selectedNonConformityItem = "";
        renderNonConformities();
        return;
    }
    renderHome();
    setActiveScreen("home");
});
on(elements.activityDetailBackButton, "click", openActivitiesMenu);
on(elements.resetChecklist, "click", resetChecklist);
on(elements.submitChecklist, "click", submitChecklist);
on(elements.backButton, "click", () => {
    if (state.vehicleFamilyFilter) {
        renderVehicleFamilyScreen();
        setActiveScreen("vehicleFamily");
        return;
    }
    setActiveScreen("vehicles");
});
on(elements.vehicleFamilyBackButton, "click", () => {
    renderVehicles();
    setActiveScreen("vehicles");
});
on(elements.newChecklistButton, "click", () => {
    state.selectedVehicle = null;
    renderHome();
    setActiveScreen("home");
});
on(elements.ncChecklistFilterOpen, "click", async () => {
    if (state.ncChecklistStatus === "abertas") {
        return;
    }
    state.ncChecklistStatus = "abertas";
    try {
        await loadNonConformityHubData();
        renderNonConformities();
    } catch (error) {
        showToast(error.message, true);
    }
});
on(elements.ncChecklistFilterClosed, "click", async () => {
    if (state.ncChecklistStatus === "resolvidas") {
        return;
    }
    state.ncChecklistStatus = "resolvidas";
    try {
        await loadNonConformityHubData();
        renderNonConformities();
    } catch (error) {
        showToast(error.message, true);
    }
});
on(elements.ncMechanicFilterOpen, "click", async () => {
    if (state.ncMechanicStatus === "abertas") {
        return;
    }
    state.ncMechanicStatus = "abertas";
    try {
        await loadNonConformityHubData();
        renderNonConformities();
    } catch (error) {
        showToast(error.message, true);
    }
});
on(elements.ncMechanicFilterClosed, "click", async () => {
    if (state.ncMechanicStatus === "resolvidas") {
        return;
    }
    state.ncMechanicStatus = "resolvidas";
    try {
        await loadNonConformityHubData();
        renderNonConformities();
    } catch (error) {
        showToast(error.message, true);
    }
});
on(elements.mechanicNcBeforePhoto, "change", () => {
    bindPhotoPreview(elements.mechanicNcBeforePhoto, elements.mechanicNcBeforePreview);
});
on(elements.mechanicNcCreateForm, "submit", createMechanicNonConformity);
document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLImageElement) || !target.classList.contains("photo-preview")) {
        return;
    }
    const sourceUrl = target.currentSrc || target.getAttribute("src") || "";
    if (!sourceUrl) {
        return;
    }
    openPhotoViewer(sourceUrl, target.dataset.zoomLabel || target.alt || "Visualização ampliada da evidência");
});
document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains("camera-trigger")) {
        return;
    }
    if (event.key !== "Enter" && event.key !== " ") {
        return;
    }
    event.preventDefault();
    target.closest(".evidence-input")?.querySelector("input[type='file']")?.click();
});
window.addEventListener("online", () => {
    updateConnectionStatus();
    syncPendingChecklists({ silent: true });
    syncPendingTechnicalInspections();
    syncPendingMobileOperations();
});
window.addEventListener("offline", updateConnectionStatus);
["pointerdown", "keydown", "input", "scroll", "touchstart"].forEach((eventName) => {
    window.addEventListener(eventName, trackSessionActivity, { capture: true, passive: true });
});
window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        trackSessionActivity();
        syncServerNotifications();
    }
});
window.addEventListener("focus", trackSessionActivity);
window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.topbarNotificationsMenu && !elements.topbarNotificationsMenu.classList.contains("hidden")) {
        event.preventDefault();
        closeTopbarNotificationsMenu();
        return;
    }
    if (event.key === "Escape" && elements.topbarSettingsMenu && !elements.topbarSettingsMenu.classList.contains("hidden")) {
        event.preventDefault();
        closeTopbarSettingsMenu();
        return;
    }
    if (event.key === "Escape" && elements.passwordModal && !elements.passwordModal.classList.contains("hidden")) {
        event.preventDefault();
        closePasswordResetModal();
        return;
    }
    if (event.key === "Escape" && elements.photoViewerModal && !elements.photoViewerModal.classList.contains("hidden")) {
        event.preventDefault();
        closePhotoViewer();
    }
});

unregisterServiceWorkers();
registerServiceWorker();
window.checklistAppReady = true;
updateEvidenceInputState(elements.mechanicNcBeforePhoto);
initPullToRefresh();
bootstrap();

function unregisterServiceWorkers() {
    if (!("serviceWorker" in navigator) || window.CHECKLIST_CONFIG?.ENABLE_CHECKLIST_PWA) {
        return;
    }
    const appCachePrefix = "cf-checklist-frota";
    navigator.serviceWorker.getRegistrations()
        .then((registrations) => Promise.all(registrations.map((registration) => registration.unregister())))
        .then(() => {
            if (!("caches" in window)) {
                return null;
            }
            return caches.keys().then((names) => Promise.all(
                names
                    .filter((name) => name.startsWith(appCachePrefix))
                    .map((name) => caches.delete(name))
            ));
        })
        .catch(() => {});
}
