import * as Builder from "./builder.js";
import { builderState } from "./builder_state.js";

export function initBuilder() {
    registrarEventos();
    renderBuilder();
}

export function renderBuilder() {
    sincronizarIntro();
    renderSections();
    renderBenefits();
}

function registrarEventos() {

    document.getElementById(

        "btn-add-section"

    ).onclick = () => {

        Builder.adicionarSecao();

        renderBuilder();

    };

    document.getElementById(

        "btn-add-benefit"

    ).onclick = () => {

        Builder.adicionarBeneficio();

        renderBuilder();

    };

    document.getElementById(

        "builder-intro"

    ).oninput = e => {

        builderState.intro = e.target.value;

    };

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

    card.className = "builder-card";

    card.innerHTML = `

        <div class="builder-header">

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

        <div class="builder-items"></div>

        <div style="display:flex;gap:10px;margin-top:15px;">

            <button class="btn-small add-item">

                + Item

            </button>

            <button class="btn-small remove-section">

                Remover

            </button>

        </div>

    `;

    const icon = card.querySelector(".builder-icon");

    const title = card.querySelector(".builder-title");

    icon.addEventListener("input", e => {

        Builder.atualizarSecao(

            secao.id,

            "icon",

            e.target.value

        );

    });

    title.addEventListener("input", e => {

        Builder.atualizarSecao(

            secao.id,

            "title",

            e.target.value

        );

    });

    card
        .querySelector(".remove-section")
        .addEventListener("click", () => {

            Builder.removerSecao(

                secao.id

            );

            renderBuilder();

        });

    card
        .querySelector(".add-item")
        .addEventListener("click", () => {

            Builder.adicionarItem(

                secao.id

            );

            renderBuilder();

        });

    renderItems(

        card.querySelector(".builder-items"),

        secao

    );

    return card;

}

function renderItems(container, secao) {

    container.innerHTML = "";

    const itens = secao.items.length
        ? secao.items
        : [""];

    itens.forEach((item, index) => {

        const linha = document.createElement("div");

        linha.className = "builder-item-row";

        linha.innerHTML = `

            <input
                class="builder-item"
                value="${item}"
                placeholder="Novo item"
            >

            <button
                class="btn-small remove-item"
            >

                ✕

            </button>

        `;

        linha
            .querySelector(".builder-item")
            .addEventListener("input", e => {

                Builder.atualizarItem(

                    secao.id,

                    index,

                    e.target.value

                );

            });

        linha
            .querySelector(".remove-item")
            .addEventListener("click", () => {

                Builder.removerItem(

                    secao.id,

                    index

                );

                renderBuilder();

            });

        container.appendChild(linha);

    });

}

function renderBenefits() {

    const container =
        document.getElementById(
            "builder-benefits"
        );

    if (!container) return;

    container.innerHTML = "";

    builderState.benefits.forEach(

        (beneficio, index) => {

            const linha = document.createElement("div");

            linha.className =

                "builder-benefit-row";

            linha.innerHTML = `

                <input

                    class="builder-benefit"

                    value="${beneficio}"

                    placeholder="Benefício"

                >

                <button

                    class="btn-small remove-benefit"

                >

                    ✕

                </button>

            `;

            linha
                .querySelector(".builder-benefit")
                .addEventListener("input", e => {

                    Builder.atualizarBeneficio(

                        index,

                        e.target.value

                    );

                });

            linha
                .querySelector(".remove-benefit")
                .addEventListener("click", () => {

                    Builder.removerBeneficio(
                        index
                    );

                    renderBuilder();

                });
            container.appendChild(linha);
        }
    );
}

export function atualizarBuilder(json) {
    Builder.carregarBuilder(
        json
    );
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
    limparBuilder
};