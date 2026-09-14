import { authFetch } from "../auth.js";


async function data(responsePromise, fallback) {
    const response = await responsePromise;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
        const error = new Error(typeof body?.detail === "string" ? body.detail : fallback);
        error.status = response.status;
        throw error;
    }
    return body;
}


export const listarSubscribers = () => data(authFetch("/newsletter/subscribers"), "Não foi possível carregar inscritos.");
export const listarCampanhas = () => data(authFetch("/newsletter/campaigns"), "Não foi possível carregar campanhas.");
export const buscarCampanha = (id) => data(authFetch(`/newsletter/campaigns/${id}`), "Não foi possível abrir a campanha.");
export const criarCampanha = (payload) => data(authFetch("/newsletter/campaigns", { method: "POST", body: JSON.stringify(payload) }), "Não foi possível criar a campanha.");
export const atualizarCampanha = (id, payload) => data(authFetch(`/newsletter/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(payload) }), "Não foi possível salvar a campanha.");
export const enviarCampanha = (id) => data(authFetch(`/newsletter/campaigns/${id}/send`, { method: "POST" }), "Não foi possível enviar a campanha.");
export const cancelarSubscriber = (id) => data(authFetch(`/newsletter/subscribers/${id}`, { method: "PATCH", body: JSON.stringify({ ativo: false }) }), "Não foi possível cancelar a inscrição.");
