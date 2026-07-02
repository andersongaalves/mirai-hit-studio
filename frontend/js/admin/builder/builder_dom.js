/* ============================================================
 * Helpers
 * ========================================================== */

function appendChildren(parent, ...children) {

    parent.append(...children);
}

/* ============================================================
 * Elementos Base
 * ========================================================== */

export function createDivElement(className = "") {

    const div = document.createElement("div");

    div.className = className;

    return div;

}

export function createInputElement({

    className = "",

    value = "",

    placeholder = "",

    type = "text"

}) {

    const input = document.createElement("input");

    input.type = type;

    input.className = className;

    input.value = value;

    input.placeholder = placeholder;

    return input;

}

export function createButtonElement({

    className = "",

    text = "",

    type = "button"

}) {

    const button = document.createElement("button");

    button.type = type;

    button.className = className;

    button.textContent = text;

    return button;

}

/* ============================================================
 * Componentes
 * ========================================================== */

export function createSectionCardElement(secao) {

    const card =
        createDivElement("builder-card");

    const bodyDisplay =
        secao.open ? "block" : "none";

    card.innerHTML = `

        <div class="builder-header">

            <button
                type="button"
                class="toggle-section"
            >
                ${secao.open ? "▼" : "▶"}
            </button>

            <input
                class="builder-icon"
                value="${secao.icon}"
                placeholder="🎹"
            >

            <input
                class="builder-title"
                value="${secao.title}"
                placeholder="Título"
            >

        </div>

        <div
            class="builder-items"
            style="display:${bodyDisplay}"
        ></div>

        <div
            class="builder-actions"
            style="display:${bodyDisplay}"
        >

            <button
                class="btn-small add-item"
            >
                + Adicionar Item
            </button>

            <button
                class="btn-small remove-section"
            >
                🗑 Remover Seção
            </button>

        </div>

    `;

    return card;

}

export function createItemRowElement({

    value = "",

    placeholder = "Novo Item"

} = {}) {

    const row =
        createDivElement("builder-item-row");

    const input =
        createInputElement({

            className: "builder-item",

            value,

            placeholder

        });

    const button =
        createButtonElement({

            className: "btn-small",

            text: "✕"

        });

    appendChildren(
        row,
        input,
        button
    );

    return {

        row,

        input,

        button

    };

}

export function createBenefitRowElement({

    value = "",

    placeholder = "Benefício"

} = {}) {

    const row =
        createDivElement("builder-benefit-row");

    const input =
        createInputElement({

            className: "builder-benefit",

            value,

            placeholder

        });

    const button =
        createButtonElement({

            className: "btn-small",

            text: "✕"

        });

    appendChildren(
        row,
        input,
        button
    );

    return {

        row,

        input,

        button

    };

}