export function createDivElement(className = "") {
    const div = document.createElement("div");

    if (className) {
        div.className = className;
    }

    return div;
}

export function createTextElement(tag = "span", text = "", className = "") {
    const element = document.createElement(tag);

    element.textContent = text ?? "";

    if (className) {
        element.className = className;
    }

    return element;
}

export function createButtonElement({
    text = "",
    className = "btn-small",
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

export function createServicoCardElement() {
    const card = createDivElement("admin-list-item");
    const info = createDivElement("servico-info");
    const actions = createDivElement("servico-actions");

    card.append(info, actions);

    return {
        card,
        info,
        actions,
    };
}
