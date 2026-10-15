// Roadmap 3.0, 5.09: contractual file quotas of a catalog service (admin).
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { quotaEditor } from "../../modules/file_quotas.js";

const state = { serviceId: null, editor: null, busy: false, revision: 0 };
const byId = id => document.getElementById(id);

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    return data;
}

function render(cotas = []) {
    const slot = byId("servico-cotas-editor");
    if (!slot) return;
    state.editor = state.serviceId ? quotaEditor({ cotas, idPrefix: `servico-${state.serviceId}-cota` }) : null;
    slot.replaceChildren(...(state.editor ? [state.editor.element] : []));
    const save = byId("servico-cotas-save");
    if (save) save.disabled = !state.serviceId;
}

export async function carregarCotasServico(serviceId) {
    const revision = ++state.revision;
    state.serviceId = serviceId ? Number(serviceId) : null;
    byId("servico-cotas-unsaved")?.classList.toggle("hidden", Boolean(state.serviceId));
    render([]);
    if (!state.serviceId) return;
    try {
        const cotas = await responseData(await authFetch(`/servicos/${state.serviceId}/cotas-arquivos`), "Erro ao carregar cotas.");
        if (revision === state.revision) render(Array.isArray(cotas) ? cotas : []);
    } catch (error) {
        if (revision === state.revision) Notify.error(error.message);
    }
}

async function save() {
    if (!state.serviceId || !state.editor || state.busy) return;
    let cotas;
    try {
        cotas = state.editor.read();
    } catch (error) {
        Notify.error(error.message);
        return;
    }
    state.busy = true;
    const button = byId("servico-cotas-save");
    button.disabled = true;
    try {
        const saved = await responseData(await authFetch(`/servicos/${state.serviceId}/cotas-arquivos`, {
            method: "PUT",
            body: JSON.stringify({ cotas }),
        }), "Erro ao salvar cotas.");
        render(saved);
        Notify.success("Cotas salvas.");
    } catch (error) {
        Notify.error(error.message);
    } finally {
        state.busy = false;
        button.disabled = !state.serviceId;
    }
}

function init() {
    const button = byId("servico-cotas-save");
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", save);
    render([]);
}

init();
