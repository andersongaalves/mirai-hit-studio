import * as Notify from "../../utils/notifications.js";
import { $ } from "../../utils/dom.js";
import * as ProducoesAPI from "./producoes_api.js";
import * as ProducoesModal from "./producoes_modal.js";
import { producoesState } from "./producoes_state.js";
import * as ProducoesUI from "./producoes_ui.js";
import { filtrarOrdenarProducoes } from "./producoes_utils.js";

document.addEventListener("proposta:comercial-atualizada", (event) => {
    if (event.detail?.proposta?.status === "aceita") carregarProducoes();
});

function atualizarState(atualizado) {
    const index = producoesState.lista.findIndex(
        (item) => item.id === atualizado.id,
    );
    if (index === -1) {
        producoesState.lista.push(atualizado);
        return atualizado;
    }

    producoesState.lista[index] = {
        ...producoesState.lista[index],
        ...atualizado,
    };
    return producoesState.lista[index];
}

function handlers() {
    return {
        onVisualizar: visualizarProducao,
        onAlterarStatus: alterarStatus,
        onSalvarEtapas: salvarEtapas,
        onSalvarPrazo: salvarPrazo,
        onSalvarObservacoes: salvarObservacoes,
    };
}

function registrarEventos() {
    const busca = $("producoes-search");
    const status = $("producoes-status-filter");
    const prazo = $("producoes-prazo-filter");

    if (busca) {
        busca.value = producoesState.filtro.busca;
        busca.oninput = (event) => {
            producoesState.filtro.busca = event.target.value;
            refresh();
        };
    }
    if (status) {
        status.value = producoesState.filtro.status;
        status.onchange = (event) => {
            producoesState.filtro.status = event.target.value;
            refresh();
        };
    }
    if (prazo) {
        prazo.value = producoesState.filtro.prazo;
        prazo.onchange = (event) => {
            producoesState.filtro.prazo = event.target.value;
            refresh();
        };
    }
}

export function refresh() {
    if (producoesState.loading) {
        ProducoesUI.renderizarLoading();
        return;
    }
    if (producoesState.error) {
        ProducoesUI.renderizarErro(producoesState.error);
        return;
    }
    ProducoesUI.renderizarProducoes(
        filtrarOrdenarProducoes(
            producoesState.lista,
            producoesState.filtro,
        ),
        handlers(),
    );
}

export async function carregarProducoes() {
    producoesState.loading = true;
    producoesState.error = "";
    refresh();

    try {
        const producoes = await ProducoesAPI.buscarProducoes();
        producoesState.lista = Array.isArray(producoes) ? producoes : [];
    } catch (error) {
        console.error(error);
        producoesState.error = "Não foi possível carregar as produções.";
        Notify.error(producoesState.error);
    } finally {
        producoesState.loading = false;
        refresh();
    }
}

async function salvarCom(apiCall, successMessage, errorMessage) {
    try {
        const atualizado = atualizarState(await apiCall());
        ProducoesModal.atualizarModalProducao(atualizado);
        refresh();
        if (successMessage) Notify.success(successMessage);
        return atualizado;
    } catch (error) {
        console.error(error);
        Notify.error(error.message || errorMessage);
        refresh();
        return null;
    }
}

export function alterarStatus(id, status) {
    return salvarCom(
        () => ProducoesAPI.atualizarStatus(id, status),
        "Status atualizado.",
        "Erro ao alterar produção.",
    );
}

export async function visualizarProducao(id) {
    try {
        const producao = atualizarState(await ProducoesAPI.buscarProducao(id));
        ProducoesModal.abrirModalProducao(producao, handlers());
    } catch (error) {
        console.error(error);
        Notify.error(error.message || "Erro ao abrir produção.");
    }
}

export function salvarEtapas(id, etapas) {
    return salvarCom(
        () => ProducoesAPI.atualizarEtapas(id, etapas),
        "Etapas atualizadas.",
        "Erro ao salvar etapas.",
    );
}

export function salvarPrazo(id, prazo) {
    return salvarCom(
        () => ProducoesAPI.atualizarPrazo(id, prazo),
        "Prazo atualizado.",
        "Erro ao salvar prazo.",
    );
}

export function salvarObservacoes(id, observacoes) {
    return salvarCom(
        () => ProducoesAPI.atualizarObservacoes(id, observacoes),
        "Observações atualizadas.",
        "Erro ao salvar observações.",
    );
}

export function initProducoes() {
    registrarEventos();
    return carregarProducoes();
}
