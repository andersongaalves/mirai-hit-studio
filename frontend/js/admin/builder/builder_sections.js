import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import {
    createItemRowElement,
    createSectionCardElement,
} from "./builder_dom.js";
import { refresh } from "./builder_ui.js";

/* ============================================================
 * Renderização
 * ========================================================== */

export function renderSections() {
    const container = document.getElementById("builder-sections");

    if (!container) return;

    container.innerHTML = "";

    builderState.sections.forEach((secao) => {
        container.appendChild(createSectionCard(secao));
    });
}

/* ============================================================
 * Card
 * ========================================================== */

function createSectionCard(secao) {
    const card = createSectionCardElement(secao);

    bindSectionEvents(card, secao);

    renderItems(card.querySelector(".builder-items"), secao);

    return card;
}

/* ============================================================
 * Eventos
 * ========================================================== */

function bindSectionEvents(card, secao) {
    const toggle = card.querySelector(".toggle-section");

    const icon = card.querySelector(".builder-icon");

    const title = card.querySelector(".builder-title");

    const addItem = card.querySelector(".add-item");

    const removeSection = card.querySelector(".remove-section");

    toggle.onclick = () => {
        Builder.alternarSecao(secao.id);

        refresh("sections");
    };

    icon.oninput = (e) => {
        Builder.atualizarSecao(secao.id, "icon", e.target.value);

        refresh("preview");
    };

    title.oninput = (e) => {
        Builder.atualizarSecao(secao.id, "title", e.target.value);

        refresh("preview");
    };

    addItem.onclick = () => {
        Builder.adicionarItem(secao.id);

        refresh("sections");
    };

    removeSection.onclick = () => {
        Builder.removerSecao(secao.id);

        refresh("sections");
    };
}

/* ============================================================
 * Itens
 * ========================================================== */

function renderItems(container, secao) {
    container.innerHTML = "";

    secao.items.forEach((item, index) => {
        const ui = createItemRowElement({
            value: item,
        });

        bindItemEvents(ui, secao, index);

        container.appendChild(ui.row);
    });
}

function bindItemEvents(ui, secao, index) {
    ui.input.oninput = (e) => {
        Builder.atualizarItem(
            secao.id,

            index,

            e.target.value,
        );

        refresh("preview");
    };

    ui.button.onclick = () => {
        Builder.removerItem(
            secao.id,

            index,
        );

        refresh("sections");
    };
}
