// Roadmap 3.0, 5.10: portal policies a catalog service overrides (admin).
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { policyForm } from "../../modules/policies.js";

const state = { serviceId: null, form: null, busy: false, revision: 0 };
const byId = id => document.getElementById(id);

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    return data;
}

function render(data = null) {
    const slot = byId("servico-politicas-editor");
    if (!slot) return;
    state.form = state.serviceId && data
        ? policyForm({ values: data.politicas, inherited: data.herdadas, inheritLabel: "Padrão global", idPrefix: `servico-${state.serviceId}-politica` })
        : null;
    slot.replaceChildren(...(state.form ? [state.form.element] : []));
    const save = byId("servico-politicas-save");
    if (save) save.disabled = !state.form;
}

export async function carregarPoliticasServico(serviceId) {
    const revision = ++state.revision;
    state.serviceId = serviceId ? Number(serviceId) : null;
    byId("servico-politicas-unsaved")?.classList.toggle("hidden", Boolean(state.serviceId));
    render();
    if (!state.serviceId) return;
    try {
        const data = await responseData(await authFetch(`/servicos/${state.serviceId}/politicas`), "Erro ao carregar políticas.");
        if (revision === state.revision) render(data);
    } catch (error) {
        if (revision === state.revision) Notify.error(error.message);
    }
}

async function save() {
    if (!state.serviceId || !state.form || state.busy) return;
    state.busy = true;
    const button = byId("servico-politicas-save");
    button.disabled = true;
    try {
        render(await responseData(await authFetch(`/servicos/${state.serviceId}/politicas`, {
            method: "PUT",
            body: JSON.stringify(state.form.read()),
        }), "Erro ao salvar políticas."));
        Notify.success("Políticas do serviço salvas.");
    } catch (error) {
        Notify.error(error.message);
    } finally {
        state.busy = false;
        button.disabled = !state.form;
    }
}

function init() {
    const button = byId("servico-politicas-save");
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", save);
    render();
}

init();
