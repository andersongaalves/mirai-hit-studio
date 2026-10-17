import { escapeHtml } from "../utils/security.js";
import { limitLines, readStructure } from "./service_catalog.js";
import { money } from "../utils/format.js";
import { catalogDiscount } from "./catalog_pricing.js";
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
    (combo.servicos || []).forEach((servico) => {
        const linhas = limitLines(readStructure(servico.estrutura).limites);
        const destaques = readStructure(servico.estrutura).destaques;
        html += `
            <div class="service-section active">
                <strong class="service-section-title">${escapeHtml(servico.nome)}</strong>
                <ul class="service-items">${[...linhas, ...destaques].map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </div>`;
    });
    if ((combo.destaques || []).length) {
        html += `<div class="service-benefits">${combo.destaques
            .map(item => `<div class="service-benefit">✓ ${escapeHtml(item)}</div>`).join("")}</div>`;
    }
    return html;
}

/** The same customer-facing card for single services and modular combos. */
export function renderizarCardServico(servico, config = {}) {
    const desconto = catalogDiscount(servico, config);
    const preco = servico.preco_catalogo?.preco_vigente ?? Number(servico.valor_base) * (1 - desconto / 100);
    const dias = servico.prazo_estimado_dias;
    const prazo = Number.isInteger(dias) && dias >= 0
        ? `Prazo estimado: ${dias} ${dias === 1 ? "dia" : "dias"}`
        : "Prazo a combinar na proposta";
    const conteudo = servico.tipo === "combo"
        ? renderizarCombo(servico.combo)
        : renderizarEstrutura(servico.estrutura_servico);
    return `<div class="radio-card catalog-card">
        <input type="radio" name="servico" id="srv_${escapeHtml(servico.id)}" value="${escapeHtml(servico.id)}">
        <label for="srv_${escapeHtml(servico.id)}">
            <span class="catalog-card__kind">${servico.tipo === "combo" ? "Combo" : "Serviço avulso"}</span>
            <span class="service-title">${escapeHtml(servico.nome)}</span>
            ${servico.subtitulo ? `<span class="service-subtitle">${escapeHtml(servico.subtitulo)}</span>` : ""}
            <div class="service-price">A partir de <strong>${money(preco)}</strong>
                ${desconto > 0 ? `<s>${money(servico.valor_base)}</s>` : ""}
                ${servico.preco_catalogo?.promocao_ativa ? '<span class="service-promotion">Promoção</span>' : ""}
                ${desconto > 0 ? `<span class="service-discount">-${escapeHtml(desconto)}% OFF</span>` : ""}
            </div>
            <p class="catalog-card__deadline">${prazo}</p>
            <div class="service-details"><strong class="catalog-card__includes">O que inclui</strong>
                <div class="service-description">${conteudo || "Escopo definido na proposta."}</div>
            </div>
            <span class="service-selected" aria-hidden="true">Selecionado</span>
        </label>
    </div>`;
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
