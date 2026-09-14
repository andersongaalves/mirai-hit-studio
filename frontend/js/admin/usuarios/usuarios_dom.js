import { roleLabel } from "./usuarios_utils.js";


export function textElement(tag, text = "", className = "") {
    const element = document.createElement(tag);
    element.textContent = text ?? "";
    element.className = className;
    return element;
}


export function statusBadge(usuario) {
    return textElement(
        "span",
        usuario.ativo ? "Ativo" : "Inativo",
        `badge badge-${usuario.ativo ? "success" : "neutral"}`,
    );
}


export function roleBadge(usuario) {
    return textElement(
        "span",
        roleLabel(usuario.role),
        `badge badge-${usuario.role === "admin" ? "info" : "neutral"}`,
    );
}


export function actionButton(usuario, onOpen) {
    const button = textElement("button", "Abrir usuario", "btn-small");
    button.type = "button";
    button.setAttribute("aria-label", `Abrir usuario ${usuario.username}`);
    button.onclick = () => onOpen?.(usuario.id);
    return button;
}
