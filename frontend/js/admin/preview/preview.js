// Admin "Pré-visualização": every screen of the site and the portals in a frame, at
// computer, tablet or phone size. Public pages open as any visitor sees them; portal
// screens open as a chosen client or producer, through a 30-minute read-only session
// (the API refuses anything but reads and records each session in the audit log).
import { authFetch } from "../auth.js";
import { clearPreviewSessions, previewSession, savePreviewSession } from "../../modules/preview_frame.js";

const TELAS = [
    { grupo: "Site", itens: [
        ["/", "Início"], ["/artists", "Artistas"], ["/creators", "Criadores"], ["/media-games", "Media & Games"],
        ["/portfolio", "Portfólio"], ["/beats", "Beats"], ["/orcamento", "Pedido de orçamento"],
        ["/acesso", "Entrar"], ["/cadastro", "Criar conta"], ["/privacidade", "Política de Privacidade"],
    ] },
    { grupo: "Portal do cliente", portal: "cliente", itens: [
        ["/cliente", "Início"], ["/cliente/projetos", "Projetos"], ["/cliente/propostas", "Propostas"],
        ["/cliente/explorar", "Explorar beats"], ["/cliente/creditos", "Créditos"],
    ] },
    { grupo: "Portal do produtor", portal: "produtor", itens: [
        ["/produtor", "Início"], ["/produtor/producoes", "Produções"], ["/produtor/beats", "Meus beats"],
        ["/produtor/catalogo", "Catálogo de beats"], ["/produtor/financeiro", "Financeiro"],
        ["/produtor/portfolio", "Portfólio"], ["/produtor/perfil", "Perfil"],
    ] },
];
const APARELHOS = [
    ["desktop", "Computador", 1280, 800],
    ["tablet", "Tablet", 820, 1180],
    ["celular", "Celular", 390, 844],
];
const RENOVAR_ANTES_MS = 60 * 1000;

const state = { tela: "/", aparelho: "desktop", contas: { cliente: null, produtor: null }, bound: false, busca: 0 };
const byId = id => document.getElementById(id);

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function portalDe(path) {
    return TELAS.find(grupo => grupo.portal && grupo.itens.some(([value]) => value === path))?.portal || null;
}

async function json(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    return data;
}

const hora = value => new Date(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

function build(host) {
    const toolbar = el("div", "preview-toolbar");
    const telaField = el("label", "preview-field");
    telaField.append(el("span", "", "Tela"));
    const tela = el("select");
    tela.id = "preview-tela";
    TELAS.forEach(grupo => {
        const group = el("optgroup");
        group.label = grupo.grupo;
        grupo.itens.forEach(([value, label]) => {
            const option = el("option", "", label);
            option.value = value;
            group.append(option);
        });
        tela.append(group);
    });
    telaField.append(tela);

    const contaField = el("div", "preview-field preview-account");
    contaField.id = "preview-conta";
    contaField.hidden = true;
    const contaLabel = el("label", "");
    contaLabel.htmlFor = "preview-conta-busca";
    contaLabel.id = "preview-conta-label";
    const busca = el("input");
    busca.id = "preview-conta-busca";
    busca.type = "search";
    busca.placeholder = "Buscar por nome ou login";
    busca.autocomplete = "off";
    const lista = el("select");
    lista.id = "preview-conta-lista";
    lista.setAttribute("aria-labelledby", "preview-conta-label");
    contaField.append(contaLabel, busca, lista);

    const aparelhos = el("div", "preview-devices");
    aparelhos.setAttribute("role", "group");
    aparelhos.setAttribute("aria-label", "Tamanho da tela");
    APARELHOS.forEach(([value, label]) => {
        const button = el("button", "btn-small", label);
        button.type = "button";
        button.dataset.aparelho = value;
        aparelhos.append(button);
    });
    const acoes = el("div", "preview-actions");
    const recarregar = el("button", "btn-small", "Recarregar");
    recarregar.type = "button";
    recarregar.id = "preview-recarregar";
    const novaAba = el("a", "btn-small", "Abrir em nova aba");
    novaAba.id = "preview-nova-aba";
    novaAba.target = "_blank";
    novaAba.rel = "noopener";
    acoes.append(recarregar, novaAba);
    toolbar.append(telaField, contaField, aparelhos, acoes);

    const status = el("p", "admin-field-help preview-status");
    status.id = "preview-status";
    status.setAttribute("role", "status");
    const palco = el("div", "preview-stage");
    palco.id = "preview-stage";
    const moldura = el("div", "preview-device");
    moldura.id = "preview-device";
    const frame = el("iframe");
    frame.id = "preview-frame";
    frame.title = "Pré-visualização da tela";
    frame.referrerPolicy = "same-origin";
    moldura.append(frame);
    const vazio = el("p", "preview-empty");
    vazio.id = "preview-empty";
    vazio.hidden = true;
    palco.append(moldura, vazio);
    host.replaceChildren(toolbar, status, palco);

    tela.addEventListener("change", () => { state.tela = tela.value; atualizar(); });
    aparelhos.addEventListener("click", event => {
        const button = event.target.closest("button[data-aparelho]");
        if (!button) return;
        state.aparelho = button.dataset.aparelho;
        ajustar();
    });
    let timer = null;
    busca.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => carregarContas(portalDe(state.tela)), 250); });
    lista.addEventListener("change", () => {
        const portal = portalDe(state.tela);
        const conta = (state.listadas || []).find(item => String(item.id) === lista.value) || null;
        state.contas[portal] = conta;
        atualizar({ novaSessao: true });
    });
    recarregar.addEventListener("click", () => atualizar());
    frame.addEventListener("load", mostrarEndereco);
    window.addEventListener("resize", ajustar);
    document.addEventListener("admin:logout", () => {
        clearPreviewSessions();
        state.contas = { cliente: null, produtor: null };
        frame.src = "about:blank";
    });
}

