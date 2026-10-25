import { renderAdminState } from "../ui.js";
import { actionButton, roleBadge, statusBadge, textElement } from "./usuarios_dom.js";
import { classificarConta } from "./usuarios.js";

function classificationButton(user) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn-small";
    button.textContent = user.is_test ? "TESTE · Tornar real" : "Classificar como teste";
    button.disabled = user.role === "admin" || user.is_admin;
    button.onclick = () => classificarConta(user, button);
    return button;
}


// AUD6-S09-002: producers open their page (productions and beats) from the list.
function overviewButton(user) {
    if (user.role !== "produtor") return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn-small";
    button.textContent = "Visão geral";
    button.setAttribute("aria-label", `Visão geral de ${user.nome_exibicao || user.username}`);
    button.onclick = async () => {
        const { openProdutorResumo } = await import("../produtor_resumo.js");
        await openProdutorResumo(user.id);
    };
    return button;
}


// Display name first (used in credits); the login username stays visible below it.
function nameCell(tag, usuario) {
    const cell = document.createElement(tag);
    if (usuario.nome_exibicao && usuario.nome_exibicao !== usuario.username) {
        cell.append(textElement("span", usuario.nome_exibicao, "usuario-display-name"));
        cell.append(textElement("small", `@${usuario.username}`, "usuario-login-name"));
    } else {
        cell.textContent = usuario.username;
    }
    return cell;
}


function tableView(usuarios, onOpen) {
    const wrapper = textElement("div", "", "admin-table-wrap usuarios-table-view");
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    const body = document.createElement("tbody");
    table.className = "admin-table usuarios-table";
    table.setAttribute("aria-label", "Lista de usuarios");
    ["Usuario", "Papel", "Status", "Acao"].forEach((label) => {
        const cell = textElement("th", label);
        cell.scope = "col";
        headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    usuarios.forEach((usuario) => {
        const row = document.createElement("tr");
        const role = document.createElement("td");
        const status = document.createElement("td");
        const action = textElement("td", "", "admin-table__cell--actions");
        role.appendChild(roleBadge(usuario));
        status.appendChild(statusBadge(usuario));
        action.appendChild(actionButton(usuario, onOpen));
        const tableOverview = overviewButton(usuario);
        if (tableOverview) action.appendChild(tableOverview);
        action.appendChild(classificationButton(usuario));
        row.append(nameCell("td", usuario), role, status, action);
        body.appendChild(row);
    });
    table.append(head, body);
    wrapper.appendChild(table);
    return wrapper;
}


function cardView(usuarios, onOpen) {
    const container = textElement("div", "", "usuarios-mobile-view");
    usuarios.forEach((usuario) => {
        const card = textElement("article", "", "admin-entity-card usuario-card");
        const header = textElement("div", "", "admin-entity-card__header");
        const meta = textElement("div", "", "admin-entity-card__meta");
        const actions = textElement("div", "", "admin-entity-card__actions");
        header.append(nameCell("strong", usuario), statusBadge(usuario));
        meta.appendChild(roleBadge(usuario));
        actions.appendChild(actionButton(usuario, onOpen));
        const cardOverview = overviewButton(usuario);
        if (cardOverview) actions.appendChild(cardOverview);
        actions.appendChild(classificationButton(usuario));
        if (usuario.is_test) meta.append(textElement("span", "TESTE", "badge badge-info"));
        card.append(header, meta, actions);
        container.appendChild(card);
    });
    return container;
}


export function renderUsuarios(usuarios, { onOpen, filtered = false } = {}) {
    const container = document.getElementById("usuarios-list");
    if (!container) return;
    if (!usuarios.length) {
        renderAdminState(container, "empty", filtered
            ? "Nenhum usuario corresponde aos filtros."
            : "Nenhum usuario cadastrado.");
        return;
    }
    container.replaceChildren(tableView(usuarios, onOpen), cardView(usuarios, onOpen));
}


export function renderLoading() {
    renderAdminState(document.getElementById("usuarios-list"), "loading", "Carregando usuarios...");
}


export function renderError() {
    renderAdminState(document.getElementById("usuarios-list"), "error", "Nao foi possivel carregar os usuarios.");
}


export function renderSummary(total, visible, filtered) {
    const summary = document.getElementById("usuarios-summary");
    if (!summary) return;
    summary.textContent = filtered ? `${visible} de ${total} usuarios` : `${total} usuario${total === 1 ? "" : "s"}`;
}
