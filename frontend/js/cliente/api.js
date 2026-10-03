import { authFetch } from "../admin/auth.js";

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    }
    return data;
}

export async function listarProducoes() {
    return responseData(
        await authFetch("/portal/cliente/producoes"),
        "Não foi possível carregar seus projetos.",
    );
}

export async function obterProducao(id) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${id}`),
        "Não foi possível carregar este projeto.",
    );
}

export async function obterFinanceiro(id) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${id}/financeiro`),
        "Não foi possível carregar a situação de pagamento.",
    );
}

export async function listarArquivos(producaoId) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/arquivos`),
        "Não foi possível carregar os arquivos.",
    );
}

export async function enviarArquivo(producaoId, arquivo, tipo, substituiId = null) {
    const form = new FormData();
    form.append("arquivo", arquivo);
    form.append("tipo", tipo);
    if (substituiId) form.append("substitui_arquivo_id", String(substituiId));
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/arquivos`, {
            method: "POST",
            body: form,
        }),
        "Não foi possível enviar o arquivo.",
    );
}

export async function baixarArquivo(id) {
    const response = await authFetch(`/portal/cliente/arquivos/${id}/conteudo`);
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Não foi possível acessar o arquivo.");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return { blob, filename: encoded ? decodeURIComponent(encoded) : "arquivo" };
}
