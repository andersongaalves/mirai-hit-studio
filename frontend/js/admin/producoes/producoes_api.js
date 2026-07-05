import { authFetch } from "../auth.js";

export async function buscarProducoes() {
    const response = await authFetch("/producoes");

    if (!response.ok) {
        throw new Error("Erro ao buscar produções");
    }

    return await response.json();
}

export async function atualizarStatus(id, status) {
    const response = await authFetch(
        `/producoes/${id}/status`,

        {
            method: "PATCH",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify({
                status,
            }),
        },
    );

    if (!response.ok) {
        throw new Error("Erro ao atualizar status");
    }

    return await response.json();
}

export async function atualizarEtapas(id, etapas) {
    const response = await authFetch(
        `/producoes/${id}/etapas`,

        {
            method: "PATCH",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify({
                etapas: JSON.stringify(etapas),
            }),
        },
    );

    if (!response.ok) {
        throw new Error("Erro ao atualizar etapas");
    }

    return await response.json();
}

export async function atualizarPrazo(id, prazo_entrega) {
    const response = await authFetch(
        `/producoes/${id}/prazo`,

        {
            method: "PATCH",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify({
                prazo_entrega,
            }),
        },
    );

    if (!response.ok) {
        throw new Error("Erro ao atualizar prazo");
    }

    return await response.json();
}
