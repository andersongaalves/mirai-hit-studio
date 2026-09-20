const ACTION_LABELS = {
    "user.created": "Usuário criado",
    "user.updated": "Usuário atualizado",
    "user.deactivated": "Usuário desativado",
    "user.reactivated": "Usuário reativado",
    "user.password_reset": "Senha redefinida",
    "proposal.sent": "Proposta enviada",
    "proposal.approved": "Proposta aprovada",
    "production.status_changed": "Status da produção alterado",
    "newsletter.campaign_sent": "Campanha enviada",
    "newsletter.subscriber_admin_unsubscribed": "Inscrição cancelada pelo admin",
    "payment.reconciled": "Pagamento conciliado",
    "payment.reconciliation_required": "Conciliação necessária",
    "payment.reconciliation_conflict": "Conflito de conciliação",
};

const ENTITY_LABELS = {
    user: "Usuário",
    proposal: "Proposta",
    production: "Produção",
    newsletter_campaign: "Campanha",
    newsletter_subscriber: "Inscrito",
    payment: "Pagamento",
};

const METADATA_LABELS = {
    old_status: "Status anterior",
    new_status: "Novo status",
    old_role: "Papel anterior",
    new_role: "Novo papel",
    old_active: "Ativo antes",
    new_active: "Ativo agora",
    total_sent: "Enviados",
    total_failed: "Falhas",
    total_skipped: "Ignorados",
};

export const actionLabel = value => ACTION_LABELS[value] || value || "Ação desconhecida";
export const entityLabel = value => ENTITY_LABELS[value] || value || "Sistema";

export function actionVariant(action) {
    if (action?.includes("conflict")) return "danger";
    if (action?.includes("deactivated") || action?.includes("unsubscribed") || action?.includes("required")) return "warning";
    if (action?.includes("approved") || action?.includes("sent") || action?.includes("reactivated")) return "success";
    return "info";
}

export function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
}

export function metadataSummary(metadata) {
    if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) return "Sem detalhes adicionais";
    const parts = Object.entries(metadata)
        .filter(([key, value]) => METADATA_LABELS[key] && ["string", "number", "boolean"].includes(typeof value))
        .map(([key, value]) => `${METADATA_LABELS[key]}: ${typeof value === "boolean" ? (value ? "sim" : "não") : value}`);
    return parts.join(" · ") || "Sem detalhes adicionais";
}
