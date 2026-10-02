import { getMixComparisons } from "../api.js";
import { safeURL } from "../utils/security.js";

const VERSION_LABELS = {
    before: "Antes",
    after: "Depois",
};

function formatTime(value) {
    if (!Number.isFinite(value) || value < 0) return "0:00";
    const minutes = Math.floor(value / 60);
    const seconds = Math.floor(value % 60).toString().padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function validProject(project) {
    return project
        && safeURL(project.audio_before_url)
        && safeURL(project.audio_after_url);
}

export async function initMixComparison() {
    const section = document.getElementById("mix-comparison");
    if (!section) return;

    let projects;
    try {
        projects = (await getMixComparisons()).filter(validProject).slice(0, 4);
    } catch (error) {
        console.warn("Não foi possível carregar as comparações de mixagem.", error);
        return;
    }

    if (!projects.length) return;

    const elements = {
        title: document.getElementById("mix-title"),
        artist: document.getElementById("mix-artist"),
        position: document.getElementById("mix-position"),
        coverWrap: document.getElementById("mix-cover-wrap"),
        cover: document.getElementById("mix-cover"),
        externalLink: document.getElementById("mix-external-link"),
        selector: document.getElementById("mix-project-selector"),
        play: document.getElementById("mix-play"),
        progress: document.getElementById("mix-progress"),
        currentTime: document.getElementById("mix-current-time"),
        duration: document.getElementById("mix-duration"),
        status: document.getElementById("mix-status"),
        heroLink: document.getElementById("mix-hero-link"),
        before: document.getElementById("mix-audio-before"),
        after: document.getElementById("mix-audio-after"),
        versionButtons: [...section.querySelectorAll("[data-mix-version]")],
    };

    let selectedIndex = 0;
    let activeVersion = "before";
    let playRequest = 0;

    const activeAudio = () => elements[activeVersion];
    const inactiveAudio = () => elements[activeVersion === "before" ? "after" : "before"];

    function setTime(audio, value) {
        try {
            audio.currentTime = value;
            delete audio.dataset.pendingTime;
        } catch {
            audio.dataset.pendingTime = String(value);
        }
    }

    function updateTimeline() {
        const audio = activeAudio();
        const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
        const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
        elements.progress.max = String(duration);
        elements.progress.value = String(Math.min(current, duration || current));
        elements.currentTime.textContent = formatTime(current);
        elements.duration.textContent = formatTime(duration);
    }

    function updatePlayButton() {
        const isPlaying = !activeAudio().paused && !activeAudio().ended;
        elements.play.querySelector("span").textContent = isPlaying ? "Ⅱ" : "▶";
        elements.play.setAttribute(
            "aria-label",
            `${isPlaying ? "Pausar" : "Reproduzir"} versão ${VERSION_LABELS[activeVersion]}`,
        );
    }

    function announce(message) {
        elements.status.textContent = message;
    }

    async function playActive() {
        const request = ++playRequest;
        const audio = activeAudio();
        inactiveAudio().pause();
        try {
            await audio.play();
            if (request !== playRequest || audio !== activeAudio()) audio.pause();
        } catch {
            announce("Não foi possível reproduzir este áudio.");
        }
        updatePlayButton();
    }

    function pauseAll() {
        playRequest += 1;
        elements.before.pause();
        elements.after.pause();
        updatePlayButton();
    }

    function setVersion(version) {
        if (version === activeVersion) return;
        const previous = activeAudio();
        const wasPlaying = !previous.paused && !previous.ended;
        const time = previous.currentTime || 0;
        playRequest += 1;
        previous.pause();
        activeVersion = version;
        setTime(activeAudio(), time);
        elements.versionButtons.forEach(button => {
            button.setAttribute("aria-pressed", String(button.dataset.mixVersion === version));
        });
        updateTimeline();
        updatePlayButton();
        announce(`Versão ${VERSION_LABELS[version]} selecionada.`);
        if (wasPlaying) void playActive();
    }

    function renderSelector() {
        elements.selector.replaceChildren();
        projects.forEach((project, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.projectIndex = String(index);
            button.setAttribute("aria-pressed", String(index === selectedIndex));
            const number = document.createElement("span");
            number.textContent = String(index + 1).padStart(2, "0");
            const name = document.createElement("strong");
            name.textContent = project.titulo;
            button.append(number, name);
            button.addEventListener("click", () => selectProject(index));
            elements.selector.append(button);
        });
        elements.selector.hidden = projects.length < 2;
    }

    function selectProject(index) {
        pauseAll();
        selectedIndex = index;
        activeVersion = "before";
        const project = projects[index];
        elements.before.src = safeURL(project.audio_before_url);
        elements.after.src = safeURL(project.audio_after_url);
        elements.before.load();
        elements.after.load();
        elements.title.textContent = project.titulo;
        elements.artist.textContent = project.artista;
        elements.position.textContent = `Comparação ${String(index + 1).padStart(2, "0")}`;

        const coverURL = safeURL(project.link_capa);
        elements.coverWrap.hidden = !coverURL;
        if (coverURL) elements.cover.src = coverURL;
        else elements.cover.removeAttribute("src");
        elements.cover.alt = coverURL ? `Capa de ${project.titulo}` : "";

        const externalURL = safeURL(project.link_audio);
        elements.externalLink.hidden = !externalURL;
        if (externalURL) elements.externalLink.href = externalURL;
        else elements.externalLink.removeAttribute("href");

        elements.versionButtons.forEach(button => {
            button.setAttribute("aria-pressed", String(button.dataset.mixVersion === "before"));
        });
        elements.selector.querySelectorAll("button").forEach((button, buttonIndex) => {
            button.setAttribute("aria-pressed", String(buttonIndex === index));
        });
        updateTimeline();
        updatePlayButton();
        announce(`${project.titulo}, versão Antes selecionada.`);
    }

    elements.versionButtons.forEach(button => {
        button.addEventListener("click", () => setVersion(button.dataset.mixVersion));
    });
    elements.play.addEventListener("click", () => {
        if (activeAudio().paused || activeAudio().ended) void playActive();
        else pauseAll();
    });
    elements.progress.addEventListener("input", () => {
        const time = Number(elements.progress.value) || 0;
        setTime(elements.before, time);
        setTime(elements.after, time);
        updateTimeline();
    });
    elements.cover.addEventListener("error", () => {
        elements.coverWrap.hidden = true;
    });

    [elements.before, elements.after].forEach(audio => {
        audio.addEventListener("loadedmetadata", () => {
            if (audio.dataset.pendingTime) setTime(audio, Number(audio.dataset.pendingTime));
            if (audio === activeAudio()) updateTimeline();
        });
        audio.addEventListener("timeupdate", () => {
            if (audio === activeAudio()) updateTimeline();
        });
        audio.addEventListener("play", () => {
            if (audio !== activeAudio()) audio.pause();
            else {
                inactiveAudio().pause();
                updatePlayButton();
            }
        });
        audio.addEventListener("pause", updatePlayButton);
        audio.addEventListener("ended", updatePlayButton);
    });

    renderSelector();
    selectProject(0);
    section.hidden = false;
    elements.heroLink.hidden = false;
}
