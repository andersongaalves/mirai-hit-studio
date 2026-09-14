import { renderAdminState } from "../ui.js";
import { badge, element } from "./auditoria_dom.js";
import { actionLabel, actionVariant, entityLabel, formatDate, metadataSummary } from "./auditoria_utils.js";


function table(items) {
    const wrapper = element("div", "", "admin-table-wrap audit-table-view");
    const table = element("table", "", "admin-table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Data", "Ator", "Ação", "Entidade", "Resumo"].forEach(label => {
        const th = element("th", label);
        th.scope = "col";
        headRow.appendChild(th);
    });
    head.appendChild(headRow);
    const body = document.createElement("tbody");
    items.forEach(item => {
        const row = document.createElement("tr");
        const actionCell = document.createElement("td");
        actionCell.appendChild(badge(actionLabel(item.action), actionVariant(item.action)));
        row.append(
            element("td", formatDate(item.created_at)),
            element("td", item.actor_username || "Sistema"),
            actionCell,
            element("td", `${entityLabel(item.entity_type)}${item.entity_id ? ` #${item.entity_id}` : ""}`),
            element("td", metadataSummary(item.metadata), "audit-summary-cell"),
        );
        body.appendChild(row);
    });
    table.append(head, body);
    wrapper.appendChild(table);
    return wrapper;
}


function cards(items) {
    const container = element("div", "", "audit-mobile-view");
    items.forEach(item => {
        const card = element("article", "", "admin-entity-card audit-card");
        const header = element("div", "", "admin-entity-card__header");
        header.append(element("strong", `${entityLabel(item.entity_type)}${item.entity_id ? ` #${item.entity_id}` : ""}`), badge(actionLabel(item.action), actionVariant(item.action)));
        card.append(
            header,
            element("div", `${item.actor_username || "Sistema"} · ${formatDate(item.created_at)}`, "admin-entity-card__meta"),
            element("p", metadataSummary(item.metadata), "audit-summary-cell"),
        );
        container.appendChild(card);
    });
    return container;
}


export function renderAuditoria(state, { onRetry } = {}) {
    const container = document.getElementById("audit-list");
    const pagination = document.getElementById("audit-pagination");
    if (!container) return;
    if (state.loading) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "loading", "Carregando auditoria...");
    }
    if (state.error) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "error", state.error, { onRetry });
    }
    if (!state.items.length) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "empty", "Nenhum registro de auditoria encontrado.");
    }
    container.replaceChildren(table(state.items), cards(state.items));
    pagination?.classList.toggle("hidden", state.pages <= 1);
    document.getElementById("audit-page-label").textContent = `Página ${state.page} de ${state.pages}`;
    document.getElementById("audit-previous-page").disabled = state.page <= 1;
    document.getElementById("audit-next-page").disabled = state.page >= state.pages;
}
