import { closeAdminModal, openAdminModal } from "../admin_modal.js";
import { badge, button, definition, element } from "./financeiro_dom.js";
import { formatDate, methodLabel, money, paymentTypeLabel, reconciliationLabel, reconciliationReason, statusLabel, statusVariant } from "./financeiro_utils.js";


function paymentCard(payment, { onReconcile, reconcilingPaymentId }) {
    const card = element("article", "", "financeiro-payment");
    const header = element("div", "", "financeiro-payment__header");
    header.append(
        element("strong", `${paymentTypeLabel(payment.tipo)} · ${money(payment.valor)}`),
        badge(statusLabel(payment.status), statusVariant(payment.status)),
    );
    const details = element("dl", "", "financeiro-detail-grid");
    details.append(
        definition("Método", methodLabel(payment.metodo)),
        definition("Provider", payment.provider || "—"),
        definition("Order", payment.provider_order_id || "—"),
        definition("Criado em", formatDate(payment.created_at)),
    );
    card.append(header, details);
    if (payment.reconciliation_status) {
        card.append(
            badge(reconciliationLabel(payment.reconciliation_status), "danger"),
            element("p", reconciliationReason(payment.reconciliation_reason), "financeiro-payment__notice"),
        );
    }
    if (payment.provider_order_id) {
        const reconcile = button(
            reconcilingPaymentId === payment.id ? "Conciliando..." : "Conciliar com provider",
            "btn-small",
            () => onReconcile(payment.id),
        );
        reconcile.disabled = reconcilingPaymentId !== null;
        card.appendChild(reconcile);
    }
    return card;
}


export function renderFinanceiroModal(detail, options) {
    const title = document.getElementById("financeiro-modal-title");
    const summary = document.getElementById("financeiro-detail-summary");
    const payments = document.getElementById("financeiro-payments");
    const copy = document.getElementById("financeiro-copy-link");
    if (!title || !summary || !payments || !copy) return;
    title.textContent = `Cobrança #${detail.id}`;
    summary.replaceChildren(
        definition("Cliente", detail.cliente_nome),
        definition("E-mail", detail.cliente_email || "—"),
        definition("Proposta", detail.proposta_numero),
        definition("Status", statusLabel(detail.status)),
        definition("Valor total", money(detail.valor_total)),
        definition("Valor pago", money(detail.valor_pago)),
        definition("Saldo", money(detail.saldo_pendente)),
        definition("Criada em", formatDate(detail.created_at)),
    );
    payments.replaceChildren(...detail.pagamentos.map(payment => paymentCard(payment, options)));
    if (!detail.pagamentos.length) payments.appendChild(element("p", "Nenhuma tentativa de pagamento registrada.", "admin-state__message"));
    copy.onclick = () => options.onCopy(detail.checkout_url);
    const listVariant = window.matchMedia("(max-width: 768px)").matches
        ? ".financeiro-mobile-view"
        : ".financeiro-table-view";
    openAdminModal("modal-financeiro", {
        onRequestClose: closeFinanceiroModal,
        initialFocus: "#financeiro-close-modal",
        opener: `${listVariant} [data-financeiro-charge-id="${detail.id}"]`,
    });
}


export function closeFinanceiroModal() {
    closeAdminModal("modal-financeiro");
}
