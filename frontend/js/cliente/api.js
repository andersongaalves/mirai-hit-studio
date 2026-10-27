import { authFetch } from "../admin/auth.js";
import { humanClientMessage } from "./messages.js";

async function responseData(response, fallback) {
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(humanClientMessage(data?.detail, fallback));
        error.status = response.status;
        throw error;
    }
    return data;
}

export async function listarPropostas() {
    return responseData(
        await authFetch("/portal/cliente/propostas"),
        "Não foi possível carregar suas propostas.",
    );
}

export async function obterCreditos() {
    return responseData(await authFetch("/portal/cliente/creditos"), "Não foi possível carregar seus créditos.");
}

export async function listarBeats() {
    return responseData(await authFetch("/portal/cliente/beats"), "Não foi possível carregar o catálogo de beats.");
}

export async function ouvirBeat(id) {
    const response = await authFetch(`/beats/${id}/preview`);
    if (!response.ok) throw new Error("Não foi possível ouvir o beat.");
    return response.blob();
}

export async function solicitarBeat(id, licenca, idempotencyKey) {
    return responseData(await authFetch(`/portal/cliente/beats/${id}/solicitar`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ licenca }),
    }), "Não foi possível solicitar esta licença.");
}

export async function baixarBeat(id, kind) {
    const response = await authFetch(`/portal/cliente/beats/${id}/arquivo/${kind}`);
    if (!response.ok) return responseData(response, "Não foi possível acessar o arquivo adquirido.");
    if ((response.headers.get("content-type") || "").includes("application/json")) return response.json();
    const disposition = response.headers.get("content-disposition") || "";
    const filename = disposition.match(/filename="([^"]+)"/i)?.[1] || `beat-${id}.${kind}`;
    return { type: "file", blob: await response.blob(), filename };
}

export async function baixarContratoBeat(licencaId) {
    const response = await authFetch(`/portal/cliente/beats/licencas/${licencaId}/contrato`);
    if (!response.ok) return responseData(response, "Não foi possível baixar o contrato.");
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return { blob: await response.blob(), filename: encoded ? decodeURIComponent(encoded) : `contrato-${licencaId}.pdf` };
}

export async function obterProposta(id) {
    return responseData(
        await authFetch(`/portal/cliente/propostas/${id}`),
        "Não foi possível carregar esta proposta.",
    );
}

export async function aceitarProposta(id, versao) {
    return responseData(
        await authFetch(`/portal/cliente/propostas/${id}/aceitar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ versao }),
        }),
        "Não foi possível aceitar esta proposta.",
    );
}

export async function recusarProposta(id, versao) {
    return responseData(
        await authFetch(`/portal/cliente/propostas/${id}/recusar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ versao }),
        }),
        "Não foi possível recusar esta proposta.",
    );
}

export async function baixarProposta(id) {
    const response = await authFetch(`/portal/cliente/propostas/${id}/documento`);
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        const error = new Error(humanClientMessage(data?.detail, "Documento indisponível."));
        error.status = response.status;
        throw error;
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return { blob, filename: encoded ? decodeURIComponent(encoded) : `proposta-${id}.pdf` };
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

export async function enviarArquivo(producaoId, arquivo, tipo, substituiId = null, observacao = "") {
    const form = new FormData();
    form.append("arquivo", arquivo);
    form.append("tipo", tipo);
    if (substituiId) form.append("substitui_arquivo_id", String(substituiId));
    if (observacao.trim()) form.append("observacao", observacao.trim());
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
        throw new Error(humanClientMessage(data?.detail, "Não foi possível acessar o arquivo."));
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return { blob, filename: encoded ? decodeURIComponent(encoded) : "arquivo" };
}

export async function obterConfiguracao() {
    return responseData(
        await authFetch("/portal/cliente/configuracao"),
        "Não foi possível carregar as preferências do portal.",
    );
}

export async function listarMultitracksAdquiridos() {
    return responseData(await authFetch("/portal/cliente/beats/adquiridos"), "Não foi possível carregar seus multitracks.");
}

export async function acessarMultitrack(beatId) {
    const response = await authFetch(`/portal/cliente/beats/${beatId}/multitrack`);
    if (!response.ok) return responseData(response, "Não foi possível acessar o multitrack.");
    if ((response.headers.get("content-type") || "").includes("application/json")) return response.json();
    const disposition = response.headers.get("content-disposition") || "";
    const filename = disposition.match(/filename="([^"]+)"/i)?.[1] || "multitrack.zip";
    return { type: "file", blob: await response.blob(), filename };
}

export async function listarMensagens(producaoId) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/mensagens`),
        "Não foi possível carregar as mensagens.",
    );
}

export async function enviarMensagem(producaoId, payload) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/mensagens`, {
            method: "POST",
            body: JSON.stringify(payload),
        }),
        "Não foi possível enviar a mensagem.",
    );
}

// Roadmap 5.06: contract stages (read-only for the client, no values).
export async function listarEtapas(producaoId) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/etapas`),
        "Não foi possível carregar as etapas.",
    );
}

// Roadmap 5.09: contractual file quotas of the production, with usage.
export async function listarCotas(producaoId) {
    return responseData(
        await authFetch(`/portal/cliente/producoes/${producaoId}/cotas-arquivos`),
        "Não foi possível carregar as cotas de arquivos.",
    );
}
