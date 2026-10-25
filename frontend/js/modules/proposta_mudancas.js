// AUD6-S05-002: "what changed since the version sent before", for the Admin
// editor and the client portal. Text only; values come formatted by the caller.
const CAMPOS = Object.freeze({
    objeto: "Objeto",
    descricao: "Descrição",
    condicoes: "Condições",
    politica_pagamento: "Forma de pagamento",
});

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function linha(dados, money) {
    if (!dados) return "";
    const desconto = Number(dados.desconto) > 0 ? ` (desconto de ${money(dados.desconto)})` : "";
    return `${Number(dados.quantidade).toLocaleString("pt-BR")} × ${money(dados.valor_unitario)}${desconto}`;
}

export function renderMudancas(mudancas, { money, titulo } = {}) {
    if (!mudancas || typeof money !== "function") return null;
    const box = element("section", "proposta-mudancas");
    box.setAttribute("aria-labelledby", "proposta-mudancas-title");
    const heading = element("h2", "proposta-mudancas__title",
        titulo || `O que mudou desde a versão ${mudancas.versao_anterior}`);
    heading.id = "proposta-mudancas-title";
    box.append(heading);
    const list = element("ul", "proposta-mudancas__list");
    for (const item of mudancas.itens || []) {
        const text = item.tipo === "adicionado"
            ? `Novo item: ${item.descricao} — ${linha(item.depois, money)}`
            : item.tipo === "removido"
                ? `Item retirado: ${item.descricao} — era ${linha(item.antes, money)}`
                : `${item.descricao}: de ${linha(item.antes, money)} para ${linha(item.depois, money)}`;
        list.append(element("li", `proposta-mudancas__item proposta-mudancas__item--${item.tipo}`, text));
    }
    const total = mudancas.total || {};
    if (Number(total.antes) !== Number(total.depois)) {
        list.append(element("li", "proposta-mudancas__item", `Total: de ${money(total.antes)} para ${money(total.depois)}`));
    }
    const campos = (mudancas.campos_alterados || []).map(campo => CAMPOS[campo]).filter(Boolean);
    if (campos.length) list.append(element("li", "proposta-mudancas__item", `Texto revisado: ${campos.join(", ")}`));
    if (!list.children.length) return null;
    box.append(list);
    return box;
}
