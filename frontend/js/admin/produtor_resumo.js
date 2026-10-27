import { authFetch } from "./auth.js";

// AUD6-S09-002: the producer page — what they have in hand, beats and recent work,
// with links to each production. Read-only; built with text nodes only.
const STATUS = Object.freeze({
    aguardando_inicio: "Aguardando início",
    em_producao: "Em produção",
    revisao: "Em revisão",
    ajustes: "Ajustes",
    finalizado: "Finalizado",
    entregue: "Entregue",
});

let dialog = null;

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function ensureDialog() {
    if (dialog?.isConnected) return dialog;
    dialog = element("dialog", "portal-dialog admin-entity-dialog");
    dialog.id = "produtor-resumo-dialog";
    dialog.setAttribute("aria-labelledby", "produtor-resumo-title");
    document.body.append(dialog);
    return dialog;
}

export function closeProdutorResumo() {
    if (dialog?.open) dialog.close();
}

async function openProduction(id) {
    closeProdutorResumo();
    await window.mostrarSecao?.("section-producoes");
    const { visualizarProducao } = await import("./producoes/producoes.js");
    await visualizarProducao(id);
}

function render(data) {
    const host = ensureDialog();
    const header = element("header");
    const name = data.produtor.nome_exibicao || data.produtor.username;
    const title = element("h2", "", name);
    title.id = "produtor-resumo-title";
    const close = element("button", "", "Fechar");
    close.type = "button";
    close.addEventListener("click", closeProdutorResumo);
    header.append(title, close);
    const meta = element("p", "admin-entity-dialog__meta",
        `Login ${data.produtor.username} · ${data.produtor.ativo ? "ativo" : "inativo"}${data.produtor.painel_beats ? " · painel de beats" : ""}${(data.produtor.especialidades || []).length ? ` · ${data.produtor.especialidades.map(item => ({ beatmaker: "Beatmaker", mixagem: "Engenheiro de mixagem", masterizacao: "Engenheiro de masterização" })[item] || item).join(", ")}` : ""}`);
    const counts = element("dl", "admin-entity-dialog__counts");
    const c = data.contagens;
    for (const [label, value] of [
        ["Produções ativas", c.producoes_ativas], ["Atrasadas", c.producoes_atrasadas],
        ["Finalizadas", c.producoes_finalizadas], ["Beats em revisão", c.beats_em_revisao],
        ["Beats no catálogo", c.beats_aprovados], ["Beats vendidos", c.beats_vendidos],
    ]) {
        const item = element("div");
        item.append(element("dt", "", label), element("dd", "", String(value ?? 0)));
        counts.append(item);
    }
    const section = element("section");
    section.append(element("h3", "", "Produções"));
    if (!data.producoes.length) {
        section.append(element("p", "admin-empty", "Nenhuma produção atribuída."));
    } else {
        const list = element("ul", "admin-entity-dialog__list");
        for (const item of data.producoes) {
            const row = element("li");
            const open = element("button", "admin-entity-dialog__link", `#${item.id} ${item.titulo}`);
            open.type = "button";
            open.addEventListener("click", () => openProduction(item.id).catch(() => {}));
            const status = `${item.cliente} · ${STATUS[item.status] || item.status}${item.atrasada ? " · atrasada" : ""}`;
            row.append(open, element("span", item.atrasada ? "admin-entity-dialog__late" : "", status));
            list.append(row);
        }
        section.append(list);
    }
    host.replaceChildren(header, meta, counts, section);
}

export async function openProdutorResumo(id) {
    const host = ensureDialog();
    host.replaceChildren(element("p", "admin-empty", "Carregando produtor..."));
    if (!host.open) host.showModal();
    try {
        const response = await authFetch(`/admin/produtores/${encodeURIComponent(id)}/resumo`);
        const data = await response.json().catch(() => null);
        if (!response.ok || !data?.produtor) throw new Error(typeof data?.detail === "string" ? data.detail : "Não foi possível abrir o produtor.");
        render(data);
    } catch (error) {
        const close = element("button", "btn-small", "Fechar");
        close.type = "button";
        close.addEventListener("click", closeProdutorResumo);
        host.replaceChildren(element("p", "admin-empty", error.message || "Não foi possível abrir o produtor."), close);
    }
}

document.addEventListener("admin:logout", () => {
    closeProdutorResumo();
    dialog?.remove();
    dialog = null;
});
