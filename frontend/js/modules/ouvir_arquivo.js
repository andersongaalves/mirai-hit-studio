// In-page player for previews and deliveries, in the portfolio player's style:
// round play button, timeline with times and, when there are two versions
// (with tag / original), a toggle that keeps the position. Nothing is saved
// to disk; the audio loads on the first play.
const players = new Set();
let playing = null;

export function podeOuvir(file) {
    return /^(audio|video)\//.test(file?.mime_type || "");
}

export function pararTodos() {
    players.forEach(player => player.destroy());
    players.clear();
    playing = null;
}

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function formatTime(value) {
    if (!Number.isFinite(value) || value < 0) return "0:00";
    return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

/**
 * opcoes: [{ versao: "processada"|"original"|null, rotulo }]; load(versao) resolves a Blob.
 * ganhos: { [versao]: dB } plays each version with that gain (loudness match); a boost goes
 * through a limiter so it never clips.
 */
export function controlesOuvir(file, { opcoes, load, onError, titulo = "", inicial, ganhos = null }) {
    const wrap = el("div", "file-player");
    const audio = document.createElement("audio");
    audio.preload = "none";
    audio.className = "ouvir-arquivo__media";
    audio.setAttribute("aria-label", `Áudio: ${file.nome_exibicao}`);
    const sources = new Map(); // versao -> object URL
    let current = inicial !== undefined ? inicial : (opcoes[0]?.versao ?? null);

    if (titulo) wrap.append(el("p", "file-player__title", titulo));

    let versionButtons = [];
    if (opcoes.length > 1) {
        const versions = el("div", "file-player__versions");
        versions.setAttribute("role", "group");
        versions.setAttribute("aria-label", "Versão do áudio");
        versionButtons = opcoes.map(opcao => {
            const choice = el("button", "", opcao.rotulo);
            choice.type = "button";
            choice.dataset.versao = opcao.versao ?? "";
            choice.setAttribute("aria-pressed", String(opcao.versao === current));
            choice.addEventListener("click", () => switchTo(opcao.versao));
            versions.append(choice);
            return choice;
        });
        wrap.append(versions);
    }

    const controls = el("div", "file-player__controls");
    const play = el("button", "file-player__play");
    play.type = "button";
    play.setAttribute("aria-label", `Reproduzir ${file.nome_exibicao}`);
    play.append(el("span", "file-player__icon"));
    const timeline = el("div", "file-player__timeline");
    const range = document.createElement("input");
    range.type = "range";
    range.min = "0";
    range.max = "1000";
    range.value = "0";
    range.setAttribute("aria-label", `Posição em ${file.nome_exibicao}`);
    const times = el("div", "file-player__times");
    const elapsed = el("span", "", "0:00");
    const total = el("span", "", "--:--");
    times.append(elapsed, total);
    timeline.append(range, times);
    controls.append(play, timeline);
    const status = el("p", "file-player__status");
    status.setAttribute("aria-live", "polite");
    wrap.append(controls, status, audio);

    const setPlaying = value => {
        wrap.classList.toggle("is-playing", value);
        play.setAttribute("aria-label", `${value ? "Pausar" : "Reproduzir"} ${file.nome_exibicao}`);
    };
    const refresh = () => {
        const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
        range.value = duration ? String(Math.round(audio.currentTime / duration * 1000)) : "0";
        elapsed.textContent = formatTime(audio.currentTime);
        total.textContent = duration ? formatTime(duration) : "--:--";
    };

    async function ensure(versao) {
        if (sources.has(versao)) return sources.get(versao);
        status.textContent = "Carregando áudio...";
        wrap.classList.add("is-loading");
        try {
            const result = await load(versao);
            const blob = result?.blob instanceof Blob ? result.blob : result;
            if (!(blob instanceof Blob) || !blob.size) throw new Error("Áudio indisponível.");
            const url = URL.createObjectURL(blob);
            sources.set(versao, url);
            status.textContent = "";
            return url;
        } finally {
            wrap.classList.remove("is-loading");
        }
    }

    // Loudness match (Web Audio): gain per version; a limiter only while boosting.
    let graph = null;
    function ensureGraph() {
        if (!ganhos || graph) return;
        const Context = window.AudioContext || window.webkitAudioContext;
        if (!Context) return;
        try {
            const context = new Context();
            const source = context.createMediaElementSource(audio);
            const gain = context.createGain();
            const limiter = context.createDynamicsCompressor();
            limiter.threshold.value = -1;
            limiter.knee.value = 0;
            limiter.ratio.value = 20;
            limiter.attack.value = 0.003;
            limiter.release.value = 0.25;
            limiter.connect(context.destination);
            source.connect(gain);
            graph = { context, gain, limiter, boosting: null };
        } catch {
            graph = null;
        }
    }
    function applyGain() {
        if (!graph) return;
        const db = Number(ganhos?.[current]) || 0;
        graph.gain.gain.value = Math.pow(10, db / 20);
        const boosting = db > 0;
        if (graph.boosting === boosting) return;
        graph.gain.disconnect();
        graph.gain.connect(boosting ? graph.limiter : graph.context.destination);
        graph.boosting = boosting;
    }

    async function start() {
        try {
            ensureGraph();
            if (graph?.context.state === "suspended") await graph.context.resume();
            applyGain();
            const url = await ensure(current);
            if (audio.src !== url) audio.src = url;
            if (playing && playing !== api) playing.pause();
            playing = api;
            await audio.play();
        } catch (error) {
            status.textContent = "";
            onError?.(error);
        }
    }

    async function switchTo(versao) {
        if (versao === current) return;
        const ratio = Number.isFinite(audio.duration) && audio.duration ? audio.currentTime / audio.duration : 0;
        const resume = !audio.paused;
        current = versao;
        applyGain();
        versionButtons.forEach(choice => choice.setAttribute("aria-pressed", String((choice.dataset.versao || null) === (versao ?? null))));
        if (!audio.src && !resume) return;
        try {
            audio.src = await ensure(versao);
            audio.addEventListener("loadedmetadata", () => {
                if (Number.isFinite(audio.duration)) audio.currentTime = ratio * audio.duration;
                if (resume) start();
            }, { once: true });
        } catch (error) {
            onError?.(error);
        }
    }

    play.addEventListener("click", () => (audio.paused ? start() : audio.pause()));
    range.addEventListener("input", () => {
        if (Number.isFinite(audio.duration)) audio.currentTime = Number(range.value) * audio.duration / 1000;
    });
    audio.addEventListener("loadedmetadata", refresh);
    audio.addEventListener("timeupdate", refresh);
    audio.addEventListener("play", () => setPlaying(true));
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("ended", () => { setPlaying(false); audio.currentTime = 0; refresh(); });

    const api = {
        pause: () => audio.pause(),
        destroy: () => {
            audio.pause();
            graph?.context.close().catch(() => {});
            sources.forEach(url => URL.revokeObjectURL(url));
            sources.clear();
        },
    };
    players.add(api);
    wrap.dataset.ganhos = ganhos ? JSON.stringify(ganhos) : "";
    return wrap;
}

/** Studio users (Admin and producer): both versions when the preview was processed. */
export function opcoesEstudio(file) {
    if (file.processamento_tag === "pronto") {
        return [{ versao: "processada", rotulo: "Com tag" }, { versao: "original", rotulo: "Original" }];
    }
    return [{ versao: null, rotulo: "Áudio" }];
}

document.addEventListener("admin:logout", pararTodos);
