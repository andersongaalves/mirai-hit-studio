const STATUS_LABELS = {
    pendente: "Pendente",
    parcialmente_paga: "Parcialmente paga",
    paga: "Paga",
    cancelada: "Cancelada",
    aprovado: "Aprovado",
    recusado: "Recusado",
    cancelado: "Cancelado",
    reembolsado: "Reembolsado",
};

const PAYMENT_TYPES = { integral: "Integral", entrada: "Entrada", saldo: "Saldo" };
const METHODS = { pix: "Pix", cartao: "Cartão" };


export function money(value) {
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
        : "—";
}


export function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
}


export const statusLabel = value => STATUS_LABELS[value] || "Desconhecido";
export const paymentTypeLabel = value => PAYMENT_TYPES[value] || value || "—";
export const methodLabel = value => METHODS[value] || value || "—";


export function statusVariant(value) {
    if (["paga", "aprovado"].includes(value)) return "success";
    if (["parcialmente_paga", "pendente"].includes(value)) return "warning";
    if (["cancelada", "cancelado", "recusado", "reembolsado"].includes(value)) return "danger";
    return "neutral";
}


export function reconciliationLabel(value) {
    return value === "conflict" ? "Conflito" : value === "required" ? "Conciliação necessária" : "Conciliado";
}


export function reconciliationReason(value) {
    const labels = {
        missing_provider_order_id: "Ordem do provedor ausente",
        provider_mismatch: "Provedor divergente",
        provider_order_id_mismatch: "Ordem divergente",
        external_reference_mismatch: "Referência divergente",
        amount_mismatch: "Valor divergente",
        currency_mismatch: "Moeda divergente",
        overpayment: "Valor pago acima do contratado",
        invalid_status_transition: "Transição de status inválida",
        beat_reservation_released: "Pagamento após a reserva do beat ser liberada",
        ambiguous_external_reference: "Referência associada a mais de uma cobrança",
        payment_not_found: "Pagamento não encontrado no provedor",
        status_mismatch: "Status do provedor diferente do registrado",
        cancel_status_mismatch: "Cancelamento com status divergente no provedor",
        cancel_confirmation_pending: "Cancelamento aguardando confirmação do provedor",
        chargeback_unsupported: "Contestação (chargeback) aberta pelo cliente",
        partial_refund_unsupported: "Reembolso parcial feito no provedor",
        unsupported_provider_status: "Status do provedor não reconhecido",
    };
    return labels[value] || "Revisão operacional necessária";
}
