// Files by contract stage (Rough Mix, Mixagem...). Shared by the Admin and both portals.
// Markup contract, independent of how each portal renders its lists:
//   [data-etapa-id]       a file or delivery ("" = general, no stage)
//   [data-stage-filter]   where the stage chips go (Todas, each stage, Gerais)
//   [data-stage-group]    a list whose items are filtered; shows a note when empty
//   select[data-stage-field]  the "Etapa" field of an upload form
//   [data-stage-select]   a control in the stages panel that opens that stage's files

import { orderedStages } from "./stage_tree.js";

const GENERAL = "geral";
let state = { productionId: null, stages: [], selected: null };

function activeStage(stages) {
    return stages.find(stage => ["em_andamento", "em_revisao"].includes(stage.status))
        || stages.find(stage => stage.status !== "concluida" && !stage.administrativa)
        || null;
}

export function setStages(productionId, stages = []) {
    if (state.productionId !== productionId) state = { productionId, stages: [], selected: null };
    state.stages = stages.filter(stage => stage && stage.id != null);
    if (state.selected !== null && state.selected !== GENERAL && !state.stages.some(stage => stage.id === state.selected)) {
        state.selected = null;
    }
    applyStageFiles();
}

export function resetStageFiles(productionId) {
    if (state.productionId !== productionId) state = { productionId, stages: [], selected: null };
}

export function selectStage(stageId) {
    state.selected = stageId === null || stageId === GENERAL ? stageId : Number(stageId);
    applyStageFiles();
}

export function selectedStage() {
    return state.selected;
}

// Value for an upload: the select's choice; "" means a general file.
/** The stages of the production in view, for edit forms: [{ id, label }]. */
export function stageChoices() {
    return orderedStages(state.stages).map(({ stage, parent }) => ({
        id: stage.id,
        label: parent ? `${parent.nome} › ${stage.nome}` : stage.nome,
    }));
}

export function stageFieldValue(form) {
    const value = form?.querySelector("select[data-stage-field]")?.value || "";
    return /^\d+$/.test(value) ? value : "";
}

export function stageField(className = "portal-field") {
    const wrapper = document.createElement("label");
    wrapper.className = `${className} stage-field hidden`.trim();
    wrapper.append(document.createTextNode("Etapa"));
    const select = document.createElement("select");
    select.name = "etapa_id";
    select.dataset.stageField = "";
    wrapper.append(select);
    return wrapper;
}

function matches(item) {
    const id = item.dataset.etapaId || "";
    if (state.selected === null) return true;
    if (state.selected === GENERAL) return id === "";
    return id === String(state.selected);
}

function counts(root) {
    const total = new Map();
    root.querySelectorAll("[data-etapa-id]").forEach(item => {
        const key = item.dataset.etapaId || GENERAL;
        total.set(key, (total.get(key) || 0) + 1);
    });
    return total;
}

function chip(label, value, count, parent = null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = parent ? "stage-chip stage-chip--sub" : "stage-chip";
    button.textContent = count == null ? label : `${label} (${count})`;
    if (parent) button.title = `Etapa interna de ${parent.nome}`;
    const pressed = state.selected === value;
    button.setAttribute("aria-pressed", String(pressed));
    button.addEventListener("click", () => selectStage(value));
    return button;
}

export function applyStageFiles(root = document) {
    const total = counts(root);
    const hasStages = state.stages.length > 0;

    root.querySelectorAll("[data-stage-filter]").forEach(bar => {
        bar.classList.toggle("hidden", !hasStages);
        if (!hasStages) { bar.replaceChildren(); return; }
        const chips = [chip("Todas", null, null)];
        orderedStages(state.stages).forEach(({ stage, label, parent }) => chips.push(chip(label, stage.id, total.get(String(stage.id)) || 0, parent)));
        if (total.get(GENERAL)) chips.push(chip("Gerais", GENERAL, total.get(GENERAL)));
        bar.setAttribute("role", "group");
        bar.setAttribute("aria-label", "Filtrar arquivos por etapa");
        bar.replaceChildren(...chips);
    });

    root.querySelectorAll("[data-etapa-id]").forEach(item => { item.hidden = hasStages && !matches(item); });

    root.querySelectorAll("[data-stage-group]").forEach(group => {
        const items = [...group.querySelectorAll("[data-etapa-id]")];
        let note = group.querySelector(":scope > .stage-files-empty");
        const empty = hasStages && items.length > 0 && items.every(item => item.hidden);
        if (empty && !note) {
            note = document.createElement(group.tagName === "UL" || group.tagName === "OL" ? "li" : "p");
            note.className = "stage-files-empty producer-empty";
            note.textContent = "Nenhum arquivo nesta etapa.";
            group.append(note);
        }
        if (note) note.hidden = !empty;
    });

    const preferred = typeof state.selected === "number" ? state.selected : activeStage(state.stages)?.id ?? null;
    root.querySelectorAll("select[data-stage-field]").forEach(select => {
        select.closest(".stage-field")?.classList.toggle("hidden", !hasStages);
        if (!hasStages) return;
        const keep = select.dataset.userChoice === "true" ? select.value : null;
        const options = [new Option("Geral (sem etapa)", "")];
        orderedStages(state.stages).forEach(({ stage, parent }) => options.push(new Option(parent ? `${parent.nome} › ${stage.nome}` : stage.nome, String(stage.id))));
        select.replaceChildren(...options);
        select.value = keep ?? (preferred != null ? String(preferred) : "");
        if (!select.dataset.bound) {
            select.dataset.bound = "true";
            select.addEventListener("change", () => { select.dataset.userChoice = "true"; });
            // After a form reset, go back to the stage in view (or the active one).
            select.form?.addEventListener("reset", () => setTimeout(() => {
                delete select.dataset.userChoice;
                applyStageFiles(select.form || document);
            }));
        }
    });

    // Stage names on final deliveries (and anything else that asks for it).
    const names = new Map(orderedStages(state.stages).map(({ stage, parent }) => [String(stage.id), parent ? `${parent.nome} › ${stage.nome}` : stage.nome]));
    root.querySelectorAll("[data-stage-label]").forEach(label => {
        const id = label.dataset.stageLabel;
        label.textContent = id ? names.get(id) || "Etapa" : "Entrega geral";
    });

    root.querySelectorAll("[data-stage-select]").forEach(control => {
        const id = Number(control.dataset.stageSelect);
        const count = total.get(String(id)) || 0;
        control.textContent = count ? `Arquivos (${count})` : "Arquivos";
        control.setAttribute("aria-pressed", String(state.selected === id));
        control.closest(".production-stage")?.classList.toggle("production-stage--selected", state.selected === id);
    });
}
