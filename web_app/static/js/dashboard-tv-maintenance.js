(function () {
    "use strict";

    const PAGE_COUNT = 4;
    const ROTATION_MS = 40 * 1000;
    const REFRESH_MS = 60 * 1000;
    const PAUSE_AFTER_MANUAL_MS = 60 * 1000;
    const clockFormatter = new Intl.DateTimeFormat("pt-BR", {
        timeZone: "America/Manaus",
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
    const state = { page: 0, rotationPausedUntil: 0, lastValidData: null, apiBaseUrl: "" };
    const elements = {
        slider: document.getElementById("maintenance-tv-slider"),
        pageLabel: document.getElementById("maintenance-tv-page-label"),
        dots: document.getElementById("maintenance-tv-dots"),
        clock: document.getElementById("maintenance-tv-clock"),
        connection: document.getElementById("maintenance-tv-connection"),
        pause: document.getElementById("maintenance-tv-pause"),
        fullscreen: document.getElementById("maintenance-tv-fullscreen"),
    };

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
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
        if (elements.clock) elements.clock.textContent = clockFormatter.format(new Date());
    }

    function setConnection(label, tone) {
        elements.connection.textContent = label;
        elements.connection.className = `connection-status ${tone}`;
    }

    function renderDots() {
        elements.dots.innerHTML = Array.from({ length: PAGE_COUNT }, (_, index) => (
            `<button type="button" class="page-dot${index === state.page ? " active" : ""}" aria-label="Ir para a página ${index + 1}" aria-current="${index === state.page ? "page" : "false"}" data-page="${index}"></button>`
        )).join("");
    }

    function renderPage() {
        elements.slider.style.setProperty("--current-page", state.page);
        elements.pageLabel.textContent = `PÁGINA ${state.page + 1} DE ${PAGE_COUNT}`;
        renderDots();
    }

    function pauseRotation() {
        state.rotationPausedUntil = Date.now() + PAUSE_AFTER_MANUAL_MS;
        elements.pause.setAttribute("aria-pressed", "true");
        elements.pause.textContent = "ROTAÇÃO PAUSADA";
    }

    function moveTo(page, manual = false) {
        state.page = (page + PAGE_COUNT) % PAGE_COUNT;
        if (manual) pauseRotation();
        renderPage();
    }

    function rotate() {
        if (Date.now() < state.rotationPausedUntil) return;
        moveTo(state.page + 1);
        elements.pause.setAttribute("aria-pressed", "false");
        elements.pause.textContent = "PAUSAR";
    }

    function toggleFullscreen() {
        if (document.fullscreenElement) document.exitFullscreen?.();
        else document.documentElement.requestFullscreen?.();
    }

    function handleKey(event) {
        if (["ArrowRight", "PageDown"].includes(event.key)) {
            event.preventDefault();
            moveTo(state.page + 1, true);
        } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
            event.preventDefault();
            moveTo(state.page - 1, true);
        }
    }

    function formatNumber(value) {
        return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("pt-BR") : "SEM DADOS";
    }

    function formatPercentage(value) {
        return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "SEM DADOS";
    }

    function formatHours(value) {
        return typeof value === "number" && Number.isFinite(value) ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h` : "SEM DADOS";
    }

    function setShellValue(name, value) {
        const target = document.querySelector(`[data-shell-value="${name}"]`);
        if (target) target.textContent = value;
    }

    function statusLabel(value) {
        return String(value || "SEM DADOS").replaceAll("_", " ");
    }

    function renderList(name, items, renderItem, emptyMessage) {
        const target = document.querySelector(`[data-shell-list="${name}"]`);
        if (!target) return;
        target.innerHTML = items.length ? items.map(renderItem).join("") : `<div>${escapeHtml(emptyMessage)}</div>`;
    }

    function renderTable(name, headers, items, rowRenderer, emptyMessage) {
        const target = document.querySelector(`[data-shell-table="${name}"]`);
        if (!target) return;
        target.innerHTML = `<div class="table-head">${headers.map((header) => `<b>${escapeHtml(header)}</b>`).join("")}</div>${items.length ? items.map(rowRenderer).join("") : `<div class="table-empty">${escapeHtml(emptyMessage)}</div>`}`;
    }

    function renderDashboard(data) {
        const kpis = data.kpis || {};
        const orders = kpis.work_orders || {};
        const reliability = kpis.reliability || {};
        const schedule = kpis.schedule || {};
        const preventive = kpis.preventives || {};
        const backlog = kpis.backlog || {};
        setShellValue("availability", formatPercentage(kpis.availability_percentage));
        setShellValue("unavailable", formatNumber(kpis.equipment_unavailable));
        setShellValue("maintenance", formatNumber(kpis.equipment_in_maintenance));
        setShellValue("without-forecast", formatNumber(kpis.equipment_without_forecast));
        setShellValue("open-orders", formatNumber(orders.open));
        setShellValue("overdue-orders", formatNumber(orders.overdue));
        setShellValue("in-execution", formatNumber(orders.in_execution));
        setShellValue("blocked-orders", formatNumber(orders.blocked_by_material));
        setShellValue("overdue-preventives", formatNumber(preventive.overdue));
        setShellValue("backlog", formatNumber(backlog.total));
        setShellValue("critical", formatNumber(kpis.critical_equipment));
        setShellValue("materials", formatNumber(kpis.materials_blocked));
        setShellValue("action-plans", formatNumber(kpis.action_plans_overdue));
        setShellValue("decisions", formatNumber(kpis.decisions_open));

        renderList("operational", data.operational_status || [], (item) => `<div><strong>${escapeHtml(statusLabel(item.status))}</strong><span>${formatNumber(item.total)} equipamentos</span></div>`, "Sem apontamentos operacionais.");
        renderList("offenders", data.critical_equipment || [], (item) => `<div><strong>${escapeHtml(item.vehicle)} · ${escapeHtml(statusLabel(item.status))}</strong><span>${escapeHtml(item.reason || "Sem motivo informado")}</span></div>`, "Nenhum equipamento crítico no período.");
        renderList("execution", [
            ["PROGRAMADAS", schedule.programmed], ["EXECUTADAS", schedule.executed], ["REPROGRAMADAS", schedule.rescheduled], ["NÃO EXECUTADAS", schedule.not_executed],
        ].map(([label, total]) => ({ label, total })), (item) => `<div><strong>${escapeHtml(item.label)}</strong><span>${formatNumber(item.total)}</span></div>`, "Sem programação no período.");
        renderList("preventives", data.preventives || [], (item) => `<div><strong>${escapeHtml(item.vehicle)} · ${escapeHtml(statusLabel(item.status))}</strong><span>${escapeHtml(item.title || item.code || "Preventiva")}</span></div>`, `Preventivas vencidas: ${formatNumber(preventive.overdue)}.`);
        renderList("backlog", data.backlog || [], (item) => `<div><strong>${escapeHtml(item.order_number || "OS")} · ${escapeHtml(item.vehicle)}</strong><span>${escapeHtml(item.priority)} · ${formatNumber(item.age_days)} dias</span></div>`, `Backlog atual: ${formatNumber(backlog.total)}.`);
        renderList("actions", data.action_plans?.items || [], (item) => `<div><strong>${escapeHtml(item.title || "Plano de ação")}</strong><span>${escapeHtml(item.status || "ABERTO")}</span></div>`, "Plano de ação ainda não cadastrado.");
        renderTable("schedule", ["ATIVIDADE", "STATUS", "PREVISÃO"], data.schedule || [], (item) => `<div class="table-row"><span>${escapeHtml(item.activity)}</span><span>${escapeHtml(statusLabel(item.status))}</span><span>${escapeHtml(item.scheduled_date || "Sem data")}</span></div>`, "Sem programação no período.");
        renderTable("materials", ["MATERIAL", "STATUS", "IMPACTO"], data.materials || [], (item) => `<div class="table-row"><span>${escapeHtml(item.reference)} · ${escapeHtml(item.description)}</span><span>${escapeHtml(statusLabel(item.status))}</span><span>${escapeHtml(item.vehicle)}</span></div>`, "Nenhum material bloqueante.");
        setShellValue("mttr", formatHours(reliability.mttr_hours));
        setShellValue("mtbf", formatHours(reliability.mtbf_hours));
        setConnection("DADOS ATUALIZADOS", "ok");
    }

    async function loadDashboard() {
        if (!state.apiBaseUrl) {
            setConnection("API NÃO CONFIGURADA", "error");
            return;
        }
        setConnection("ATUALIZANDO DADOS", "neutral");
        try {
            const response = await fetch(`${state.apiBaseUrl}/api/dashboard-tv/manutencao`, { cache: "no-store" });
            const body = await response.json().catch(() => ({}));
            if (!response.ok || body.success === false) throw new Error(body.error || "Falha ao carregar o Dashboard TV.");
            state.lastValidData = body.data || body;
            renderDashboard(state.lastValidData);
        } catch (error) {
            setConnection(state.lastValidData ? "ÚLTIMO DADO VÁLIDO" : "FALHA DE COMUNICAÇÃO", "error");
        }
    }

    elements.dots.addEventListener("click", (event) => {
        const button = event.target.closest("[data-page]");
        if (button) moveTo(Number(button.dataset.page), true);
    });
    document.getElementById("maintenance-tv-prev").addEventListener("click", () => moveTo(state.page - 1, true));
    document.getElementById("maintenance-tv-next").addEventListener("click", () => moveTo(state.page + 1, true));
    elements.pause.addEventListener("click", () => {
        if (Date.now() < state.rotationPausedUntil) {
            state.rotationPausedUntil = 0;
            elements.pause.setAttribute("aria-pressed", "false");
            elements.pause.textContent = "PAUSAR";
            return;
        }
        pauseRotation();
    });
    elements.fullscreen.addEventListener("click", toggleFullscreen);
    document.addEventListener("keydown", handleKey);

    state.apiBaseUrl = resolveApiBaseUrl();
    updateClock();
    renderPage();
    window.setInterval(updateClock, 1000);
    window.setInterval(rotate, ROTATION_MS);
    window.setInterval(loadDashboard, REFRESH_MS);
    loadDashboard();

    window.MaintenanceTvShell = {
        setData(data) { state.lastValidData = data || null; renderDashboard(state.lastValidData || {}); },
        setError() { setConnection(state.lastValidData ? "ÚLTIMO DADO VÁLIDO" : "FALHA DE COMUNICAÇÃO", "error"); },
        goToPage: (page) => moveTo(Number(page), true),
    };
}());
