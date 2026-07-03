import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";

export function abrirModalOrcamento(orcamento) {

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