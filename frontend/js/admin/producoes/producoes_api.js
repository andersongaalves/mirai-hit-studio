import {
    authFetch
} from "../auth.js";


export async function buscarProducoes() {

    const response = await authFetch(
        "/producoes"
    );


    if (!response.ok) {

        throw new Error(
            "Erro ao buscar produções"
        );

    }


    return await response.json();

}



export async function atualizarStatus(
    id,
    status
) {

    const response = await authFetch(

        `/producoes/${id}/status`,

        {
            method: "PATCH",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify({

                status

            })

        }

    );


    if (!response.ok) {

        throw new Error(
            "Erro ao atualizar status"
        );

    }


    return await response.json();

}