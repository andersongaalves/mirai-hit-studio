export function createDivElement(className = "") {
    const div = document.createElement("div");

    if (className) {
        div.className = className;
    }

    return div;
}

export function createButtonElement({
    text = "",
    className = "",
    type = "button",
} = {}) {
    const button = document.createElement("button");

    button.type = type;
    button.textContent = text ?? "";

    if (className) {
        button.className = className;
    }

    return button;
}

export function createOrcamentoCardElement() {
    const card = createDivElement("admin-list-item");
    const info = createDivElement("orcamento-info");
    const actions = createDivElement("orcamento-actions");

    card.append(info, actions);

    return {
        card,
        info,
        actions,
    };
}

export function createTextElement(tag = "span", text = "", className = "") {
    const element = document.createElement(tag);

    element.textContent = text ?? "";

    if (className) {
        element.className = className;
    }

    return element;
}

export function createSelectElement({
    options = [],
    value = "",
    className = "",
} = {}) {
    const select = document.createElement("select");

    if (className) {
        select.className = className;
    }

    options.forEach((item) => {
        const option = document.createElement("option");

        option.value = item.value ?? "";
        option.textContent = item.label ?? "";

        select.appendChild(option);
    });

    select.value = value ?? "";

    return select;
}
