function formatTime(value) {
    if (!Number.isFinite(value) || value < 0) return "0:00";
    return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}

function icon(className) {
    const element = document.createElement("span");
    element.className = className;
    element.setAttribute("aria-hidden", "true");
    return element;
}

export function beatPreview(loader) {
    const wrap = document.createElement("div");
    wrap.className = "beat-preview";
    const audio = document.createElement("audio");
    audio.preload = "metadata";
    const play = document.createElement("button");
    play.type = "button";
    play.className = "beat-preview__play";
    play.setAttribute("aria-label", "Reproduzir prévia");
    play.append(icon("beat-preview__play-icon"));
    play.disabled = true;
    const timeline = document.createElement("input");
    timeline.type = "range";
    timeline.className = "beat-preview__timeline";
    timeline.min = "0";
    timeline.max = "1000";
    timeline.value = "0";
    timeline.setAttribute("aria-label", "Posição da prévia");
    timeline.disabled = true;
    const time = document.createElement("span");
    time.className = "beat-preview__time";
    time.textContent = "0:00 / 0:00";
    const volume = document.createElement("button");
    volume.type = "button";
    volume.className = "beat-preview__volume";
    volume.setAttribute("aria-label", "Silenciar prévia");
    volume.append(icon("beat-preview__volume-icon"));
    volume.disabled = true;
    const status = document.createElement("span");
    status.className = "beat-preview__status";
    status.setAttribute("role", "status");
    status.textContent = "Carregando prévia...";
    const updateTime = () => {
        const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
        timeline.value = duration ? String(Math.round(audio.currentTime / duration * 1000)) : "0";
        time.textContent = `${formatTime(audio.currentTime)} / ${formatTime(duration)}`;
    };
    const updatePlay = () => {
        const playing = !audio.paused && !audio.ended;
        play.classList.toggle("is-playing", playing);
        play.setAttribute("aria-label", playing ? "Pausar prévia" : "Reproduzir prévia");
    };
    play.addEventListener("click", async () => {
        if (audio.paused) await audio.play().catch(() => {});
        else audio.pause();
        updatePlay();
    });
    volume.addEventListener("click", () => {
        audio.muted = !audio.muted;
        volume.classList.toggle("is-muted", audio.muted);
        volume.setAttribute("aria-label", audio.muted ? "Ativar som da prévia" : "Silenciar prévia");
    });
    timeline.addEventListener("input", () => {
        if (Number.isFinite(audio.duration)) audio.currentTime = Number(timeline.value) * audio.duration / 1000;
    });
    audio.addEventListener("loadedmetadata", updateTime);
    audio.addEventListener("timeupdate", updateTime);
    audio.addEventListener("play", updatePlay);
    audio.addEventListener("pause", updatePlay);
    audio.addEventListener("ended", updatePlay);
    const load = async () => {
        status.textContent = "Carregando prévia...";
        status.classList.remove("is-error");
        try {
            const result = await loader();
            const blob = result?.blob instanceof Blob ? result.blob : result;
            if (!(blob instanceof Blob) || blob.size === 0 || !blob.type.startsWith("audio/")) {
                throw new Error("A prévia recebida não é um áudio válido.");
            }
            audio.src = URL.createObjectURL(blob);
            audio.load();
            play.disabled = false;
            timeline.disabled = false;
            volume.disabled = false;
            status.textContent = "Prévia pronta";
            status.classList.add("is-ready");
        } catch (error) {
            status.textContent = error.message || "Não foi possível carregar a prévia.";
            status.classList.add("is-error");
            const retry = document.createElement("button");
            retry.type = "button";
            retry.className = "beat-preview__retry";
            retry.textContent = "Tentar novamente";
            retry.addEventListener("click", () => { retry.remove(); load(); }, { once: true });
            wrap.append(retry);
        }
    };
    wrap.append(audio, play, timeline, time, volume, status);
    queueMicrotask(load);
    return wrap;
}
