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

export function createSelectElement({
    value,
    options,
    className = "",
    ariaLabel = "",
}) {
    const select = document.createElement("select");
    select.className = className;
    if (ariaLabel) select.setAttribute("aria-label", ariaLabel);

    const known = options.some((item) => item.value === value);
    const normalizedOptions = known || !value
        ? options
        : [{ value, label: `Status desconhecido: ${value}` }, ...options];

    normalizedOptions.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.value;
        option.textContent = item.label;
        option.selected = item.value === value;
        select.appendChild(option);
    });
    return select;
}

export function createButtonElement(text, className = "btn-small") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = text;
    return button;
}

export function createProducaoCardElement() {
    const card = createDivElement("admin-list-item producao-card");
    const info = createDivElement("producao-info");
    const actions = createDivElement("producao-actions");
    card.append(info, actions);
    return { card, info, actions };
}
