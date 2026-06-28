export function renderizarEstrutura(estrutura) {

    if (!estrutura) return "";

    let dados = estrutura;

    if (typeof estrutura === "string") {

        try {

            dados = JSON.parse(estrutura);

        } catch {

            return "";

        }

    }

    let html = "";

    // INTRO
    if (dados.intro) {

        html += `
            <p class="service-intro">
                ${dados.intro}
            </p>
        `;

    }

    // SEÇÕES
    (dados.sections ?? []).forEach(secao => {

        html += `
            <div class="service-section">

                <div class="service-section-title">

                    <span class="service-icon">
                        ${secao.icon ?? ""}
                    </span>

                    <span>
                        ${secao.title ?? ""}
                    </span>

                </div>

                <ul class="service-items">
        `;

        (secao.items ?? []).forEach(item => {

            html += `
                <li>${item}</li>
            `;

        });

        html += `
                </ul>

            </div>
        `;

    });

    // BENEFÍCIOS
    if ((dados.benefits ?? []).length) {

        html += `

            <div class="service-benefits">

        `;

        dados.benefits.forEach(item => {

            html += `

                <div class="service-benefit">

                    ✓ ${item}

                </div>

            `;

        });

        html += `

            </div>

        `;

    }

    return html;

}