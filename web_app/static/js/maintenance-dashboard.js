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
    governanceToggle: document.getElementById("dashboard-governance-toggle"),
    governancePanel: document.getElementById("dashboard-governance-panel"),
    governanceState: document.getElementById("dashboard-governance-state"),
    governanceTargetsForm: document.getElementById("dashboard-governance-targets-form"),
    governanceTargetAvailability: document.getElementById("governance-target-availability"),
    governanceTargetMttr: document.getElementById("governance-target-mttr"),
    governanceTargetMtbf: document.getElementById("governance-target-mtbf"),
    governanceTargetPreventive: document.getElementById("governance-target-preventive"),
    governanceClassificationForm: document.getElementById("dashboard-governance-classification-form"),
    governanceWorkOrder: document.getElementById("governance-work-order"),
    governanceFailureCause: document.getElementById("governance-failure-cause"),
    governanceAffectedComponent: document.getElementById("governance-affected-component"),
    governanceWorkShift: document.getElementById("governance-work-shift"),
    governanceCostForm: document.getElementById("dashboard-governance-cost-form"),
    governanceCostCategory: document.getElementById("governance-cost-category"),
    governanceCostAmount: document.getElementById("governance-cost-amount"),
    governanceCostDescription: document.getElementById("governance-cost-description"),
    governanceCostSupplier: document.getElementById("governance-cost-supplier"),
    governanceCostComponent: document.getElementById("governance-cost-component"),
    governanceCostOccurredAt: document.getElementById("governance-cost-occurred-at"),
    governanceCostNotes: document.getElementById("governance-cost-notes"),
    governanceCostSummary: document.getElementById("governance-cost-summary"),
    governanceCostList: document.getElementById("governance-cost-list"),
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

function formatMoney(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
}

function renderGovernanceTargets(data) {
    const targets = data.targets || {};
    dashboardElements.governanceTargetAvailability.value = targets.availability_min_percent ?? "";
    dashboardElements.governanceTargetMttr.value = targets.mttr_max_hours ?? "";
    dashboardElements.governanceTargetMtbf.value = targets.mtbf_min_hours ?? "";
    dashboardElements.governanceTargetPreventive.value = targets.preventive_compliance_min_percent ?? "";
}

async function loadGovernanceTargets() {
    renderGovernanceTargets(await apiFetch("/manutencao/governanca/metas"));
}

