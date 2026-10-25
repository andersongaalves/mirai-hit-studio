import { authFetch } from "../auth.js";

// AUD6-S08-002: previews whose tag failed are listed on the dashboard with a retry action.

function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
}

async function listarFalhas() {
    const response = await authFetch("/admin/audio-tag/previas/falhas");
    if (!response.ok) throw new Error("Não foi possível listar as prévias com falha.");
    const data = await response.json().catch(() => null);
    return Array.isArray(data) ? data : [];
}

async function reprocessar(arquivoId) {
    const response = await authFetch(`/admin/audio-tag/previas/${encodeURIComponent(arquivoId)}/reprocessar`, { method: "POST" });
    if (!response.ok) throw new Error("Não foi possível reprocessar a prévia.");
    return response.json().catch(() => ({}));
}

function linha(falha, onDone) {
    const item = element("li", "dashboard-tag-failures__item");
    const texto = element("span", "dashboard-tag-failures__text");
    texto.append(element("strong", "", falha.producao_titulo || `Produção ${falha.producao_id}`), document.createTextNode(` · ${falha.arquivo_nome || "Prévia"}`));
    const button = element("button", "btn-small", "Reprocessar");
    button.type = "button";
    button.setAttribute("aria-label", `Reprocessar a tag de ${falha.arquivo_nome || "prévia"}`);
    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Reprocessando...";
        try {
            await reprocessar(falha.arquivo_id);
            item.replaceChildren(element("span", "dashboard-tag-failures__text", `${falha.arquivo_nome || "Prévia"}: na fila para reprocessar.`));
            onDone?.();
        } catch (error) {
            button.disabled = false;
            button.textContent = "Tentar novamente";
            item.append(element("span", "dashboard-tag-failures__error", error.message));
        }
    });
    item.append(texto, button);
    return item;
}

export async function renderFalhasTag(data, { onDone } = {}) {
    const host = document.getElementById("dashboard-attention");
    if (!host || !(Number(data?.attention?.falhas_processamento_tag) > 0)) return;
    let falhas;
    try {
        falhas = await listarFalhas();
    } catch {
        return;
    }
    if (!falhas.length || !document.body.contains(host)) return;
    host.querySelector(".dashboard-tag-failures")?.remove();
    const section = element("div", "dashboard-tag-failures");
    section.append(element("p", "dashboard-tag-failures__title", "Prévias com falha na tag"));
    const list = element("ul", "dashboard-tag-failures__list");
    list.append(...falhas.map(falha => linha(falha, onDone)));
    section.append(list);
    host.append(section);
}
