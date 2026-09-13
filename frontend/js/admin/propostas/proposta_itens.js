import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";

import {
    adicionarItem,
    removerItem,
    atualizarItem,
    getTotalItens
} from "./proposta_state.js";

import {
    calcularSubtotalItem,
    escapeHtml
} from "./proposta_utils.js";

export function renderizarItens(proposta, onRefresh = () => {}, onChange = () => {}) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    const itens = proposta.itens ?? [];

    container.innerHTML = `
        <div class="admin-info">
            <div id="proposta-itens-list"></div>
            <button id="btn-add-proposta-item" class="btn-small" type="button">
                + Adicionar item
            </button>
            <p><strong>Total:</strong> <span id="proposta-itens-total">${money(getTotalItens())}</span></p>
        </div>
    `;

    const list = $("proposta-itens-list");

    itens.forEach((item, index) => {
        const row = document.createElement("div");

        row.className = "admin-list-item proposta-item-row";
        row.innerHTML = `
            <div class="form-group">
                <label>Descrição</label>
                <input data-campo="descricao" value="${escapeHtml(item.descricao)}">
            </div>
            <div class="form-group">
                <label>Qtd.</label>
                <input data-campo="quantidade" type="number" min="0" step="any" value="${escapeHtml(item.quantidade ?? 0)}">
            </div>
            <div class="form-group">
                <label>Valor unitário</label>
                <input data-campo="valor_unitario" type="number" min="0" step="0.01" value="${escapeHtml(item.valor_unitario ?? 0)}">
            </div>
            <div class="form-group">
                <label>Desconto</label>
                <input data-campo="desconto" type="number" min="0" step="0.01" value="${escapeHtml(item.desconto ?? 0)}">
            </div>
            <span data-subtotal>${money(calcularSubtotalItem(item))}</span>
            <button class="btn-small btn-danger" type="button">Remover</button>
        `;

        row.querySelectorAll("input").forEach(input => {
            input.oninput = e => {
                const campo = e.target.dataset.campo;
                const value = e.target.value;

                atualizarItem(index, campo, value);
                row.querySelector("[data-subtotal]").textContent = money(calcularSubtotalItem(item));
                $("proposta-itens-total").textContent = money(getTotalItens());
                onChange();
            };
        });

        row.querySelector("button").onclick = () => {
            removerItem(index);
            onRefresh();
        };

        list.appendChild(row);
    });

    $("btn-add-proposta-item").onclick = () => {
        adicionarItem();
        onRefresh();
    };
}
