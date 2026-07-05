export function renderizarEstrutura(estrutura) {

    if (!estrutura) return "";

    let dados = estrutura;


    if (typeof estrutura === "string") {

        try {

            dados = JSON.parse(
                estrutura
            );

        }

        catch {

            return "";

        }

    }


    let html = "";


    // ===========================
    // INTRO
    // ===========================

    if (dados.intro) {

        html += `
            <p class="service-intro">
                ${dados.intro}
            </p>
        `;

    }


    // ===========================
    // SEÇÕES
    // ===========================

    (dados.sections ?? [])
        .forEach((secao, index) => {


        html += `

            <div class="service-section ${index === 0 ? "active" : ""}">

                <div 
                    class="service-section-title"
                    onclick="toggleServiceSection(this)"
                >

                    <div>

                        <span class="service-icon">
                            ${secao.icon ?? ""}
                        </span>


                        <span>
                            ${secao.title ?? ""}
                        </span>

                    </div>


                    <span class="section-arrow">
                        ▼
                    </span>


                </div>


                <ul class="service-items">

        `;


        (secao.items ?? [])
            .forEach(item => {


            html += `

                <li>
                    ${item}
                </li>

            `;


        });


        html += `

                </ul>

            </div>

        `;


    });


    // ===========================
    // BENEFÍCIOS
    // ===========================

    if (
        (dados.benefits ?? []).length
    ) {


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


// ===========================
// ACCORDION
// ===========================

window.toggleServiceSection = function(header) {


    const section =
        header.closest(
            ".service-section"
        );


    const parent =
        section.parentElement;



    parent

        .querySelectorAll(
            ".service-section"
        )

        .forEach(item => {


            if (item !== section) {


                item.classList.remove(
                    "active"
                );


            }


        });



    section.classList.toggle(
        "active"
    );

};