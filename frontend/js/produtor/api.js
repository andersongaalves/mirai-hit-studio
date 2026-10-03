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
        await authFetch("/portal/produtor/producoes"),
        "Não foi possível carregar suas produções.",
    );
}

export async function obterProducao(id) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${id}`),
        "Não foi possível carregar esta produção.",
    );
}

export async function atualizarStatus(id, status) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${id}/status`, {
            method: "PATCH",
            body: JSON.stringify({ status }),
        }),
        "Não foi possível atualizar o andamento.",
    );
}

export async function listarArquivos(producaoId) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/arquivos`),
        "Não foi possível carregar os arquivos.",
    );
}

export async function enviarArquivo(producaoId, arquivo, tipo, substituiId = null) {
    const form = new FormData();
    form.append("arquivo", arquivo);
    form.append("tipo", tipo);
    if (substituiId) form.append("substitui_arquivo_id", String(substituiId));
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/arquivos`, {
            method: "POST",
            body: form,
        }),
        "Não foi possível enviar o arquivo.",
    );
}

export async function listarRepasses() {
    return responseData(
        await authFetch("/portal/produtor/repasses"),
        "Não foi possível carregar os recebimentos.",
    );
}

async function baixar(url, fallback) {
    const response = await authFetch(url);
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return { blob, filename: encoded ? decodeURIComponent(encoded) : "arquivo" };
}

export function baixarArquivo(id) {
    return baixar(`/portal/produtor/arquivos/${id}/conteudo`, "Não foi possível baixar o arquivo.");
}

export function baixarComprovante(id) {
    return baixar(`/portal/produtor/repasses/${id}/comprovante`, "Não foi possível baixar o comprovante.");
}
