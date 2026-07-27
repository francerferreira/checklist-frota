(function () {
    "use strict";

    const PAGE_COUNT = 4;
    const ROTATION_MS = 40 * 1000;
    const REFRESH_MS = 60 * 1000;
    const PAUSE_AFTER_MANUAL_MS = 60 * 1000;
    const clockFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Manaus", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const state = { page: 0, rotationPausedUntil: 0, lastData: null, lastValidAt: null, apiBaseUrl: "" };
    const elements = {
        slider: document.getElementById("stops-tv-slider"),
        dots: document.getElementById("stops-tv-dots"),
        pageLabel: document.getElementById("stops-tv-page-label"),
        clock: document.getElementById("stops-tv-clock"),
    };

    function updateClock() { elements.clock.textContent = clockFormatter.format(new Date()); }
    function renderDots() {
        elements.dots.innerHTML = Array.from({ length: PAGE_COUNT }, (_, index) => `<button type="button" class="page-dot${index === state.page ? " active" : ""}" aria-label="Ir para a página ${index + 1}" data-page="${index}"></button>`).join("");
    }
    function renderPage() {
        elements.slider.style.setProperty("--current-page", state.page);
        elements.pageLabel.textContent = `PÁGINA ${state.page + 1} DE ${PAGE_COUNT}`;
        renderDots();
    }
    function pauseRotation() { state.rotationPausedUntil = Date.now() + PAUSE_AFTER_MANUAL_MS; }
    function moveTo(page, manual = false) { state.page = (page + PAGE_COUNT) % PAGE_COUNT; if (manual) pauseRotation(); renderPage(); }
    function rotate() { if (Date.now() >= state.rotationPausedUntil) moveTo(state.page + 1); }
    function toggleFullscreen() { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.(); }
    function handleKey(event) {
        if (["ArrowRight", "PageDown"].includes(event.key)) { event.preventDefault(); moveTo(state.page + 1, true); }
        if (["ArrowLeft", "PageUp"].includes(event.key)) { event.preventDefault(); moveTo(state.page - 1, true); }
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

    function formatHours(value) {
        return typeof value === "number" && Number.isFinite(value) ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} h` : "SEM DADOS";
    }

    function formatDate(value) {
        const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
        return match ? `${match[3]}/${match[2]}/${match[1]}` : "SEM DATA";
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function setConnection(message, tone) {
        const element = document.getElementById("stops-tv-connection");
        element.textContent = message;
        element.className = `connection-status ${tone}`;
    }

    function setText(selector, value) {
        const target = document.querySelector(`[data-stop-value="${selector}"]`);
        if (target) target.textContent = value ?? "SEM DADOS";
    }
    function setProgress(selector, value) {
        const target = document.querySelector(`[data-stop-progress="${selector}"]`);
        if (target) target.style.width = `${Math.max(0, Math.min(100, Number(value) || 0))}%`;
    }
    function renderTarget(code, item) {
        const prefix = code === "rtg-alfandegado" ? "rtg-alf" : code;
        setText(`${prefix}-hours`, formatHours(item?.hours));
        setText(`${prefix}-goal`, item?.goal_hours == null ? "SEM DADOS" : `${formatHours(item.goal_hours)}`);
        setText(`${prefix}-percent`, item?.percentage == null ? "SEM DADOS" : `${item.percentage.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`);
        setText(`${prefix}-balance`, item?.balance_hours == null ? "SEM DADOS" : formatHours(item.balance_hours));
        setText(`${prefix}-status`, item?.status || "SEM DADOS");
        setProgress(code, item?.percentage);
    }

    function renderChart(selector, items, labelKey, valueKey, emptyMessage) {
        const target = document.querySelector(`[data-stop-chart="${selector}"]`);
        if (!target) return;
        if (!items.length) { target.innerHTML = `<span>${escapeHtml(emptyMessage)}</span>`; return; }
        const max = Math.max(1, ...items.map((item) => Number(item[valueKey]) || 0));
        target.innerHTML = `<div class="chart-bars">${items.map((item) => `<div class="chart-bar"><strong>${escapeHtml(item[labelKey] || "SEM DADOS")}</strong><i style="height:${Math.max(3, Math.min(100, (Number(item[valueKey]) || 0) / max * 100))}%"></i><small>${escapeHtml(formatHours(item[valueKey]))}</small></div>`).join("")}</div>`;
    }

    function renderList(selector, items, renderer, emptyMessage) {
        const target = document.querySelector(`[data-stop-list="${selector}"]`);
        if (!target) return;
        target.innerHTML = items.length ? items.map(renderer).join("") : `<div>${escapeHtml(emptyMessage)}</div>`;
    }

    function renderDashboard(data) {
        state.lastData = data || null;
        const period = data?.period || {};
        document.getElementById("stops-tv-period").textContent = period.label || "COMPETÊNCIA: SEM DADOS";
        document.getElementById("stops-tv-range").textContent = period.range || "PERÍODO: SEM DADOS";
        state.lastValidAt = data?.generated_at || new Date().toISOString();
        document.getElementById("stops-tv-last-update").textContent = state.lastValidAt ? `ATUALIZADO EM ${formatDate(state.lastValidAt)} ${state.lastValidAt.slice(11, 19)}` : "SEM DADOS";
        setConnection("DADOS ATUALIZADOS", "ok");
        const targets = data?.targets || {};
        ["lbs-pier", "rtg-atr", "rtg-alfandegado", "rtg-total"].forEach((code) => renderTarget(code, targets[code]));
        renderChart("targets", ["lbs-pier", "rtg-atr", "rtg-alfandegado", "rtg-total"].map((code) => ({ label: targets[code]?.label || code, hours: targets[code]?.hours || 0, goal: targets[code]?.goal_hours || 0 })), "label", "hours", "Nenhuma parada registrada no período");
        renderChart("rtg-distribution", ["rtg-atr", "rtg-alfandegado"].map((code) => ({ label: targets[code]?.label || code, hours: targets[code]?.hours || 0 })), "label", "hours", "Nenhuma parada RTG registrada");
        renderChart("daily-trend", data?.daily_trend || [], "date", "hours", "Nenhuma parada registrada no período");
        const active = data?.active_stops || [];
        const activeTable = document.querySelector('[data-stop-table="active"]');
        activeTable.innerHTML = `<div class="table-head"><b>EQUIPAMENTO</b><b>ÁREA</b><b>INÍCIO</b><b>DURAÇÃO</b><b>MOTIVO</b><b>STATUS</b></div>${active.length ? active.map((item) => `<div class="table-row"><span><strong>${escapeHtml(item.vehicle)}</strong><small>${escapeHtml(item.family)}</small></span><span>${escapeHtml(item.area)}</span><span>${escapeHtml(item.started_at?.slice(11, 16) || "SEM HORA")}</span><span>${escapeHtml(item.duration || formatHours(item.hours))}</span><span>${escapeHtml(item.reason)}</span><span class="status-badge ${item.status === "INDISPONIVEL" ? "bad" : "warn"}">${escapeHtml(item.status)}</span></div>`).join("") : '<div class="table-empty">Nenhum equipamento parado no momento</div>'}`;
        renderList("active-summary", [{ label: "EQUIPAMENTOS PARADOS", value: data?.active_summary?.total }, { label: "HORAS EM ANDAMENTO", value: formatHours(data?.active_summary?.hours) }, { label: "MAIS ANTIGA", value: data?.active_summary?.oldest_started_at ? formatDate(data.active_summary.oldest_started_at) : "SEM DADOS" }], (item) => `<div><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.value == null ? "SEM DADOS" : item.value)}</span></div>`, "Nenhum equipamento parado no momento");
        renderList("offenders", data?.offenders || [], (item, index) => `<div><strong>${index + 1}. ${escapeHtml(item.vehicle)}</strong><span>${escapeHtml(item.area)} · ${escapeHtml(formatHours(item.hours))} · ${escapeHtml(item.events)} ocorrências</span></div>`, "Nenhum ofensor no período");
        renderList("reasons", data?.reasons || [], (item, index) => `<div><strong>${index + 1}. ${escapeHtml(item.reason)}</strong><span>${escapeHtml(formatHours(item.hours))} · ${escapeHtml(item.events)} ocorrências</span></div>`, "Nenhum motivo registrado");
        const projections = data?.projections || {};
        ["lbs", "atr", "alf"].forEach((key) => { setText(`projection-${key}`, projections[key]?.hours == null ? "SEM DADOS" : formatHours(projections[key].hours)); setText(`projection-${key}-status`, projections[key]?.status || "SEM DADOS"); });
        renderList("decisions", data?.data_availability?.projections === false ? [] : data?.decisions || [], (item) => `<div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.detail)}</span></div>`, data?.data_availability?.message || "Sem decisões para o período");
    }

    async function loadDashboard() {
        if (!state.apiBaseUrl) { setConnection("API NÃO CONFIGURADA", "error"); return; }
        setConnection("ATUALIZANDO DADOS", "warn");
        try {
            const response = await fetch(`${state.apiBaseUrl}/api/dashboard-tv/paradas`, { cache: "no-store" });
            const body = await response.json().catch(() => ({}));
            if (!response.ok || body.success === false) throw new Error(body.error || "Falha ao atualizar os dados");
            renderDashboard(body.data || body);
        } catch (error) {
            setConnection(state.lastData ? `ÚLTIMOS DADOS VÁLIDOS · ${state.lastValidAt?.slice(11, 19) || "SEM HORA"}` : "FALHA AO ATUALIZAR", "error");
        }
    }

    document.getElementById("stops-tv-prev").addEventListener("click", () => moveTo(state.page - 1, true));
    document.getElementById("stops-tv-next").addEventListener("click", () => moveTo(state.page + 1, true));
    elements.dots.addEventListener("click", (event) => { const button = event.target.closest("[data-page]"); if (button) moveTo(Number(button.dataset.page), true); });
    document.addEventListener("keydown", handleKey);
    document.addEventListener("dblclick", toggleFullscreen);
    state.apiBaseUrl = resolveApiBaseUrl();
    state.lastData = null;
    updateClock();
    renderPage();
    window.setInterval(updateClock, 1000);
    window.setInterval(rotate, ROTATION_MS);
    window.setInterval(loadDashboard, REFRESH_MS);
    loadDashboard();

    window.StopsTvShell = { setData: renderDashboard, goToPage: (page) => moveTo(Number(page), true), toggleFullscreen };
}());
