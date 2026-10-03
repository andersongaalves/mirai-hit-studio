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

export async function buscarArquivos(id) {
    return handleResponse(await authFetch(`/producoes/${id}/arquivos`), "Erro ao buscar arquivos.");
}

export async function enviarArquivo(id, form) {
    return handleResponse(await authFetch(`/producoes/${id}/arquivos`, {
        method: "POST",
        body: form,
    }), "Erro ao enviar arquivo.");
}

export async function atualizarVisibilidadeArquivo(producaoId, arquivoId, payload) {
    return handleResponse(await authFetch(`/producoes/${producaoId}/arquivos/${arquivoId}/visibilidade`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao atualizar visibilidade.");
}

export async function baixarArquivo(producaoId, arquivoId) {
    const response = await authFetch(`/producoes/${producaoId}/arquivos/${arquivoId}/conteudo`);
    if (!response.ok) return handleResponse(response, "Erro ao baixar arquivo.");
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return {
        blob: await response.blob(),
        filename: encoded ? decodeURIComponent(encoded) : "arquivo",
    };
}

export async function buscarRepasse(id) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse`), "Erro ao buscar repasse.");
}

export async function definirRepasse(id, valor) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse`, {
        method: "PUT",
        headers: jsonHeaders,
        body: JSON.stringify({ valor_combinado: valor }),
    }), "Erro ao definir repasse.");
}

export async function liberarRepasse(id) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/liberar`, { method: "POST" }), "Erro ao liberar repasse.");
}

export async function pagarRepasse(id, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/pagar`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao registrar pagamento.");
}

export async function corrigirRepasse(id, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/correcao`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao corrigir repasse.");
}
