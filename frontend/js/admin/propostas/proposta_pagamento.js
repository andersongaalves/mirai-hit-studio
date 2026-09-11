import { $ } from "../../utils/dom.js";
import { atualizarPagamento } from "./proposta_state.js";
import { escapeHtml } from "./proposta_utils.js";

const camposValores = [
    ["entrada", "Entrada / Parcial 1 (local)", "number"],
    ["restante", "Restante", "number", true],
    ["valor_total", "Valor total", "number", true],
    ["prazo", "Prazo (local)", "text"],
    ["validade", "Validade (local)", "date"]
];

const camposLinks = [
    ["pagamento_completo_url", "Link pagamento completo"],
    ["pagamento_parcial_1_url", "Link pagamento parcial 1"],
    ["pagamento_parcial_2_url", "Link pagamento parcial 2"]
];

export function renderizarPagamento(
    proposta,
    {
        onRefresh = () => {},
        onChange = () => {}
    } = {}
) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    const pagamento = proposta.pagamento ?? {};

    container.innerHTML = `
        <div class="admin-info proposta-form-grid">
            ${camposValores.map(([id, label, type, readonly]) => `
                <div class="form-group">
                    <label>${label}</label>
                    <input
                        id="proposta_pagamento_${id}"
                        type="${type}"
                        step="${type === "number" ? "0.01" : ""}"
                        value="${escapeHtml(pagamento[id])}"
                        ${readonly ? "readonly" : ""}
                    >
                </div>
            `).join("")}

            ${camposLinks.map(([id, label]) => `
                <div class="form-group">
                    <label>${label}</label>
                    <input
                        id="proposta_pagamento_${id}"
                        type="url"
                        value="${escapeHtml(pagamento[id])}"
                        placeholder="https://..."
                    >
                </div>
            `).join("")}

            <div class="form-group">
                <label>
                    <input
                        id="proposta_pagamento_parcial_2_disponivel"
                        type="checkbox"
                        ${pagamento.parcial_2_disponivel ? "checked" : ""}
                        style="width:auto;"
                    >
                    Disponibilizar parcial 2 no PDF
                </label>
            </div>

            <div class="form-group">
                <label>PIX (local)</label>
                <input
                    id="proposta_pagamento_pix"
                    value="${escapeHtml(pagamento.pix)}"
                >
            </div>

            <div class="form-group">
                <label>Mercado Pago (local)</label>
                <input
                    id="proposta_pagamento_mercado_pago"
                    value="${escapeHtml(pagamento.mercado_pago)}"
                >
            </div>

            <div class="form-group">
                <label>Observações (local)</label>
                <textarea id="proposta_pagamento_observacoes" rows="6">${escapeHtml(pagamento.observacoes)}</textarea>
            </div>
        </div>
    `;

    registrarCamposValores(onRefresh, onChange);
    registrarCamposTexto(onChange);
    registrarParcial2(onChange);
}

function registrarCamposValores(onRefresh, onChange) {
    camposValores.forEach(([id, , type, readonly]) => {
        const input = $(`proposta_pagamento_${id}`);

        if (!input || readonly) return;

        input.oninput = e => {
            atualizarPagamento(
                id,
                type === "number"
                    ? Number(e.target.value || 0)
                    : e.target.value
            );

            if (id === "entrada") {
                onRefresh();
                return;
            }

            onChange();
        };
    });
}

function registrarCamposTexto(onChange) {
    [
        ...camposLinks.map(([id]) => id),
        "pix",
        "mercado_pago",
        "observacoes"
    ].forEach(id => {
        const input = $(`proposta_pagamento_${id}`);

        if (!input) return;

        input.oninput = e => {
            atualizarPagamento(
                id,
                e.target.value
            );
            onChange();
        };
    });
}

function registrarParcial2(onChange) {
    const checkbox = $("proposta_pagamento_parcial_2_disponivel");

    if (!checkbox) return;

    checkbox.onchange = e => {
        atualizarPagamento(
            "parcial_2_disponivel",
            e.target.checked
        );
        onChange();
    };
}
