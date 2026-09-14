import { API_URL } from "./config.js";

// ===========================
// REQUEST BASE
// ===========================

async function request(endpoint, options = {}) {
    const response = await fetch(
        `${API_URL}/${endpoint}`,

        options,
    );

    if (!response.ok) {
        let mensagem = `Erro na requisição: ${response.status}`;

        try {
            const erro = await response.json();

            mensagem = erro.detail || mensagem;
        } catch {}

        throw new Error(mensagem);
    }

    return await response.json();
}

// ===========================
// GET
// ===========================

export function getAPI(endpoint) {
    return request(endpoint);
}

// ===========================
// POST
// ===========================

export function postAPI(endpoint, payload) {
    return request(
        endpoint,

        {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify(payload),
        },
    );
}

// ===========================
// ORÇAMENTO
// ===========================

export function postOrcamento(payload) {
    return postAPI(
        "orcamentos",

        payload,
    );
}

// ===========================
// NEWSLETTER
// ===========================

export function postNewsletter(payload) {
    return postAPI(
        "newsletter/subscribe",

        payload,
    );
}

// ===========================
// PORTFÓLIO
// ===========================

export function getProjetos() {
    return getAPI("projetos");
}
