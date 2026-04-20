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
const OFFLINE_DB_VERSION = 1;
const CHECKLIST_QUEUE_STORE = "checklistQueue";
const OFFLINE_VEHICLES_KEY = "offlineVehicles";
const OFFLINE_CATALOG_KEY = "offlineCatalog";

function readJsonStorage(key, fallback = null) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
    } catch {
        localStorage.removeItem(key);
        return fallback;
    }
}

const state = {
    apiBaseUrl: resolveApiBaseUrl(),
    token: localStorage.getItem("token") || "",
    user: readJsonStorage("user", null),
    vehicles: [],
    catalog: {},
    activities: [],
    washOverview: null,
    washYear: new Date().getFullYear(),
    washMonth: new Date().getMonth() + 1,
    selectedWashDate: "",
    selectedActivity: null,
    selectedVehicle: null,
    currentModule: "TODOS",
};

const screens = {
    login: document.getElementById("login-screen"),
    home: document.getElementById("home-screen"),
    vehicles: document.getElementById("vehicles-screen"),
    checklist: document.getElementById("checklist-screen"),
    activities: document.getElementById("activities-screen"),
    activityDetail: document.getElementById("activity-detail-screen"),
    washes: document.getElementById("washes-screen"),
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
    submitChecklist: document.getElementById("submit-checklist"),
    successSummary: document.getElementById("success-summary"),
    toast: document.getElementById("toast"),
    homeSummary: document.getElementById("home-summary"),
    syncPanel: document.getElementById("sync-panel"),
    syncCounter: document.getElementById("sync-counter"),
    syncList: document.getElementById("sync-list"),
    syncNowButton: document.getElementById("sync-now-button"),
    homeLogoutButton: document.getElementById("home-logout-button"),
    openChecklistMenu: document.getElementById("open-checklist-menu"),
    openActivitiesMenu: document.getElementById("open-activities-menu"),
    openWashesMenu: document.getElementById("open-washes-menu"),
    vehiclesBackButton: document.getElementById("vehicles-back-button"),
    activitiesBackButton: document.getElementById("activities-back-button"),
    activityCounter: document.getElementById("activity-counter"),
    activitiesList: document.getElementById("activities-list"),
    activityDetailBackButton: document.getElementById("activity-detail-back-button"),
    activityTitle: document.getElementById("activity-title"),
    activitySummary: document.getElementById("activity-summary"),
    activityItemsList: document.getElementById("activity-items-list"),
    washesBackButton: document.getElementById("washes-back-button"),
    washCounter: document.getElementById("wash-counter"),
    washMonthTitle: document.getElementById("wash-month-title"),
    washPrevMonth: document.getElementById("wash-prev-month"),
    washNextMonth: document.getElementById("wash-next-month"),
    washCalendar: document.getElementById("wash-calendar"),
    washDayPanel: document.getElementById("wash-day-panel"),
    washesList: document.getElementById("washes-list"),
    backButton: document.getElementById("back-button"),
    newChecklistButton: document.getElementById("new-checklist-button"),
    connectionStatus: document.getElementById("connection-status"),
};

elements.apiBaseUrl.value = state.apiBaseUrl;
updateConnectionStatus();

