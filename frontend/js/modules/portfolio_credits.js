// Roadmap 3.0, 5.19: credits of portfolio projects, shared by the Admin editor and the site.

export const CREDIT_ROLES = Object.freeze([
    ["producao", "Produção"],
    ["mixagem", "Mixagem"],
    ["masterizacao", "Masterização"],
    ["composicao", "Composição"],
    ["gravacao", "Gravação"],
    ["beat", "Beat"],
    ["outra", "Outra função"],
]);

const ROLE_LABELS = Object.freeze(Object.fromEntries(CREDIT_ROLES));
export const MAX_CREDITS = 20;

export function creditRoleLabel(credit) {
    if (credit?.funcao === "outra") return String(credit.funcao_outra || "").trim() || "Colaboração";
    return ROLE_LABELS[credit?.funcao] || "Colaboração";
}

/** Public list: one <li> per credit, text only. */
export function creditsList(credits, className = "portfolio-card__credits") {
    const items = (Array.isArray(credits) ? credits : []).filter(credit => String(credit?.nome || "").trim());
    if (!items.length) return null;
    const list = document.createElement("ul");
    list.className = className;
    list.setAttribute("aria-label", "Créditos");
    items.forEach(credit => {
        const item = document.createElement("li");
        const role = document.createElement("span");
        role.className = `${className}-role`;
        role.textContent = creditRoleLabel(credit);
        const name = document.createElement("span");
        name.className = `${className}-name`;
        name.textContent = String(credit.nome).trim();
        item.append(role, name);
        list.append(item);
    });
    return list;
}

/** Comparable, API-shaped copy of a credit list. */
export function normalizeCredits(credits) {
    return (Array.isArray(credits) ? credits : []).map(credit => ({
        funcao: credit.funcao,
        funcao_outra: credit.funcao === "outra" ? (credit.funcao_outra || "").trim() || null : null,
        nome: String(credit.nome || "").trim(),
        usuario_id: Number.isInteger(credit.usuario_id) ? credit.usuario_id : null,
    }));
}
