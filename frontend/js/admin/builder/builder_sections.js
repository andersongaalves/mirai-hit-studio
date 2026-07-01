import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import { renderPreview } from "./builder_preview.js";

export function renderSections() {

    const container = document.getElementById(
        "builder-sections"
    );

    if (!container) return;

    container.innerHTML = "";

    builderState.sections.forEach(secao => {

        container.appendChild(

            createSectionCard(secao)

        );

    });

}

function createSectionCard(secao) {

    const card = document.createElement("div");

    card.className = "builder-card";

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
                type="button"
                class="btn-small add-item"
            >
                + Adicionar Item
            </button>

            <button
                type="button"
                class="btn-small remove-section"
            >
                🗑 Remover Seção
            </button>

        </div>

    `;

    bindSectionEvents(card, secao);

    renderItems(
        card.querySelector(".builder-items"),
        secao
    );

    return card;

}

function bindSectionEvents(card, secao) {

    const toggle =
        card.querySelector(".toggle-section");

    const icon =
        card.querySelector(".builder-icon");

    const title =
        card.querySelector(".builder-title");

    const btnAddItem =
        card.querySelector(".add-item");

    const btnRemove =
        card.querySelector(".remove-section");

    toggle.onclick = () => {

        Builder.alternarSecao(secao.id);

        renderSections();

        renderPreview();

    };

    icon.oninput = (e) => {

        Builder.atualizarSecao(
            secao.id,
            "icon",
            e.target.value
        );

        renderPreview();

    };

    title.oninput = (e) => {

        Builder.atualizarSecao(
            secao.id,
            "title",
            e.target.value
        );

        renderPreview();

    };

    btnAddItem.onclick = () => {

        Builder.adicionarItem(secao.id);

        renderSections();

        renderPreview();

    };

    btnRemove.onclick = () => {

        Builder.removerSecao(secao.id);

        renderSections();

        renderPreview();

    };

}

function renderItems(container, secao) {

    container.innerHTML = "";

    if (secao.items.length === 0) {

        Builder.adicionarItem(secao.id);

    }

    secao.items.forEach((item, index) => {

        const row = document.createElement("div");

        row.className = "builder-item-row";

        const input = document.createElement("input");

        input.className = "builder-item";

        input.value = item;

        input.placeholder = "Novo Item";

        input.oninput = (e) => {

            Builder.atualizarItem(
                secao.id,
                index,
                e.target.value
            );

            renderPreview();

        };

        const btn = document.createElement("button");

        btn.className = "btn-small";

        btn.textContent = "✕";

        btn.onclick = () => {

            Builder.removerItem(
                secao.id,
                index
            );

            renderSections();

            renderPreview();

        };

        row.appendChild(input);

        row.appendChild(btn);

        container.appendChild(row);

    });

}