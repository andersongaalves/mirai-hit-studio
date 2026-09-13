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
import * as PropostaAPI from "./proposta_api.js";

import {
    propostaState,
    resetPropostaState,
    setProposta,
    getEditorProposta,
    getPropostaPayload,
    podeEditar
} from "./proposta_state.js";

let contexto = 0;
let orcamentoCarregando = null;

function renderizarConteudoAba() {
    PropostaPreview.limparPreview();
    const proposta = getEditorProposta();

    PropostaTabs.renderizarTabs({
        abaAtiva: propostaState.abaAtiva,
        onChange: alterarAba
    });

    if (propostaState.abaAtiva === "cliente") {
        PropostaCliente.renderizarCliente(
            propostaState.proposta.cliente_snapshot
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
            renderizarAbaAtiva,
            atualizarStatusLocal
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
            propostaState.dirty
        );
    }
}

function renderizarAbaAtiva() {
    renderizarConteudoAba();
    atualizarStatusLocal();
}

function atualizarStatusLocal() {
    const status = $("proposta-status");
    const { proposta, carregando, salvando, gerando, processando, dirty } = propostaState;
    const ocupado = carregando || salvando || gerando || processando;
    if (status) status.textContent = carregando ? "Carregando proposta..."
        : salvando ? "Salvando proposta..."
        : gerando ? "Gerando PDF..."
        : processando ? "Processando proposta..."
        : proposta ? `${proposta.numero} | ${proposta.status} | Versão ${proposta.versao}${dirty ? " | Alterações não salvas" : ""}`
        : "Proposta não carregada";
    const salvar = $("btn-save-proposta");
    if (salvar) {
        salvar.disabled = !podeEditar() || !dirty;
        salvar.onclick = salvarProposta;
    }
    const gerar = $("btn-gerar-pdf-proposta");
    if (gerar) {
        gerar.disabled = !proposta || ocupado || dirty;
        gerar.title = dirty ? "Salve as alterações antes de gerar o PDF." : "Gerar PDF";
        gerar.onclick = gerarDocumento;
    }
    if (status && dirty) status.textContent += " | Salve as alterações antes de gerar o PDF.";
    const enviar = $("btn-enviar-proposta"), aprovar = $("btn-aprovar-proposta");
    if (enviar) {
        enviar.disabled = ocupado || dirty || !["rascunho", "pronta"].includes(proposta?.status);
        enviar.onclick = enviarProposta;
    }
    if (aprovar) {
        aprovar.disabled = ocupado || dirty || proposta?.status !== "enviada";
        aprovar.onclick = aprovarProposta;
    }
    const content = $("proposta-content");
    if (content) {
        content.inert = ocupado;
        content.querySelectorAll("input, textarea, select, button").forEach(input => {
            input.disabled = !podeEditar();
        });
    }
    $("proposta-tabs")?.querySelectorAll("button").forEach(button => {
        button.disabled = ocupado;
    });
    $("modal-proposta")?.setAttribute("aria-busy", String(ocupado));
}

function alterarAba(aba) {
    if (propostaState.carregando || propostaState.salvando || propostaState.gerando || propostaState.processando || !propostaState.proposta) return;
    propostaState.abaAtiva = aba;
    renderizarAbaAtiva();
}

export async function abrirEditorProposta(orcamento) {
    if (!Number.isInteger(orcamento?.id) || orcamento.id <= 0) {
        Notify.error(
            "Orçamento não encontrado."
        );
        return;
    }

    if (propostaState.salvando || propostaState.processando || orcamentoCarregando === orcamento.id) return;
    if (propostaState.proposta?.orcamento_id === orcamento.id) return;
    if (propostaState.dirty && !confirm("Descartar as alterações não salvas desta proposta?")) return;
    const atual = ++contexto;
    PropostaPreview.limparPreview();
    resetPropostaState();
    propostaState.carregando = true;
    orcamentoCarregando = orcamento.id;
    if ($("proposta-content")) $("proposta-content").textContent = "Carregando proposta...";
    if ($("proposta-tabs")) $("proposta-tabs").replaceChildren();
    PropostaModal.abrirModalProposta(null);
    atualizarStatusLocal();
    try {
        let proposta;
        try {
            proposta = await PropostaAPI.buscarPorOrcamento(orcamento.id);
        } catch (error) {
            if (error.status !== 404) throw error;
            if (atual !== contexto) return;
            proposta = await PropostaAPI.criarPorOrcamento(orcamento.id);
        }
        if (atual !== contexto) return;
        setProposta(proposta);
        propostaState.carregando = false;
        PropostaModal.abrirModalProposta(propostaState.orcamento);
        renderizarAbaAtiva();
    } catch (error) {
        if (atual !== contexto) return;
        if ($("proposta-content")) $("proposta-content").textContent = error.message;
        Notify.error(error.message);
    } finally {
        if (atual === contexto) {
            orcamentoCarregando = null;
            propostaState.carregando = false;
            atualizarStatusLocal();
        }
    }
}

