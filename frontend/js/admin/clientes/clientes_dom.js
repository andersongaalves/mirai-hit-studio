export function textElement(tag, text = "", className = "") {
    const element = document.createElement(tag);
    element.textContent = text ?? "";
    element.className = className;
    return element;
}


export function buttonElement(text, ariaLabel = "") {
    const button = textElement("button", text, "btn-small");
    button.type = "button";
    if (ariaLabel) button.setAttribute("aria-label", ariaLabel);
    return button;
}


export function badgeElement(cliente) {
    return textElement(
        "span",
        cliente.ativo ? "Ativo" : "Inativo",
        `badge badge-${cliente.ativo ? "success" : "neutral"}`,
    );
}


export function tableElement() {
    const wrapper = textElement("div", "", "admin-table-wrap clientes-table-view");
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const row = document.createElement("tr");
    const body = document.createElement("tbody");
    table.className = "admin-table clientes-table";
    table.setAttribute("aria-label", "Lista de clientes");
    ["Cliente", "Contato", "Última interação", "Orçamentos", "Status", "Ações"]
        .forEach((label) => {
            const cell = textElement("th", label);
            cell.scope = "col";
            row.appendChild(cell);
        });
    head.appendChild(row);
    table.append(head, body);
    wrapper.appendChild(table);
    return { wrapper, body };
}
