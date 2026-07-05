import { authFetch } from "../auth.js";

const jsonHeaders = {
    "Content-Type": "application/json",
};

async function handleResponse(response, message) {
    if (!response.ok) {
        throw new Error(message);
    }

    if (response.status === 204) {
        return null;
    }

    const text = await response.text();

    return text ? JSON.parse(text) : null;
}

export async function buscarOrcamentos() {
    const response = await authFetch("/orcamentos");

    return handleResponse(response, "Erro ao buscar orçamentos.");
}

export async function buscarProdutores() {
    const response = await authFetch("/usuarios");

    return handleResponse(response, "Erro ao buscar produtores.");
}

export async function excluirOrcamento(id) {
    const response = await authFetch(`/orcamentos/${id}`, {
        method: "DELETE",
    });

    return handleResponse(response, "Erro ao excluir orçamento.");
}

export async function atualizarStatus(id, status) {
    const response = await authFetch(`/orcamentos/${id}/status`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify({
            status,
        }),
    });

    return handleResponse(response, "Erro ao atualizar status.");
}

export async function atualizarProdutor(id, produtor_id) {
    const response = await authFetch(`/orcamentos/${id}/produtor`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify({
            produtor_id,
        }),
    });

    return handleResponse(response, "Erro ao atualizar produtor.");
}

export async function atualizarObservacoes(id, observacoes) {
    const response = await authFetch(`/orcamentos/${id}/observacoes`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify({
            observacoes,
        }),
    });

    return handleResponse(response, "Erro ao atualizar observações.");
}
