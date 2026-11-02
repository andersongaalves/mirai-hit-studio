// "Avisos e pop-ups": everything shown to clients and producers outside the flow.
// Pop-ups (create, preview live, pause, delete) and the fixed notice at the top of
// each portal (moved here from Configurações > Portais).
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { buildPopup } from "../../modules/portal_popup.js";

const PUBLICOS = { cliente: "Clientes", produtor: "Produtores", todos: "Clientes e produtores" };
const TEMAS = { ciano: "Ciano", roxo: "Roxo", amarelo: "Amarelo", verde: "Verde", vermelho: "Vermelho" };
const TAMANHOS = { pequeno: "Pequeno", medio: "Médio" };
const FREQUENCIAS = { uma_vez: "Uma vez por pessoa (até fechar)", cada_sessao: "A cada acesso ao portal" };
const PORTAIS = { cliente: "Portal do cliente", produtor: "Portal do produtor" };
const EMPTY = {
    titulo: "", mensagem: "", publico: "todos", tema: "ciano", tamanho: "pequeno",
    botao_rotulo: "", botao_url: "", frequencia: "uma_vez", inicio: null, fim: null, ativo: true,
};

const state = { popups: [], editing: null, bound: false };
const byId = id => document.getElementById(id);

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

async function data(response, fallback) {
    if (response.status === 204) return null;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = body?.detail;
        const message = typeof detail === "string" ? detail
            : Array.isArray(detail) ? String(detail[0]?.msg || "").replace(/^Value error, /, "") : "";
        const error = new Error(message || fallback);
        error.status = response.status;
        throw error;
    }
    return body;
}

const localInput = value => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const isoFromLocal = value => (value ? new Date(value).toISOString() : null);
const formatDate = value => (value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "");

function situacao(popup) {
    const now = Date.now();
    if (!popup.ativo) return ["Pausado", "pausado"];
    if (popup.inicio && new Date(popup.inicio).getTime() > now) return [`Agendado para ${formatDate(popup.inicio)}`, "agendado"];
    if (popup.fim && new Date(popup.fim).getTime() <= now) return ["Encerrado", "encerrado"];
    return ["No ar", "ativo"];
}

// ---------- Pop-ups ----------

function field(label, control, { full = false, help = "" } = {}) {
    const wrap = el("label", `form-group${full ? " admin-form-field--full" : ""}`);
    wrap.append(el("span", "avisos-label", label), control);
    if (help) wrap.append(el("small", "admin-help", help));
    return wrap;
}

function choice(name, options, value, label) {
    const group = el("fieldset", "avisos-choice-group");
    group.append(el("legend", "avisos-label", label));
    const pills = el("div", "admin-choice");
    Object.entries(options).forEach(([key, text]) => {
        const option = el("label", "");
        const input = el("input");
        input.type = "radio";
        input.name = name;
        input.value = key;
        input.checked = key === value;
        option.append(input, document.createTextNode(text));
        pills.append(option);
    });
    group.append(pills);
    return group;
}

function swatches(value) {
    const group = el("fieldset", "avisos-choice-group");
    group.append(el("legend", "avisos-label", "Cor de destaque"));
    const row = el("div", "avisos-swatches");
    Object.entries(TEMAS).forEach(([key, text]) => {
        const option = el("label", `avisos-swatch avisos-swatch--${key}`);
        option.title = text;
        const input = el("input");
        input.type = "radio";
        input.name = "tema";
        input.value = key;
        input.checked = key === value;
        input.setAttribute("aria-label", text);
        option.append(input);
        row.append(option);
    });
    group.append(row);
    return group;
}

function readForm(form) {
    const value = name => form.elements.namedItem(name);
    const checked = name => form.querySelector(`input[name="${name}"]:checked`)?.value;
    return {
        titulo: value("titulo").value.trim(),
        mensagem: value("mensagem").value.trim(),
        publico: checked("publico") || "todos",
        tema: checked("tema") || "ciano",
        tamanho: checked("tamanho") || "pequeno",
        botao_rotulo: value("botao_rotulo").value.trim() || null,
        botao_url: value("botao_url").value.trim() || null,
        frequencia: value("frequencia").value,
        inicio: isoFromLocal(value("inicio").value),
        fim: isoFromLocal(value("fim").value),
        ativo: value("ativo").checked,
    };
}

