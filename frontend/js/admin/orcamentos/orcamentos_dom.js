export function createDivElement(className = "") {

    const div = document.createElement("div");

    div.className = className;

    return div;

}

export function createButtonElement({

    text = "",

    className = "",

    type = "button"

}) {

    const button = document.createElement("button");

    button.type = type;

    button.className = className;

    button.textContent = text;

    return button;

}

export function createOrcamentoCardElement() {

    const card = createDivElement(
        "admin-list-item"
    );

    const info = createDivElement(
        "orcamento-info"
    );

    const actions = createDivElement(
        "orcamento-actions"
    );

    card.appendChild(info);

    card.appendChild(actions);

    return {

        card,

        info,

        actions

    };

}

export function createTextElement(
    tag,
    text = "",
    className = ""
) {

    const element =
        document.createElement(tag);

    element.textContent = text;

    element.className = className;

    return element;

}

export function createBadgeElement({

    text = "",

    status = ""

}) {

    const badge =
        document.createElement("span");

    badge.className =
        `status-badge status-${status}`;

    badge.textContent = text;

    return badge;

}

export function createSelectElement({

    options = [],

    value = "",

    className = ""

}) {

    const select =
        document.createElement("select");


    select.className =
        className;


    options.forEach(item => {

        const option =
            document.createElement("option");


        option.value =
            item.value;


        option.textContent =
            item.label;


        select.appendChild(option);

    });


    select.value =
        value;


    return select;

}