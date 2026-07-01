import { builderState } from "./builder_state.js";

export function renderPreview() {

    const preview = document.getElementById(
        "builder-preview-render"
    );

    if (!preview) return;

    let html = "";

    // INTRO
    if (builderState.intro.trim()) {

        html += `
            <p class="preview-intro">
                ${builderState.intro}
            </p>
        `;

    }

    // SEÇÕES
    builderState.sections.forEach(secao => {

        html += `

            <div class="preview-section">

                <h4>

                    <span class="preview-icon">

                        ${secao.icon}

                    </span>

                    ${secao.title}

                </h4>

                <ul>

                    ${secao.items
                        .filter(item => item.trim() !== "")
                        .map(item => `
                            <li>${item}</li>
                        `)
                        .join("")}

                </ul>

            </div>

        `;

    });

    preview.innerHTML = html;

}