function mostrarEndereco() {
    const frame = byId("preview-frame");
    let path = "";
    try {
        const address = new URL(frame.contentWindow.location.href);
        address.searchParams.delete("previa");
        path = address.pathname + address.search;
    } catch { path = ""; }
    if (!path || path === "blank") return;
    const sessao = portalDe(state.tela) ? previewSession(portalDe(state.tela)) : null;
    const partes = [`Endereço: ${path}`];
    if (sessao) partes.push(`vendo como ${sessao.conta.nome}, só leitura até ${hora(sessao.expira_em)}`);
    byId("preview-status").textContent = partes.join(" · ");
}

function ajustar() {
    const [, , largura, altura] = APARELHOS.find(([value]) => value === state.aparelho);
    document.querySelectorAll(".preview-devices button").forEach(button => {
        button.setAttribute("aria-pressed", String(button.dataset.aparelho === state.aparelho));
    });
    const palco = byId("preview-stage");
    const moldura = byId("preview-device");
    const frame = byId("preview-frame");
    const disponivel = Math.max(280, palco.clientWidth - 2);
    const escala = Math.min(1, disponivel / largura);
    frame.style.width = `${largura}px`;
    frame.style.height = `${altura}px`;
    frame.style.transform = `scale(${escala})`;
    moldura.style.width = `${Math.round(largura * escala)}px`;
    moldura.style.height = `${Math.round(altura * escala)}px`;
    moldura.dataset.aparelho = state.aparelho;
}

async function carregarContas(portal) {
    const lista = byId("preview-conta-lista");
    const request = ++state.busca;
    const termo = byId("preview-conta-busca").value.trim();
    try {
        const query = new URLSearchParams({ portal, busca: termo });
        const contas = await json(await authFetch(`/admin/preview/contas?${query}`), "Não foi possível carregar as contas.");
        if (request !== state.busca) return;
        state.listadas = contas;
        const escolhida = state.contas[portal];
        const vazio = el("option", "", contas.length ? "Escolha uma conta" : "Nenhuma conta encontrada");
        vazio.value = "";
        lista.replaceChildren(vazio, ...contas.map(conta => {
            const option = el("option", "", `${conta.nome} (${conta.login})${conta.teste ? " · teste" : ""}`);
            option.value = String(conta.id);
            return option;
        }));
        if (escolhida && contas.some(conta => conta.id === escolhida.id)) lista.value = String(escolhida.id);
    } catch (error) {
        byId("preview-status").textContent = error.message;
    }
}

async function sessaoPara(portal, { novaSessao = false } = {}) {
    const conta = state.contas[portal];
    const atual = previewSession(portal);
    const valida = atual && atual.conta?.id === conta.id && Date.parse(atual.expira_em) - Date.now() > RENOVAR_ANTES_MS;
    if (valida && !novaSessao) return atual;
    const sessao = await json(await authFetch("/admin/preview/sessao", {
        method: "POST",
        body: JSON.stringify({ usuario_id: conta.id }),
    }), "Não foi possível abrir a visualização desta conta.");
    savePreviewSession(portal, sessao);
    return sessao;
}

async function atualizar(options = {}) {
    const portal = portalDe(state.tela);
    const frame = byId("preview-frame");
    const vazio = byId("preview-empty");
    const contaField = byId("preview-conta");
    const novaAba = byId("preview-nova-aba");
    const status = byId("preview-status");
    contaField.hidden = !portal;
    // Portal screens use the preview session of this tab; only public pages open elsewhere.
    novaAba.hidden = Boolean(portal);
    novaAba.href = state.tela;
    status.textContent = "";
    if (portal) {
        byId("preview-conta-label").textContent = portal === "cliente" ? "Conta de cliente" : "Conta de produtor";
        if (contaField.dataset.portal !== portal) {
            contaField.dataset.portal = portal;
            byId("preview-conta-busca").value = "";
            carregarContas(portal);
        }
        if (!state.contas[portal]) {
            byId("preview-device").hidden = true;
            vazio.hidden = false;
            vazio.textContent = portal === "cliente"
                ? "Escolha uma conta de cliente para ver o portal como ela vê."
                : "Escolha uma conta de produtor para ver o portal como ela vê.";
            return;
        }
        try {
            await sessaoPara(portal, options);
        } catch (error) {
            byId("preview-device").hidden = true;
            vazio.hidden = false;
            vazio.textContent = error.message;
            return;
        }
    }
    vazio.hidden = true;
    byId("preview-device").hidden = false;
    // A new address (with a marker) so the same screen reloads after a change of account.
    frame.src = `${state.tela}${state.tela.includes("?") ? "&" : "?"}previa=${Date.now().toString(36)}`;
    ajustar();
}

export function initPreview() {
    const host = byId("preview-content");
    if (!host) return;
    if (!state.bound) {
        state.bound = true;
        build(host);
    }
    byId("preview-tela").value = state.tela;
    atualizar();
}
