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
const OFFLINE_DB_VERSION = 2;
const CHECKLIST_QUEUE_STORE = "checklistQueue";
const CHECKLIST_DRAFT_STORE = "checklistDrafts";
const OFFLINE_VEHICLES_KEY = "offlineVehicles";
const OFFLINE_CATALOG_KEY = "offlineCatalog";
const ACTIVE_CHECKLIST_DRAFT_KEY = "activeChecklistDraftVehicleId";
const SESSION_STARTED_AT_KEY = "sessionStartedAt";
const SESSION_MAX_AGE_MS = 8 * 60 * 60 * 1000;
const appTopbar = document.querySelector(".app-topbar");

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
    const startedAt = Number(localStorage.getItem(SESSION_STARTED_AT_KEY) || 0);
    return Boolean(token && user && startedAt && Date.now() - startedAt < SESSION_MAX_AGE_MS);
}

function saveSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
    localStorage.setItem(SESSION_STARTED_AT_KEY, String(Date.now()));
}

function clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem(SESSION_STARTED_AT_KEY);
}

const state = {
    apiBaseUrl: resolveApiBaseUrl(),
    token: "",
    user: null,
    vehicles: [],
    catalog: {},
    activities: [],
    materials: [],
    washOverview: null,
    nonConformityMacro: [],
    nonConformityMicro: [],
    nonConformityChecklist: [],
    nonConformityMechanic: [],
    maintenanceOverview: null,
    ncChecklistStatus: "abertas",
    ncMechanicStatus: "abertas",
    washYear: new Date().getFullYear(),
    washMonth: new Date().getMonth() + 1,
    selectedWashDate: "",
    selectedWashShiftTab: "TODOS",
    maintenanceYear: new Date().getFullYear(),
    maintenanceMonth: new Date().getMonth() + 1,
    selectedMaintenanceDate: "",
    selectedActivity: null,
    selectedVehicle: null,
    currentModule: "TODOS",
    checklistHistory: {
        tipo: "",
        dataInicio: "",
        dataFim: "",
        columns: [],
        rows: [],
    },
};

const screens = {
    login: document.getElementById("login-screen"),
    home: document.getElementById("home-screen"),
    vehicles: document.getElementById("vehicles-screen"),
    checklist: document.getElementById("checklist-screen"),
    activities: document.getElementById("activities-screen"),
    activityDetail: document.getElementById("activity-detail-screen"),
    washes: document.getElementById("washes-screen"),
    checklistHistory: document.getElementById("checklist-history-screen"),
    nonConformities: document.getElementById("non-conformities-screen"),
    maintenance: document.getElementById("maintenance-screen"),
    success: document.getElementById("success-screen"),
};

const elements = {
    apiBaseUrl: document.getElementById("api-base-url"),
    loginForm: document.getElementById("login-form"),
    loginButton: document.getElementById("login-button"),
    vehiclesList: document.getElementById("vehicles-list"),
    vehicleSearch: document.getElementById("vehicle-search"),
    vehicleCounter: document.getElementById("vehicle-counter"),
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
    homeChangePasswordButton: document.getElementById("home-change-password-button"),
    homeLogoutButton: document.getElementById("home-logout-button"),
    passwordModal: document.getElementById("password-modal"),
    passwordChangeForm: document.getElementById("password-change-form"),
    passwordCurrentInput: document.getElementById("password-current-input"),
    passwordNewInput: document.getElementById("password-new-input"),
    passwordConfirmInput: document.getElementById("password-confirm-input"),
    passwordChangeCancel: document.getElementById("password-change-cancel"),
    passwordChangeSubmit: document.getElementById("password-change-submit"),
    openChecklistMenu: document.getElementById("open-checklist-menu"),
    openChecklistHistoryMenu: document.getElementById("open-checklist-history-menu"),
    openActivitiesMenu: document.getElementById("open-activities-menu"),
    openWashesMenu: document.getElementById("open-washes-menu"),
    openNonConformitiesMenu: document.getElementById("open-non-conformities-menu"),
    openMaintenanceMenu: document.getElementById("open-maintenance-menu"),
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
    checklistHistoryTypeFilter: document.getElementById("checklist-history-type-filter"),
    checklistHistoryStartDate: document.getElementById("checklist-history-start-date"),
    checklistHistoryEndDate: document.getElementById("checklist-history-end-date"),
    checklistHistoryApplyFilter: document.getElementById("checklist-history-apply-filter"),
    checklistHistoryTableWrap: document.getElementById("checklist-history-table-wrap"),
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
    maintenanceBackButton: document.getElementById("maintenance-back-button"),
    maintenanceCounter: document.getElementById("maintenance-counter"),
    maintenanceSummary: document.getElementById("maintenance-summary"),
    maintenanceMonthTitle: document.getElementById("maintenance-month-title"),
    maintenancePrevMonth: document.getElementById("maintenance-prev-month"),
    maintenanceNextMonth: document.getElementById("maintenance-next-month"),
    maintenanceCalendar: document.getElementById("maintenance-calendar"),
    maintenanceDayPanel: document.getElementById("maintenance-day-panel"),
    maintenanceList: document.getElementById("maintenance-list"),
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

elements.apiBaseUrl.value = state.apiBaseUrl;
updateConnectionStatus();

function resolveApiBaseUrl() {
    const savedUrl = localStorage.getItem("apiBaseUrl");
    const configuredUrl = window.CHECKLIST_CONFIG?.API_BASE_URL?.replace(/\/$/, "");
    const currentHost = window.location.hostname || "127.0.0.1";
    const currentProtocol = window.location.protocol === "https:" ? "https:" : "http:";
    const currentUrl = `${currentProtocol}//${currentHost}:5000`;
    const isRemoteAccess = currentHost !== "127.0.0.1" && currentHost !== "localhost";
    const isSavedLocal = savedUrl?.includes("127.0.0.1") || savedUrl?.includes("localhost");

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
    elements.connectionStatus.textContent = navigator.onLine ? "ONLINE" : "OFFLINE";
    elements.connectionStatus.classList.toggle("offline", !navigator.onLine);
}

function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.ENABLE_CHECKLIST_PWA) {
        return;
    }

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("./service-worker.js").catch(() => {
            showToast("PWA NÃO PÔDE SER ATIVADO NESTE NAVEGADOR.", true);
        });
    });
}

function showToast(message, isError = false) {
    elements.toast.textContent = message;
    elements.toast.classList.toggle("error", isError);
    elements.toast.classList.remove("hidden");
    window.clearTimeout(showToast.timeoutId);
    showToast.timeoutId = window.setTimeout(() => {
        elements.toast.classList.add("hidden");
    }, 3200);
}

