import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import { renderPreview } from "./builder_preview.js";
import { renderBenefits } from "./builder_benefits.js";
import { renderSections } from "./builder_sections.js";

/* ============================================================
 * Inicialização
 * ========================================================== */

export function initBuilder() {
    registerEvents();

    renderBuilder();
}

/* ============================================================
 * Renderização
 * ========================================================== */

export function renderBuilder() {
    syncIntro();

    renderSections();

    renderBenefits();

    renderPreview();
}

export function refresh(type = "all") {
    switch (type) {
        case "preview":
            renderPreview();

            break;

        case "sections":
            renderSections();

            renderPreview();

            break;

        case "benefits":
            renderBenefits();

            renderPreview();

            break;

        default:
            renderBuilder();
    }
}

/* ============================================================
 * Eventos
 * ========================================================== */

function registerEvents() {
    bindIntro();

    bindButtons();
}

function bindIntro() {
    const intro = document.getElementById("builder-intro");

    if (!intro) return;

    intro.oninput = (e) => {
        Builder.atualizarIntro(e.target.value);

        refresh("preview");
    };
}

function bindButtons() {
    const btnAddSection = document.getElementById("btn-add-section");

    if (btnAddSection) {
        btnAddSection.onclick = handleAddSection;
    }

    const btnAddBenefit = document.getElementById("btn-add-benefit");

    if (btnAddBenefit) {
        btnAddBenefit.onclick = handleAddBenefit;
    }
}

/* ============================================================
 * Ações
 * ========================================================== */

function handleAddSection() {
    Builder.adicionarSecao();

    refresh();
}

function handleAddBenefit() {
    Builder.adicionarBeneficio();

    refresh();
}

/* ============================================================
 * Estado
 * ========================================================== */

function syncIntro() {
    const intro = document.getElementById("builder-intro");

    if (!intro) return;

    intro.value = builderState.intro;
}

export function atualizarBuilder(json) {
    Builder.carregarBuilder(json);

    renderBuilder();
}

export function limparBuilder() {
    Builder.resetBuilder();

    renderBuilder();
}

/* ============================================================
 * Debug
 * ========================================================== */

window.BuilderUI = {
    initBuilder,

    renderBuilder,

    refresh,

    atualizarBuilder,

    limparBuilder,
};
