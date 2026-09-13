export function createDivElement(className = "") {
    const div = document.createElement("div");
    div.className = className;
    return div;
}

export function createTextElement(tag, text = "", className = "") {
    const element = document.createElement(tag);
    element.textContent = text ?? "";
    element.className = className;
    return element;
}

export function createTableElement(headers = []) {
    const wrapper = createDivElement("admin-table-wrap producoes-table-view");
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    const body = document.createElement("tbody");

    table.className = "admin-table producoes-table";
    table.setAttribute("aria-label", "Lista de produções");
    headers.forEach(({ label, className = "" }) => {
        const cell = createTextElement("th", label, className);
        cell.scope = "col";
        headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.append(head, body);
    wrapper.appendChild(table);
    return { wrapper, body };
}

export function createTableCellElement(className = "") {
    return createTextElement("td", "", className);
}

export function createBadgeElement(text, variant = "neutral", className = "") {
    return createTextElement(
        "span",
        text,
        `badge badge-${variant}${className ? ` ${className}` : ""}`,
    );
}

export function createProgressElement(progress, label) {
    const container = createDivElement("producao-progress");
    container.appendChild(createTextElement("span", label));
    if (progress.total) {
        const indicator = document.createElement("progress");
        indicator.max = 100;
        indicator.value = progress.percentual;
        indicator.setAttribute("aria-label", `Progresso da produção: ${progress.percentual}%`);
        container.appendChild(indicator);
    }
    return container;
}

export function createButtonElement(text, className = "btn-small") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = text;
    return button;
}

export function createProducaoCardElement() {
    const card = document.createElement("article");
    const header = createDivElement("admin-entity-card__header");
    const content = createDivElement("producao-card__content");
    const actions = createDivElement("admin-entity-card__actions");
    card.className = "admin-entity-card producao-card";
    card.append(header, content, actions);
    return { card, header, content, actions };
}
