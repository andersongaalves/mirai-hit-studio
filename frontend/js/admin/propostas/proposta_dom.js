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
    type = "button"
} = {}) {
    const button = document.createElement("button");

    button.type = type;
    button.textContent = text;

    if (className) {
        button.className = className;
    }

    return button;
}