function renderEditor(panel) {
    const popup = state.editing || EMPTY;
    const wrap = el("div", "avisos-editor");
    const form = el("form", "avisos-form");
    form.noValidate = true;
    form.setAttribute("aria-label", state.editing ? "Editar pop-up" : "Novo pop-up");

    const content = el("section", "admin-form-section");
    content.append(el("h3", "", state.editing ? `Editando: ${state.editing.titulo}` : "Novo pop-up"));
    const title = el("input");
    title.name = "titulo";
    title.maxLength = 80;
    title.required = true;
    title.value = popup.titulo;
    const message = el("textarea");
    message.name = "mensagem";
    message.maxLength = 600;
    message.rows = 4;
    message.required = true;
    message.value = popup.mensagem;
    const grid = el("div", "admin-form-grid");
    grid.append(field("Título", title, { full: true }), field("Mensagem", message, { full: true, help: "Até 600 caracteres. Quebras de linha são mantidas." }));
    content.append(grid, choice("publico", PUBLICOS, popup.publico, "Para quem"));

    const look = el("section", "admin-form-section");
    look.append(el("h3", "", "Aparência"), swatches(popup.tema), choice("tamanho", TAMANHOS, popup.tamanho, "Tamanho"));
    const buttonLabel = el("input");
    buttonLabel.name = "botao_rotulo";
    buttonLabel.maxLength = 40;
    buttonLabel.placeholder = "Ex.: Ver projetos";
    buttonLabel.value = popup.botao_rotulo || "";
    const buttonUrl = el("input");
    buttonUrl.name = "botao_url";
    buttonUrl.maxLength = 300;
    buttonUrl.placeholder = "/cliente/projetos ou https://...";
    buttonUrl.value = popup.botao_url || "";
    const buttonGrid = el("div", "admin-form-grid");
    buttonGrid.append(field("Botão (opcional)", buttonLabel), field("Link do botão", buttonUrl, { help: "Uma página do site (/...) ou um endereço https://." }));
    look.append(buttonGrid);

    const timing = el("section", "admin-form-section");
    timing.append(el("h3", "", "Quando aparece"));
    const frequency = el("select");
    frequency.name = "frequencia";
    Object.entries(FREQUENCIAS).forEach(([key, text]) => frequency.append(new Option(text, key)));
    frequency.value = popup.frequencia;
    const start = el("input");
    start.type = "datetime-local";
    start.name = "inicio";
    start.value = localInput(popup.inicio);
    const end = el("input");
    end.type = "datetime-local";
    end.name = "fim";
    end.value = localInput(popup.fim);
    const timingGrid = el("div", "admin-form-grid admin-form-grid--3");
    timingGrid.append(field("Frequência", frequency), field("Início (opcional)", start), field("Fim (opcional)", end));
    const active = el("input");
    active.type = "checkbox";
    active.name = "ativo";
    active.checked = popup.ativo !== false;
    const activeLabel = el("label", "admin-check");
    activeLabel.append(active, document.createTextNode("Ativo (desmarque para salvar sem publicar)"));
    timing.append(timingGrid, activeLabel);

    const error = el("p", "avisos-error");
    error.setAttribute("role", "alert");
    const footer = el("div", "admin-form-footer admin-form-footer--inline");
    if (state.editing) {
        const cancel = el("button", "btn-outline", "Cancelar edição");
        cancel.type = "button";
        cancel.addEventListener("click", () => { state.editing = null; renderPopups(); });
        footer.append(cancel);
    }
    const submit = el("button", "btn-cta", state.editing ? "Salvar alterações" : "Enviar pop-up");
    submit.type = "submit";
    footer.append(submit);
    form.append(content, look, timing, error, footer);

    // Live preview: the same component the portals render.
    const preview = el("aside", "avisos-preview");
    preview.setAttribute("aria-label", "Prévia do pop-up");
    const previewTitle = el("p", "avisos-preview__title", "Prévia");
    const stage = el("div", "avisos-preview__stage");
    const audience = el("p", "avisos-preview__audience");
    preview.append(previewTitle, stage, audience);
    const refresh = () => {
        const values = readForm(form);
        stage.replaceChildren(buildPopup({ ...values, id: "preview" }, { preview: true }));
        audience.textContent = `Aparece para: ${PUBLICOS[values.publico]} · ${FREQUENCIAS[values.frequencia].toLowerCase()}`;
    };
    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    refresh();

    form.addEventListener("submit", async event => {
        event.preventDefault();
        const values = readForm(form);
        if (!values.titulo || !values.mensagem) {
            error.textContent = "Preencha o título e a mensagem.";
            return;
        }
        if (Boolean(values.botao_rotulo) !== Boolean(values.botao_url)) {
            error.textContent = "Informe o texto e o link do botão, ou deixe os dois em branco.";
            return;
        }
        submit.disabled = true;
        error.textContent = "";
        try {
            const editing = state.editing;
            await data(await authFetch(editing ? `/admin/popups/${editing.id}` : "/admin/popups", {
                method: editing ? "PUT" : "POST",
                body: JSON.stringify(values),
            }), "Não foi possível salvar o pop-up.");
            Notify.success(editing ? "Pop-up atualizado." : values.ativo ? "Pop-up enviado." : "Pop-up salvo (pausado).");
            state.editing = null;
            await loadPopups();
        } catch (saveError) {
            error.textContent = saveError.message;
            submit.disabled = false;
        }
    });

    wrap.append(form, preview);
    panel.append(wrap);
}

