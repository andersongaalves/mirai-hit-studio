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

export async function enviarArquivo(producaoId, arquivo, tipo, substituiId = null, observacao = "") {
    const form = new FormData();
    form.append("arquivo", arquivo);
    form.append("tipo", tipo);
    if (substituiId) form.append("substitui_arquivo_id", String(substituiId));
    if (observacao.trim()) form.append("observacao", observacao.trim());
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

export async function listarRepassesEtapas() {
    return responseData(await authFetch("/portal/produtor/repasses-etapas"), "Repasses por etapa indisponiveis.");
}

export function baixarComprovanteEtapa(id) {
    return baixar(`/portal/produtor/repasses-etapas/${id}/comprovante`, "Nao foi possivel baixar o comprovante.");
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

export async function obterConfiguracao() {
    return responseData(
        await authFetch("/portal/produtor/configuracao"),
        "Não foi possível carregar as preferências do portal.",
    );
}

export async function listarBeats() {
    return responseData(await authFetch("/portal/produtor/beats"), "Não foi possível carregar seus beats.");
}

export async function listarCatalogoBeats() {
    return responseData(
        await authFetch("/portal/produtor/catalogo-beats"),
        "Não foi possível carregar o catálogo de beats.",
    );
}

export async function obterConfiguracaoBeats() {
    return responseData(
        await authFetch("/portal/produtor/beats/configuracao"),
        "Não foi possível carregar os limites do catálogo.",
    );
}

export async function enviarBeat(form) {
    return responseData(await authFetch("/portal/produtor/beats", { method: "POST", body: form }), "Não foi possível enviar o beat.");
}

export function ouvirBeat(id) {
    return baixar(`/beats/${id}/preview`, "Não foi possível ouvir o beat.");
}

export async function listarMensagens(producaoId) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/mensagens`),
        "Não foi possível carregar as mensagens.",
    );
}

export async function enviarMensagem(producaoId, payload) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/mensagens`, {
            method: "POST",
            body: JSON.stringify(payload),
        }),
        "Não foi possível enviar a mensagem.",
    );
}

// Roadmap 5.06: contract stages; the server decides the allowed transitions.
export async function listarEtapas(producaoId) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/etapas`),
        "Não foi possível carregar as etapas.",
    );
}

export async function atualizarEtapa(producaoId, etapaId, payload) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/etapas/${etapaId}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
        }),
        "Não foi possível atualizar a etapa.",
    );
}

// Roadmap 5.09: contractual file quotas of the production, with usage.
export async function listarCotas(producaoId) {
    return responseData(
        await authFetch(`/portal/produtor/producoes/${producaoId}/cotas-arquivos`),
        "Não foi possível carregar as cotas de arquivos.",
    );
}

// AUD6-S08-001: tag state for the dashboard notice (secondary; failures are ignored).
export async function obterTag() {
    return responseData(await authFetch("/portal/produtor/audio-tag"), "Não foi possível carregar sua tag.");
}
