import { $ } from "../../utils/dom.js";
import { atualizarCampoProposta, atualizarPagamento } from "./proposta_state.js";
import { escapeHtml } from "./proposta_utils.js";

const camposValores = [
    ["entrada", "Entrada / Parcial 1 (local)", "number", true],
    ["restante", "Restante", "number", true],
    ["valor_total", "Valor total", "number", true],
    ["prazo", "Prazo (local)", "text", true],
    ["validade", "Validade (local)", "date", true]
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
    const politica = proposta.politica_pagamento ?? "entrada_50_50";

    container.innerHTML = `
        <div class="admin-info proposta-form-grid">
            <div class="form-group">
                <label for="proposta_politica_pagamento">Política de pagamento</label>
                <select id="proposta_politica_pagamento">
                    <option value="integral" ${politica === "integral" ? "selected" : ""}>Pagamento integral</option>
                    <option value="entrada_50_50" ${politica === "entrada_50_50" ? "selected" : ""}>Entrada de 50% + saldo de 50%</option>
                </select>
            </div>

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
                    readonly
                    value="${escapeHtml(pagamento.pix)}"
                >
            </div>

            <div class="form-group">
                <label>Mercado Pago (local)</label>
                <input
                    id="proposta_pagamento_mercado_pago"
                    readonly
                    value="${escapeHtml(pagamento.mercado_pago)}"
                >
            </div>

            <div class="form-group">
                <label>Observações (local)</label>
                <textarea id="proposta_pagamento_observacoes" readonly rows="6">${escapeHtml(pagamento.observacoes)}</textarea>
            </div>
        </div>
    `;

    registrarCamposValores(onRefresh, onChange);
    registrarPolitica(onChange);
    registrarCamposTexto(onChange);
    registrarParcial2(onChange);
}

function registrarPolitica(onChange) {
    const select = $("proposta_politica_pagamento");
    if (!select) return;
    select.onchange = event => {
        atualizarCampoProposta("politica_pagamento", event.target.value);
        onChange();
    };
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

        if (!input || input.readOnly) return;

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