function resolveApiBaseUrl() {
    const savedUrl = localStorage.getItem("apiBaseUrl");
    const currentHost = window.location.hostname || "127.0.0.1";
    const currentProtocol = window.location.protocol === "https:" ? "https:" : "http:";
    const currentUrl = `${currentProtocol}//${currentHost}:5000`;
    const isRemoteAccess = currentHost !== "127.0.0.1" && currentHost !== "localhost";

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
    if (!("serviceWorker" in navigator)) {
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

function setActiveScreen(key) {
    Object.entries(screens).forEach(([screenKey, screen]) => {
        screen.classList.toggle("hidden", screenKey !== key);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function apiFetch(path, options = {}) {
    const response = await fetch(`${state.apiBaseUrl}${path}`, {
        ...options,
        headers: {
            ...(options.headers || {}),
            Authorization: state.token ? `Bearer ${state.token}` : "",
        },
    });

    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "FALHA NA COMUNICAÇÃO COM A API.");
    }

    return response.json();
}

async function login(credentials) {
    const response = await fetch(`${state.apiBaseUrl}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(body.error || "NÃO FOI POSSÍVEL ENTRAR.");
    }

    state.token = body.token;
    state.user = body.user;
    localStorage.setItem("token", body.token);
    localStorage.setItem("user", JSON.stringify(body.user));
}

async function bootstrap() {
    if (!state.token || !state.user) {
        setActiveScreen("login");
        return;
    }

    try {
        await loadVehiclesAndCatalog();
        renderHome();
        setActiveScreen("home");
        syncPendingChecklists({ silent: true });
    } catch (error) {
        logout();
        showToast(error.message, true);
    }
}

async function loadVehiclesAndCatalog() {
    const now = new Date();
    try {
        const [vehicles, catalog, activities, washOverview] = await Promise.all([
            apiFetch("/veiculos?ativos=true"),
            apiFetch("/config/checklists"),
            apiFetch("/atividades?status=ABERTA"),
            apiFetch(`/lavagens/visao?ano=${now.getFullYear()}&mes=${now.getMonth() + 1}`),
        ]);
        state.vehicles = vehicles.filter((vehicle) => vehicle.ativo !== false);
        state.catalog = normalizeCatalog(catalog);
        state.activities = activities || [];
        state.washOverview = washOverview;
        cacheOfflineReferenceData();
    } catch (error) {
        if (loadOfflineReferenceData()) {
            state.activities = [];
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
    refreshSyncQueuePanel();
}

function openChecklistMenu() {
    renderVehicles();
    setActiveScreen("vehicles");
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
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function withChecklistQueueStore(mode, action) {
    const db = await openOfflineDb();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(CHECKLIST_QUEUE_STORE, mode);
        const store = transaction.objectStore(CHECKLIST_QUEUE_STORE);
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
            <small>${resumo.pendentes || 0} PENDENTES | ${resumo.instalados || 0} INSTALADOS | ${resumo.nao_instalados || 0} NÃO INSTALADOS</small>
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
            <button type="button" class="status-button nc" data-status="NAO_INSTALADO">NÃO INSTALADO</button>
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
    `;

    const statusButtons = card.querySelectorAll(".activity-status-group .status-button");
    statusButtons.forEach((button) => {
        if (button.dataset.status === item.status_execucao) {
            button.classList.add("active");
        }
        button.addEventListener("click", () => {
            statusButtons.forEach((statusButton) => statusButton.classList.remove("active"));
            button.classList.add("active");
            card.dataset.status = button.dataset.status;
        });
    });
    card.dataset.status = item.status_execucao || "PENDENTE";

    card.querySelectorAll("input[type='file']").forEach((input) => {
        input.addEventListener("change", () => previewFile(input, card));
    });
    card.querySelector(".activity-save-button").addEventListener("click", () => submitActivityItem(card, activity, item));
    return card;
}

function previewFile(input, card) {
    const [file] = input.files;
    const preview = card.querySelector(input.dataset.photo === "before" ? ".before-preview" : ".after-preview");
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
}

async function submitActivityItem(card, activity, item) {
    const vehicle = item.veiculo || {};
    const status = card.dataset.status;
    if (!status || status === "PENDENTE") {
        showToast("SELECIONE INSTALADO OU NÃO INSTALADO.", true);
        return;
    }

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
        } else if (item.foto_antes) {
            payload.foto_antes = item.foto_antes;
        }
        if (afterFile) {
            payload.foto_depois = await uploadEvidence(afterFile, vehicle.frota || "EQUIPAMENTO", activity.item_nome || "ATIVIDADE", "atividade_depois", "ATIVIDADES");
        } else if (item.foto_depois) {
            payload.foto_depois = item.foto_depois;
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
            await apiFetch("/lavagens/registrar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    queue_item_id: item.queue_item_id,
                    wash_date: `${item.scheduled_date}T${(item.scheduled_shift || "MANHA") === "MANHA" ? "08:00:00" : "14:00:00"}`,
                    local: card.querySelector(".wash-location").value.trim(),
                    valor: item.valor_sugerido,
                    tipo_equipamento: item.categoria_lavagem,
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

function renderWashes() {
    const scheduleItems = getWashScheduleItems();
    const pendingItems = scheduleItems.filter((item) => item.status_execucao !== "LAVADO");
    const days = state.washOverview?.cronograma?.days || [];
    const period = state.washOverview?.periodo || {};

    elements.washCounter.textContent = `${pendingItems.length} PROGRAMADOS`;
    elements.washes.querySelector(".list-toolbar span").textContent = "ESCOLHA O DIA E REGISTRE O PARECER.";
    elements.washMonthTitle.textContent = String(period.rotulo || `${state.washMonth}/${state.washYear}`).toUpperCase();
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
    `;
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

    renderWashShift("MANHÃ", selectedDay.morning || []);
    renderWashShift("TARDE", selectedDay.afternoon || []);
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

function makeWashCard(item, index) {
    const status = item.status_execucao || "PENDENTE";
    const isWashed = status === "LAVADO";
    const isNotTaken = status === "NAO_CUMPRIDO" || status === "NAO_LEVADO";
    const statusLabel = isWashed ? "LAVADO" : isNotTaken ? "NÃO LEVADO" : "PENDENTE";
    const evidenceUrl = item.foto_path ? makeAbsoluteUrl(item.foto_path) : "";
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
    return card;
}

function selectVehicle(vehicle) {
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
            <button type="button" class="status-button nc" data-status="NC">NC</button>
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
        });
    });

    fileInput.addEventListener("change", () => {
        const [file] = fileInput.files;
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

    return card;
}

function updateProgress() {
    const cards = Array.from(document.querySelectorAll(".checklist-item-card"));
    const total = cards.length;
    const done = cards.filter((card) => card.dataset.status).length;
    const nc = cards.filter((card) => card.dataset.status === "NC").length;
    const percent = total ? Math.round((done / total) * 100) : 0;

    elements.checklistProgress.textContent = `${done} DE ${total} AVALIADOS | ${nc} NC`;
    elements.progressBar.style.width = `${percent}%`;
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

async function uploadEvidence(file, vehicleName, itemName, photoType, moduleName) {
    const formData = new FormData();
    formData.append("file", file);
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
                throw new Error(`SELECIONE OK OU NC PARA O ITEM ${card.dataset.itemName}.`);
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
                    throw new Error(`ANEXE A EVIDÊNCIA DA NC PARA ${card.dataset.itemName}.`);
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

    for (const card of cards) {
        const status = card.dataset.status;
        if (!status) {
            throw new Error(`SELECIONE OK OU NC PARA O ITEM ${card.dataset.itemName}.`);
        }

        const item = {
            item_nome: card.dataset.itemName,
            module: card.dataset.module,
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
                throw new Error(`ANEXE A EVIDÊNCIA DA NC PARA ${card.dataset.itemName}.`);
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
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setActiveScreen("login");
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
            login: document.getElementById("login").value.trim(),
            senha: document.getElementById("password").value,
        });
        await loadVehiclesAndCatalog();
        renderHome();
        setActiveScreen("home");
        showToast("LOGIN REALIZADO COM SUCESSO.");
        syncPendingChecklists({ silent: true });
    } catch (error) {
        showToast(error.message, true);
    } finally {
        elements.loginButton.disabled = false;
        elements.loginButton.textContent = "ENTRAR NO SISTEMA";
    }
}

on(elements.loginButton, "click", handleLoginSubmit);
on(elements.vehicleSearch, "input", renderVehicles);
on(elements.openChecklistMenu, "click", openChecklistMenu);
on(elements.openActivitiesMenu, "click", openActivitiesMenu);
on(elements.openWashesMenu, "click", openWashesMenu);
on(elements.washPrevMonth, "click", () => changeWashMonth(-1));
on(elements.washNextMonth, "click", () => changeWashMonth(1));
on(elements.syncNowButton, "click", () => syncPendingChecklists({ silent: false }));
on(elements.homeLogoutButton, "click", logout);
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
on(elements.activityDetailBackButton, "click", openActivitiesMenu);
on(elements.submitChecklist, "click", submitChecklist);
on(elements.backButton, "click", () => setActiveScreen("vehicles"));
on(elements.newChecklistButton, "click", () => {
    state.selectedVehicle = null;
    renderHome();
    setActiveScreen("home");
});
window.addEventListener("online", () => {
    updateConnectionStatus();
    syncPendingChecklists({ silent: true });
});
window.addEventListener("offline", updateConnectionStatus);

registerServiceWorker();
window.checklistAppReady = true;
bootstrap();
