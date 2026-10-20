import { getMixComparisons } from "../api.js";
import { safeURL } from "../utils/security.js";

const VERSION_LABELS = { before: "Antes", after: "Depois" };
let disposePlayers = () => {};

function formatTime(value) {
    if (!Number.isFinite(value) || value < 0) return "0:00";
    return `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2, "0")}`;
}

function validProject(project) {
    return project && Number.isInteger(Number(project.id)) && Number(project.id) > 0
        && safeURL(project.audio_before_url) && safeURL(project.audio_after_url);
}

function mountPlayer(card, project, activate, ownsPlayback) {
    const root = document.createElement("div");
    root.className = "hit-mix";
    root.setAttribute("role", "group");
    root.setAttribute("aria-label", `Comparar mixagem de ${project.titulo}`);
    root.innerHTML = `
        <div class="hit-mix__versions" role="group" aria-label="Versão da mixagem">
            <button type="button" data-mix-version="before" aria-pressed="true">Antes</button>
            <button type="button" data-mix-version="after" aria-pressed="false">Depois</button>
        </div>
        <div class="hit-mix__wave">
            <div class="hit-mix__bars" aria-hidden="true"></div>
            <input type="range" data-mix-progress min="0" max="0" step="0.01" value="0" aria-label="Posição da reprodução">
        </div>
        <div class="hit-mix__controls">
            <button type="button" class="hit-mix__play" data-mix-play aria-label="Reproduzir versão Antes" title="Reproduzir versão Antes"></button>
            <div class="hit-mix__times" aria-hidden="true"><span data-mix-current>0:00</span><span>/</span><span data-mix-duration>0:00</span></div>
            <div class="hit-mix__volume">
                <button type="button" data-mix-mute aria-label="Silenciar áudio" aria-pressed="false" title="Silenciar áudio"></button>
                <input type="range" data-mix-volume min="0" max="1" step="0.05" value="1" aria-label="Volume">
            </div>
        </div>
        <p class="hit-mix__status sr-only" data-mix-status aria-live="polite"></p>
        <audio data-mix-audio="before" preload="metadata"></audio>
        <audio data-mix-audio="after" preload="metadata"></audio>`;
    card.append(root);
    const before = root.querySelector('[data-mix-audio="before"]');
    const after = root.querySelector('[data-mix-audio="after"]');
    const play = root.querySelector("[data-mix-play]");
    const progress = root.querySelector("[data-mix-progress]");
    const status = root.querySelector("[data-mix-status]");
    const volume = root.querySelector("[data-mix-volume]");
    const mute = root.querySelector("[data-mix-mute]");
    const versions = root.querySelectorAll("[data-mix-version]");
    const bars = root.querySelector(".hit-mix__bars");
    // A stylized transport indicator, not a decoded amplitude waveform.
    const heights = [24, 56, 92, 42, 70, 100, 52, 78, 36, 64, 94, 46];
    for (let index = 0; index < 36; index += 1) {
        const bar = document.createElement("span");
        bar.style.height = `${heights[index % heights.length]}%`;
        bars.append(bar);
    }
    let version = "before";
    let requestId = 0;
    let wantsPlayback = false;
    let previousVolume = 1;
    const activeAudio = () => version === "before" ? before : after;
    const inactiveAudio = () => version === "before" ? after : before;

    function seek(audio, value) {
        const time = Math.max(0, Math.min(value, Number.isFinite(audio.duration) ? audio.duration : value));
        if (audio.readyState < 1) audio.dataset.pendingTime = String(time);
        try { audio.currentTime = time; }
        catch { audio.dataset.pendingTime = String(time); }
    }

    function updateTimeline() {
        const audio = activeAudio();
        const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
        const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
        progress.max = String(duration);
        progress.value = String(Math.min(current, duration || current));
        root.querySelector("[data-mix-current]").textContent = formatTime(current);
        root.querySelector("[data-mix-duration]").textContent = formatTime(duration);
        [...bars.children].forEach((bar, index) => bar.classList.toggle("is-played", duration > 0 && index / 36 < current / duration));
    }

    function updatePlayButton() {
        root.classList.toggle("is-playing", wantsPlayback);
        const label = `${wantsPlayback ? "Pausar" : "Reproduzir"} versão ${VERSION_LABELS[version]}`;
        play.setAttribute("aria-label", label);
        play.title = label;
    }

    function pause() {
        requestId += 1;
        wantsPlayback = false;
        before.pause();
        after.pause();
        updatePlayButton();
    }

    const controller = { pause };
    async function playActive() {
        const request = ++requestId;
        const audio = activeAudio();
        wantsPlayback = true;
        status.textContent = "";
        activate(controller);
        inactiveAudio().pause();
        updatePlayButton();
        try {
            await audio.play();
            if (audio !== activeAudio() || !wantsPlayback || !ownsPlayback(controller)) audio.pause();
        } catch {
            if (request === requestId) {
                wantsPlayback = false;
                status.textContent = "Não foi possível reproduzir este áudio.";
            }
        }
        updatePlayButton();
    }

    versions.forEach(button => button.addEventListener("click", () => {
        if (button.dataset.mixVersion === version) return;
        const resume = wantsPlayback;
        const time = activeAudio().currentTime || 0;
        requestId += 1;
        activeAudio().pause();
        version = button.dataset.mixVersion;
        seek(activeAudio(), time);
        versions.forEach(item => item.setAttribute("aria-pressed", String(item.dataset.mixVersion === version)));
        updateTimeline();
        updatePlayButton();
        status.textContent = `Versão ${VERSION_LABELS[version]} selecionada.`;
        if (resume) void playActive();
    }));
    play.addEventListener("click", () => {
        if (wantsPlayback) pause();
        else void playActive();
    });
    progress.addEventListener("input", () => {
        const time = Number(progress.value) || 0;
        seek(before, time);
        seek(after, time);
        updateTimeline();
    });
    function setVolume(value) {
        if (value > 0) previousVolume = value;
        [before, after].forEach(audio => { audio.volume = value; audio.muted = value === 0; });
        volume.value = String(value);
        mute.setAttribute("aria-pressed", String(value === 0));
        mute.setAttribute("aria-label", value === 0 ? "Ativar áudio" : "Silenciar áudio");
        mute.title = mute.getAttribute("aria-label");
    }
    volume.addEventListener("input", () => setVolume(Number(volume.value)));
    mute.addEventListener("click", () => setVolume(before.muted ? previousVolume : 0));
    [before, after].forEach(audio => {
        audio.addEventListener("loadedmetadata", () => {
            const pending = audio.dataset.pendingTime;
            delete audio.dataset.pendingTime;
            if (pending !== undefined) seek(audio, Number(pending));
            if (audio === activeAudio()) updateTimeline();
        });
        audio.addEventListener("timeupdate", () => {
            if (audio === activeAudio()) updateTimeline();
        });
        audio.addEventListener("play", () => {
            if (audio !== activeAudio() || !wantsPlayback || !ownsPlayback(controller)) audio.pause();
            updatePlayButton();
        });
        audio.addEventListener("ended", () => {
            if (audio === activeAudio()) { wantsPlayback = false; updatePlayButton(); }
        });
        audio.addEventListener("error", () => {
            if (audio === activeAudio()) {
                pause();
                status.textContent = "Não foi possível reproduzir este áudio.";
            }
        });
    });
    before.src = safeURL(project.audio_before_url);
    after.src = safeURL(project.audio_after_url);
    before.load();
    after.load();
    return controller;
}