export async function salvarProposta() {
    if (!podeEditar() || !propostaState.dirty) return;
    const atual = contexto;
    const id = propostaState.proposta.id;
    const payload = getPropostaPayload();
    propostaState.salvando = true;
    atualizarStatusLocal();
    try {
        const resposta = await PropostaAPI.salvarProposta(id, payload);
        if (atual !== contexto) return;
        setProposta(resposta);
        propostaState.salvando = false;
        renderizarAbaAtiva();
        Notify.success("Proposta salva.");
    } catch (error) {
        if (atual === contexto) Notify.error(error.message);
    } finally {
        if (atual === contexto) {
            propostaState.salvando = false;
            atualizarStatusLocal();
        }
    }
}

export async function gerarDocumento() {
    const { proposta, dirty, carregando, salvando, gerando } = propostaState;
    if (dirty) {
        Notify.warning("Salve as alterações antes de gerar o PDF.");
        return;
    }
    if (!proposta || carregando || salvando || gerando || propostaState.processando) return;
    const atual = contexto;
    propostaState.gerando = true;
    atualizarStatusLocal();
    try {
        const resposta = await PropostaAPI.gerarDocumento(proposta.id);
        if (atual !== contexto) return;
        if (resposta.id !== proposta.id || !resposta.pdf_path || !resposta.gerada_em) {
            throw new Error("Resposta de geração inválida.");
        }
        setProposta(resposta);
        propostaState.gerando = false;
        propostaState.abaAtiva = "preview";
        renderizarAbaAtiva();
        Notify.success("PDF gerado.");
    } catch (error) {
        if (atual === contexto) Notify.error(error.message);
    } finally {
        if (atual === contexto) {
            propostaState.gerando = false;
            atualizarStatusLocal();
        }
    }
}

export function fecharEditorProposta() {
    if (propostaState.salvando || propostaState.processando) {
        Notify.warning("Aguarde a operação terminar.");
        return false;
    }
    if (propostaState.dirty && !confirm("Descartar as alterações não salvas desta proposta?")) return false;
    encerrarEditor();
    return true;
}

function encerrarEditor() {
    contexto++;
    PropostaPreview.limparPreview();
    orcamentoCarregando = null;
    PropostaModal.fecharModalProposta();
    resetPropostaState();
    $("proposta-content")?.replaceChildren();
    $("proposta-tabs")?.replaceChildren();
    atualizarStatusLocal();
}

document.addEventListener("admin:logout", encerrarEditor);

async function executarAcaoComercial(acao) {
    const { proposta, dirty, carregando, salvando, gerando, processando } = propostaState;
    if (!proposta || dirty || carregando || salvando || gerando || processando) return;
    const envio = acao === "enviar";
    if (!(envio ? ["rascunho", "pronta"].includes(proposta.status) : proposta.status === "enviada")) return;
    if (!confirm(envio ? "Enviar esta proposta por e-mail ao cliente do snapshot?"
        : "Confirmar o aceite do cliente e criar a produção desta proposta?")) return;
    const atual = contexto;
    propostaState.processando = true;
    atualizarStatusLocal();
    try {
        const resposta = await (envio ? PropostaAPI.enviarProposta : PropostaAPI.aprovarProposta)(proposta.id);
        if (atual !== contexto) return;
        if (resposta.id !== proposta.id || resposta.status !== (envio ? "enviada" : "aceita")) throw new Error("Resposta comercial inválida.");
        setProposta(resposta);
        document.dispatchEvent(new CustomEvent("proposta:comercial-atualizada", { detail: { proposta: resposta } }));
        renderizarAbaAtiva();
        Notify.success(envio ? "Proposta enviada." : "Proposta aceita. Produção disponível.");
    } catch (error) {
        if (atual === contexto) Notify.error(error.message);
    } finally {
        if (atual === contexto) {
            propostaState.processando = false;
            atualizarStatusLocal();
        }
    }
}

export const enviarProposta = () => executarAcaoComercial("enviar");
export const aprovarProposta = () => executarAcaoComercial("aprovar");
