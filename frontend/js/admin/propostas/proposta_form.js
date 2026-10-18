import { $ } from "../../utils/dom.js";
import { atualizarCampoProposta } from "./proposta_state.js";
import { escapeHtml } from "./proposta_utils.js";

const campos = [
    {
        id: "numero",
        label: "Número da proposta",
        type: "text",
        readonly: true,
        placeholder: ""
    },
    {
        id: "data",
        label: "Data",
        type: "date",
        readonly: true
    },
    {
        id: "prestador",
        label: "Prestador (local)",
        type: "text",
        readonly: true
    },
    {
        id: "produtor_id",
        label: "ID do produtor responsável",
        type: "number"
    },
    {
        id: "objeto",
        label: "Objeto da proposta",
        type: "text"
    }
];

export function renderizarProposta(
    proposta,
    onChange = () => {}
) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    container.innerHTML = `
        <div class="admin-info proposta-form-grid">
            <div class="form-group">
                <label for="proposta_finalidade">Finalidade</label>
                <select id="proposta_finalidade">
                    <option value="producao" ${proposta.finalidade !== "creditos" ? "selected" : ""}>Produção</option>
                    <option value="creditos" ${proposta.finalidade === "creditos" ? "selected" : ""}>Créditos de serviços</option>
                </select>
            </div>
            ${campos.map(campo => `
                <div class="form-group">
                    <label>${campo.label}</label>
                    <input
                        id="proposta_${campo.id}"
                        type="${campo.type}"
                        value="${escapeHtml(proposta[campo.id])}"
                        placeholder="${escapeHtml(campo.placeholder)}"
                        ${campo.readonly ? "readonly" : ""}
                    >
                </div>
            `).join("")}

            <div class="form-group">
                <label>Descrição</label>
                <textarea id="proposta_descricao" rows="8">${escapeHtml(proposta.descricao)}</textarea>
            </div>
        </div>
    `;

    campos.forEach(campo => {
        const input = $(`proposta_${campo.id}`);

        if (!input) return;

        if (campo.readonly) return;

        input.oninput = e => {
            atualizarCampoProposta(
                campo.id,
                e.target.value
            );
            onChange();
        };
    });
    $("proposta_finalidade").onchange = event => {
        atualizarCampoProposta("finalidade", event.target.value);
        if (event.target.value === "creditos") atualizarCampoProposta("politica_pagamento", "integral");
        onChange();
    };

    const descricao = $("proposta_descricao");

    if (descricao) {
        descricao.oninput = e => {
            atualizarCampoProposta(
                "descricao",
                e.target.value
            );
            onChange();
        };
    }
}