function popupCard(popup) {
    const card = el("article", "avisos-card");
    card.dataset.popupId = String(popup.id);
    const [label, kind] = situacao(popup);
    const head = el("div", "avisos-card__head");
    head.append(el("span", `avisos-badge avisos-badge--${kind}`, label), el("span", `avisos-dot avisos-swatch--${popup.tema}`));
    card.append(head, el("h4", "", popup.titulo), el("p", "avisos-card__message", popup.mensagem));
    const meta = [PUBLICOS[popup.publico], FREQUENCIAS[popup.frequencia], `${popup.fechamentos} fechamento${popup.fechamentos === 1 ? "" : "s"}`];
    if (popup.fim) meta.push(`até ${formatDate(popup.fim)}`);
    card.append(el("p", "admin-help", meta.join(" · ")));
    const actions = el("div", "avisos-card__actions");
    const edit = el("button", "btn-small", "Editar");
    edit.type = "button";
    edit.setAttribute("aria-label", `Editar pop-up ${popup.titulo}`);
    edit.addEventListener("click", () => {
        state.editing = popup;
        renderPopups();
        byId("avisos-popups-panel").querySelector(".avisos-form input")?.focus();
    });
    const toggle = el("button", "btn-small", popup.ativo ? "Pausar" : "Ativar");
    toggle.type = "button";
    toggle.setAttribute("aria-label", `${popup.ativo ? "Pausar" : "Ativar"} pop-up ${popup.titulo}`);
    toggle.addEventListener("click", async () => {
        toggle.disabled = true;
        try {
            const { id, created_at, updated_at, fechamentos, ...fields } = popup;
            await data(await authFetch(`/admin/popups/${id}`, { method: "PUT", body: JSON.stringify({ ...fields, ativo: !popup.ativo }) }),
                "Não foi possível atualizar o pop-up.");
            await loadPopups();
        } catch (toggleError) {
            Notify.error(toggleError.message);
            toggle.disabled = false;
        }
    });
    const remove = el("button", "btn-small btn-danger", "Excluir");
    remove.type = "button";
    remove.setAttribute("aria-label", `Excluir pop-up ${popup.titulo}`);
    remove.addEventListener("click", async () => {
        if (!window.confirm(`Excluir o pop-up "${popup.titulo}"? Ele deixa de aparecer nos portais.`)) return;
        remove.disabled = true;
        try {
            await data(await authFetch(`/admin/popups/${popup.id}`, { method: "DELETE" }), "Não foi possível excluir o pop-up.");
            if (state.editing?.id === popup.id) state.editing = null;
            Notify.success("Pop-up excluído.");
            await loadPopups();
        } catch (removeError) {
            Notify.error(removeError.message);
            remove.disabled = false;
        }
    });
    actions.append(edit, toggle, remove);
    card.append(actions);
    return card;
}

function renderPopups() {
    const panel = byId("avisos-popups-panel");
    if (!panel) return;
    panel.replaceChildren();
    renderEditor(panel);
    const list = el("section", "avisos-list");
    list.setAttribute("aria-labelledby", "avisos-list-title");
    const heading = el("h3", "", "Pop-ups enviados");
    heading.id = "avisos-list-title";
    list.append(heading);
    if (!state.popups.length) list.append(el("p", "admin-empty", "Nenhum pop-up enviado ainda."));
    const grid = el("div", "avisos-list__grid");
    state.popups.forEach(popup => grid.append(popupCard(popup)));
    list.append(grid);
    panel.append(list);
}

