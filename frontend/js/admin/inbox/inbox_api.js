import { authFetch } from "../auth.js";

async function readResponse(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(typeof data?.detail === "string" ? data.detail : fallback);
        error.status = response.status;
        throw error;
    }
    return data;
}

function queryString(filters, page, pageSize) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    for (const [key, value] of Object.entries(filters)) {
        if (value === "" || value === false) continue;
        params.set(key, String(value));
    }
    return params.toString();
}

export async function listarConversas(filters, page, pageSize) {
    return readResponse(
        await authFetch(`/admin/ai/conversations?${queryString(filters, page, pageSize)}`),
        "Não foi possível carregar a Inbox.",
    );
}

export async function buscarConversa(id, before = null) {
    const query = before ? `?before=${encodeURIComponent(before)}` : "";
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}${query}`), "Não foi possível carregar a conversa.");
}

export async function buscarMetricas(days = 7) {
    return readResponse(await authFetch(`/admin/ai/conversations/metrics?days=${days === 30 ? 30 : 7}`),
        "Não foi possível carregar as métricas.");
}

export async function assumirConversa(id) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/assign`, { method: "POST" }), "Não foi possível assumir a conversa.");
}

export async function alterarModo(id, mode) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/mode`, {
        method: "PATCH", body: JSON.stringify({ mode }),
    }), "Não foi possível alterar o modo da conversa.");
}

export async function gerarSugestao(id, messageId = null) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/suggestions`, {
        method: "POST", body: JSON.stringify(messageId ? { message_id: messageId } : {}),
    }), "Não foi possível gerar a sugestão.");
}

export async function enviarMensagem(id, payload) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/messages`, {
        method: "POST", body: JSON.stringify(payload),
    }), "Não foi possível enviar a mensagem.");
}

export async function encerrarConversa(id) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/close`, { method: "POST" }), "Não foi possível encerrar a conversa.");
}

export async function ignorarSugestao(id, suggestionId) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/suggestions/${encodeURIComponent(suggestionId)}`, {
        method: "DELETE",
    }), "Não foi possível ignorar a sugestão.");
}

export async function reenviarMensagem(id, messageId) {
    return readResponse(await authFetch(`/admin/ai/conversations/${encodeURIComponent(id)}/messages/${encodeURIComponent(messageId)}/retry`, {
        method: "POST",
    }), "Não foi possível reenviar a mensagem.");
}
