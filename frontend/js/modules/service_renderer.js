import { escapeHtml } from "../utils/security.js";
import { limitLines, readStructure } from "./service_catalog.js";
// Catalog rework: intro, what the service includes (typed limits) and highlights.
// Legacy structures are converted on read (readStructure); everything is escaped.
export function renderizarEstrutura(estrutura) {
    if (!estrutura) return "";
    if (typeof estrutura === "string") {
        try {
            JSON.parse(estrutura);
        } catch {
            return '<p class="service-intro">Descrição indisponível.</p>';
        }
    }
    const dados = readStructure(estrutura);
    let html = "";
    if (dados.intro) html += `<p class="service-intro">${escapeHtml(dados.intro)}</p>`;
    const linhas = limitLines(dados.limites);
    if (linhas.length) {
        html += `<ul class="service-limits">${linhas.map(linha => `<li>${escapeHtml(linha)}</li>`).join("")}</ul>`;
    }
    if (dados.destaques.length) {
        html += `<div class="service-benefits">${dados.destaques
            .map(item => `<div class="service-benefit">✓ ${escapeHtml(item)}</div>`).join("")}</div>`;
    }
    return html;
}

/** A combo: its description, each service with what it includes, and the combo's highlights. */
export function renderizarCombo(combo) {
    if (!combo) return "";
    let html = combo.descricao ? `<p class="service-intro">${escapeHtml(combo.descricao)}</p>` : "";
    (combo.servicos || []).forEach((servico, index) => {
        const linhas = limitLines(readStructure(servico.estrutura).limites);
        const destaques = readStructure(servico.estrutura).destaques;
        html += `
            <div class="service-section ${index === 0 ? "active" : ""}">
                <div class="service-section-title" data-service-toggle>
                    <div><span>${escapeHtml(servico.nome)}</span></div>
                    <span class="section-arrow">▼</span>
                </div>
                <ul class="service-items">${[...linhas, ...destaques].map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </div>`;
    });
    if ((combo.destaques || []).length) {
        html += `<div class="service-benefits">${combo.destaques
            .map(item => `<div class="service-benefit">✓ ${escapeHtml(item)}</div>`).join("")}</div>`;
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

document.addEventListener("click", event => {
    const header = event.target.closest("[data-service-toggle]");
    if (header) window.toggleServiceSection(header);
});
