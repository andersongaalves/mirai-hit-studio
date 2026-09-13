import { authFetch } from "../auth.js";

const jsonHeaders = { "Content-Type": "application/json" };

async function handleResponse(response, fallback) {
    const text = await response.text();
    let data = null;
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = null;
        }
    }
    if (!response.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : fallback;
        const error = new Error(detail);
        error.status = response.status;
        throw error;
    }
    return data;
}

export async function buscarProducoes() {
    return handleResponse(
        await authFetch("/producoes"),
        "Erro ao buscar produções.",
    );
}

export async function buscarProducao(id) {
    return handleResponse(
        await authFetch(`/producoes/${id}`),
        "Erro ao buscar produção.",
    );
}

async function atualizar(id, endpoint, payload, fallback) {
    const response = await authFetch(`/producoes/${id}/${endpoint}`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    });
    return handleResponse(response, fallback);
}

export function atualizarStatus(id, status) {
    return atualizar(id, "status", { status }, "Erro ao atualizar status.");
}

export function atualizarEtapas(id, etapas) {
    return atualizar(
        id,
        "etapas",
        { etapas: JSON.stringify(etapas) },
        "Erro ao atualizar etapas.",
    );
}

export function atualizarPrazo(id, prazoEntrega) {
    return atualizar(
        id,
        "prazo",
        { prazo_entrega: prazoEntrega || null },
        "Erro ao atualizar prazo.",
    );
}

export function atualizarObservacoes(id, observacoes) {
    return atualizar(
        id,
        "observacoes",
        { observacoes },
        "Erro ao atualizar observações.",
    );
}