async function loadPopups() {
    state.popups = await data(await authFetch("/admin/popups"), "Não foi possível carregar os pop-ups.");
    renderPopups();
}

// ---------- Fixed notice at the top of each portal ----------

async function loadNotice(portal) {
    return data(await authFetch(`/admin/portais/${portal}/configuracao`), "Não foi possível carregar o aviso.");
}

function noticeCard(portal, current) {
    const card = el("form", "admin-form-section avisos-topo");
    card.setAttribute("aria-label", `Aviso no topo: ${PORTAIS[portal]}`);
    card.append(el("h3", "", PORTAIS[portal]));
    const aviso = current.config.aviso || { ativo: false, nivel: "info", texto: "" };
    const active = el("input");
    active.type = "checkbox";
    active.checked = Boolean(aviso.ativo);
    const activeLabel = el("label", "admin-check");
    activeLabel.append(active, document.createTextNode("Exibir aviso no topo do portal"));
    const level = el("select");
    level.append(new Option("Informativo", "info"), new Option("Atenção", "atencao"));
    level.value = aviso.nivel || "info";
    const text = el("textarea");
    text.maxLength = 280;
    text.rows = 2;
    text.value = aviso.texto || "";
    const grid = el("div", "admin-form-grid");
    grid.append(field("Tipo", level), field("Texto (até 280 caracteres)", text, { full: true }));
    const preview = el("p", "avisos-topo__preview");
    const refresh = () => {
        preview.textContent = text.value.trim() || "Prévia do aviso";
        preview.dataset.level = level.value;
        preview.classList.toggle("avisos-topo__preview--off", !active.checked);
    };
    [active, level, text].forEach(control => control.addEventListener("input", refresh));
    active.addEventListener("change", refresh);
    refresh();
    const save = el("button", "btn-cta", "Publicar aviso");
    save.type = "submit";
    const footer = el("div", "admin-form-footer admin-form-footer--inline");
    footer.append(save);
    card.append(activeLabel, grid, el("p", "avisos-label", "Prévia"), preview, footer);
    card.addEventListener("submit", async event => {
        event.preventDefault();
        save.disabled = true;
        try {
            // The notice is part of the versioned portal settings: publish a new version with it.
            const latest = await loadNotice(portal);
            const config = { ...latest.config, aviso: { ativo: active.checked, nivel: level.value, texto: text.value.trim() } };
            await data(await authFetch(`/admin/portais/${portal}/configuracao`, {
                method: "PUT",
                body: JSON.stringify({ base_versao: latest.versao, config }),
            }), "Não foi possível publicar o aviso.");
            Notify.success("Aviso publicado.");
            await loadNotices();
        } catch (saveError) {
            Notify.error(saveError.message);
            save.disabled = false;
        }
    });
    return card;
}

async function loadNotices() {
    const panel = byId("avisos-topo-panel");
    if (!panel) return;
    const help = el("p", "admin-help", "Uma faixa fixa no topo do portal, para avisos que ficam enquanto valem (feriados, manutenção). Cada publicação cria uma nova versão das configurações do portal.");
    const [cliente, produtor] = await Promise.all([loadNotice("cliente"), loadNotice("produtor")]);
    panel.replaceChildren(help, noticeCard("cliente", cliente), noticeCard("produtor", produtor));
}

function selectTab(name) {
    const popups = name === "popups";
    byId("avisos-tab-popups")?.setAttribute("aria-selected", String(popups));
    byId("avisos-tab-topo")?.setAttribute("aria-selected", String(!popups));
    const popupsPanel = byId("avisos-popups-panel");
    const topPanel = byId("avisos-topo-panel");
    if (popupsPanel) popupsPanel.hidden = !popups;
    if (topPanel) topPanel.hidden = popups;
    if (!popups) loadNotices().catch(error => Notify.error(error.message));
}

export async function initAvisos() {
    if (!state.bound) {
        state.bound = true;
        byId("avisos-tab-popups")?.addEventListener("click", () => selectTab("popups"));
        byId("avisos-tab-topo")?.addEventListener("click", () => selectTab("topo"));
    }
    await loadPopups();
}

document.addEventListener("admin:logout", () => {
    state.popups = [];
    state.editing = null;
    byId("avisos-popups-panel")?.replaceChildren();
    byId("avisos-topo-panel")?.replaceChildren();
});
