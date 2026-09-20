import * as Notify from "../../utils/notifications.js";
import * as Auth from "../auth.js";
import * as API from "./financeiro_api.js";
import { closeFinanceiroModal, renderFinanceiroModal } from "./financeiro_modal.js";
import { financeiroState } from "./financeiro_state.js";
import { renderList, renderSummary } from "./financeiro_ui.js";


function filtersFromForm() {
    return {
        search: document.getElementById("financeiro-search")?.value.trim() || "",
        status: document.getElementById("financeiro-status-filter")?.value || "",
        reconciliationStatus: document.getElementById("financeiro-reconciliation-filter")?.value || "",
        dateFrom: document.getElementById("financeiro-date-from")?.value || "",
        dateTo: document.getElementById("financeiro-date-to")?.value || "",
    };
}


function refresh() {
    renderSummary(financeiroState.summary);
    renderList(financeiroState, { onOpen: abrirCobranca, onRetry: carregarFinanceiro });
    const summary = document.getElementById("financeiro-summary");
    if (summary) summary.textContent = `${financeiroState.total} cobrança${financeiroState.total === 1 ? "" : "s"}`;
}


export async function carregarFinanceiro() {
    if (!Auth.isAdmin()) return;
    financeiroState.loading = true;
    financeiroState.error = "";
    refresh();
    try {
        const [summary, page] = await Promise.all([
            API.carregarResumo(),
            API.listarCobrancas(financeiroState),
        ]);
        financeiroState.summary = summary;
        financeiroState.items = Array.isArray(page.items) ? page.items : [];
        financeiroState.total = Number(page.total) || 0;
        financeiroState.pages = Number(page.pages) || 0;
        financeiroState.page = Number(page.page) || 1;
    } catch (error) {
        financeiroState.error = error.message || "Não foi possível carregar o financeiro.";
    } finally {
        financeiroState.loading = false;
        refresh();
    }
}


export async function abrirCobranca(id) {
    try {
        financeiroState.selected = await API.buscarCobranca(id);
        renderSelected();
    } catch (error) {
        Notify.error(error.message || "Não foi possível abrir a cobrança.");
    }
}


function renderSelected() {
    if (!financeiroState.selected) return;
    renderFinanceiroModal(financeiroState.selected, {
        reconcilingPaymentId: financeiroState.reconcilingPaymentId,
        onCopy: copyCheckoutLink,
        onReconcile: reconcilePayment,
    });
}


async function copyCheckoutLink(value) {
    try {
        await navigator.clipboard.writeText(value);
        Notify.success("Link do checkout copiado.");
    } catch {
        Notify.error("Não foi possível copiar o link.");
    }
}


async function reconcilePayment(paymentId) {
    if (financeiroState.reconcilingPaymentId !== null) return;
    if (!window.confirm("Consultar o provider e conciliar este pagamento agora?")) return;
    financeiroState.reconcilingPaymentId = paymentId;
    renderSelected();
    try {
        await API.conciliarPagamento(paymentId);
        Notify.success("Pagamento conciliado.");
    } catch (error) {
        Notify.error(error.message || "Não foi possível conciliar o pagamento.");
    } finally {
        financeiroState.reconcilingPaymentId = null;
        const selectedId = financeiroState.selected?.id;
        await carregarFinanceiro();
        if (selectedId) await abrirCobranca(selectedId);
    }
}


function registerControls() {
    document.getElementById("financeiro-apply-filters").onclick = () => {
        financeiroState.filters = filtersFromForm();
        financeiroState.page = 1;
        carregarFinanceiro();
    };
    document.getElementById("financeiro-clear-filters").onclick = () => {
        ["financeiro-search", "financeiro-status-filter", "financeiro-reconciliation-filter", "financeiro-date-from", "financeiro-date-to"]
            .forEach(id => { const field = document.getElementById(id); if (field) field.value = ""; });
        financeiroState.filters = filtersFromForm();
        financeiroState.page = 1;
        carregarFinanceiro();
    };
    document.getElementById("financeiro-previous-page").onclick = () => {
        if (financeiroState.page > 1) { financeiroState.page--; carregarFinanceiro(); }
    };
    document.getElementById("financeiro-next-page").onclick = () => {
        if (financeiroState.page < financeiroState.pages) { financeiroState.page++; carregarFinanceiro(); }
    };
    document.getElementById("financeiro-close-modal").onclick = closeFinanceiroModal;
}


export function initFinanceiro() {
    if (!Auth.isAdmin()) return Promise.resolve();
    registerControls();
    return carregarFinanceiro();
}


export { closeFinanceiroModal };
