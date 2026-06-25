import { API_URL } from "./config.js";

export async function getAPI(endpoint) {

    const res = await fetch(
        `${API_URL}/${endpoint}`
    );

    if (!res.ok) {
        throw new Error(
            `Erro ao buscar ${endpoint}: ${res.status}`
        );

    }

    return await res.json();
}

export async function postOrcamento(payload) {

    const res = await fetch(
        `${API_URL}/orcamentos`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        }
    );

    if (!res.ok) {
        throw new Error(
            "Erro ao enviar o orçamento"
        );

    }
    return await res.json();
}

export async function postNewsletter(payload) {

    const res = await fetch(
        `${API_URL}/newsletter`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        }
    );

    if (!res.ok) {

        const erro = await res.json();

        throw new Error(
            erro.detail || "Erro ao cadastrar e-mail."
        );

    }

    return await res.json();

}

export async function getProjetos() {

    const res = await fetch(
        `${API_URL}/projetos`
    );

    if (!res.ok) {
        throw new Error(
            "Erro ao buscar projetos"
        );
    }
    return await res.json();
}