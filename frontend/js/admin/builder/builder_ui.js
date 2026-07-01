import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";
import { renderPreview } from "./builder_preview.js";

export function initBuilder() {
    registrarEventos();
    renderBuilder();
}

export function renderBuilder() {
    const intro = document.getElementById("builder-intro");

    if (intro) {
        intro.value = builderState.intro;
    }

    renderSections();
    renderBenefits();
    renderPreview();
}

function registrarEventos() {

    const intro = document.getElementById("builder-intro");

    if (intro) {

        intro.oninput = (e) => {

            builderState.intro = e.target.value;

            renderPreview();

        };

    }

    const btnAddSection =
        document.getElementById("btn-add-section");

    if (btnAddSection) {

        btnAddSection.onclick = () => {

            novaSecao();

        };

    }

    const btnAddBenefit =
        document.getElementById("btn-add-benefit");

    if (btnAddBenefit) {

        btnAddBenefit.onclick = () => {
            novoBeneficio();
        };
    }
}

function sincronizarIntro() {

    const textarea = document.getElementById(
        "builder-intro"
    );

    if (!textarea) return;

    textarea.value = builderState.intro;

}

function renderSections() {

    const container = document.getElementById(
        "builder-sections"
    );

    if (!container) return;

    container.innerHTML = "";

    builderState.sections.forEach(secao => {

        container.appendChild(

            criarCard(secao)

        );

    });

}

function criarCard(secao) {

    const card = document.createElement("div");

    const bodyDisplay = secao.open? "block": "none";

    card.innerHTML = `

        <div class="builder-header">
            <button class="toggle-section">
                ▼
            </button>

            <input class="builder-icon">
            <input class="builder-title">
        </div>

        <div class="builder-items" style="display:${bodyDisplay}"></div>

        <div style="display:flex;gap:10px;margin-top:15px;">
        
            <button type="button" class="btn-small add-item">
                + Adicionar Item
            </button>

            <button type="button" class="btn-small remove-section">
                🗑 Remover Seção
            </button>
        </div>
    `;

    card.querySelector(".toggle-section").onclick = () => {
        Builder.alternarSecao(secao.id);
        renderBuilder();
    };

    const icon = card.querySelector(".builder-icon");

    const title = card.querySelector(".builder-title");

    icon.addEventListener("input", e => {

        Builder.atualizarSecao(
            secao.id,
            "icon",
            e.target.value
        );
        renderPreview();
    });

    title.addEventListener("input", e => {

        Builder.atualizarSecao(
            secao.id,
            "title",
            e.target.value
        );

        renderPreview();
    });

    card
        .querySelector(".remove-section")
        .addEventListener("click", () => {

            Builder.removerSecao(
                secao.id
            );

            renderBuilder();
            renderPreview();
        });

    card
        .querySelector(".add-item")
        .addEventListener("click", () => {

            Builder.adicionarItem(
                secao.id
            );

            renderBuilder();
            renderPreview();
        });

    renderItems(

        card.querySelector(".builder-items"),

        secao

    );

    return card;

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
        input.placeholder = "Novo Item";
        input.value = item;
        
        input.oninput = e => {

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
            renderBuilder();
        };

        row.appendChild(input);
        row.appendChild(btn);
        container.appendChild(row);
    });
}

function renderBenefits() {

    const container = document.getElementById(

        "builder-benefits"

    );

    if (!container) return;

    container.innerHTML = "";

    builderState.benefits.forEach(

        (beneficio, index) => {

            const row = document.createElement("div");

            row.className = "builder-benefit-row";

            const input = document.createElement("input");

            input.className = "builder-benefit";

            input.placeholder = "Benefício";

            input.value = beneficio;

            input.oninput = e => {

                Builder.atualizarBeneficio(

                    index,

                    e.target.value

                );

            };

            const btn = document.createElement("button");

            btn.className = "btn-small";

            btn.textContent = "✕";

            btn.onclick = () => {

                Builder.removerBeneficio(index);

                renderBuilder();

            };

            row.appendChild(input);

            row.appendChild(btn);

            container.appendChild(row);

        }

    );

}

export function atualizarBuilder(json) {
    Builder.carregarBuilder(
        json
    );
    renderBuilder();
}

function novaSecao() {
    console.log(builderState);
    Builder.adicionarSecao();
    renderBuilder();

}

function novoBeneficio() {
    Builder.adicionarBeneficio();
    renderBuilder();
}

export function limparBuilder() {
    Builder.resetBuilder();
    renderBuilder();
}

window.BuilderUI = {
    initBuilder,
    renderBuilder,
    atualizarBuilder,
    limparBuilder,
    novaSecao,
    novoBeneficio
};