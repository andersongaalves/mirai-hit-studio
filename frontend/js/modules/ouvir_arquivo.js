// Listen to production audio in the page, without saving a file: the tagged
// version (processed) and the original upload, when the viewer may hear it.
const players = new Set();

function button(text) {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "btn-outline btn-small ouvir-arquivo__button";
    node.textContent = text;
    return node;
}

export function podeOuvir(file) {
    return /^(audio|video)\//.test(file?.mime_type || "");
}

export function pararTodos() {
    players.forEach(media => {
        media.pause();
        if (media.src.startsWith("blob:")) URL.revokeObjectURL(media.src);
    });
    players.clear();
}

/**
 * Buttons plus a player slot.
 * opcoes: [{ versao: "processada"|"original"|null, rotulo }]; load(versao) resolves a Blob.
 */
export function controlesOuvir(file, { opcoes, load, onError }) {
    const wrap = document.createElement("div");
    wrap.className = "ouvir-arquivo";
    const actions = document.createElement("div");
    actions.className = "ouvir-arquivo__actions";
    const slot = document.createElement("div");
    slot.className = "ouvir-arquivo__player";
    const status = document.createElement("p");
    status.className = "ouvir-arquivo__status";
    status.setAttribute("aria-live", "polite");
    for (const opcao of opcoes) {
        const trigger = button(opcao.rotulo);
        trigger.addEventListener("click", async () => {
            trigger.disabled = true;
            status.textContent = "Carregando áudio...";
            try {
                const blob = await load(opcao.versao);
                slot.querySelectorAll("audio, video").forEach(media => {
                    media.pause();
                    players.delete(media);
                    if (media.src.startsWith("blob:")) URL.revokeObjectURL(media.src);
                });
                const media = document.createElement(file.mime_type.startsWith("video/") && opcao.versao !== "processada" ? "video" : "audio");
                media.controls = true;
                media.preload = "metadata";
                media.playsInline = true;
                media.className = "ouvir-arquivo__media";
                media.setAttribute("aria-label", `${opcao.rotulo}: ${file.nome_exibicao}`);
                media.src = URL.createObjectURL(blob);
                players.add(media);
                slot.replaceChildren(media);
                status.textContent = `Tocando: ${opcao.rotulo.toLowerCase()}.`;
                await media.play().catch(() => {});
            } catch (error) {
                status.textContent = "";
                onError?.(error);
            } finally {
                trigger.disabled = false;
            }
        });
        actions.append(trigger);
    }
    wrap.append(actions, status, slot);
    return wrap;
}

/** Studio users (Admin and producer): both versions when the preview was processed. */
export function opcoesEstudio(file) {
    if (file.processamento_tag === "pronto") {
        return [{ versao: "processada", rotulo: "Ouvir com tag" }, { versao: "original", rotulo: "Ouvir original" }];
    }
    return [{ versao: null, rotulo: "Ouvir" }];
}

document.addEventListener("admin:logout", pararTodos);
