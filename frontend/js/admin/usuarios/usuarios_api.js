import { authFetch } from "../auth.js";


async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(typeof data?.detail === "string" ? data.detail : fallback);
        error.status = response.status;
        throw error;
    }
    return data;
}


export async function listarUsuarios() {
    return responseData(await authFetch("/usuarios"), "Nao foi possivel carregar os usuarios.");
}


export async function buscarUsuario(id) {
    return responseData(await authFetch(`/usuarios/${id}`), "Nao foi possivel carregar o usuario.");
}


export async function criarUsuario(payload) {
    return responseData(await authFetch("/usuarios", {
        method: "POST",
        body: JSON.stringify(payload),
    }), "Nao foi possivel criar o usuario.");
}


export async function atualizarUsuario(id, payload) {
    return responseData(await authFetch(`/usuarios/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
    }), "Nao foi possivel atualizar o usuario.");
}


export async function redefinirSenha(id, novaSenha) {
    return responseData(await authFetch(`/usuarios/${id}/senha`, {
        method: "PATCH",
        body: JSON.stringify({ nova_senha: novaSenha }),
    }), "Nao foi possivel redefinir a senha.");
}
