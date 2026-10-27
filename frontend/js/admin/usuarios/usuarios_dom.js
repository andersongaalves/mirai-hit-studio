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


export const ESPECIALIDADES = { beatmaker: "Beatmaker", mixagem: "Engenheiro de mixagem", masterizacao: "Engenheiro de masterização" };


// Producer specialties, plus a warning when a beatmaker still lacks the CPF for contracts.
export function specialtyBadges(usuario) {
    const list = usuario.role === "produtor" ? (usuario.especialidades || []) : [];
    const badges = list.map((item) => textElement("span", ESPECIALIDADES[item] || item, "badge badge-neutral"));
    if (list.includes("beatmaker") && !usuario.cpf_cadastrado) badges.push(textElement("span", "CPF pendente", "badge badge-warning"));
    return badges;
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
