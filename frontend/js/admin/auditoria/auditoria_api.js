import { authFetch } from "../auth.js";


export async function listarAuditoria(state) {
    const query = new URLSearchParams({ page: String(state.page), page_size: String(state.pageSize) });
    const fields = {
        action: state.filters.action,
        entity_type: state.filters.entityType,
        entity_id: state.filters.entityId,
        actor_user_id: state.filters.actorUserId,
        date_from: state.filters.dateFrom,
        date_to: state.filters.dateTo,
    };
    Object.entries(fields).forEach(([key, value]) => { if (value) query.set(key, value); });
    const response = await authFetch(`/audit-logs?${query}`);
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Não foi possível carregar a auditoria.");
    return body;
}
