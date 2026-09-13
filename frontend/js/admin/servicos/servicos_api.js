import * as API from "../../api.js";
import { authFetch } from "../auth.js";

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

export async function buscarServicos() {
    return handleResponse(await authFetch("/servicos"), "Erro ao carregar serviços.");
}

export async function salvarServicoRequest(id, payload) {
    const response = await authFetch(id ? `/servicos/${id}` : "/servicos", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });

    return handleResponse(response, "Erro ao salvar serviço.");
}

export async function excluirServico(id) {
    const response = await authFetch(`/servicos/${id}`, {
        method: "DELETE",
    });

    return handleResponse(response, "Erro ao excluir serviço.");
}
