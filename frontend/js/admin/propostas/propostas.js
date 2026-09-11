import * as Notify from "../../utils/notifications.js";
import { $ } from "../../utils/dom.js";

import * as PropostaModal from "./proposta_modal.js";
import * as PropostaTabs from "./proposta_tabs.js";
import * as PropostaCliente from "./proposta_cliente.js";
import * as PropostaForm from "./proposta_form.js";
import * as PropostaItens from "./proposta_itens.js";
import * as PropostaCondicoes from "./proposta_condicoes.js";
import * as PropostaPagamento from "./proposta_pagamento.js";
import * as PropostaPreview from "./proposta_preview.js";

import {
    propostaState,
    resetPropostaState,
    setProposta,
    getEditorProposta
} from "./proposta_state.js";

import {
    criarPropostaInicial
} from "./proposta_utils.js";

function renderizarAbaAtiva() {
    atualizarStatusLocal();
    const proposta = getEditorProposta();

    PropostaTabs.renderizarTabs({
        abaAtiva: propostaState.abaAtiva,
        onChange: alterarAba
    });

    if (propostaState.abaAtiva === "cliente") {
        PropostaCliente.renderizarCliente(
            propostaState.orcamento
        );
        return;
    }

    if (propostaState.abaAtiva === "proposta") {
        PropostaForm.renderizarProposta(
            proposta,
            atualizarStatusLocal
        );
        return;
    }

    if (propostaState.abaAtiva === "itens") {
        PropostaItens.renderizarItens(
            proposta,
            renderizarAbaAtiva
        );
        return;
    }

    if (propostaState.abaAtiva === "condicoes") {
        PropostaCondicoes.renderizarCondicoes(
            proposta,
            atualizarStatusLocal
        );
        return;
    }

    if (propostaState.abaAtiva === "pagamento") {
        PropostaPagamento.renderizarPagamento(
            proposta,
            {
                onRefresh: renderizarAbaAtiva,
                onChange: atualizarStatusLocal
            }
        );
        return;
    }

    if (propostaState.abaAtiva === "preview") {
        PropostaPreview.renderizarPreview(
            proposta,
            propostaState.orcamento
        );
    }
}

function atualizarStatusLocal() {
    const status = $("proposta-status");

    if (!status) return;

    status.textContent = propostaState.dirty
        ? "Alterações locais não salvas"
        : "Rascunho local";
}

function alterarAba(aba) {
    propostaState.abaAtiva = aba;
    renderizarAbaAtiva();
}

export function abrirEditorProposta(orcamento) {
    if (!orcamento) {
        Notify.error(
            "Orçamento não encontrado."
        );
        return;
    }

    resetPropostaState();
    propostaState.orcamento = orcamento;

    setProposta(
        criarPropostaInicial(orcamento)
    );

    PropostaModal.abrirModalProposta(orcamento);
    renderizarAbaAtiva();
}

export function fecharEditorProposta() {
    PropostaModal.fecharModalProposta();
    resetPropostaState();
}
