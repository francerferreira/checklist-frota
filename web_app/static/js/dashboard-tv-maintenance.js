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
    const state = { page: 0, rotationPausedUntil: 0, lastValidData: null };
    const elements = {
        slider: document.getElementById("maintenance-tv-slider"),
        pageLabel: document.getElementById("maintenance-tv-page-label"),
        dots: document.getElementById("maintenance-tv-dots"),
        clock: document.getElementById("maintenance-tv-clock"),
        connection: document.getElementById("maintenance-tv-connection"),
        pause: document.getElementById("maintenance-tv-pause"),
        fullscreen: document.getElementById("maintenance-tv-fullscreen"),
    };

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

    function markShellReady() {
        setConnection("ESTRUTURA PRONTA · API NA ETAPA 3", "neutral");
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

    updateClock();
    renderPage();
    markShellReady();
    window.setInterval(updateClock, 1000);
    window.setInterval(rotate, ROTATION_MS);
    // Reservado para a conexão agregada da Etapa 3. Não recarrega a página.
    window.setInterval(() => {
        if (state.lastValidData) setConnection("DADOS ATUALIZADOS", "ok");
    }, REFRESH_MS);

    window.MaintenanceTvShell = {
        setData(data) {
            state.lastValidData = data || null;
            setConnection("DADOS ATUALIZADOS", "ok");
        },
        setError() {
            setConnection(state.lastValidData ? "ÚLTIMO DADO VÁLIDO" : "FALHA DE COMUNICAÇÃO", "error");
        },
        goToPage: (page) => moveTo(Number(page), true),
    };
}());
