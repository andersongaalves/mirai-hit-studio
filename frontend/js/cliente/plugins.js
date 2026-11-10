// Portal do cliente > Plugins: Mirai Hit Labs licenses, keys and installer downloads,
// plus the purchase step that starts from the Labs store (/cliente/plugins/comprar/<slug>).
import { authFetch } from "../admin/auth.js";
import { humanClientMessage } from "./messages.js";

export const LABS_URL = "https://labs.miraihitstudio.com.br";
const SISTEMAS = { windows: "Windows", macos: "macOS" };

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

async function data(response, fallback) {
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(humanClientMessage(payload?.detail, fallback));
        error.status = response.status;
        throw error;
    }
    return payload;
}

export async function listarPlugins() {
    return data(await authFetch("/portal/cliente/plugins"), "Não foi possível carregar seus plugins.");
}

export async function comprarPlugin(slug, idempotencyKey) {
    return data(await authFetch(`/labs/plugins/${encodeURIComponent(slug)}/comprar`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
    }), "Não foi possível iniciar a compra.");
}

async function baixar(licenseId, sistema) {
    const response = await authFetch(`/portal/cliente/plugins/${licenseId}/download/${sistema}`);
    if (!response.ok) return data(response, "Não foi possível baixar o instalador.");
    if ((response.headers.get("content-type") || "").includes("application/json")) return response.json();
    const disposition = response.headers.get("content-disposition") || "";
    return { type: "file", blob: await response.blob(), filename: disposition.match(/filename="([^"]+)"/i)?.[1] || "instalador.zip" };
}

function deliver(delivery) {
    if (delivery.type === "file") {
        const url = URL.createObjectURL(delivery.blob);
        const link = el("a");
        link.href = url;
        link.download = delivery.filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
        return;
    }
    if (!/^https:\/\//.test(delivery.url || "")) throw new Error("Link de download inválido.");
    const link = el("a");
    link.href = delivery.url;
    link.rel = "noopener noreferrer";
    if (delivery.type === "link") link.target = "_blank";
    else link.download = delivery.filename || "";
    link.click();
}

function cover(item) {
    const box = el("div", "client-plugin__cover");
    if (item.capa_url) {
        const image = el("img");
        image.src = item.capa_url;
        image.alt = "";
        image.loading = "lazy";
        box.append(image);
    } else {
        box.append(el("span", "", item.plugin.slice(0, 1)));
    }
    return box;
}

function keyRow(chave) {
    const row = el("div", "client-plugin__key");
    row.append(el("span", "", "Chave da licença"));
    const code = el("code", "", chave);
    const copy = el("button", "btn-small", "Copiar");
    copy.type = "button";
    copy.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(chave);
            copy.textContent = "Copiada";
        } catch {
            copy.textContent = "Selecione e copie";
        }
        setTimeout(() => { copy.textContent = "Copiar"; }, 2000);
    });
    row.append(code, copy);
    return row;
}

function pluginCard(item) {
    const card = el("article", `client-plugin client-plugin--${item.status}`);
    const body = el("div", "client-plugin__body");
    const head = el("div", "client-plugin__head");
    head.append(el("h2", "", item.plugin));
    const STATUS = { ativa: "Licença ativa", aguardando_pagamento: "Aguardando pagamento", suspensa: "Suspensa" };
    head.append(el("span", `client-plugin__status client-plugin__status--${item.status}`, STATUS[item.status] || item.status));
    body.append(head);
    if (item.status === "ativa") {
        const facts = [item.versao && `Versão ${item.versao}`, item.formatos?.join(" · "), item.origem === "gratuito" ? "Grátis" : item.origem === "cortesia" ? "Cortesia do estúdio" : ""].filter(Boolean);
        if (facts.length) body.append(el("p", "client-plugin__facts", facts.join(" · ")));
        body.append(keyRow(item.chave));
        const downloads = el("div", "client-plugin__downloads");
        const status = el("p", "client-plugin__message");
        status.setAttribute("role", "status");
        if (!item.sistemas.length) downloads.append(el("p", "client-plugin__facts", "O instalador ainda está sendo preparado. Volte em breve."));
        item.sistemas.forEach(sistema => {
            const button = el("button", "btn-cta", `Baixar para ${SISTEMAS[sistema.sistema] || sistema.sistema}`);
            button.type = "button";
            if (sistema.versao) button.title = `Versão ${sistema.versao}`;
            button.addEventListener("click", async () => {
                button.disabled = true;
                status.textContent = "Preparando o download...";
                try {
                    deliver(await baixar(item.id, sistema.sistema));
                    status.textContent = "Download iniciado.";
                } catch (error) {
                    status.textContent = error.message;
                } finally {
                    button.disabled = false;
                }
            });
            downloads.append(button);
        });
        body.append(downloads, status);
    } else if (item.status === "aguardando_pagamento") {
        body.append(el("p", "client-plugin__facts", "A licença e os downloads aparecem aqui assim que o pagamento for confirmado."));
        const pay = el("a", "btn-cta", "Concluir pagamento");
        pay.href = item.checkout_path;
        body.append(pay);
    } else {
        body.append(el("p", "client-plugin__facts", "O pagamento desta compra foi revertido. Fale com o estúdio para reativar a licença."));
    }
    const store = el("a", "client-plugin__store", "Ver na loja");
    store.href = `${LABS_URL}/plugins/${item.slug}`;
    store.target = "_blank";
    store.rel = "noopener";
    body.append(store);
    card.append(cover(item), body);
    return card;
}

export function renderPlugins(root, items) {
    if (!items.length) {
        const empty = el("div", "client-plugins__empty");
        empty.append(el("strong", "", "Você ainda não tem plugins."),
            el("p", "", "Na Mirai Hit Labs você encontra plugins de áudio feitos pelo estúdio. O que você comprar aparece aqui, com a chave e os downloads."));
        const go = el("a", "btn-cta", "Conhecer a Mirai Hit Labs");
        go.href = LABS_URL;
        go.target = "_blank";
        go.rel = "noopener";
        empty.append(go);
        root.replaceChildren(empty);
        return;
    }
    root.replaceChildren(...items.map(pluginCard));
}

// The Labs store sends the buyer here; the portal only opens with a client session.
export async function startPurchase(root, slug, { onFree }) {
    root.replaceChildren(el("p", "client-plugins__loading", "Preparando sua compra..."));
    let key;
    try {
        key = sessionStorage.getItem(`mirai.labs.compra.${slug}`) || crypto.randomUUID();
        sessionStorage.setItem(`mirai.labs.compra.${slug}`, key);
    } catch {
        key = crypto.randomUUID();
    }
    try {
        const result = await comprarPlugin(slug, key);
        try { sessionStorage.removeItem(`mirai.labs.compra.${slug}`); } catch { /* ignore */ }
        if (result.gratuito) {
            onFree();
            return;
        }
        location.replace(result.checkout_path);
    } catch (error) {
        const box = el("div", "client-plugins__empty");
        box.append(el("strong", "", "Não foi possível concluir"), el("p", "", error.message));
        const back = el("a", "btn-outline", "Voltar para a loja");
        back.href = `${LABS_URL}/plugins/${encodeURIComponent(slug)}`;
        const mine = el("a", "btn-cta", "Meus plugins");
        mine.href = "/cliente/plugins";
        mine.dataset.route = "plugins";
        box.append(mine, back);
        root.replaceChildren(box);
    }
}
