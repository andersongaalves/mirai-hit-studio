import { builderState } from "./builder_state.js";

/* ============================================================
 * Renderização
 * ========================================================== */

export function renderPreview() {
    const preview = document.getElementById("builder-preview-render");

    if (!preview) return;

    preview.innerHTML = [
        renderIntro(),
        renderSections(),
        renderBenefits(),
    ].join("");
}

/* ============================================================
 * Intro
 * ========================================================== */

function renderIntro() {
    if (!builderState.intro.trim()) {
        return "";
    }

    return `

        <p class="preview-intro">

            ${builderState.intro}

        </p>

    `;
}

/* ============================================================
 * Seções
 * ========================================================== */

function renderSections() {
    return builderState.sections

        .map(renderSection)

        .join("");
}

function renderSection(secao) {
    return `

        <div class="preview-section">

            <h4>

                <span class="preview-icon">

                    ${secao.icon}

                </span>

                ${secao.title}

            </h4>

            <ul>

                ${renderItems(secao)}

            </ul>

        </div>

    `;
}

function renderItems(secao) {
    return secao.items

        .filter((item) => item.trim())

        .map(
            (item) => `

            <li>${item}</li>

        `,
        )

        .join("");
}

/* ============================================================
 * Benefícios
 * ========================================================== */

function renderBenefits() {
    const benefits = builderState.benefits.filter((item) => item.trim());

    if (benefits.length === 0) {
        return "";
    }

    return `

        <div class="preview-benefits">

            <h4>

                Benefícios

            </h4>

            <ul>

                ${benefits

                    .map(
                        (item) => `

                        <li>${item}</li>

                    `,
                    )

                    .join("")}

            </ul>

        </div>

    `;
}
