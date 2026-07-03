import { authFetch } from "../auth.js";

export async function buscarOrcamentos() {

    const response = await authFetch(
        "/orcamentos"
    );

    if (!response.ok) {

        throw new Error(
            "Erro ao buscar orçamentos."
        );

    }

    return await response.json();

}

export async function excluirOrcamento(id) {

    const response = await authFetch(

        `/orcamentos/${id}`,

        {
            method: "DELETE"
        }

    );

    if (!response.ok) {

        throw new Error(
            "Erro ao excluir orçamento."
        );

    }

}

export async function atualizarStatus(
    id,
    status
) {

    const response = await authFetch(

        `/orcamentos/${id}/status`,

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
            "Erro ao atualizar status."
        );

    }


    return await response.json();

}

export async function buscarProdutores() {

    const response = await authFetch(
        "/usuarios"
    );


    if (!response.ok) {

        throw new Error(
            "Erro ao buscar produtores"
        );

    }


    return await response.json();

}


export async function atualizarProdutor(
    id,
    produtor_id
) {

    const response = await authFetch(

        `/orcamentos/${id}/produtor`,

        {

            method: "PATCH",

            headers: {

                "Content-Type": "application/json"

            },


            body: JSON.stringify({

                produtor_id

            })

        }

    );


    if (!response.ok) {

        throw new Error(
            "Erro ao atualizar produtor"
        );

    }


    return await response.json();

}