const DASHBOARD_SESSION_TIMEOUT_MS = 30 * 60 * 1000;
const DASHBOARD_CLOCK_FORMAT = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Manaus",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});

const dashboardState = {
    apiBaseUrl: "",
    token: "",
    user: null,
    filters: null,
};

const dashboardElements = {
    content: document.getElementById("dashboard-content"),
    accessState: document.getElementById("dashboard-access-state"),
    subtitle: document.getElementById("dashboard-subtitle"),
    clock: document.getElementById("dashboard-clock"),
    lastUpdate: document.getElementById("dashboard-last-update"),
    refresh: document.getElementById("dashboard-refresh"),
    dateFrom: document.getElementById("dashboard-date-from"),
    dateTo: document.getElementById("dashboard-date-to"),
    family: document.getElementById("dashboard-family"),
    vehicle: document.getElementById("dashboard-vehicle"),
    location: document.getElementById("dashboard-location"),
    applyFilters: document.getElementById("dashboard-apply-filters"),
    clearFilters: document.getElementById("dashboard-clear-filters"),
    familyAvailability: document.getElementById("dashboard-family-availability"),
    preventiveList: document.getElementById("dashboard-preventive-list"),
    criticalList: document.getElementById("dashboard-critical-list"),
    ordersTable: document.getElementById("dashboard-orders-table"),
    availabilityCaption: document.getElementById("dashboard-availability-caption"),
    preventiveCaption: document.getElementById("dashboard-preventive-caption"),
    criticalCaption: document.getElementById("dashboard-critical-caption"),
    ordersCaption: document.getElementById("dashboard-orders-caption"),
    dataGap: document.getElementById("dashboard-data-gap"),
    operationalStatusChart: document.getElementById("dashboard-operational-status-chart"),
    workOrderStatusChart: document.getElementById("dashboard-work-order-status-chart"),
    preventiveStatusChart: document.getElementById("dashboard-preventive-status-chart"),
    operationalTrend: document.getElementById("dashboard-operational-trend"),
    unavailabilityReasonsChart: document.getElementById("dashboard-unavailability-reasons-chart"),
    statusCaption: document.getElementById("dashboard-status-caption"),
    workOrderChartCaption: document.getElementById("dashboard-work-order-chart-caption"),
    preventiveChartCaption: document.getElementById("dashboard-preventive-chart-caption"),
    trendCaption: document.getElementById("dashboard-trend-caption"),
    reasonCaption: document.getElementById("dashboard-reason-caption"),
    performance: document.getElementById("dashboard-performance"),
    tvAccessToggle: document.getElementById("dashboard-tv-access-toggle"),
    tvAccessPanel: document.getElementById("dashboard-tv-access-panel"),
    tvAccessName: document.getElementById("dashboard-tv-access-name"),
    tvAccessDuration: document.getElementById("dashboard-tv-access-duration"),
    tvAccessCreate: document.getElementById("dashboard-tv-access-create"),
    tvAccessResult: document.getElementById("dashboard-tv-access-result"),
    tvAccessList: document.getElementById("dashboard-tv-access-list"),
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function setDashboardState(title, message = "", isError = false) {
    dashboardElements.accessState.classList.toggle("error", isError);
    dashboardElements.accessState.innerHTML = `<strong>${escapeHtml(title)}</strong>${message ? `<span>${escapeHtml(message)}</span>` : ""}`;
}

function getDefaultRange() {
    const now = new Date();
    const date = new Intl.DateTimeFormat("en-CA", {
        timeZone: "America/Manaus", year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(now).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
    return { from: `${date.year}-${date.month}-01`, to: `${date.year}-${date.month}-${date.day}` };
}

function resolveApiBaseUrl() {
    const saved = localStorage.getItem("apiBaseUrl") || "";
    const configured = window.CHECKLIST_CONFIG?.API_BASE_URL || "";
    return (saved || configured).replace(/\/$/, "");
}

function hasDashboardSession() {
    const lastActivityAt = Number(localStorage.getItem("sessionLastActivityAt") || 0);
    return Boolean(
        dashboardState.token
        && dashboardState.user
        && lastActivityAt
        && Date.now() - lastActivityAt < DASHBOARD_SESSION_TIMEOUT_MS
    );
}

function updateClock() {
    dashboardElements.clock.textContent = DASHBOARD_CLOCK_FORMAT.format(new Date());
}

function refreshSessionActivity() {
    localStorage.setItem("sessionLastActivityAt", String(Date.now()));
}

async function apiFetch(path, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
        const headers = { Authorization: `Bearer ${dashboardState.token}` };
        if (options.body !== undefined) headers["Content-Type"] = "application/json";
        const response = await fetch(`${dashboardState.apiBaseUrl}${path}`, {
            method: options.method || "GET",
            headers,
            body: options.body === undefined ? undefined : JSON.stringify(options.body),
            signal: controller.signal,
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || body.success === false) {
            const error = new Error(body.error || "Não foi possível carregar o dashboard.");
            error.status = response.status;
            throw error;
        }
        refreshSessionActivity();
        return Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error("A API demorou demais para responder.");
        }
        throw error;
    } finally {
        window.clearTimeout(timeout);
    }
}

function buildQuery() {
    const params = new URLSearchParams();
    const values = [
        ["data_inicial", dashboardElements.dateFrom.value],
        ["data_final", dashboardElements.dateTo.value],
        ["familia_id", dashboardElements.family.value],
        ["veiculo_id", dashboardElements.vehicle.value],
        ["local_id", dashboardElements.location.value],
    ];
    values.forEach(([key, value]) => { if (value) params.set(key, value); });
    return params.toString();
}

function withQuery(path) {
    const query = buildQuery();
    return query ? `${path}?${query}` : path;
}

function setKpi(id, value, detail = "") {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
    const detailElement = document.getElementById(`${id}-detail`);
    if (detailElement) detailElement.textContent = detail;
}

function formatHours(value) {
    return typeof value === "number" ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} h` : "SEM DADOS";
}

function renderSummary(data) {
    const kpis = data.kpis || {};
    const orders = kpis.work_orders || {};
    const reliability = kpis.reliability || {};
    document.getElementById("kpi-equipment-total").textContent = kpis.equipment_total ?? "--";
    document.getElementById("kpi-available").textContent = kpis.equipment_available ?? "--";
    document.getElementById("kpi-unavailable").textContent = kpis.equipment_unavailable ?? "--";
    document.getElementById("kpi-maintenance").textContent = kpis.equipment_in_maintenance ?? "--";
    document.getElementById("kpi-availability").textContent = typeof kpis.availability_percentage === "number" ? `${kpis.availability_percentage.toFixed(2)}%` : "SEM DADOS";
    document.getElementById("kpi-measured").textContent = `${kpis.availability_measured_equipment || 0} EQUIPAMENTOS MEDIDOS`;
    document.getElementById("kpi-open-orders").textContent = orders.open ?? "--";
    document.getElementById("kpi-overdue-orders").textContent = `${orders.overdue || 0} VENCIDAS | ${orders.blocked_by_material || 0} BLOQUEADAS`;
    document.getElementById("kpi-preventives").textContent = kpis.preventives_due_or_overdue ?? "--";
    document.getElementById("kpi-reliability").textContent = `${formatHours(reliability.mttr_hours)} / ${formatHours(reliability.mtbf_hours)}`;
    document.getElementById("kpi-reliability-detail").textContent = `${reliability.completed_repairs || 0} REPAROS | ${reliability.comparable_failures || 0} FALHAS COMPARÁVEIS`;

    const gaps = data.data_availability || {};
    dashboardElements.dataGap.innerHTML = `<strong>Indicadores ainda indisponíveis</strong><p>${escapeHtml(gaps.reason || "Não há dados suficientes para todos os indicadores.")}</p>`;
}

function renderAvailability(data) {
    const groups = data.by_family || [];
    dashboardElements.availabilityCaption.textContent = `${data.summary?.measured_equipment || 0} EQUIPAMENTOS MEDIDOS`;
    dashboardElements.familyAvailability.innerHTML = groups.length ? groups.map((group) => {
        const percentage = typeof group.availability_percentage === "number" ? group.availability_percentage : 0;
        return `<article class="dashboard-family-row">
            <div><strong>${escapeHtml(group.family_name)}</strong><span>${group.total} ATIVOS | ${group.available} DISPONÍVEIS</span></div>
            <div class="dashboard-progress" aria-label="Disponibilidade ${percentage}%"><i style="width:${Math.max(0, Math.min(100, percentage))}%"></i></div>
            <em>${group.availability_percentage === null ? "SEM DADOS" : `${percentage.toFixed(2)}%`}</em>
        </article>`;
    }).join("") : '<span class="dashboard-empty">Não há equipamentos para os filtros selecionados.</span>';
}

function chartStatusClass(value) {
    return `status-${String(value || "sem-dados").toLowerCase().replace(/_/g, "-")}`;
}

function renderBarChart(element, items, getLabel, emptyMessage) {
    const max = Math.max(1, ...items.map((item) => Number(item.total) || 0));
    element.innerHTML = items.length ? items.map((item) => {
        const total = Number(item.total) || 0;
        const label = getLabel(item);
        const width = Math.max(0, Math.min(100, (total / max) * 100));
        return `<div class="dashboard-bar-row ${chartStatusClass(item.status)}"><strong title="${escapeHtml(label)}">${escapeHtml(label)}</strong><div class="dashboard-bar-track"><i style="width:${width}%"></i></div><em>${total}</em></div>`;
    }).join("") : `<span class="dashboard-empty">${escapeHtml(emptyMessage)}</span>`;
}

function renderOperationalTrend(items) {
    const max = Math.max(1, ...items.map((item) => Number(item.total) || 0));
    dashboardElements.operationalTrend.innerHTML = items.length ? items.map((item) => {
        const total = Number(item.total) || 0;
        const height = Math.max(4, Math.min(100, (total / max) * 100));
        const day = String(item.date || "");
        const label = day.length === 10 ? `${day.slice(8, 10)}/${day.slice(5, 7)}` : day;
        return `<div class="dashboard-trend-column" title="${escapeHtml(`${day}: ${total} apontamentos`)}"><i style="height:${height}%"></i><span>${escapeHtml(label)}</span></div>`;
    }).join("") : '<span class="dashboard-empty">Nao ha apontamentos operacionais no periodo selecionado.</span>';
}

function renderCharts(data) {
    const operationalLabels = {
        DISPONIVEL: "DISPONIVEL",
        INDISPONIVEL: "INDISPONIVEL",
        RESTRICAO: "RESTRICAO",
        MANUTENCAO: "EM MANUTENCAO",
        SEM_APONTAMENTO: "SEM APONTAMENTO",
    };
    renderAvailability({
        summary: data.availability_summary || {},
        by_family: data.availability_by_family || [],
    });
    renderBarChart(
        dashboardElements.operationalStatusChart,
        data.operational_status || [],
        (item) => operationalLabels[item.status] || item.status,
        "Nao ha ativos para os filtros selecionados.",
    );
    renderBarChart(
        dashboardElements.workOrderStatusChart,
        data.work_orders_by_status || [],
        (item) => item.status || "SEM STATUS",
        "Nao ha ordens de servico para os filtros selecionados.",
    );
    renderBarChart(
        dashboardElements.preventiveStatusChart,
        data.preventives_by_status || [],
        (item) => item.status || "SEM DADOS",
        "Nao ha planos preventivos ativos para os filtros selecionados.",
    );
    renderOperationalTrend(data.operational_events_trend || []);
    renderBarChart(
        dashboardElements.unavailabilityReasonsChart,
        data.unavailability_reasons || [],
        (item) => item.reason || "SEM MOTIVO REGISTRADO",
        "Nao ha motivos de indisponibilidade registrados no periodo.",
    );
    dashboardElements.statusCaption.textContent = `${(data.operational_status || []).reduce((total, item) => total + (Number(item.total) || 0), 0)} ATIVOS`;
    dashboardElements.workOrderChartCaption.textContent = `${(data.work_orders_by_status || []).reduce((total, item) => total + (Number(item.total) || 0), 0)} OS`;
    dashboardElements.preventiveChartCaption.textContent = `${(data.preventives_by_status || []).reduce((total, item) => total + (Number(item.total) || 0), 0)} PLANOS`;
    dashboardElements.trendCaption.textContent = `${(data.operational_events_trend || []).length} DIAS COM EVENTOS`;
    dashboardElements.reasonCaption.textContent = `${(data.unavailability_reasons || []).length} MOTIVOS`;
    const performance = data.performance || {};
    dashboardElements.performance.textContent = performance.cached
        ? `GRAFICOS REUTILIZADOS DO CACHE OPERACIONAL (${performance.cache_ttl_seconds || 0} s).`
        : `CONSULTA DOS GRAFICOS: ${performance.query_duration_ms ?? "--"} ms. CACHE OPERACIONAL: ${performance.cache_ttl_seconds || 0} s.`;
}

function formatTvAccessDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : DASHBOARD_CLOCK_FORMAT.format(date);
}

function renderTvAccesses(items) {
    dashboardElements.tvAccessList.innerHTML = items.length ? items.map((item) => {
        const state = item.active ? "ATIVO" : (item.revoked_at ? "REVOGADO" : "EXPIRADO");
        const action = item.active ? `<button type="button" data-tv-access-revoke="${item.id}">REVOGAR</button>` : "";
        return `<article class="dashboard-tv-access-row"><div><strong>${escapeHtml(item.name)}</strong><span>${state} | EXPIRA: ${escapeHtml(formatTvAccessDate(item.expires_at))}</span><small>ULTIMO USO: ${escapeHtml(formatTvAccessDate(item.last_used_at))}</small></div>${action}</article>`;
    }).join("") : '<span class="dashboard-empty">Nenhum acesso TV foi gerado.</span>';
    dashboardElements.tvAccessList.querySelectorAll("[data-tv-access-revoke]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!window.confirm("Revogar este acesso TV imediatamente?")) return;
            try {
                await apiFetch(`/dashboard-manutencao/tv/acessos/${button.dataset.tvAccessRevoke}`, { method: "DELETE" });
                await loadTvAccesses();
            } catch (error) {
                setDashboardState("Falha ao revogar acesso TV", error.message, true);
            }
        });
    });
}

async function loadTvAccesses() {
    const data = await apiFetch("/dashboard-manutencao/tv/acessos");
    renderTvAccesses(data.items || []);
}

async function createTvAccess() {
    dashboardElements.tvAccessCreate.disabled = true;
    dashboardElements.tvAccessCreate.textContent = "GERANDO...";
    try {
        const data = await apiFetch("/dashboard-manutencao/tv/acessos", {
            method: "POST",
            body: {
                name: dashboardElements.tvAccessName.value,
                expires_in_minutes: Number(dashboardElements.tvAccessDuration.value),
            },
        });
        dashboardElements.tvAccessResult.classList.remove("hidden");
        dashboardElements.tvAccessResult.innerHTML = `<strong>Codigo gerado. Copie agora: ele nao sera mostrado novamente.</strong><code>${escapeHtml(data.token)}</code><span>Expira em: ${escapeHtml(formatTvAccessDate(data.access?.expires_at))}</span>`;
        await loadTvAccesses();
    } catch (error) {
        setDashboardState("Falha ao gerar acesso TV", error.message, true);
    } finally {
        dashboardElements.tvAccessCreate.disabled = false;
        dashboardElements.tvAccessCreate.textContent = "GERAR CODIGO";
    }
}

function renderPreventives(data) {
    const items = data.items || [];
    dashboardElements.preventiveCaption.textContent = `${data.total_due_or_overdue || 0} ITENS`;
    dashboardElements.preventiveList.innerHTML = items.length ? items.slice(0, 6).map((item) => {
        const due = item.due || {};
        return `<article class="dashboard-simple-row"><strong>${escapeHtml(item.code)} - ${escapeHtml(item.title)}</strong><span>${escapeHtml(item.vehicle?.frota || "EQUIPAMENTO")} | ${escapeHtml(item.priority || "SEM PRIORIDADE")}</span><span>${due.overdue ? "VENCIDA" : "PRÓXIMA DO VENCIMENTO"}</span></article>`;
    }).join("") : '<span class="dashboard-empty">Não há preventivas vencendo ou vencidas no filtro.</span>';
}

function formatCriticalReasons(reasons) {
    const labels = {
        STATUS_OPERACIONAL: "STATUS OPERACIONAL",
        PREVENTIVA_VENCENDO_OU_VENCIDA: "PREVENTIVA",
        OS_EM_ABERTO: "OS EM ABERTO",
        EMERGENCIAL_ABERTA: "EMERGENCIAL",
    };
    return (reasons || []).map((reason) => labels[reason] || reason).join(" | ");
}

function renderCriticalEquipment(data) {
    const items = data.items || [];
    dashboardElements.criticalCaption.textContent = `${data.total || 0} ATIVOS`;
    dashboardElements.criticalList.innerHTML = items.length ? items.map((item) => `<article class="dashboard-critical-row">
        <div><strong>${escapeHtml(item.vehicle?.frota || "EQUIPAMENTO")}</strong><span>${escapeHtml(item.family?.name || "SEM FAMÍLIA")} | ${escapeHtml(item.location?.full_name || "SEM LOCAL")}</span></div>
        <div><span class="dashboard-status-badge">${escapeHtml(item.operational_status || "SEM APONTAMENTO")}</span><span>${escapeHtml(item.status_reason || "Sem motivo operacional informado.")}</span><span class="dashboard-reasons">${escapeHtml(formatCriticalReasons(item.reasons))}</span></div>
        <strong>${escapeHtml(item.criticality || "MEDIA")}</strong>
    </article>`).join("") : '<span class="dashboard-empty">Nenhum equipamento crítico identificado para os filtros selecionados.</span>';
}

function renderOrders(data) {
    const items = data.items || [];
    dashboardElements.ordersCaption.textContent = `${data.total || 0} REGISTROS`;
    dashboardElements.ordersTable.innerHTML = items.length ? items.map((item) => `<tr>
        <td>${escapeHtml(item.order_number)}</td><td>${escapeHtml(item.vehicle?.frota || "-")}</td><td>${escapeHtml(item.source || "-")}</td>
        <td class="${item.overdue ? "status-overdue" : ""}">${escapeHtml(item.status || "-")}</td><td>${escapeHtml(item.scheduled_date || "-")}</td>
        <td>${item.age_days === null ? "-" : `${item.age_days} dias`}</td><td>${escapeHtml(item.assigned_mechanic?.nome || "NÃO ATRIBUÍDA")}</td>
    </tr>`).join("") : '<tr><td colspan="7">Não há ordens de serviço para os filtros selecionados.</td></tr>';
}

function appendOptions(select, items, label) {
    select.innerHTML = `<option value="">${label}</option>${items.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")}`;
}

function syncVehicleOptions() {
    const options = dashboardState.filters?.vehicles || [];
    const familyId = dashboardElements.family.value;
    const locationId = dashboardElements.location.value;
    const filtered = options.filter((item) => (!familyId || String(item.family_id) === familyId) && (!locationId || String(item.location_id) === locationId));
    appendOptions(dashboardElements.vehicle, filtered.map((item) => ({ id: item.id, label: `${item.frota} - ${item.modelo}` })), "TODOS");
}

function renderFilterOptions(data) {
    dashboardState.filters = data;
    appendOptions(dashboardElements.family, (data.families || []).map((item) => ({ id: item.id, label: item.name })), "TODAS");
    appendOptions(dashboardElements.location, (data.locations || []).map((item) => ({ id: item.id, label: item.full_name })), "TODOS");
    syncVehicleOptions();
}

async function loadDashboard() {
    dashboardElements.refresh.disabled = true;
    dashboardElements.refresh.textContent = "ATUALIZANDO...";
    setDashboardState("Atualizando dados operacionais", "Consultando somente registros reais da base.");
    try {
        const [summary, charts, preventives, critical, orders] = await Promise.all([
            apiFetch(withQuery("/dashboard-manutencao/resumo")),
            apiFetch(withQuery("/dashboard-manutencao/graficos")),
            apiFetch(withQuery("/dashboard-manutencao/preventivas")),
            apiFetch(withQuery("/dashboard-manutencao/ativos-criticos")),
            apiFetch(`${withQuery("/dashboard-manutencao/ordens")}${buildQuery() ? "&" : "?"}tamanho_pagina=20`),
        ]);
        renderSummary(summary);
        renderCharts(charts);
        renderPreventives(preventives);
        renderCriticalEquipment(critical);
        renderOrders(orders);
        dashboardElements.content.classList.remove("hidden");
        setDashboardState("Dados operacionais atualizados", "Indicadores sem histórico suficiente são exibidos como sem dados.");
        dashboardElements.lastUpdate.textContent = `ATUALIZADO EM ${DASHBOARD_CLOCK_FORMAT.format(new Date())}`;
    } catch (error) {
        if (error.status === 401) {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            window.location.href = "../";
            return;
        }
        const accessError = error.status === 403;
        setDashboardState(accessError ? "Acesso não permitido" : "Falha ao carregar o dashboard", error.message, true);
        if (accessError) dashboardElements.content.classList.add("hidden");
    } finally {
        dashboardElements.refresh.disabled = false;
        dashboardElements.refresh.textContent = "ATUALIZAR";
    }
}

async function bootstrapDashboard() {
    updateClock();
    window.setInterval(updateClock, 1000);
    dashboardState.apiBaseUrl = resolveApiBaseUrl();
    dashboardState.token = localStorage.getItem("token") || "";
    try { dashboardState.user = JSON.parse(localStorage.getItem("user") || "null"); } catch { dashboardState.user = null; }
    if (!hasDashboardSession() || !dashboardState.apiBaseUrl) {
        setDashboardState("Sessão necessária", "Entre no sistema para acessar o Dashboard Operacional de Manutenção.", true);
        return;
    }
    dashboardElements.subtitle.textContent = `${dashboardState.user.nome || dashboardState.user.login} | ${String(dashboardState.user.tipo || "").toUpperCase()} | BASE CONECTADA`;
    const range = getDefaultRange();
    dashboardElements.dateFrom.value = range.from;
    dashboardElements.dateTo.value = range.to;
    try {
        renderFilterOptions(await apiFetch("/dashboard-manutencao/filtros"));
        await loadDashboard();
    } catch (error) {
        setDashboardState("Falha ao preparar o dashboard", error.message, true);
    }
}

dashboardElements.refresh.addEventListener("click", loadDashboard);
dashboardElements.applyFilters.addEventListener("click", loadDashboard);
dashboardElements.tvAccessToggle.addEventListener("click", async () => {
    const willOpen = dashboardElements.tvAccessPanel.classList.contains("hidden");
    dashboardElements.tvAccessPanel.classList.toggle("hidden", !willOpen);
    if (!willOpen) return;
    dashboardElements.tvAccessResult.classList.add("hidden");
    try {
        await loadTvAccesses();
    } catch (error) {
        setDashboardState("Falha ao carregar acessos TV", error.message, true);
    }
});
dashboardElements.tvAccessCreate.addEventListener("click", createTvAccess);
dashboardElements.clearFilters.addEventListener("click", () => {
    const range = getDefaultRange();
    dashboardElements.dateFrom.value = range.from;
    dashboardElements.dateTo.value = range.to;
    dashboardElements.family.value = "";
    dashboardElements.location.value = "";
    syncVehicleOptions();
    loadDashboard();
});
dashboardElements.family.addEventListener("change", syncVehicleOptions);
dashboardElements.location.addEventListener("change", syncVehicleOptions);
document.addEventListener("pointerdown", refreshSessionActivity, { passive: true });
document.addEventListener("keydown", refreshSessionActivity);

bootstrapDashboard();