function setLoginStatus(message, isError = false) {
    const status = document.getElementById("login-status");
    if (!status) {
        return;
    }
    status.textContent = message || "";
    status.className = `login-status${isError ? " error" : ""}`;
}

function setActiveScreen(key) {
    Object.entries(screens).forEach(([screenKey, screen]) => {
        screen.classList.toggle("hidden", screenKey !== key);
    });
    const isEntryScreen = key === "login";
    document.body.classList.toggle("entry-screen", isEntryScreen);
    appTopbar?.classList.toggle("hidden", isEntryScreen);
    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function apiFetch(path, options = {}) {
    try {
        const response = await fetch(`${state.apiBaseUrl}${path}`, {
            ...options,
            headers: {
                ...(options.headers || {}),
                Authorization: state.token ? `Bearer ${state.token}` : "",
            },
        });

        const body = await response.json().catch(() => ({}));
        if (!response.ok || (Object.prototype.hasOwnProperty.call(body, "success") && body.success === false)) {
            const error = new Error(body.error || body.message || "FALHA NA COMUNICACAO COM A API.");
            error.status = response.status;
            throw error;
        }

        return Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    } catch (error) {
        if (error.name === "TypeError" && (error.message.includes("fetch") || error.message.includes("NetworkError"))) {
            throw new Error("SERVIDOR INDISPONIVEL OU SEM CONEXAO.");
        }
        throw error;
    }
}

async function login(credentials) {
    const response = await fetch(`${state.apiBaseUrl}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok || (Object.prototype.hasOwnProperty.call(body, "success") && body.success === false)) {
        throw new Error(body.error || "NAO FOI POSSIVEL ENTRAR.");
    }

    const payload = Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    state.token = payload.token;
    state.user = payload.user;
    saveSession(payload.token, payload.user);
}

async function bootstrap() {
    setLoginStatus("");
    if (hasValidSession()) {
        state.token = localStorage.getItem("token") || "";
        state.user = readJsonStorage("user", null);
        await enterAuthenticatedApp();
        return;
    }
    state.token = "";
    state.user = null;
    clearSession();
    setActiveScreen("login");
}

async function enterAuthenticatedApp() {
    try {
        setLoginStatus("Carregando dados do sistema...");
        await loadVehiclesAndCatalog();
        if (await restoreActiveChecklistDraft()) {
            setLoginStatus("");
            syncPendingChecklists({ silent: true });
            return;
        }
        renderHome();
        setActiveScreen("home");
        setLoginStatus("");
        syncPendingChecklists({ silent: true });
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            state.token = "";
            state.user = null;
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
    localStorage.setItem(SESSION_STARTED_AT_KEY, localStorage.getItem(SESSION_STARTED_AT_KEY) || String(Date.now()));
    await enterAuthenticatedApp();
};

async function loadVehiclesAndCatalog() {
    const now = new Date();
    try {
        const [vehicles, catalog, activities, washOverview, materials] = await Promise.all([
            apiFetch("/veiculos?ativos=true"),
            apiFetch("/config/checklists"),
            apiFetch("/atividades?status=ABERTA"),
            apiFetch(`/lavagens/visao?ano=${now.getFullYear()}&mes=${now.getMonth() + 1}`),
            apiFetch("/materiais?ativos=true"),
        ]);
        state.vehicles = vehicles.filter((vehicle) => vehicle.ativo !== false);
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

function renderHome() {
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
            <span>ATIVIDADES</span>
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
    refreshSyncQueuePanel();
    refreshCloudAdminPanel();
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
    return userType === "admin" || userType === "gestor" || userType === "mecanico";
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
            ? "CRITICO"
            : [database.level, storage.level].includes("vermelho")
                ? "ATENCAO"
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

function openChecklistMenu() {
    renderVehicles();
    setActiveScreen("vehicles");
}

function formatDateInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

async function openChecklistHistoryMenu() {
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
        if (elements.checklistHistoryStartDate) {
            elements.checklistHistoryStartDate.value = state.checklistHistory.dataInicio || "";
        }
        if (elements.checklistHistoryEndDate) {
            elements.checklistHistoryEndDate.value = state.checklistHistory.dataFim || "";
        }

        await loadChecklistHistory();
        setActiveScreen("checklistHistory");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function openActivitiesMenu() {
    try {
        await loadOpenActivities();
        renderHome();
        renderActivities();
        setActiveScreen("activities");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function openWashesMenu() {
    try {
        await loadWashOverview();
        renderHome();
        renderWashes();
        setActiveScreen("washes");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function openNonConformitiesMenu() {
    if (!hasMechanicWorkspaceAccess()) {
        showToast("MÓDULO DE NÃO CONFORMIDADES RESTRITO AO MECÂNICO E GESTÃO.", true);
        return;
    }
    try {
        await loadNonConformityHubData();
        renderHome();
        renderNonConformities();
        setActiveScreen("nonConformities");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function openMaintenanceMenu() {
    if (!hasMaintenanceAccess()) {
        showToast("MÓDULO DE MANUTENÇÃO RESTRITO AO MECÂNICO E GESTÃO.", true);
        return;
    }
    try {
        await loadMaintenanceOverview();
        renderHome();
        renderMaintenance();
        setActiveScreen("maintenance");
    } catch (error) {
        showToast(error.message, true);
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
    state.maintenanceOverview = await apiFetch(`/manutencao/visao?ano=${state.maintenanceYear}&mes=${state.maintenanceMonth}`);
}

async function loadChecklistHistory() {
    const params = new URLSearchParams();
    if (state.checklistHistory.tipo) {
        params.set("tipo", state.checklistHistory.tipo);
    }
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

function renderChecklistHistory() {
    if (!elements.checklistHistoryTableWrap || !elements.checklistHistoryCounter) {
        return;
    }

    const columns = state.checklistHistory.columns || [];
    const rows = state.checklistHistory.rows || [];

    elements.checklistHistoryCounter.textContent = `${rows.length} FROTAS`;
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
        elements.checklistHistoryTableWrap.innerHTML = `
            <article class="empty-state">
                <strong>SEM DATAS PARA O PERÍODO SELECIONADO.</strong>
                <span>AJUSTE O FILTRO DE DATA PARA VISUALIZAR O HISTÓRICO.</span>
            </article>
        `;
        return;
    }

    if (!rows.length) {
        elements.checklistHistoryTableWrap.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA FROTA ENCONTRADA NESTE FILTRO.</strong>
                <span>AJUSTE O TIPO CAVALO/CARRETA OU O PERÍODO.</span>
            </article>
        `;
        return;
    }

    const headerColumns = columns
        .map((column) => `<th>${escapeHtml(String(column.label || "-"))}</th>`)
        .join("");
    const bodyRows = rows
        .map((row) => {
            const cellValues = (row.cells || [])
                .map((value) => `<td>${value ? escapeHtml(String(value)) : ""}</td>`)
                .join("");
            return `
                <tr>
                    <th>
                        <strong>${escapeHtml(String(row.frota || "-"))}</strong>
                        <span>${escapeHtml(String(row.placa || "-").toUpperCase())}</span>
                    </th>
                    ${cellValues}
                </tr>
            `;
        })
        .join("");

    elements.checklistHistoryTableWrap.innerHTML = `
        <table class="history-table">
            <thead>
                <tr>
                    <th>FROTA</th>
                    ${headerColumns}
                </tr>
            </thead>
            <tbody>
                ${bodyRows}
            </tbody>
        </table>
    `;
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

function renderNonConformities() {
    if (!elements.nonConformitiesSummary) {
        return;
    }
    const checklistOpen = state.nonConformityMacro.reduce((total, row) => total + Number(row.abertas || 0), 0);
    const checklistResolved = state.nonConformityMacro.reduce((total, row) => total + Number(row.resolvidas || 0), 0);
    const mechanicOpen = state.nonConformityMechanic.filter((row) => !row.resolvido).length;
    const mechanicResolved = state.nonConformityMechanic.filter((row) => row.resolvido).length;
    const openTotal = checklistOpen + mechanicOpen;

    elements.nonConformitiesSummary.innerHTML = `
        <div>
            <strong>CHECKLIST ABERTAS: ${checklistOpen}</strong>
            <span>RESOLVIDAS: ${checklistResolved}</span>
        </div>
        <div>
            <strong>NÃO CONFORMIDADES INTERNAS ABERTAS: ${mechanicOpen}</strong>
            <span>RESOLVIDAS: ${mechanicResolved}</span>
        </div>
        <div class="progress-track" aria-hidden="true">
            <span style="width:${Math.min(100, Math.max(0, openTotal ? Math.round((checklistResolved + mechanicResolved) / (checklistResolved + mechanicResolved + openTotal) * 100) : 0))}%"></span>
        </div>
    `;

    elements.nonConformitiesCounter.textContent = `${openTotal} ABERTAS`;
    elements.nonConformitiesMacroCounter.textContent = `${state.nonConformityMacro.length} ITENS`;
    elements.nonConformitiesChecklistCounter.textContent = `${state.nonConformityChecklist.length} REGISTROS`;
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
    const macroTop = state.nonConformityMacro.slice(0, 5);
    const microTop = state.nonConformityMicro.slice(0, 5);

    if (!macroTop.length) {
        elements.nonConformitiesMacroList.innerHTML = `
            <article class="empty-state compact">
                <strong>SEM DADOS NO MACRO.</strong>
                <span>AS NÃO CONFORMIDADES DO CHECKLIST APARECERÃO AQUI.</span>
            </article>
        `;
    } else {
        elements.nonConformitiesMacroList.innerHTML = `
            <article class="list-toolbar">
                <strong>TOP ITENS COM NÃO CONFORMIDADE</strong>
                <span>VISAO MACRO</span>
            </article>
            <div class="nc-grid">
                ${macroTop.map((row) => `
                    <article class="nc-report-row">
                        <div>
                            <strong>${escapeHtml(String(row.item_nome || "-").toUpperCase())}</strong>
                            <span>${Number(row.abertas || 0)} ABERTAS | ${Number(row.resolvidas || 0)} RESOLVIDAS</span>
                        </div>
                        <em>${Number(row.total_nc || 0)} NÃO CONFORMIDADES</em>
                    </article>
                `).join("")}
            </div>
        `;
    }

    if (!microTop.length) {
        elements.nonConformitiesMicroList.innerHTML = `
            <article class="empty-state compact">
                <strong>SEM DADOS NO MICRO.</strong>
                <span>O RESUMO POR EQUIPAMENTO APARECERA AQUI.</span>
            </article>
        `;
    } else {
        elements.nonConformitiesMicroList.innerHTML = `
            <article class="list-toolbar">
                <strong>TOP EQUIPAMENTOS COM NÃO CONFORMIDADE</strong>
                <span>VISAO MICRO</span>
            </article>
            <div class="nc-grid">
                ${microTop.map((row) => `
                    <article class="nc-report-row">
                        <div>
                            <strong>${escapeHtml(String(row.frota || "-").toUpperCase())}</strong>
                            <span>${escapeHtml(String(row.placa || "-").toUpperCase())} | ${escapeHtml(String(row.tipo || "-").toUpperCase())}</span>
                        </div>
                        <em>${Number(row.total_nc || 0)} NÃO CONFORMIDADES</em>
                    </article>
                `).join("")}
            </div>
        `;
    }
}

function renderChecklistNonConformities() {
    const rows = state.nonConformityChecklist || [];
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

    rows.forEach((row, index) => {
        elements.nonConformitiesChecklistList.appendChild(makeChecklistNonConformityCard(row, index + 1));
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
    const days = overview.cronograma?.days || [];
    const selectedDay = ensureSelectedMaintenanceDate(days);
    const selectedItems = selectedDay?.items || [];

    elements.maintenanceCounter.textContent = `${Number(resumo.programados || resumo.itens || 0)} PROGRAMADOS`;
    elements.maintenanceMonthTitle.textContent = String(overview.periodo?.rotulo || `${state.maintenanceMonth}/${state.maintenanceYear}`).toUpperCase();
    renderMaintenanceSummary(resumo);
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

function renderMaintenanceSummary(resumo) {
    if (!elements.maintenanceSummary) {
        return;
    }
    const percent = Number(resumo.percentual_conclusao || 0);
    elements.maintenanceSummary.innerHTML = `
        <div>
            <strong>${Number(resumo.pendentes || 0)} PENDENTES | ${Number(resumo.instalados || 0)} INSTALADOS</strong>
            <span>${Number(resumo.nao_executados || 0)} NÃO EXECUTADOS | ${Number(resumo.aguardando_material || 0)} AGUARDANDO MATERIAL</span>
        </div>
        <div class="progress-track" aria-hidden="true">
            <span style="width:${Math.min(100, Math.max(0, percent))}%"></span>
        </div>
        <span>${percent}% CONCLUÍDO | ${Number(resumo.dias_utilizados || 0)} DIAS UTILIZADOS | CAPACIDADE MÉDIA ${Number(resumo.capacidade_media || 0)}</span>
    `;
}

function ensureSelectedMaintenanceDate(days) {
    if (days.find((day) => day.date === state.selectedMaintenanceDate)) {
        return days.find((day) => day.date === state.selectedMaintenanceDate);
    }
    const today = new Date();
    const todayKey = formatDateKey(today.getFullYear(), today.getMonth() + 1, today.getDate());
    const firstDayWithItems = days.find((day) => (day.items || []).length);
    if (today.getFullYear() === state.maintenanceYear && today.getMonth() + 1 === state.maintenanceMonth) {
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
    const today = new Date();
    const todayKey = formatDateKey(today.getFullYear(), today.getMonth() + 1, today.getDate());
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
        elements.maintenanceCalendar.appendChild(makeMaintenanceDayButton(day, dateKey === todayKey));
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
    elements.maintenanceDayPanel.innerHTML = `
        <section class="wash-day-summary">
            <div>
                <span>DIA SELECIONADO</span>
                <strong>${formatDate(selectedDay.date)}</strong>
            </div>
            <div>
                <span>STATUS</span>
                <strong>${Number(selectedDay.pendentes || 0)} PENDENTES</strong>
            </div>
        </section>
    `;
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
    const materials = schedule.materiais || [];
    const photoAfter = item.photo_after ? makeAbsoluteUrl(item.photo_after) : "";
    const status = String(item.status || "PENDENTE").toUpperCase();
    const canExecute = maintenanceItemCanInstall(item);
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
            <strong>${escapeHtml(String(vehicle.frota || "EQUIPAMENTO").toUpperCase())} | ${escapeHtml(String(vehicle.placa || "-").toUpperCase())}</strong>
            <span>${escapeHtml(String(vehicle.modelo || "-").toUpperCase())}</span>
        </div>
        <div class="nc-meta-list">
            <span>DATA PROGRAMADA: ${item.scheduled_date ? formatDateTime(`${item.scheduled_date}T00:00:00`) : "SEM DATA"}</span>
            <span>STATUS: ${escapeHtml(status.replace(/_/g, " "))}</span>
            <span>PROGRAMAÇÃO: ${escapeHtml(String(schedule.status || "-").replace(/_/g, " "))}</span>
            ${schedule.assigned_mechanic ? `<span>MECÂNICO: ${escapeHtml(String(schedule.assigned_mechanic.nome || "").toUpperCase())}</span>` : ""}
        </div>
        ${materials.length ? `
            <div class="nc-meta-list">
                ${materials.map((link) => {
                    const material = link.material || {};
                    return `<span>MATERIAL: ${escapeHtml(String(material.referencia || "-").toUpperCase())} | ${escapeHtml(String(material.descricao || "-").toUpperCase())} | ESTOQUE ${Number(material.quantidade_estoque || 0)} | NECESSÁRIO ${Number(link.quantity_required || 0)} | ${escapeHtml(String(link.status || "").replace(/_/g, " "))}</span>`;
                }).join("")}
            </div>
        ` : `
            <div class="nc-meta-list">
                <span>SEM MATERIAL VINCULADO NESTA PROGRAMAÇÃO.</span>
            </div>
        `}
        ${item.observation ? `<div class="nc-meta-list"><span>OBSERVAÇÃO: ${escapeHtml(item.observation)}</span></div>` : ""}
        ${status === "INSTALADO" ? `
            <span class="nc-resolved-flag">INSTALADO</span>
            ${item.executed_by ? `<div class="nc-meta-list"><span>EXECUTADO POR: ${escapeHtml(String(item.executed_by.nome || "").toUpperCase())}</span><span>EXECUÇÃO EM: ${formatDateTime(item.executed_at)}</span></div>` : ""}
            ${item.not_executed_reason ? `<div class="nc-meta-list"><span>MOTIVO ANTERIOR: ${escapeHtml(item.not_executed_reason)}</span></div>` : ""}
            ${photoAfter ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    <img src="${photoAfter}" alt="Foto depois da manutenção">
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
                    <button type="button" class="status-button ok maintenance-execute-button"${canExecute.allowed ? "" : " disabled"}>INSTALAR</button>
                    <button type="button" class="status-button nc maintenance-not-executed-button">NÃO EXECUTADO</button>
                </div>
                ${hasWashReportAccess() ? `
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
        card.querySelector(".maintenance-execute-button")?.addEventListener("click", () => submitMaintenanceItem(card, item, "INSTALADO"));
        card.querySelector(".maintenance-not-executed-button")?.addEventListener("click", () => submitMaintenanceItem(card, item, "NAO_EXECUTADO"));
        card.querySelector(".maintenance-reprogram-button")?.addEventListener("click", () => reprogramMaintenanceItem(card, item));
    }
    attachCollapsibleCard(card);
    return card;
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
        renderMaintenance();
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
        let photoPath = item.photo_after || "";
        if (afterFile) {
            const vehicleName = item.vehicle?.frota || item.vehicle?.placa || "EQUIPAMENTO";
            const itemName = item.schedule?.title || item.item_name || "MANUTENCAO";
            photoPath = await uploadEvidence(afterFile, vehicleName, itemName, "manutencao_depois", "MANUTENCAO");
        }

        await apiFetch(`/manutencao/itens/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                status: newStatus,
                observation,
                not_executed_reason: notExecutedReason,
                foto_depois: photoPath || "",
            }),
        });

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
    const beforePhoto = item.foto_antes ? makeAbsoluteUrl(item.foto_antes) : "";
    const afterPhoto = item.foto_depois ? makeAbsoluteUrl(item.foto_depois) : "";
    const isResolved = Boolean(item.resolvido);
    const card = document.createElement("article");
    card.className = "checklist-card";
    card.dataset.itemId = item.id;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(item.item_nome || "NÃO CONFORMIDADE").toUpperCase())}</h3>
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
                    <img src="${beforePhoto}" alt="Foto antes da não conformidade">
                </figure>
            ` : ""}
            ${afterPhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    <img src="${afterPhoto}" alt="Foto depois da não conformidade">
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
                    <span>OBSERVACAO DA RESOLUCAO</span>
                    <textarea class="nc-observation" placeholder="DESCREVA O QUE FOI FEITO"></textarea>
                </label>
                <label class="evidence-input">
                    <span>EVIDENCIA DEPOIS</span>
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
    attachCollapsibleCard(card);
    return card;
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
                    <img src="${beforePhoto}" alt="Foto antes da não conformidade interna">
                </figure>
            ` : ""}
            ${afterPhoto ? `
                <figure class="nc-photo-card">
                    <figcaption>FOTO DEPOIS</figcaption>
                    <img src="${afterPhoto}" alt="Foto depois da não conformidade interna">
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
                    <span>OBSERVACAO DA RESOLUCAO</span>
                    <textarea class="nc-observation" placeholder="DESCREVA O QUE FOI FEITO"></textarea>
                </label>
                <label class="evidence-input">
                    <span>EVIDENCIA DEPOIS</span>
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
        return;
    }
    if (previewElement.dataset.objectUrl) {
        URL.revokeObjectURL(previewElement.dataset.objectUrl);
    }
    const objectUrl = URL.createObjectURL(file);
    previewElement.dataset.objectUrl = objectUrl;
    previewElement.src = objectUrl;
    previewElement.classList.add("visible");
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
    if (!value) {
        return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("pt-BR");
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
    state.vehicles = cachedVehicles;
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
    localStorage.setItem(ACTIVE_CHECKLIST_DRAFT_KEY, String(state.selectedVehicle.id));
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
    const shouldRestore = window.confirm(`Deseja voltar para o checklist do ${vehicleLabel}?`);
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
            try {
                const transfer = new DataTransfer();
                transfer.items.add(saved.foto_antes_file);
                fileInput.files = transfer.files;
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
            }
        }
    });

    state.currentModule = draft.currentModule || "TODOS";
    document.querySelectorAll(".module-tab").forEach((button) => {
        const isActive = button.querySelector("span")?.textContent === state.currentModule;
        button.classList.toggle("active", isActive);
    });
    document.querySelectorAll(".module-section").forEach((section) => {
        section.classList.toggle("hidden-by-filter", state.currentModule !== "TODOS" && section.dataset.module !== state.currentModule);
    });
    updateProgress();
    localStorage.setItem(ACTIVE_CHECKLIST_DRAFT_KEY, String(vehicleId));
    return true;
}

async function refreshSyncQueuePanel() {
    if (!elements.syncPanel) {
        return;
    }

    try {
        const queue = await getChecklistQueue();
        const visibleItems = queue
            .filter((item) => item.status !== "SINCRONIZADO")
            .sort((a, b) => String(a.queuedAt || "").localeCompare(String(b.queuedAt || "")));

        elements.syncPanel.classList.toggle("hidden", visibleItems.length === 0);
        elements.syncCounter.textContent = `${visibleItems.length} CHECKLIST${visibleItems.length === 1 ? "" : "S"} PENDENTE${visibleItems.length === 1 ? "" : "S"}`;
        elements.syncList.innerHTML = visibleItems.slice(0, 4).map((item) => `
            <article class="sync-row ${item.status === "ERRO" ? "error" : ""}">
                <div>
                    <strong>${escapeHtml(item.vehicle?.frota || "EQUIPAMENTO")}</strong>
                    <span>${new Date(item.queuedAt).toLocaleString("pt-BR")} | ${item.itens?.length || 0} ITENS</span>
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
    const filteredVehicles = state.vehicles.filter((vehicle) => {
        const searchable = normalizeText(`${vehicle.frota} ${vehicle.placa} ${vehicle.modelo} ${vehicle.tipo}`);
        return !query || searchable.includes(query);
    });

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
            <span>API</span>
            <strong>${escapeHtml(state.apiBaseUrl)}</strong>
        </div>
    `;

    elements.vehicleCounter.textContent = `${filteredVehicles.length} ATIVOS`;
    elements.vehiclesList.innerHTML = "";

    if (!filteredVehicles.length) {
        elements.vehiclesList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUM EQUIPAMENTO ATIVO ENCONTRADO.</strong>
                <span>ATUALIZE O CADASTRO NO DESKTOP OU AJUSTE A BUSCA.</span>
            </article>
        `;
        return;
    }

    filteredVehicles.forEach((vehicle) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "vehicle-card";
        card.innerHTML = `
            <span class="vehicle-type">${escapeHtml(String(vehicle.tipo || "-").toUpperCase())}</span>
            <strong>${escapeHtml(vehicle.frota || "-")}</strong>
            <span>${escapeHtml(String(vehicle.modelo || "MODELO NÃO INFORMADO").toUpperCase())}</span>
            <small>PLACA ${escapeHtml(vehicle.placa || "-")} | ${escapeHtml(String(vehicle.local || "SEM LOCAL").toUpperCase())}</small>
        `;
        card.addEventListener("click", () => selectVehicle(vehicle));
        elements.vehiclesList.appendChild(card);
    });
}

function renderActivities() {
    const openActivities = state.activities.filter((activity) => activity.status === "ABERTA");
    elements.activityCounter.textContent = `${openActivities.length} ABERTAS`;
    elements.activitiesList.innerHTML = "";

    if (!openActivities.length) {
        elements.activitiesList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA ATIVIDADE ABERTA.</strong>
                <span>AS ATIVIDADES CRIADAS NO DESKTOP APARECERÃO AQUI.</span>
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
            <strong>${escapeHtml(String(activity.titulo || activity.item_nome || "ATIVIDADE").toUpperCase())}</strong>
            <span>${escapeHtml(String(activity.item_nome || "-").toUpperCase())}</span>
            <small>${resumo.pendentes || 0} PENDENTES | ${resumo.instalados || 0} INSTALADOS | ${resumo.nao_instalados || 0} NÃO INSTALADOS${activity.assigned_mechanic ? ` | DIRECIONADO: ${escapeHtml(String(activity.assigned_mechanic.nome || "").toUpperCase())}` : ""}</small>
        `;
        card.addEventListener("click", () => selectActivity(activity.id));
        elements.activitiesList.appendChild(card);
    });
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
    elements.activityTitle.textContent = String(activity.titulo || activity.item_nome || "ATIVIDADE").toUpperCase();
    elements.activitySummary.innerHTML = `
        <div>
            <strong>${escapeHtml(String(activity.item_nome || "-").toUpperCase())}</strong>
            <span>${resumo.pendentes || 0} PENDENTES | ${resumo.instalados || 0} INSTALADOS | ${resumo.nao_instalados || 0} NÃO INSTALADOS</span>
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
            <strong>STATUS ATUAL: ${escapeHtml(String(item.status_execucao || "PENDENTE").replace("_", " "))}</strong>
            <span>PLACA ${escapeHtml(vehicle.placa || "-")}</span>
        </div>
        <div class="status-group activity-status-group" role="group" aria-label="Status da atividade">
            <button type="button" class="status-button ok" data-status="INSTALADO">INSTALADO</button>
        </div>
        <label>
            <span>OBSERVAÇÃO DA ATIVIDADE</span>
            <textarea placeholder="DESCREVA A EXECUÇÃO, PENDÊNCIA OU RESTRIÇÃO">${escapeHtml(item.observacao || "")}</textarea>
        </label>
        <label class="evidence-input">
            <span>EVIDÊNCIA ANTES</span>
            <strong>FOTO ANTES DA EXECUÇÃO</strong>
            <input type="file" data-photo="before" accept="image/*" capture="environment">
            <em>${item.foto_antes ? "FOTO ANTES JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM."}</em>
        </label>
        <img class="photo-preview before-preview" alt="PRÉVIA DA EVIDÊNCIA ANTES">
        <label class="evidence-input">
            <span>EVIDÊNCIA DEPOIS</span>
            <strong>FOTO DEPOIS DA EXECUÇÃO</strong>
            <input type="file" data-photo="after" accept="image/*" capture="environment">
            <em>${item.foto_depois ? "FOTO DEPOIS JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM."}</em>
        </label>
        <img class="photo-preview after-preview" alt="PRÉVIA DA EVIDÊNCIA DEPOIS">
        <button type="button" class="primary-button activity-save-button">SALVAR EVIDÊNCIA</button>
        ${canShare ? `<button type="button" class="share-button activity-share-button">COMPARTILHAR NO WHATSAPP</button>` : ""}
    `;

    const beforeInput = card.querySelector("input[data-photo='before']");
    const beforeHint = beforeInput?.closest(".evidence-input")?.querySelector("em");
    const beforePreview = card.querySelector(".before-preview");
    if (beforeHint) {
        beforeHint.textContent = beforePath ? "FOTO ANTES JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.";
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
        afterHint.textContent = afterPath ? "FOTO DEPOIS JÁ VINCULADA." : "TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.";
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
    card.dataset.status = "INSTALADO";
    statusButtons.forEach((statusButton) => {
        if (statusButton.dataset.status === "INSTALADO") {
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
    const status = "INSTALADO";
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
            payload.foto_antes = await uploadEvidence(beforeFile, vehicle.frota || "EQUIPAMENTO", activity.item_nome || "ATIVIDADE", "atividade_antes", "ATIVIDADES");
        } else if (currentBeforePath) {
            payload.foto_antes = currentBeforePath;
        }
        if (afterFile) {
            payload.foto_depois = await uploadEvidence(afterFile, vehicle.frota || "EQUIPAMENTO", activity.item_nome || "ATIVIDADE", "atividade_depois", "ATIVIDADES");
        } else if (currentAfterPath) {
            payload.foto_depois = currentAfterPath;
        }

        state.selectedActivity = await apiFetch(`/atividades/${activity.id}/itens/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        renderActivityDetail();
        showToast("ATIVIDADE ATUALIZADA COM SUCESSO.");
    } catch (error) {
        showToast(error.message, true);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = "SALVAR EVIDÊNCIA";
    }
}

function getWashScheduleItems() {
    const days = state.washOverview?.cronograma?.days || [];
    return days.flatMap((day) => [
        ...(day.morning || []).map((item) => ({ ...item, scheduled_date: item.scheduled_date || day.date, scheduled_shift: item.scheduled_shift || "MANHA" })),
        ...(day.afternoon || []).map((item) => ({ ...item, scheduled_date: item.scheduled_date || day.date, scheduled_shift: item.scheduled_shift || "TARDE" })),
    ]);
}

function renderWashes() {
    const scheduleItems = getWashScheduleItems()
        .filter((item) => item.status_execucao !== "LAVADO")
        .sort((a, b) => `${a.scheduled_date}${a.scheduled_shift}`.localeCompare(`${b.scheduled_date}${b.scheduled_shift}`));

    elements.washCounter.textContent = `${scheduleItems.length} PROGRAMADOS`;
    elements.washesList.innerHTML = "";

    if (!scheduleItems.length) {
        elements.washesList.innerHTML = `
            <article class="empty-state">
                <strong>NENHUMA LAVAGEM PENDENTE NO CRONOGRAMA.</strong>
                <span>OS VEÍCULOS PROGRAMADOS PELO DESKTOP APARECERÃO AQUI.</span>
            </article>
        `;
        return;
    }

    scheduleItems.forEach((item, index) => {
        elements.washesList.appendChild(makeWashCard(item, index + 1));
    });
}

function makeWashCard(item, index) {
    const card = document.createElement("article");
    card.className = "checklist-card wash-card";
    card.dataset.queueItemId = item.queue_item_id;
    card.dataset.scheduledDate = item.scheduled_date;
    card.dataset.shift = item.scheduled_shift || "MANHA";
    card.dataset.category = item.categoria_lavagem || item.categoria_sugerida || "CAVALO";
    card.dataset.value = item.valor_sugerido || "";
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(String(item.referencia || "EQUIPAMENTO").toUpperCase())}</h3>
        </div>
        <div class="activity-meta">
            <strong>${formatDate(item.scheduled_date)} | ${escapeHtml(String(item.scheduled_shift || "-").toUpperCase())}</strong>
            <span>${escapeHtml(String(item.modelo || "-").toUpperCase())} | ${escapeHtml(String(item.categoria_lavagem || "-").toUpperCase())}</span>
        </div>
        <div class="status-group activity-status-group" role="group" aria-label="Status da lavagem">
            <button type="button" class="status-button ok" data-status="LAVADO">LAVADO</button>
            <button type="button" class="status-button nc" data-status="NAO_LEVADO">NÃO LEVADO</button>
        </div>
        <label>
            <span>LOCAL DA LAVAGEM</span>
            <input type="text" class="wash-location" placeholder="INFORME O LOCAL">
        </label>
        <label>
            <span>OBSERVAÇÃO / MOTIVO</span>
            <textarea class="wash-notes" placeholder="DESCREVA A EVIDÊNCIA OU O MOTIVO DE NÃO TER SIDO LEVADO"></textarea>
        </label>
        <label class="evidence-input">
            <span>EVIDÊNCIA DA LAVAGEM</span>
            <strong>FOTO DO VEÍCULO LEVADO / LAVADO</strong>
            <input type="file" accept="image/*" capture="environment">
            <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM.</em>
        </label>
        <img class="photo-preview" alt="PRÉVIA DA EVIDÊNCIA DA LAVAGEM">
        <button type="button" class="primary-button wash-save-button">SALVAR LAVAGEM</button>
    `;

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
            if (preview.dataset.objectUrl) {
                URL.revokeObjectURL(preview.dataset.objectUrl);
                delete preview.dataset.objectUrl;
            }
            scheduleChecklistDraftSave();
            return;
        }
        if (preview.dataset.objectUrl) {
            URL.revokeObjectURL(preview.dataset.objectUrl);
        }
        const objectUrl = URL.createObjectURL(file);
        preview.dataset.objectUrl = objectUrl;
        preview.src = objectUrl;
        preview.classList.add("visible");
    });

    card.querySelector(".wash-save-button").addEventListener("click", () => submitWashEvidence(card, item));
    return card;
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
    const title = "CF - atividade";
    const message = buildPhotoShareText(title, [
        `Atividade: ${activity.item_nome || activity.titulo || "-"}`,
        `Equipamento: ${vehicle.frota || "-"} | Placa: ${vehicle.placa || "-"}`,
        `Status: ${String(item.status_execucao || "-").replace("_", " ")}`,
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
    screens.washes.querySelector(".list-toolbar span").textContent = "ESCOLHA O DIA E REGISTRE O PARECER.";
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

    const today = new Date();
    const todayKey = formatDateKey(today.getFullYear(), today.getMonth() + 1, today.getDate());
    const todayHasSchedule = days.find((day) => day.date === todayKey);
    const firstDayWithItems = days.find((day) => [...(day.morning || []), ...(day.afternoon || [])].length);

    if (today.getFullYear() === state.washYear && today.getMonth() + 1 === state.washMonth) {
        state.selectedWashDate = todayHasSchedule?.date || todayKey;
        return;
    }

    state.selectedWashDate = firstDayWithItems?.date || formatDateKey(state.washYear, state.washMonth, 1);
}

function renderWashCalendar(days) {
    const daysByDate = new Map(days.map((day) => [day.date, day]));
    const firstWeekday = new Date(state.washYear, state.washMonth - 1, 1).getDay();
    const totalDays = new Date(state.washYear, state.washMonth, 0).getDate();
    const today = new Date();
    const todayKey = formatDateKey(today.getFullYear(), today.getMonth() + 1, today.getDate());

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
        renderMaintenance();
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
            ${evidenceUrl ? `<img class="photo-preview visible" src="${evidenceUrl}" alt="EVIDÊNCIA DA LAVAGEM">` : ""}
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
    attachCollapsibleCard(card);
    return card;
}

async function selectVehicle(vehicle, options = {}) {
    state.selectedVehicle = vehicle;
    state.currentModule = "TODOS";
    const items = state.catalog[vehicle.tipo] || [];
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
        state.currentModule = moduleName;
        document.querySelectorAll(".module-tab").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        document.querySelectorAll(".module-section").forEach((section) => {
            section.classList.toggle("hidden-by-filter", moduleName !== "TODOS" && section.dataset.module !== moduleName);
        });
        scheduleChecklistDraftSave();
    });
    return button;
}

function renderChecklistModules(modules) {
    elements.checklistForm.innerHTML = "";
    let globalIndex = 0;

    modules.forEach((module) => {
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

        module.items.forEach((item) => {
            globalIndex += 1;
            section.appendChild(makeChecklistCard(item, module.name, globalIndex));
        });

        elements.checklistForm.appendChild(section);
    });
}

function makeChecklistCard(item, moduleName, index) {
    const itemName = item.item_nome;
    const itemPhotoUrl = item.foto_path ? makeAbsoluteUrl(item.foto_path) : "";
    const card = document.createElement("article");
    card.className = "checklist-card checklist-item-card";
    card.dataset.itemName = itemName;
    card.dataset.module = moduleName;
    card.innerHTML = `
        <div class="item-topline">
            <span>${String(index).padStart(2, "0")}</span>
            <h3>${escapeHtml(itemName)}</h3>
        </div>
        ${itemPhotoUrl ? `
            <figure class="reference-photo">
                <figcaption>FOTO DE REFERÊNCIA DO ITEM</figcaption>
                <img src="${itemPhotoUrl}" alt="FOTO DE REFERÊNCIA DO ITEM ${escapeHtml(itemName)}">
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
                <input type="file" accept="image/*" capture="environment">
                <em>TOQUE PARA FOTOGRAFAR OU ANEXAR IMAGEM</em>
            </label>
            <img class="photo-preview" alt="PRÉVIA DA EVIDÊNCIA ANEXADA">
        </div>
    `;

    const statusButtons = card.querySelectorAll(".status-button");
    const ncFields = card.querySelector(".nc-fields");
    const fileInput = card.querySelector("input[type='file']");
    const preview = card.querySelector(".photo-preview");

    statusButtons.forEach((button) => {
        button.addEventListener("click", () => {
            statusButtons.forEach((statusButton) => statusButton.classList.remove("active"));
            button.classList.add("active");
            card.dataset.status = button.dataset.status;
            card.classList.toggle("has-nc", button.dataset.status === "NC");
            ncFields.classList.toggle("visible", button.dataset.status === "NC");
            updateProgress();
            scheduleChecklistDraftSave();
        });
    });

    card.querySelector("textarea")?.addEventListener("input", scheduleChecklistDraftSave);

    fileInput.addEventListener("change", () => {
        const [file] = fileInput.files;
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
        scheduleChecklistDraftSave();
    });

    return card;
}

function updateProgress() {
    const cards = Array.from(document.querySelectorAll(".checklist-item-card"));
    const total = cards.length;
    const done = cards.filter((card) => card.dataset.status).length;
    const nc = cards.filter((card) => card.dataset.status === "NC").length;
    const percent = total ? Math.round((done / total) * 100) : 0;

    elements.checklistProgress.textContent = `${done} DE ${total} AVALIADOS | ${nc} NÃO CONFORMIDADES`;
    elements.progressBar.style.width = `${percent}%`;
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

    state.currentModule = "TODOS";
    document.querySelectorAll(".module-tab").forEach((button) => {
        const isAll = button.querySelector("span")?.textContent === "TODOS";
        button.classList.toggle("active", isAll);
    });
    document.querySelectorAll(".module-section").forEach((section) => {
        section.classList.remove("hidden-by-filter");
    });

    await deleteChecklistDraft(state.selectedVehicle.id).catch(() => {});
    updateProgress();
    showToast("CHECKLIST RESETADO.");
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
    return `${state.apiBaseUrl}${path}`;
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
    if (!response.ok) {
        throw new Error(body.error || `FALHA AO ENVIAR IMAGEM DO ITEM ${itemName}.`);
    }
    return body.path;
}

async function submitChecklist() {
    if (!state.selectedVehicle) {
        showToast("SELECIONE UM EQUIPAMENTO ANTES DE ENVIAR.", true);
        return;
    }

    const cards = Array.from(document.querySelectorAll(".checklist-item-card"));
    const itens = [];

    elements.submitChecklist.disabled = true;
    elements.submitChecklist.textContent = "ENVIANDO...";

    try {
        for (const card of cards) {
            const status = card.dataset.status;
            if (!status) {
                throw new Error(`SELECIONE OK OU NÃO CONFORMIDADE PARA O ITEM ${card.dataset.itemName}.`);
            }

            const item = {
                item_nome: card.dataset.itemName,
                status,
            };

            if (status === "NC") {
                const textarea = card.querySelector("textarea");
                const fileInput = card.querySelector("input[type='file']");
                const file = fileInput.files[0];

                if (!textarea.value.trim()) {
                    throw new Error(`INFORME A OBSERVAÇÃO PARA ${card.dataset.itemName}.`);
                }
                if (!file) {
                    throw new Error(`ANEXE A EVIDÊNCIA DA NÃO CONFORMIDADE PARA ${card.dataset.itemName}.`);
                }

                item.observacao = textarea.value.trim();
                item.foto_antes = await uploadImage(file, card.dataset.itemName, card.dataset.module);
            }

            itens.push(item);
        }

        const payload = {
            vehicle_id: state.selectedVehicle.id,
            itens,
        };
        const result = await apiFetch("/checklist", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const totalNc = result.total_nc || itens.filter((item) => item.status === "NC").length;
        elements.successSummary.innerHTML = `
            <strong>${escapeHtml(state.selectedVehicle.frota)}</strong>
            <span>ENVIADO EM ${new Date(result.created_at).toLocaleString("pt-BR")}</span>
            <span>NÃO CONFORMIDADES REGISTRADAS: ${totalNc}</span>
        `;
        setActiveScreen("success");
        showToast("CHECKLIST ENVIADO COM SUCESSO.");
    } catch (error) {
        showToast(error.message, true);
    } finally {
        elements.submitChecklist.disabled = false;
        elements.submitChecklist.textContent = "ENVIAR CHECKLIST";
    }
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
        if (!status) {
            throw new Error(`SELECIONE OK OU NÃO CONFORMIDADE PARA O ITEM ${card.dataset.itemName}.`);
        }

        const item = {
            item_nome: card.dataset.itemName,
            module: card.dataset.module,
            status,
        };

        if (status === "NC") {
            const textarea = card.querySelector("textarea");
            const fileInput = card.querySelector("input[type='file']");
            const restoredItem = storedItems.get(normalizeText(card.dataset.itemName));
            const file = fileInput.files[0] || restoredItem?.foto_antes_file;

            if (!textarea.value.trim()) {
                throw new Error(`INFORME A OBSERVAÇÃO PARA ${card.dataset.itemName}.`);
            }
            if (!file) {
                throw new Error(`ANEXE A EVIDÊNCIA DA NÃO CONFORMIDADE PARA ${card.dataset.itemName}.`);
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
    const when = result?.created_at ? new Date(result.created_at) : new Date(draft.createdAt);
    elements.successSummary.innerHTML = `
        <strong>${escapeHtml(draft.vehicle.frota)}</strong>
        <span>${queued ? "SALVO OFFLINE EM" : "ENVIADO EM"} ${when.toLocaleString("pt-BR")}</span>
        <span>NÃO CONFORMIDADES REGISTRADAS: ${totalNc}</span>
        ${queued ? "<span>SERÁ SINCRONIZADO AUTOMATICAMENTE QUANDO A CONEXÃO VOLTAR.</span>" : ""}
    `;
    deleteChecklistDraft(draft.vehicle.id).catch(() => {});
    setActiveScreen("success");
}

async function submitChecklist() {
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

function logout() {
    state.token = "";
    state.user = null;
    state.selectedVehicle = null;
    closePasswordResetModal();
    clearSession();
    setLoginStatus("");
    if (elements.loginForm) {
        elements.loginForm.reset();
    }
    if (elements.loginButton) {
        elements.loginButton.disabled = false;
        elements.loginButton.textContent = "ENTRAR NO SISTEMA";
    }
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
        showToast("AS SENHAS NAO CONFEREM.", true);
        elements.passwordConfirmInput?.focus();
        return;
    }

    if (elements.homeChangePasswordButton) {
        elements.homeChangePasswordButton.disabled = true;
        elements.homeChangePasswordButton.textContent = "SALVANDO...";
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
        showToast(error.message || "NAO FOI POSSIVEL ATUALIZAR A SENHA.", true);
    } finally {
        if (elements.homeChangePasswordButton) {
            elements.homeChangePasswordButton.disabled = false;
            elements.homeChangePasswordButton.textContent = "ALTERAR SENHA";
        }
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

on(elements.loginForm, "submit", async (event) => {
    event.preventDefault();
    await handleLoginSubmit();
});

async function handleLoginSubmit() {
    state.apiBaseUrl = elements.apiBaseUrl.value.replace(/\/$/, "");
    localStorage.setItem("apiBaseUrl", state.apiBaseUrl);
    elements.loginButton.disabled = true;
    elements.loginButton.textContent = "ENTRANDO...";

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
        elements.loginButton.textContent = "ENTRAR NO SISTEMA";
    }
}

on(elements.loginButton, "click", handleLoginSubmit);
on(elements.vehicleSearch, "input", renderVehicles);
on(elements.openChecklistMenu, "click", openChecklistMenu);
on(elements.openChecklistHistoryMenu, "click", openChecklistHistoryMenu);
on(elements.openActivitiesMenu, "click", openActivitiesMenu);
on(elements.openWashesMenu, "click", openWashesMenu);
on(elements.openNonConformitiesMenu, "click", openNonConformitiesMenu);
on(elements.openMaintenanceMenu, "click", openMaintenanceMenu);
on(elements.washPrevMonth, "click", () => changeWashMonth(-1));
on(elements.washNextMonth, "click", () => changeWashMonth(1));
on(elements.washExportPdfButton, "click", exportWashMonthPdf);
on(elements.maintenancePrevMonth, "click", () => changeMaintenanceMonth(-1));
on(elements.maintenanceNextMonth, "click", () => changeMaintenanceMonth(1));
on(elements.syncNowButton, "click", () => syncPendingChecklists({ silent: false }));
on(elements.cloudBackupButton, "click", createCloudBackup);
on(elements.homeChangePasswordButton, "click", requestPasswordReset);
on(elements.homeLogoutButton, "click", logout);
on(elements.passwordChangeForm, "submit", submitPasswordReset);
on(elements.passwordChangeCancel, "click", closePasswordResetModal);
on(elements.passwordModal, "click", (event) => {
    if (event.target?.dataset?.closePasswordModal === "true") {
        closePasswordResetModal();
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
on(elements.checklistHistoryApplyFilter, "click", applyChecklistHistoryFilters);
on(elements.maintenanceBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.nonConformitiesBackButton, "click", () => {
    renderHome();
    setActiveScreen("home");
});
on(elements.activityDetailBackButton, "click", openActivitiesMenu);
on(elements.resetChecklist, "click", resetChecklist);
on(elements.submitChecklist, "click", submitChecklist);
on(elements.backButton, "click", () => setActiveScreen("vehicles"));
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
window.addEventListener("online", () => {
    updateConnectionStatus();
    syncPendingChecklists({ silent: true });
});
window.addEventListener("offline", updateConnectionStatus);
window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.passwordModal && !elements.passwordModal.classList.contains("hidden")) {
        event.preventDefault();
        closePasswordResetModal();
    }
});

unregisterServiceWorkers();
registerServiceWorker();
window.checklistAppReady = true;
bootstrap();

function unregisterServiceWorkers() {
    if (!("serviceWorker" in navigator) || window.ENABLE_CHECKLIST_PWA) {
        return;
    }
    navigator.serviceWorker.getRegistrations()
        .then((registrations) => Promise.all(registrations.map((registration) => registration.unregister())))
        .catch(() => {});
}
