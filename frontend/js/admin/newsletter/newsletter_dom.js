import { badgeVariant, campaignLabel, formatDate } from "./newsletter_utils.js";


export function textElement(tag, text = "", className = "") {
    const element = document.createElement(tag);
    element.textContent = text ?? "";
    element.className = className;
    return element;
}


export function badge(text, variant) {
    return textElement("span", text, `badge badge-${variant}`);
}


export function subscriberBadge(item) {
    return badge(item.ativo ? "Ativo" : "Cancelado", badgeVariant(item.status));
}


export function campaignBadge(item) {
    return badge(campaignLabel(item.status), badgeVariant(item.status));
}


export function actionButton(label, onClick, className = "btn-small") {
    const button = textElement("button", label, className);
    button.type = "button";
    button.onclick = onClick;
    return button;
}


export { formatDate };
