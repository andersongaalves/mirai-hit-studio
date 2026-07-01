import * as API from "../api.js";
import { authFetch } from "./auth.js";
import * as Notify from "../utils/notifications.js";
import { $, $$, $$$ } from "../utils/dom.js";
import {money} from "../utils/format.js"

let orcamentos = [];

export async function carregarOrcamentos() {

    try {
        const response = await authFetch(
            "/orcamentos"
        );

        if (!response.ok) {
            throw new Error(
                "Erro ao buscar orcamentos: " +
                response.status
            );
        }

        orcamentos = await response.json();
        renderizarOrcamentos(); // <-- ESTA LINHA É NECESSÁRIA

    }

    catch (error) {
        console.error(error);
    }

}

function renderizarOrcamentos() {

    const container = $("orcamentos-list");

    if (!container) return;

    container.innerHTML = "";

    if (orcamentos.length === 0) {
        container.innerHTML = `
            <div class="admin-empty">
                Nenhum orçamento encontrado.
            </div>
        `;
        return;

    }

    orcamentos.forEach(item => {
        
        container.innerHTML += `
            <div class="admin-list-item">
                <div>
                    <strong>${item.nome_cliente}</strong>
                    <br>
                    ${item.servico}
                </div>
                <div>
                    R$ ${money(item.valor_total)}
                </div>
                <div>
                    <button onclick="visualizarOrcamento(${item.id})">
                        Ver
                    </button>
                    <button class="btn-danger"
                        onclick="deletarOrcamento(${item.id})">
                        Excluir
                    </button>
                </div>
            </div>
        `;
    });

}

export function visualizarOrcamento(id) {

    const orcamento = orcamentos.find(
        item => item.id === id
    );

    if (!orcamento) return;

    $("orc_nome").innerText =
        orcamento.nome_cliente;

    $("orc_email").innerText =
        orcamento.email;

    $("orc_whatsapp").innerText =
        orcamento.whatsapp;

    $("orc_servico").innerText =
        orcamento.servico;

    $("orc_valor").innerText =
        `R$ ${money(orcamento.valor_total)}`;

    $("orc_data").innerText =
        orcamento.data_solicitacao;

    $("orc_detalhes").innerText =
        orcamento.detalhes;

    $("orc_guia").href =
        orcamento.link_guia;

    $("modal-orcamento")
        .classList.remove("hidden");

}

export function fecharModalOrcamento() {

    $("modal-orcamento")
        .classList.add("hidden");

}

export async function deletarOrcamento(id) {

    if (!confirm("Deseja realmente excluir este orçamento?")) {
        return;
    }

    const response = await authFetch(
        `/orcamentos/${id}`,
        {
            method: "DELETE"
        }
    );

    if (!response.ok) {
        Notify.error("Erro ao excluir orçamento.");
        return;

    }
    carregarOrcamentos();
}