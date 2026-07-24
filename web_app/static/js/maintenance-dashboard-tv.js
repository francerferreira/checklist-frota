const TV_REFRESH_MS = 60 * 1000;
const TV_ROTATION_MS = 20 * 1000;
const TV_CLOCK_FORMAT = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Manaus",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});

const tvState = { apiBaseUrl: "", screen: 0 };
const tvElements = {
    dashboard: document.getElementById("tv-dashboard"),
    status: document.getElementById("tv-status"),
    clock: document.getElementById("tv-clock"),
    lastUpdate: document.getElementById("tv-last-update"),
    fullscreen: document.getElementById("tv-fullscreen"),
    screenLabel: document.getElementById("tv-screen-label"),
    operationalStatus: document.getElementById("tv-operational-status"),
    familyAvailability: document.getElementById("tv-family-availability"),
    trend: document.getElementById("tv-trend"),
    workOrders: document.getElementById("tv-work-orders"),
    preventives: document.getElementById("tv-preventives"),
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function resolveApiBaseUrl() {
    const requested = new URLSearchParams(window.location.search).get("api")?.trim().replace(/\/$/, "");
    const saved = localStorage.getItem("apiBaseUrl") || "";
    const configured = window.CHECKLIST_CONFIG?.API_BASE_URL || "";
    if (requested && /^https?:\/\//i.test(requested)) {
        localStorage.setItem("apiBaseUrl", requested);
        return requested;
    }
    return (saved || configured).replace(/\/$/, "");
}

function updateClock() {
    tvElements.clock.textContent = TV_CLOCK_FORMAT.format(new Date());
}

function setTvStatus(message, error = false) {
    tvElements.status.textContent = message;
    tvElements.status.classList.toggle("error", error);
}

function formatHours(value) {
    return typeof value === "number" ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} h` : "SEM DADOS";
}

function statusClass(value) {
    return `status-${String(value || "sem-dados").toLowerCase().replace(/_/g, "-")}`;
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function renderBars(element, items, labelFor, emptyMessage) {
    const max = Math.max(1, ...items.map((item) => Number(item.total) || 0));
    element.innerHTML = items.length ? items.map((item) => {
        const total = Number(item.total) || 0;
        const width = Math.max(0, Math.min(100, (total / max) * 100));
        const label = labelFor(item);
        return `<div class="tv-bar-row ${statusClass(item.status)}"><strong>${escapeHtml(label)}</strong><div class="tv-bar-track"><i style="width:${width}%"></i></div><em>${total}</em></div>`;
    }).join("") : `<span class="tv-empty">${escapeHtml(emptyMessage)}</span>`;
}

function renderFamilyAvailability(items) {
    tvElements.familyAvailability.innerHTML = items.length ? items.map((item) => {
        const percentage = typeof item.availability_percentage === "number" ? item.availability_percentage : 0;
        return `<div class="tv-family-row"><div><strong>${escapeHtml(item.family_name)}</strong><span>${item.total} ATIVOS | ${item.available} DISPONIVEIS</span></div><div class="tv-family-progress"><i style="width:${Math.max(0, Math.min(100, percentage))}%"></i></div><em>${item.availability_percentage === null ? "SEM DADOS" : `${percentage.toFixed(2)}%`}</em></div>`;
    }).join("") : '<span class="tv-empty">Nao ha disponibilidade medida para este periodo.</span>';
}

function renderTrend(items) {
    const max = Math.max(1, ...items.map((item) => Number(item.total) || 0));
    tvElements.trend.innerHTML = items.length ? items.map((item) => {
        const total = Number(item.total) || 0;
        const height = Math.max(5, Math.min(100, (total / max) * 100));
        const date = String(item.date || "");
        const label = date.length === 10 ? `${date.slice(8, 10)}/${date.slice(5, 7)}` : date;
        return `<div class="tv-trend-column" title="${escapeHtml(`${date}: ${total} apontamentos`)}"><i style="height:${height}%"></i><span>${escapeHtml(label)}</span></div>`;
    }).join("") : '<span class="tv-empty">Nao ha apontamentos operacionais no periodo.</span>';
}

function renderDashboard(data) {
    const kpis = data.kpis || {};
    const orders = kpis.work_orders || {};
    const reliability = kpis.reliability || {};
    setText("tv-kpi-total", kpis.equipment_total ?? "--");
    setText("tv-kpi-available", kpis.equipment_available ?? "--");
    setText("tv-kpi-unavailable", kpis.equipment_unavailable ?? "--");
    setText("tv-kpi-maintenance", kpis.equipment_in_maintenance ?? "--");
    setText("tv-kpi-availability", typeof kpis.availability_percentage === "number" ? `${kpis.availability_percentage.toFixed(2)}%` : "SEM DADOS");
    setText("tv-kpi-orders", orders.open ?? "--");
    setText("tv-kpi-preventives", kpis.preventives_due_or_overdue ?? "--");
    setText("tv-kpi-reliability", `${formatHours(reliability.mttr_hours)} / ${formatHours(reliability.mtbf_hours)}`);
    renderBars(tvElements.operationalStatus, data.operational_status || [], (item) => item.status || "SEM STATUS", "Nao ha ativos para o painel.");
    renderFamilyAvailability(data.availability_by_family || []);
    renderTrend(data.operational_events_trend || []);
    renderBars(tvElements.workOrders, data.work_orders_by_status || [], (item) => item.status || "SEM STATUS", "Nao ha ordens de servico.");
    renderBars(tvElements.preventives, data.preventives_by_status || [], (item) => item.status || "SEM STATUS", "Nao ha planos preventivos ativos.");
}

function renderScreen() {
    document.querySelectorAll("[data-tv-screen]").forEach((screen, index) => {
        screen.classList.toggle("active", index === tvState.screen);
    });
    tvElements.screenLabel.textContent = `PAINEL ${tvState.screen + 1} DE 3`;
}

function rotateScreen() {
    tvState.screen = (tvState.screen + 1) % 3;
    renderScreen();
}

async function loadTvDashboard() {
    setTvStatus("Atualizando dados operacionais...");
    try {
        const response = await fetch(`${tvState.apiBaseUrl}/dashboard-manutencao/tv/dados`, {
            headers: {},
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || body.success === false) {
            const error = new Error(body.error || "Nao foi possivel atualizar a tela TV.");
            error.status = response.status;
            throw error;
        }
        renderDashboard(body.data || body);
        tvElements.lastUpdate.textContent = `ATUALIZADO EM ${TV_CLOCK_FORMAT.format(new Date())}`;
        setTvStatus("Dados operacionais atualizados. A tela alterna automaticamente.");
    } catch (error) {
        setTvStatus(error.message, true);
    }
}
tvElements.fullscreen.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else document.documentElement.requestFullscreen?.();
});

tvState.apiBaseUrl = resolveApiBaseUrl();
updateClock();
window.setInterval(updateClock, 1000);
window.setInterval(rotateScreen, TV_ROTATION_MS);
window.setInterval(loadTvDashboard, TV_REFRESH_MS);
if (tvState.apiBaseUrl) {
    renderScreen();
    loadTvDashboard();
} else {
    setTvStatus("A URL da API nao esta configurada nesta tela.", true);
}
