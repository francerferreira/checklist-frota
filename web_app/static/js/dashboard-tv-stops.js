(function () {
    "use strict";

    const PAGE_COUNT = 4;
    const ROTATION_MS = 40 * 1000;
    const REFRESH_MS = 60 * 1000;
    const PAUSE_AFTER_MANUAL_MS = 60 * 1000;
    const clockFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Manaus", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const state = { page: 0, rotationPausedUntil: 0, lastData: null };
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

    function setText(selector, value) {
        const target = document.querySelector(`[data-stop-value="${selector}"]`);
        if (target) target.textContent = value ?? "SEM DADOS";
    }
    function setProgress(selector, value) {
        const target = document.querySelector(`[data-stop-progress="${selector}"]`);
        if (target) target.style.width = `${Math.max(0, Math.min(100, Number(value) || 0))}%`;
    }
    function renderDashboard(data) {
        state.lastData = data || null;
        const period = data?.period || {};
        document.getElementById("stops-tv-period").textContent = period.label || "COMPETÊNCIA: SEM DADOS";
        document.getElementById("stops-tv-range").textContent = period.range || "PERÍODO: SEM DADOS";
        document.getElementById("stops-tv-last-update").textContent = data?.generated_at ? `ATUALIZADO EM ${data.generated_at}` : "SEM DADOS";
        document.getElementById("stops-tv-connection").textContent = data ? "DADOS ATUALIZADOS" : "SEM CONEXÃO";
    }

    document.getElementById("stops-tv-prev").addEventListener("click", () => moveTo(state.page - 1, true));
    document.getElementById("stops-tv-next").addEventListener("click", () => moveTo(state.page + 1, true));
    elements.dots.addEventListener("click", (event) => { const button = event.target.closest("[data-page]"); if (button) moveTo(Number(button.dataset.page), true); });
    document.addEventListener("keydown", handleKey);
    document.addEventListener("dblclick", toggleFullscreen);
    state.lastData = null;
    updateClock();
    renderPage();
    window.setInterval(updateClock, 1000);
    window.setInterval(rotate, ROTATION_MS);
    window.setInterval(() => { if (state.lastData) renderDashboard(state.lastData); }, REFRESH_MS);

    window.StopsTvShell = { setData: renderDashboard, goToPage: (page) => moveTo(Number(page), true), toggleFullscreen };
}());
