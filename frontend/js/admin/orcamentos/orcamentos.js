import * as Notify from "../../utils/notifications.js";
import { $ } from "../../utils/dom.js";

import * as OrcamentosAPI from "./orcamentos_api.js";
import * as OrcamentosUI from "./orcamentos_ui.js";
import * as OrcamentosModal from "./orcamentos_modal.js";
import * as Propostas from "../propostas/propostas.js";

import { orcamentosState } from "./orcamentos_state.js";
import { filtrarOrcamentos } from "./orcamentos_filters.js";

const STATUS_MESSAGES = {
    em_analise: "Orçamento colocado em análise.",
    proposta_enviada: "Proposta enviada.",
    aprovado: "Orçamento aprovado.",
    arquivado: "Orçamento arquivado.",
};

function getUiHandlers() {
    return {
        onVisualizar: visualizarOrcamento,
        onDeletar: deletarOrcamento,
        onAlterarStatus: alterarStatus,
        onAlterarProdutor: alterarProdutor,

        onAnalisar: analisarOrcamento,
        onGerarProposta: gerarProposta,
        onAprovar: aprovarOrcamento,
        onArquivar: arquivarOrcamento,
    };
}

function atualizarState(atualizado) {
    const index = orcamentosState.lista.findIndex(
        (item) => item.id === atualizado.id,
    );

    if (index !== -1) {
        orcamentosState.lista[index] = atualizado;
    }
}

function registrarEventos() {
    const busca = $("orcamentos-search");
    const status = $("orcamentos-status-filter");

    if (status) {
        status.onchange = (e) => {
            orcamentosState.filtro.status = e.target.value;
            refresh();
        };
    }

    if (busca) {
        busca.oninput = (e) => {
            orcamentosState.filtro.busca = e.target.value;
            refresh();
        };
    }
}

export function refresh() {
    OrcamentosUI.renderizarOrcamentos(
        filtrarOrcamentos(orcamentosState.lista, orcamentosState.filtro),
        {
            produtores: orcamentosState.produtores,
            handlers: getUiHandlers(),
        },
    );
}

export async function carregarOrcamentos() {
    try {
        const [orcamentos, produtores] = await Promise.all([
            OrcamentosAPI.buscarOrcamentos(),
            OrcamentosAPI.buscarProdutores(),
        ]);

        orcamentosState.lista = Array.isArray(orcamentos) ? orcamentos : [];

        orcamentosState.produtores = Array.isArray(produtores)
            ? produtores
            : [];

        refresh();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao carregar orçamentos.");
    }
}

export function visualizarOrcamento(id) {
    const orcamento = orcamentosState.lista.find((item) => item.id === id);

    if (!orcamento) {
        Notify.error("Orçamento não encontrado.");
        return;
    }

    OrcamentosModal.abrirModalOrcamento(orcamento);
}

export const fecharModalOrcamento = OrcamentosModal.fecharModalOrcamento;

export async function deletarOrcamento(id) {
    if (!confirm("Deseja realmente excluir este orçamento?")) {
        return;
    }

    try {
        await OrcamentosAPI.excluirOrcamento(id);

        orcamentosState.lista = orcamentosState.lista.filter(
            (item) => item.id !== id,
        );

        refresh();

        Notify.success("Orçamento excluído.");
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao excluir orçamento.");
    }
}

export function initOrcamentos() {
    registrarEventos();

    OrcamentosModal.registrarEventosModal({
        onSalvarObservacoes: salvarObservacoes,
    });

    return carregarOrcamentos();
}

export async function alterarStatus(id, status) {
    const atual = orcamentosState.lista.find((item) => item.id === id);

    if (!atual || atual.status === status) {
        return;
    }

    try {
        const atualizado = await OrcamentosAPI.atualizarStatus(id, status);

        atualizarState(atualizado);

        refresh();

        Notify.success(
            STATUS_MESSAGES[status] ?? "Status atualizado."
        );
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao atualizar status.");
    }
}

export async function analisarOrcamento(id) {
    return alterarStatus(id, "em_analise");
}

export function gerarProposta(id) {
    const orcamento = orcamentosState.lista.find((item) => item.id === id);

    if (!orcamento) {
        Notify.error("Orçamento não encontrado.");
        return;
    }

    Propostas.abrirEditorProposta(orcamento);
}

export async function aprovarOrcamento(id) {
    return alterarStatus(id, "aprovado");
}

export async function arquivarOrcamento(id) {
    return alterarStatus(id, "arquivado");
}

export async function alterarProdutor(id, produtor_id) {
    try {
        const atualizado = await OrcamentosAPI.atualizarProdutor(
            id,
            produtor_id ?? null,
        );

        atualizarState(atualizado);
        refresh();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao alterar produtor.");
    }
}

export async function salvarObservacoes(id, observacoes) {
    try {
        const atualizado = await OrcamentosAPI.atualizarObservacoes(
            id,
            observacoes,
        );

        atualizarState(atualizado);

        Notify.success("Observações salvas.");

        refresh();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao salvar observações.");
    }
}
