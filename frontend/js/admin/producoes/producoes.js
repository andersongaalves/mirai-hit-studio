import * as ProducoesAPI
from "./producoes_api.js";

import * as ProducoesUI
from "./producoes_ui.js";

import {
    producoesState
} from "./producoes_state.js";

import * as Notify
from "../../utils/notifications.js";


export async function carregarProducoes() {

    try {

        producoesState.lista =
            await ProducoesAPI.buscarProducoes();


        ProducoesUI.renderizarProducoes(

            producoesState.lista

        );

    }


    catch(error){

        console.error(error);

    }

}



export async function alterarStatus(
    id,
    status
) {

    try {

        const atualizado =
            await ProducoesAPI.atualizarStatus(

                id,

                status

            );


        const index =
            producoesState.lista.findIndex(

                item => item.id === id

            );


        if(index !== -1){

            producoesState.lista[index] =
                atualizado;

        }


        carregarProducoes();


    }

    catch(error){

        console.error(error);


        Notify.error(
            "Erro ao alterar produção"
        );

    }

}



export function initProducoes(){
    carregarProducoes();
}