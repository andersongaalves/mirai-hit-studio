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


export function carregarResumo() {
    return authFetch("/financeiro/resumo")
        .then(response => responseData(response, "Não foi possível carregar o resumo financeiro."));
}


export function listarCobrancas(state) {
    const query = new URLSearchParams({ page: String(state.page), page_size: String(state.pageSize) });
    const values = {
        search: state.filters.search,
        status: state.filters.status,
        reconciliation_status: state.filters.reconciliationStatus,
        date_from: state.filters.dateFrom,
        date_to: state.filters.dateTo,
    };
    Object.entries(values).forEach(([key, value]) => { if (value) query.set(key, value); });
    return authFetch(`/financeiro/cobrancas?${query}`)
        .then(response => responseData(response, "Não foi possível carregar as cobranças."));
}


export function buscarCobranca(id) {
    return authFetch(`/financeiro/cobrancas/${id}`)
        .then(response => responseData(response, "Não foi possível carregar a cobrança."));
}


export function conciliarPagamento(id) {
    return authFetch(`/financeiro/pagamentos/${id}/reconciliar`, { method: "POST" })
        .then(response => responseData(response, "Não foi possível conciliar o pagamento."));
}
