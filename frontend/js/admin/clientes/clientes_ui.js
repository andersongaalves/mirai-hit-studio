import { renderAdminState } from "../ui.js";
import { badgeElement, buttonElement, tableElement, textElement } from "./clientes_dom.js";
import { formatarContato, formatarData } from "./clientes_utils.js";


function detailsButton(cliente, onOpen) {
    const button = buttonElement(
        "Abrir cliente",
        `Abrir cliente ${cliente.nome}`,
    );
    button.onclick = () => onOpen?.(cliente.id);
    return button;
}


function tableView(clientes, onOpen) {
    const { wrapper, body } = tableElement();
    clientes.forEach((cliente) => {
        const row = document.createElement("tr");
        const name = textElement("td");
        const contact = textElement("td", formatarContato(cliente));
        const last = textElement("td", formatarData(cliente.ultima_interacao));
        const budgets = textElement("td", String(cliente.total_orcamentos || 0));
        const status = textElement("td");
        const actions = textElement("td", "", "admin-table__cell--actions");
        name.append(
            textElement("strong", cliente.nome),
            textElement("span", `Cliente #${cliente.id}`, "cliente-secondary"),
        );
        status.appendChild(badgeElement(cliente));
        actions.appendChild(detailsButton(cliente, onOpen));
        row.append(name, contact, last, budgets, status, actions);
        body.appendChild(row);
    });
    return wrapper;
}


function cardView(clientes, onOpen) {
    const container = textElement("div", "", "clientes-mobile-view");
    clientes.forEach((cliente) => {
        const card = document.createElement("article");
        const header = textElement("div", "", "admin-entity-card__header");
        const metadata = textElement("div", "", "admin-entity-card__meta");
        const actions = textElement("div", "", "admin-entity-card__actions");
        card.className = "admin-entity-card cliente-card";
        header.append(textElement("strong", cliente.nome), badgeElement(cliente));
        metadata.append(
            textElement("span", formatarContato(cliente)),
            textElement("span", `Última interação: ${formatarData(cliente.ultima_interacao)}`),
            textElement("span", `${cliente.total_orcamentos || 0} orçamento(s)`),
        );
        actions.appendChild(detailsButton(cliente, onOpen));
        card.append(header, metadata, actions);
        container.appendChild(card);
    });
    return container;
}


export function renderLoading() {
    const container = document.getElementById("clientes-list");
    if (container) renderAdminState(container, "loading", "Carregando clientes...");
}


export function renderError(message) {
    const container = document.getElementById("clientes-list");
    if (container) renderAdminState(container, "error", message);
}


export function renderClientes(clientes, { onOpen, filtered = false } = {}) {
    const container = document.getElementById("clientes-list");
    if (!container) return;
    container.replaceChildren();
    if (!clientes.length) {
        renderAdminState(
            container,
            "empty",
            filtered ? "Nenhum cliente corresponde aos filtros." : "Nenhum cliente cadastrado.",
        );
        return;
    }
    container.append(tableView(clientes, onOpen), cardView(clientes, onOpen));
}


export function renderSummary(total, visible, filtered) {
    const summary = document.getElementById("clientes-summary");
    if (!summary) return;
    if (!Number.isFinite(total)) {
        summary.textContent = "";
        return;
    }
    summary.textContent = filtered
        ? `${visible} de ${total} clientes`
        : `${total} cliente${total === 1 ? "" : "s"}`;
}
