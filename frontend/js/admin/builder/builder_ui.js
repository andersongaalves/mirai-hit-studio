import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import { renderPreview } from "./builder_preview.js";
import { LIMIT_FIELDS } from "../../modules/service_catalog.js";

const byId = id => document.getElementById(id);

export function initBuilder() {
    registerEvents();
    renderBuilder();
}

/** Copies the state into the form and refreshes the preview. */
export function renderBuilder() {
    const intro = byId("builder-intro");
    if (intro) intro.value = builderState.intro;
    LIMIT_FIELDS.forEach(({ key }) => {
        const input = byId(`builder-lim-${key}`);
        if (input) input.value = builderState.limites[key] ?? "";
    });
    const destaques = byId("builder-destaques");
    if (destaques) destaques.value = builderState.destaques.join("\n");
    renderPreview();
}

export function refresh() {
    renderPreview();
}

function registerEvents() {
    const intro = byId("builder-intro");
    if (intro) {
        intro.oninput = event => {
            Builder.atualizarIntro(event.target.value);
            refresh();
        };
    }
    LIMIT_FIELDS.forEach(({ key }) => {
        const input = byId(`builder-lim-${key}`);
        if (input) {
            input.oninput = event => {
                Builder.atualizarLimite(key, event.target.value.trim());
                refresh();
            };
        }
    });
    const destaques = byId("builder-destaques");
    if (destaques) {
        destaques.oninput = event => {
            Builder.atualizarDestaques(event.target.value);
            refresh();
        };
    }
}

export function atualizarBuilder(json) {
    Builder.carregarBuilder(json);
    renderBuilder();
}

export function limparBuilder() {
    Builder.resetBuilder();
    renderBuilder();
}