function renderGovernanceOrderOptions(items) {
    const selected = dashboardElements.governanceWorkOrder.value;
    const options = (items || []).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.order_number)} | ${escapeHtml(item.vehicle?.frota || "ATIVO")} | ${escapeHtml(item.status)}</option>`).join("");
    dashboardElements.governanceWorkOrder.innerHTML = `<option value="">SELECIONE UMA OS</option>${options}`;
    if (selected && [...dashboardElements.governanceWorkOrder.options].some((option) => option.value === selected)) {
        dashboardElements.governanceWorkOrder.value = selected;
    }
}

function clearGovernanceOrder() {
    dashboardElements.governanceFailureCause.value = "";
    dashboardElements.governanceAffectedComponent.value = "";
    dashboardElements.governanceWorkShift.value = "";
    dashboardElements.governanceCostSummary.textContent = "Selecione uma OS para visualizar os custos.";
    dashboardElements.governanceCostList.innerHTML = "";
    dashboardElements.governanceState.textContent = "SELECIONE UMA OS";
}

function renderGovernanceOrder(data) {
    const order = data.work_order || {};
    const classification = data.classification || {};
    const summary = data.cost_summary || {};
    dashboardElements.governanceFailureCause.value = classification.failure_cause || "";
    dashboardElements.governanceAffectedComponent.value = classification.affected_component || "";
    dashboardElements.governanceWorkShift.value = classification.work_shift || "";
    dashboardElements.governanceState.textContent = `${order.order_number || "OS"} | ${summary.records || 0} LANÇAMENTOS`;
    const categories = summary.by_category || {};
    dashboardElements.governanceCostSummary.textContent = `TOTAL: ${formatMoney(summary.total)} | PEÇAS: ${formatMoney(categories.PECA)} | MÃO DE OBRA: ${formatMoney(categories.MAO_DE_OBRA)} | EXTERNO: ${formatMoney(categories.SERVICO_EXTERNO)}`;
    const costs = data.costs || [];
    dashboardElements.governanceCostList.innerHTML = costs.length ? costs.map((cost) => `<article class="dashboard-governance-cost-row">
        <div><strong>${escapeHtml(cost.category)} | ${escapeHtml(cost.description)}</strong><span>${escapeHtml(cost.supplier_name || "SEM FORNECEDOR")} | ${escapeHtml(cost.affected_component || "SEM COMPONENTE")}</span><small>${escapeHtml(formatTvAccessDate(cost.occurred_at))} | ${formatMoney(cost.amount)}</small></div>
        <button type="button" data-governance-cost-delete="${cost.id}">EXCLUIR</button>
    </article>`).join("") : '<span class="dashboard-empty">Nenhum custo registrado nesta OS.</span>';
    dashboardElements.governanceCostList.querySelectorAll("[data-governance-cost-delete]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!window.confirm("Excluir este lançamento de custo? Esta ação ficará registrada na auditoria.")) return;
            try {
                await apiFetch(`/manutencao/os/${dashboardElements.governanceWorkOrder.value}/custos/${button.dataset.governanceCostDelete}`, { method: "DELETE" });
                await loadGovernanceOrder();
            } catch (error) {
                setDashboardState("Falha ao excluir custo", error.message, true);
            }
        });
    });
}

async function loadGovernanceOrder() {
    const workOrderId = dashboardElements.governanceWorkOrder.value;
    if (!workOrderId) {
        clearGovernanceOrder();
        return;
    }
    dashboardElements.governanceState.textContent = "CARREGANDO OS...";
    try {
        renderGovernanceOrder(await apiFetch(`/manutencao/os/${workOrderId}/governanca`));
    } catch (error) {
        clearGovernanceOrder();
        setDashboardState("Falha ao carregar governança da OS", error.message, true);
    }
}

async function saveGovernanceTargets(event) {
    event.preventDefault();
    try {
        const data = await apiFetch("/manutencao/governanca/metas", {
            method: "PUT",
            body: {
                availability_min_percent: dashboardElements.governanceTargetAvailability.value,
                mttr_max_hours: dashboardElements.governanceTargetMttr.value,
                mtbf_min_hours: dashboardElements.governanceTargetMtbf.value,
                preventive_compliance_min_percent: dashboardElements.governanceTargetPreventive.value,
            },
        });
        renderGovernanceTargets(data);
        setDashboardState("Metas de governança salvas", "Nenhum valor é assumido automaticamente.");
    } catch (error) {
        setDashboardState("Falha ao salvar metas", error.message, true);
    }
}

async function saveGovernanceClassification(event) {
    event.preventDefault();
    const workOrderId = dashboardElements.governanceWorkOrder.value;
    if (!workOrderId) {
        setDashboardState("Selecione uma OS", "Escolha a ordem antes de salvar a classificação.", true);
        return;
    }
    try {
        renderGovernanceOrder(await apiFetch(`/manutencao/os/${workOrderId}/classificacao`, {
            method: "PUT",
            body: {
                failure_cause: dashboardElements.governanceFailureCause.value,
                affected_component: dashboardElements.governanceAffectedComponent.value,
                work_shift: dashboardElements.governanceWorkShift.value,
            },
        }));
        setDashboardState("Classificação da OS salva", "O registro foi incluído na trilha de auditoria.");
    } catch (error) {
        setDashboardState("Falha ao salvar classificação", error.message, true);
    }
}

async function createGovernanceCost(event) {
    event.preventDefault();
    const workOrderId = dashboardElements.governanceWorkOrder.value;
    if (!workOrderId) {
        setDashboardState("Selecione uma OS", "Escolha a ordem antes de registrar custo.", true);
        return;
    }
    try {
        renderGovernanceOrder(await apiFetch(`/manutencao/os/${workOrderId}/custos`, {
            method: "POST",
            body: {
                category: dashboardElements.governanceCostCategory.value,
                amount: dashboardElements.governanceCostAmount.value,
                description: dashboardElements.governanceCostDescription.value,
                supplier_name: dashboardElements.governanceCostSupplier.value,
                affected_component: dashboardElements.governanceCostComponent.value,
                occurred_at: dashboardElements.governanceCostOccurredAt.value,
                notes: dashboardElements.governanceCostNotes.value,
            },
        }));
        dashboardElements.governanceCostForm.reset();
        setDashboardState("Custo registrado", "O lançamento foi vinculado somente à OS selecionada e auditado.");
    } catch (error) {
        setDashboardState("Falha ao registrar custo", error.message, true);
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
        renderGovernanceOrderOptions(orders.items);
        if (dashboardElements.governanceWorkOrder.value) await loadGovernanceOrder();
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
dashboardElements.governanceToggle.addEventListener("click", async () => {
    const willOpen = dashboardElements.governancePanel.classList.contains("hidden");
    dashboardElements.governancePanel.classList.toggle("hidden", !willOpen);
    if (!willOpen) return;
    try {
        await loadGovernanceTargets();
        await loadGovernanceOrder();
    } catch (error) {
        setDashboardState("Falha ao carregar governança", error.message, true);
    }
});
dashboardElements.governanceWorkOrder.addEventListener("change", loadGovernanceOrder);
dashboardElements.governanceTargetsForm.addEventListener("submit", saveGovernanceTargets);
dashboardElements.governanceClassificationForm.addEventListener("submit", saveGovernanceClassification);
dashboardElements.governanceCostForm.addEventListener("submit", createGovernanceCost);
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
