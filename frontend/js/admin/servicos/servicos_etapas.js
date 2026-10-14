// Roadmap 3.0, 5.04: catalog stages with percentage weights in the service editor.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";

const MAX_STAGES = 20;
const state = { serviceId: null, stages: [], busy: false, revision: 0 };
const byId = id => document.getElementById(id);

function emptyStage() {
    return {
        nome: "", descricao: "", peso_percentual: "0", prazo_dias: null, unidade: "",
        revisoes_incluidas: null, depende_da_anterior: false, administrativa: false,
    };
}

// Work in hundredths so the total is exact (no floating point drift).
function toCents(value) {
    const text = String(value ?? "").trim().replace(",", ".");
    if (!/^\d{1,3}(\.\d{1,2})?$/.test(text)) return null;
    const [whole, fraction = ""] = text.split(".");
    return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

function formatPercent(cents) {
    return `${(cents / 100).toFixed(2).replace(".", ",")}%`;
}

function input(type, value, label, attributes = {}) {
    const element = document.createElement("input");
    element.type = type;
    element.value = value ?? "";
    element.setAttribute("aria-label", label);
    Object.entries(attributes).forEach(([key, attribute]) => element.setAttribute(key, attribute));
    return element;
}

function checkbox(checked, label) {
    const wrapper = document.createElement("label");
    wrapper.className = "servico-etapa__check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = Boolean(checked);
    wrapper.append(box, document.createTextNode(` ${label}`));
    return { wrapper, box };
}

function updateTotal() {
    const total = byId("servico-etapas-total");
    if (!total) return;
    if (!state.stages.length) {
        total.textContent = "Sem etapas cadastradas.";
        total.dataset.state = "empty";
        return;
    }
    const cents = state.stages.map(stage => toCents(stage.peso_percentual));
    if (cents.some(value => value === null)) {
        total.textContent = "Peso inválido: use até duas casas decimais.";
        total.dataset.state = "error";
        return;
    }
    const sum = cents.reduce((acc, value) => acc + value, 0);
    total.textContent = sum === 10000 ? `Total: ${formatPercent(sum)}` : `Total: ${formatPercent(sum)} (precisa somar 100%)`;
    total.dataset.state = sum === 10000 ? "ok" : "error";
}

function render() {
    const list = byId("servico-etapas-list");
    if (!list) return;
    list.replaceChildren();
    state.stages.forEach((stage, index) => {
        const row = document.createElement("div");
        row.className = "servico-etapa";
        const order = document.createElement("span");
        order.className = "servico-etapa__ordem";
        order.textContent = `${index + 1}.`;

        const name = input("text", stage.nome, `Nome da etapa ${index + 1}`, { maxlength: "100", placeholder: "Nome da etapa" });
        name.addEventListener("input", () => { stage.nome = name.value; });
        const weight = input("text", stage.peso_percentual, `Peso da etapa ${index + 1} em %`, { inputmode: "decimal", placeholder: "%" });
        weight.addEventListener("input", () => { stage.peso_percentual = weight.value; updateTotal(); });
        const deadline = input("number", stage.prazo_dias ?? "", `Prazo em dias da etapa ${index + 1}`, { min: "0", max: "365", placeholder: "dias" });
        deadline.addEventListener("input", () => { stage.prazo_dias = deadline.value === "" ? null : Number(deadline.value); });
        const unit = input("text", stage.unidade, `Unidade da etapa ${index + 1}`, { maxlength: "30", placeholder: "unidade (ex.: faixa)" });
        unit.addEventListener("input", () => { stage.unidade = unit.value; });
        const revisions = input("number", stage.revisoes_incluidas ?? "", `Revisões incluídas na etapa ${index + 1}`, { min: "0", max: "20", placeholder: "revisões" });
        revisions.addEventListener("input", () => { stage.revisoes_incluidas = revisions.value === "" ? null : Number(revisions.value); });

        const dependency = checkbox(stage.depende_da_anterior, "Depende da anterior");
        dependency.box.disabled = index === 0;
        dependency.box.addEventListener("change", () => { stage.depende_da_anterior = dependency.box.checked; });
        const admin = checkbox(stage.administrativa, "Administrativa");
        admin.box.addEventListener("change", () => { stage.administrativa = admin.box.checked; });

        const actions = document.createElement("div");
        actions.className = "servico-etapa__actions";
        [["↑", "Mover para cima", -1], ["↓", "Mover para baixo", 1]].forEach(([text, label, offset]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn-small";
            button.textContent = text;
            button.setAttribute("aria-label", `${label}: etapa ${index + 1}`);
            const target = index + offset;
            button.disabled = target < 0 || target >= state.stages.length;
            button.addEventListener("click", () => {
                [state.stages[index], state.stages[target]] = [state.stages[target], state.stages[index]];
                if (state.stages[0]) state.stages[0].depende_da_anterior = false;
                render();
            });
            actions.append(button);
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn-small";
        remove.textContent = "Remover";
        remove.setAttribute("aria-label", `Remover etapa ${index + 1}`);
        remove.addEventListener("click", () => {
            state.stages.splice(index, 1);
            if (state.stages[0]) state.stages[0].depende_da_anterior = false;
            render();
        });
        actions.append(remove);

        const extras = document.createElement("div");
        extras.className = "servico-etapa__extras";
        extras.append(unit, revisions, dependency.wrapper, admin.wrapper, actions);
        row.append(order, name, weight, deadline, extras);
        list.append(row);
    });
    byId("servico-etapas-add").disabled = !state.serviceId || state.stages.length >= MAX_STAGES;
    byId("servico-etapas-save").disabled = !state.serviceId;
    updateTotal();
}

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    return data;
}

export async function carregarEtapasServico(serviceId) {
    const revision = ++state.revision;
    state.serviceId = serviceId ? Number(serviceId) : null;
    state.stages = [];
    const unsaved = byId("servico-etapas-unsaved");
    if (unsaved) unsaved.classList.toggle("hidden", Boolean(state.serviceId));
    render();
    if (!state.serviceId) return;
    try {
        const stages = await responseData(await authFetch(`/servicos/${state.serviceId}/etapas`), "Erro ao carregar etapas.");
        if (revision !== state.revision) return;
        state.stages = stages.map(({ id, ordem, ...stage }) => ({ ...stage, peso_percentual: String(stage.peso_percentual) }));
        render();
    } catch (error) {
        if (revision === state.revision) Notify.error(error.message);
    }
}

async function save() {
    if (!state.serviceId || state.busy) return;
    const cents = state.stages.map(stage => toCents(stage.peso_percentual));
    if (state.stages.length && (cents.some(value => value === null) || cents.reduce((a, b) => a + b, 0) !== 10000)) {
        Notify.error("A soma dos pesos deve ser 100%.");
        return;
    }
    if (state.stages.some(stage => !stage.nome.trim())) {
        Notify.error("Informe o nome de todas as etapas.");
        return;
    }
    state.busy = true;
    const button = byId("servico-etapas-save");
    button.disabled = true;
    try {
        const payload = {
            etapas: state.stages.map((stage, index) => ({
                ...stage,
                nome: stage.nome.trim(),
                peso_percentual: String(stage.peso_percentual).trim().replace(",", "."),
                depende_da_anterior: index === 0 ? false : Boolean(stage.depende_da_anterior),
            })),
        };
        const saved = await responseData(await authFetch(`/servicos/${state.serviceId}/etapas`, {
            method: "PUT",
            body: JSON.stringify(payload),
        }), "Erro ao salvar etapas.");
        state.stages = saved.map(({ id, ordem, ...stage }) => ({ ...stage, peso_percentual: String(stage.peso_percentual) }));
        render();
        Notify.success("Etapas salvas.");
    } catch (error) {
        Notify.error(error.message);
    } finally {
        state.busy = false;
        button.disabled = !state.serviceId;
    }
}

function init() {
    if (!byId("servico-etapas")) return;
    byId("servico-etapas-add").addEventListener("click", () => {
        if (state.stages.length < MAX_STAGES) state.stages.push(emptyStage());
        render();
    });
    byId("servico-etapas-save").addEventListener("click", save);
    render();
}

init();
