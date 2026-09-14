import { renderAdminState } from "../ui.js";
import { actionButton, campaignBadge, formatDate, subscriberBadge, textElement } from "./newsletter_dom.js";


function table(headers, rows, className) {
    const wrapper = textElement("div", "", `admin-table-wrap newsletter-table-view ${className}`);
    const element = document.createElement("table");
    element.className = "admin-table";
    const thead = document.createElement("thead");
    const head = document.createElement("tr");
    headers.forEach((label) => { const th = textElement("th", label); th.scope = "col"; head.appendChild(th); });
    thead.appendChild(head);
    const tbody = document.createElement("tbody");
    rows.forEach(row => tbody.appendChild(row));
    element.append(thead, tbody);
    wrapper.appendChild(element);
    return wrapper;
}


export function renderSubscribers(items, { onCancel, filtered = false } = {}) {
    const container = document.getElementById("newsletter-subscribers-list");
    if (!container) return;
    if (!items.length) return renderAdminState(container, "empty", filtered ? "Nenhum inscrito corresponde aos filtros." : "Nenhum inscrito cadastrado.");
    const rows = items.map((item) => {
        const row = document.createElement("tr");
        const action = textElement("td", "", "admin-table__cell--actions");
        if (item.ativo) action.appendChild(actionButton("Cancelar inscrição", () => onCancel?.(item)));
        row.append(textElement("td", item.email), (() => { const td = document.createElement("td"); td.appendChild(subscriberBadge(item)); return td; })(), textElement("td", item.source), textElement("td", formatDate(item.consent_at)), action);
        return row;
    });
    const cards = textElement("div", "", "newsletter-mobile-view");
    items.forEach((item) => {
        const card = textElement("article", "", "admin-entity-card");
        const header = textElement("div", "", "admin-entity-card__header");
        const meta = textElement("div", `${item.source} · ${formatDate(item.consent_at)}`, "admin-entity-card__meta");
        const actions = textElement("div", "", "admin-entity-card__actions");
        header.append(textElement("strong", item.email), subscriberBadge(item));
        if (item.ativo) actions.appendChild(actionButton("Cancelar inscrição", () => onCancel?.(item)));
        card.append(header, meta, actions);
        cards.appendChild(card);
    });
    container.replaceChildren(table(["E-mail", "Status", "Origem", "Consentimento", "Ação"], rows, "newsletter-subscribers-table"), cards);
}


export function renderCampaigns(items, { onOpen, onSend } = {}) {
    const container = document.getElementById("newsletter-campaigns-list");
    if (!container) return;
    if (!items.length) return renderAdminState(container, "empty", "Nenhuma campanha criada.");
    const rows = items.map((item) => {
        const row = document.createElement("tr");
        const actions = textElement("td", "", "admin-table__cell--actions");
        actions.appendChild(actionButton("Abrir", () => onOpen?.(item.id)));
        if (item.status === "draft") actions.appendChild(actionButton("Enviar", () => onSend?.(item.id), "btn-small btn-danger"));
        const result = `${item.total_sent || 0} enviados${item.total_failed ? `, ${item.total_failed} falhas` : ""}`;
        row.append(textElement("td", item.titulo_interno), textElement("td", item.assunto), (() => { const td = document.createElement("td"); td.appendChild(campaignBadge(item)); return td; })(), textElement("td", formatDate(item.sent_at || item.created_at)), textElement("td", result), actions);
        return row;
    });
    const cards = textElement("div", "", "newsletter-mobile-view");
    items.forEach((item) => {
        const card = textElement("article", "", "admin-entity-card");
        const header = textElement("div", "", "admin-entity-card__header");
        const meta = textElement("div", `${item.assunto} · ${item.total_sent || 0} enviados`, "admin-entity-card__meta");
        const actions = textElement("div", "", "admin-entity-card__actions");
        header.append(textElement("strong", item.titulo_interno), campaignBadge(item));
        actions.appendChild(actionButton("Abrir", () => onOpen?.(item.id)));
        if (item.status === "draft") actions.appendChild(actionButton("Enviar", () => onSend?.(item.id), "btn-small btn-danger"));
        card.append(header, meta, actions);
        cards.appendChild(card);
    });
    container.replaceChildren(table(["Título", "Assunto", "Status", "Data", "Resultado", "Ações"], rows, "newsletter-campaigns-table"), cards);
}


export function renderLoading() {
    ["newsletter-campaigns-list", "newsletter-subscribers-list"].forEach(id => renderAdminState(document.getElementById(id), "loading", "Carregando newsletter..."));
}


export function renderError(message) {
    ["newsletter-campaigns-list", "newsletter-subscribers-list"].forEach(id => renderAdminState(document.getElementById(id), "error", message));
}
