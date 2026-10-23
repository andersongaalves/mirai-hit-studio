export function beatPreview(loader) {
    const wrap = document.createElement("div");
    wrap.className = "beat-preview";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn-outline beat-preview__load";
    button.textContent = "Carregar prévia";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.hidden = true;
    const status = document.createElement("span");
    status.setAttribute("role", "status");
    button.addEventListener("click", async () => {
        button.disabled = true;
        status.textContent = "Carregando áudio...";
        try {
            const result = await loader();
            const blob = result?.blob instanceof Blob ? result.blob : result;
            if (!(blob instanceof Blob) || blob.size === 0 || !blob.type.startsWith("audio/")) {
                throw new Error("A prévia recebida não é um áudio válido.");
            }
            audio.src = URL.createObjectURL(blob);
            audio.hidden = false;
            button.remove();
            status.textContent = "";
            await audio.play().catch(() => {});
        } catch (error) {
            button.disabled = false;
            status.textContent = error.message || "Não foi possível carregar a prévia.";
        }
    });
    wrap.append(button, audio, status);
    return wrap;
}
