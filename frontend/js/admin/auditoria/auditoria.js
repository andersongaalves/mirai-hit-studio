import * as Auth from "../auth.js";
import { listarAuditoria } from "./auditoria_api.js";
import { auditoriaState } from "./auditoria_state.js";
import { renderAuditoria } from "./auditoria_ui.js";


function filtersFromForm() {
    return {
        action: document.getElementById("audit-action-filter")?.value || "",
        entityType: document.getElementById("audit-entity-filter")?.value || "",
        entityId: document.getElementById("audit-entity-id-filter")?.value.trim() || "",
        actorUserId: document.getElementById("audit-actor-filter")?.value || "",
        dateFrom: document.getElementById("audit-date-from-filter")?.value || "",
        dateTo: document.getElementById("audit-date-to-filter")?.value || "",
    };
}


export async function carregarAuditoria() {
    if (!Auth.isAdmin()) return;
    auditoriaState.loading = true;
    auditoriaState.error = "";
    renderAuditoria(auditoriaState);
    try {
        const response = await listarAuditoria(auditoriaState);
        auditoriaState.items = Array.isArray(response.items) ? response.items : [];
        auditoriaState.total = Number(response.total) || 0;
        auditoriaState.pages = Number(response.pages) || 0;
        auditoriaState.page = Number(response.page) || 1;
    } catch (error) {
        auditoriaState.items = [];
        auditoriaState.error = error.message || "Não foi possível carregar a auditoria.";
    } finally {
        auditoriaState.loading = false;
        const summary = document.getElementById("audit-summary");
        if (summary) summary.textContent = `${auditoriaState.total} registro${auditoriaState.total === 1 ? "" : "s"}`;
        renderAuditoria(auditoriaState, { onRetry: carregarAuditoria });
    }
}


export function initAuditoria() {
    if (!Auth.isAdmin()) return Promise.resolve();
    document.getElementById("audit-apply-filters").onclick = () => {
        auditoriaState.filters = filtersFromForm();
        auditoriaState.page = 1;
        carregarAuditoria();
    };
    document.getElementById("audit-clear-filters").onclick = () => {
        ["audit-action-filter", "audit-entity-filter", "audit-entity-id-filter", "audit-actor-filter", "audit-date-from-filter", "audit-date-to-filter"]
            .forEach(id => { const field = document.getElementById(id); if (field) field.value = ""; });
        auditoriaState.filters = filtersFromForm();
        auditoriaState.page = 1;
        carregarAuditoria();
    };
    document.getElementById("audit-previous-page").onclick = () => {
        if (auditoriaState.page > 1) { auditoriaState.page--; carregarAuditoria(); }
    };
    document.getElementById("audit-next-page").onclick = () => {
        if (auditoriaState.page < auditoriaState.pages) { auditoriaState.page++; carregarAuditoria(); }
    };
    return carregarAuditoria();
}
