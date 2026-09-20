export function element(tag, text = "", className = "") {
    const node = document.createElement(tag);
    node.textContent = text ?? "";
    node.className = className;
    return node;
}


export function badge(text, variant = "neutral") {
    return element("span", text, `badge badge-${variant}`);
}


export function button(text, className, onClick) {
    const node = element("button", text, className);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
}


export function definition(label, value) {
    const item = document.createElement("div");
    item.append(element("dt", label), element("dd", value));
    return item;
}
