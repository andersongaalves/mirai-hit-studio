import { renderAdminState } from "../ui.js";
import { badge, button, element } from "./financeiro_dom.js";
import { formatDate, money, reconciliationLabel, statusLabel, statusVariant } from "./financeiro_utils.js";


function metric(label, value, variant = "") {
    const card = element("article", "", `dashboard-kpi${variant ? ` dashboard-kpi--${variant}` : ""}`);
    card.append(element("p", label, "dashboard-kpi__label"), element("strong", value, "dashboard-kpi__value"));
    return card;
}


export function renderSummary(summary) {
    const container = document.getElementById("financeiro-metrics");
    if (!container) return;
    if (!summary) {
        container.replaceChildren();
        return;
    }
    container.replaceChildren(
        metric("A receber", money(summary.valor_a_receber), "info"),
        metric("Recebido", money(summary.valor_recebido)),
        metric("Parcialmente pagas", String(summary.cobrancas_parciais)),
        metric("Requer atenção", String(summary.pagamentos_em_atencao), summary.pagamentos_em_atencao ? "danger" : ""),
    );
}


function statusCell(item) {
    const cell = document.createElement("td");
    cell.appendChild(badge(statusLabel(item.status), statusVariant(item.status)));
    if (item.reconciliation_status) {
        cell.appendChild(badge(reconciliationLabel(item.reconciliation_status), "danger"));
    }
    return cell;
}


function table(items, onOpen) {
    const wrapper = element("div", "", "admin-table-wrap financeiro-table-view");
    const table = element("table", "", "admin-table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Cobrança", "Cliente", "Proposta", "Total", "Pago", "Saldo", "Status", "Criada em", "Ações"].forEach(label => {
        const th = element("th", label);
        th.scope = "col";
        headRow.appendChild(th);
    });
    head.appendChild(headRow);
    const body = document.createElement("tbody");
    items.forEach(item => {
        const row = document.createElement("tr");
        const actions = element("td", "", "admin-table__cell--actions");
        const open = button("Detalhes", "btn-small", () => onOpen(item.id));
        open.dataset.financeiroChargeId = String(item.id);
        actions.appendChild(open);
        row.append(
            element("td", `#${item.id}`),
            element("td", item.cliente_nome),
            element("td", item.proposta_numero),
            element("td", money(item.valor_total)),
            element("td", money(item.valor_pago)),
            element("td", money(item.saldo_pendente)),
            statusCell(item),
            element("td", formatDate(item.created_at)),
            actions,
        );
        body.appendChild(row);
    });
    table.append(head, body);
    wrapper.appendChild(table);
    return wrapper;
}


function cards(items, onOpen) {
    const container = element("div", "", "financeiro-mobile-view");
    items.forEach(item => {
        const card = element("article", "", "admin-entity-card financeiro-card");
        const header = element("div", "", "admin-entity-card__header");
        header.append(element("strong", `${item.cliente_nome} · #${item.id}`, "admin-entity-card__title"), badge(statusLabel(item.status), statusVariant(item.status)));
        const meta = element("div", "", "admin-entity-card__meta");
        meta.append(
            element("span", `Proposta ${item.proposta_numero}`),
            element("span", `Saldo ${money(item.saldo_pendente)}`),
            element("span", formatDate(item.created_at)),
        );
        if (item.reconciliation_status) meta.appendChild(badge(reconciliationLabel(item.reconciliation_status), "danger"));
        const actions = element("div", "", "admin-entity-card__actions");
        const open = button("Detalhes", "btn-small", () => onOpen(item.id));
        open.dataset.financeiroChargeId = String(item.id);
        actions.appendChild(open);
        card.append(header, meta, actions);
        container.appendChild(card);
    });
    return container;
}


export function renderList(state, { onOpen, onRetry }) {
    const container = document.getElementById("financeiro-list");
    const pagination = document.getElementById("financeiro-pagination");
    if (!container) return;
    if (state.loading) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "loading", "Carregando cobranças...");
    }
    if (state.error) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "error", state.error, { onRetry });
    }
    if (!state.items.length) {
        pagination?.classList.add("hidden");
        return renderAdminState(container, "empty", "Nenhuma cobrança encontrada.");
    }
    container.replaceChildren(table(state.items, onOpen), cards(state.items, onOpen));
    pagination?.classList.toggle("hidden", state.pages <= 1);
    document.getElementById("financeiro-page-label").textContent = `Página ${state.page} de ${state.pages}`;
    document.getElementById("financeiro-previous-page").disabled = state.page <= 1;
    document.getElementById("financeiro-next-page").disabled = state.page >= state.pages;
}
