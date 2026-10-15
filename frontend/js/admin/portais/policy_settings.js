// Roadmap 3.0, 5.10: global default of the contractual portal policies (versioned).
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { policyForm } from "../../modules/policies.js";

const state = { versao: 0, padroes: null, form: null, loaded: false, busy: false };
const byId = id => document.getElementById(id);

function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
}

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(typeof data?.detail === "string" ? data.detail : fallback);
        error.status = response.status;
        throw error;
    }
    return data;
}

function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("pt-BR");
}

function renderForm(values) {
    state.form = policyForm({ values, idPrefix: "politica-global" });
    byId("policy-settings-form").replaceChildren(state.form.element);
}

function render(data) {
    state.versao = data.versao;
    state.padroes = data.padroes;
    byId("policy-settings-version").textContent = data.versao
        ? `Versão em uso: v${data.versao}`
        : "Nenhuma versão publicada: valem os padrões do sistema (comportamento atual).";
    renderForm(data.politicas);
    const list = byId("policy-settings-versions");
    list.replaceChildren();
    if (!data.versoes?.length) {
        list.append(node("li", "", "Nenhuma versão publicada."));
    }
    (data.versoes || []).forEach(item => {
        const row = node("li");
        const origin = item.restaurada_de_versao ? ` · restaurada da v${item.restaurada_de_versao}` : "";
        row.append(node("span", "", `v${item.versao} · ${formatDate(item.created_at)}${origin}`));
        if (item.versao === state.versao) {
            row.append(node("strong", "", "Em uso"));
        } else {
            const restore = node("button", "btn-small", "Restaurar");
            restore.type = "button";
            restore.setAttribute("aria-label", `Restaurar políticas v${item.versao}`);
            restore.addEventListener("click", () => send(restore, "/politicas/globais/restaurar", "POST",
                { versao: item.versao, base_versao: state.versao }, `Versão v${item.versao} restaurada como nova versão.`));
            row.append(restore);
        }
        list.append(row);
    });
    state.loaded = true;
}

async function load() {
    render(await responseData(await authFetch("/politicas/globais"), "Não foi possível carregar as políticas."));
}

async function send(button, path, method, body, message) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    try {
        render(await responseData(await authFetch(path, { method, body: JSON.stringify(body) }),
            "Não foi possível salvar as políticas."));
        Notify.success(message);
    } catch (error) {
        Notify.error(error.message);
        if (error.status === 409) await load().catch(() => {});
    } finally {
        state.busy = false;
        button.disabled = false;
    }
}

function init() {
    const tab = byId("admin-config-portals-tab");
    if (!tab || !byId("policy-settings-form")) return;
    const ensureLoaded = () => {
        if (!state.loaded) load().catch(error => Notify.error(error.message));
    };
    tab.addEventListener("click", ensureLoaded);
    tab.addEventListener("focus", ensureLoaded);
    byId("policy-settings-defaults").addEventListener("click", () => {
        if (state.padroes) renderForm(state.padroes);
    });
    byId("policy-settings-publish").addEventListener("click", event => send(event.currentTarget, "/politicas/globais",
        "PUT", { politicas: state.form?.read() || {}, base_versao: state.versao }, "Políticas publicadas."));
    document.addEventListener("admin:logout", () => {
        state.loaded = false;
        state.versao = 0;
        byId("policy-settings-form").replaceChildren();
        byId("policy-settings-versions").replaceChildren();
    });
}

init();
