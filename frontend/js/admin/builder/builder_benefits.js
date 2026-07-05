import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import { createBenefitRowElement } from "./builder_dom.js";
import { refresh } from "./builder_ui.js";

/* ============================================================
 * Renderização
 * ========================================================== */

export function renderBenefits() {
    const container = document.getElementById("builder-benefits");

    if (!container) return;

    container.innerHTML = "";

    builderState.benefits.forEach((beneficio, index) => {
        container.appendChild(createBenefitComponent(beneficio, index));
    });
}

/* ============================================================
 * Componentes
 * ========================================================== */

function createBenefitComponent(beneficio, index) {
    const ui = createBenefitRowElement({
        value: beneficio,
    });

    bindBenefitEvents(ui, index);

    return ui.row;
}

/* ============================================================
 * Eventos
 * ========================================================== */

function bindBenefitEvents(ui, index) {
    ui.input.oninput = (e) => {
        Builder.atualizarBeneficio(
            index,

            e.target.value,
        );

        refresh("preview");
    };

    ui.button.onclick = () => {
        Builder.removerBeneficio(index);

        refresh("benefits");
    };
}
