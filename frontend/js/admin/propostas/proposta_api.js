import { authFetch } from "../auth.js";
export { mapResponseToState, buildPropostaPayload } from "./proposta_mapper.js";

async function responseFor(path, options = {}) {
    const response = await authFetch(path, options);
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = data?.detail;
        const message = typeof detail === "string" ? detail
            : Array.isArray(detail) ? detail.map(item => `${item.loc?.slice(1).join(".")}: ${item.msg}`).join("; ")
            : "Não foi possível concluir a operação da proposta.";
        const error = new Error(message);
        error.status = response.status;
        throw error;
    }
    return response;
}

async function request(path, options = {}) {
    const response = await responseFor(path, options);
    const data = await response.json().catch(() => null);
    if (!data?.id || !data.cliente_snapshot || !Array.isArray(data.itens) || !Array.isArray(data.pagamentos)) {
        throw new Error("Resposta de proposta inválida.");
    }
    return data;
}

export const buscarPorId = id => request(`/propostas/${id}`);
export const buscarPorOrcamento = id => request(`/propostas/orcamento/${id}`);
export const criarPorOrcamento = id => request(`/orcamentos/${id}/proposta`, {
    method: "POST", body: JSON.stringify({})
});
export const salvarProposta = (id, payload) => request(`/propostas/${id}`, {
    method: "PATCH", body: JSON.stringify(payload)
});

export const gerarDocumento = id => request(`/propostas/${id}/gerar-documento`, { method: "POST" });
export const enviarProposta = id => request(`/propostas/${id}/enviar`, { method: "POST" });
export const aprovarProposta = id => request(`/propostas/${id}/aprovar`, { method: "POST" });
export async function buscarPreview(id) {
    const response = await responseFor(`/propostas/${id}/preview`);
    if (!response.headers.get("content-type")?.includes("text/html")) throw new Error("Preview inválido.");
    const html = await response.text();
    if (!html.trim()) throw new Error("Preview vazio.");
    return html;
}
export async function baixarDocumento(id) {
    const response = await responseFor(`/propostas/${id}/documento`);
    if (!response.headers.get("content-type")?.includes("application/pdf")) throw new Error("Arquivo PDF inválido.");
    const blob = await response.blob();
    if (!(await blob.slice(0, 5).text()).startsWith("%PDF-")) throw new Error("Arquivo PDF inválido.");
    return blob;
}
