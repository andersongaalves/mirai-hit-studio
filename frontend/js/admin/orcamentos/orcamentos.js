import * as API from "../../api.js";
import * as Notify from "../../utils/notifications.js";
import { $, $$, $$$ } from "../../utils/dom.js";
import {money} from "../../utils/format.js"

import * as OrcamentosAPI from "./orcamentos_api.js";
import * as OrcamentosUI from "./orcamentos_ui.js";
import * as OrcamentosModal from "./orcamentos_modal.js";
import { orcamentosState } from "./orcamentos_state.js";
import { filtrarOrcamentos } from "./orcamentos_filters.js";
import {
    registrarEventosModal
} from "./orcamentos_modal.js";

export function refresh(tipo = "all") {

    switch (tipo) {

        case "lista":

            OrcamentosUI.renderizarOrcamentos(

                filtrarOrcamentos()

            );

            break;

        default:

            OrcamentosUI.renderizarOrcamentos(

                filtrarOrcamentos()

            );

    }

}

export async function carregarOrcamentos() {

    try {

        const [
            orcamentos,
            produtores
        ] = await Promise.all([

            OrcamentosAPI.buscarOrcamentos(),

            OrcamentosAPI.buscarProdutores()

        ]);


        orcamentosState.lista =
            orcamentos;


        orcamentosState.produtores =
            produtores;


        refresh("lista");

    }

    catch(error) {

        console.error(error);

    }

}

export function visualizarOrcamento(id) {

    const orcamento = orcamentosState.lista.find(
        item => item.id === id
    );

    OrcamentosModal.abrirModalOrcamento(
        orcamento
    );
}
 
export const fecharModalOrcamento =
    OrcamentosModal.fecharModalOrcamento;

export async function deletarOrcamento(id) {
    if (!confirm(
        "Deseja realmente excluir este orçamento?"
    )) {
        return;
    }

    try {
        await OrcamentosAPI.excluirOrcamento(id);
        carregarOrcamentos();
    }

    catch {
        Notify.error(
            "Erro ao excluir orçamento."
        );
    }
}

function registrarEventos() {

    const busca = $("orcamentos-search");
    const status =
        $("orcamentos-status-filter");


    if (status) {

        status.onchange = (e) => {


            orcamentosState.filtro.status =
                e.target.value;


            refresh(
                "lista"
            );

        };

    }

    if (!busca) return;

    busca.oninput = (e) => {

        orcamentosState.filtro.busca =
            e.target.value;

        refresh("lista");

    };

}

export function initOrcamentos() {
    registrarEventos();
    registrarEventosModal();
    carregarOrcamentos();
}

export async function alterarStatus(
    id,
    status
) {

    try {

        const atualizado =
            await OrcamentosAPI.atualizarStatus(
                id,
                status
            );


        const index =
            orcamentosState.lista.findIndex(

                item => item.id === id

            );


        if (index !== -1) {

            orcamentosState.lista[index] =
                atualizado;

        }


        refresh("lista");

    }

    catch(error) {

        console.error(error);

        Notify.error(
            "Erro ao atualizar status."
        );

    }

}

export async function alterarProdutor(
    id,
    produtor_id
) {

    try {

        const atualizado =
            await OrcamentosAPI.atualizarProdutor(
                id,
                produtor_id || null
            );


        const index =
            orcamentosState.lista.findIndex(
                item => item.id === id
            );


        if (index !== -1) {

            orcamentosState.lista[index] =
                atualizado;

        }


        refresh("lista");

    }


    catch(error) {

        console.error(error);

        Notify.error(
            "Erro ao alterar produtor"
        );

    }

}

export async function salvarObservacoes(
    id,
    observacoes
) {

    try {

        const atualizado =
            await OrcamentosAPI.atualizarObservacoes(

                id,

                observacoes

            );


        const index =
            orcamentosState.lista.findIndex(

                item => item.id === id

            );


        if (index !== -1) {

            orcamentosState.lista[index] =
                atualizado;

        }


        Notify.success(
            "Observações salvas."
        );


        refresh("lista");

    }


    catch(error) {

        console.error(error);


        Notify.error(

            "Erro ao salvar observações"

        );

    }

}