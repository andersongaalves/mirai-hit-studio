import * as API
from "../api.js";


import {
    authFetch
} from "./auth.js";


import * as Notify
from "../utils/notifications.js";


import {
    $
} from "../utils/dom.js";


// ===========================
// CAMPOS
// ===========================

const CONFIG_FIELDS = [

    "cfg_desconto",

    "val_extra_duracao",

    "val_extra_pessoa",

    "val_extra_canal_voz",

    "val_extra_canal_inst",

    "val_extra_melodia",

    "val_extra_revisao",

    "val_inst_hibrido",

    "val_inst_gravado",

    "val_prazo_urgente",

    "val_prazo_express",

    "val_lease_desconto"

];


// ===========================
// LOAD
// ===========================

export async function carregarConfiguracoes() {


    try {


        const config =
            await API.getAPI(
                "config"
            );


        preencherFormulario(
            config
        );


    }


    catch(error){


        console.error(error);


        Notify.error(
            "Erro ao carregar configurações."
        );


    }

}


// ===========================
// FORM
// ===========================

function preencherFormulario(
    config
) {


    Object
        .entries(config)
        .forEach(([campo, valor]) => {


            const input =
                $(campo);


            if (!input) {

                return;

            }


            input.value =
                valor ?? "";


        });

}


// ===========================
// PAYLOAD
// ===========================

function gerarPayload() {


    const payload = {};


    CONFIG_FIELDS
        .forEach(campo => {


            payload[campo] =

                parseFloat(
                    $(campo)?.value
                )

                ||

                0;


        });


    return payload;

}


// ===========================
// SAVE
// ===========================

export async function salvarConfiguracoesExtras() {


    try {


        const response =
            await authFetch(

                "/config",

                {

                    method: "PUT",

                    body: JSON.stringify(

                        gerarPayload()

                    )

                }

            );


        if (!response.ok) {


            throw new Error(
                "Erro ao salvar configurações"
            );


        }


        Notify.success(

            "Configurações atualizadas."

        );


    }


    catch(error){


        console.error(error);


        Notify.error(

            error.message ||

            "Erro ao salvar."

        );


    }

}