export async function initMixComparison() {
    const track = document.getElementById("home-portfolio-track");
    if (!track) return;
    disposePlayers();
    // Keep existing links to /#mix-comparison, now pointing to the hits themselves.
    document.querySelector(".mix-showcase#mix-comparison")?.remove();
    const section = track.closest(".home-portfolio");
    if (section) {
        section.id = "mix-comparison";
        if (location.hash === "#mix-comparison") section.scrollIntoView({ block: "start", behavior: "instant" });
    }
    const heroLink = document.getElementById("mix-hero-link");
    if (heroLink) heroLink.hidden = true;
    track.querySelectorAll(".hit-mix").forEach(player => player.remove());
    let comparisons;
    try {
        const result = await getMixComparisons();
        comparisons = new Map((Array.isArray(result) ? result : []).filter(validProject).map(p => [String(p.id), p]));
    } catch {
        return; // Hits still work if comparison audio is unavailable.
    }
    const controllers = [];
    let owner = null;
    const activate = current => {
        owner = current;
        controllers.forEach(controller => { if (controller !== current) controller.pause(); });
    };
    track.querySelectorAll(".home-hit[data-project-id]").forEach(card => {
        const project = comparisons.get(card.dataset.projectId);
        if (project) controllers.push(mountPlayer(card, project, activate, current => owner === current));
    });
    const pauseAll = () => controllers.forEach(controller => controller.pause());
    window.addEventListener("pagehide", pauseAll);
    disposePlayers = () => { pauseAll(); window.removeEventListener("pagehide", pauseAll); };
    if (heroLink) heroLink.hidden = controllers.length === 0;
}
