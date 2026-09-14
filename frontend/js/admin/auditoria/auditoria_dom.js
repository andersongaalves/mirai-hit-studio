export function element(tag, text = "", className = "") {
    const node = document.createElement(tag);
    node.textContent = text ?? "";
    node.className = className;
    return node;
}


export function badge(text, variant) {
    return element("span", text, `badge badge-${variant}`);
}
