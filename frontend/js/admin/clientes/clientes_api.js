import { authFetch } from "../auth.js";


async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(
            typeof data?.detail === "string" ? data.detail : fallback,
        );
        error.status = response.status;
        throw error;
    }
    return data;
}


export async function listarClientes() {
    return responseData(
        await authFetch("/clientes"),
        "Não foi possível carregar os clientes.",
    );
}


export async function buscarCliente(id) {
    return responseData(
        await authFetch(`/clientes/${id}`),
        "Não foi possível carregar o cliente.",
    );
}


export async function criarCliente(payload) {
    return responseData(
        await authFetch("/clientes", {
            method: "POST",
            body: JSON.stringify(payload),
        }),
        "Não foi possível criar o cliente.",
    );
}


export async function atualizarCliente(id, payload) {
    return responseData(
        await authFetch(`/clientes/${id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
        }),
        "Não foi possível atualizar o cliente.",
    );
}
