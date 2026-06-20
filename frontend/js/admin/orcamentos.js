import * as API from "../api.js";
import { authFetch } from "./auth.js";

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

    const container = document.getElementById("orcamentos-list");

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
                    R$ ${Number(item.valor_total).toFixed(2)}
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

    document.getElementById("orc_nome").innerText =
        orcamento.nome_cliente;

    document.getElementById("orc_email").innerText =
        orcamento.email;

    document.getElementById("orc_whatsapp").innerText =
        orcamento.whatsapp;

    document.getElementById("orc_servico").innerText =
        orcamento.servico;

    document.getElementById("orc_valor").innerText =
        `R$ ${Number(orcamento.valor_total).toFixed(2)}`;

    document.getElementById("orc_data").innerText =
        orcamento.data_solicitacao;

    document.getElementById("orc_detalhes").innerText =
        orcamento.detalhes;

    document.getElementById("orc_guia").href =
        orcamento.link_guia;

    document.getElementById("modal-orcamento")
        .classList.remove("hidden");

}

export function fecharModalOrcamento() {

    document.getElementById("modal-orcamento")
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
        alert("Erro ao excluir orçamento.");
        return;

    }
    carregarOrcamentos();
}