import * as ProducoesAPI from "./producoes_api.js";

import * as ProducoesUI from "./producoes_ui.js";

import { producoesState } from "./producoes_state.js";

import * as Notify from "../../utils/notifications.js";

import * as ProducoesModal from "./producoes_modal.js";

export async function carregarProducoes() {
    try {
        producoesState.lista = await ProducoesAPI.buscarProducoes();

        ProducoesUI.renderizarProducoes(producoesState.lista);
    } catch (error) {
        console.error(error);
    }
}

export async function alterarStatus(id, status) {
    try {
        const atualizado = await ProducoesAPI.atualizarStatus(
            id,

            status,
        );

        const index = producoesState.lista.findIndex((item) => item.id === id);

        if (index !== -1) {
            producoesState.lista[index] = atualizado;
        }

        carregarProducoes();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao alterar produção");
    }
}

export function initProducoes() {
    carregarProducoes();
}

export function visualizarProducao(id) {
    const producao = producoesState.lista.find((item) => item.id === id);

    ProducoesModal.abrirModalProducao(producao);
}

export async function salvarEtapas(id, etapas) {
    try {
        const atualizado = await ProducoesAPI.atualizarEtapas(
            id,

            etapas,
        );

        const index = producoesState.lista.findIndex((item) => item.id === id);

        if (index !== -1) {
            producoesState.lista[index] = atualizado;
        }
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao salvar etapas");
    }
}

export async function salvarPrazo(id, prazo) {
    try {
        const atualizado = await ProducoesAPI.atualizarPrazo(
            id,

            prazo,
        );

        const index = producoesState.lista.findIndex((item) => item.id === id);

        if (index !== -1) {
            producoesState.lista[index] = atualizado;
        }

        Notify.success("Prazo atualizado");
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao salvar prazo");
    }
}
