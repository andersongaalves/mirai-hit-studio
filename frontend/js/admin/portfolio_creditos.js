// Roadmap 3.0, 5.19: ordered credit editor inside the portfolio project modal.
import { CREDIT_ROLES, MAX_CREDITS, normalizeCredits } from "../modules/portfolio_credits.js";

let rows = [];
let producers = [];

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function list() {
    return document.getElementById("proj_creditos");
}

function syncAddButton() {
    const add = document.getElementById("proj_credito_add");
    if (add) add.disabled = rows.length >= MAX_CREDITS;
}

function render() {
    const container = list();
    if (!container) return;
    container.replaceChildren();
    if (!rows.length) {
        container.append(element("li", "portfolio-credits__empty", "Nenhum crédito adicionado."));
    }
    rows.forEach((credit, index) => container.append(row(credit, index)));
    syncAddButton();
}

function row(credit, index) {
    const item = element("li", "portfolio-credits__item");
    const number = index + 1;

    const role = element("select");
    role.setAttribute("aria-label", `Função do crédito ${number}`);
    CREDIT_ROLES.forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        role.append(option);
    });
    role.value = credit.funcao;

    const other = element("input");
    other.type = "text";
    other.maxLength = 60;
    other.placeholder = "Qual função?";
    other.setAttribute("aria-label", `Outra função do crédito ${number}`);
    other.value = credit.funcao_outra || "";
    other.hidden = credit.funcao !== "outra";

    const person = element("select");
    person.setAttribute("aria-label", `Pessoa do crédito ${number}`);
    const external = element("option", "", "Colaborador externo");
    external.value = "";
    person.append(external);
    const ids = new Set(producers.map(producer => producer.id));
    if (Number.isInteger(credit.usuario_id) && !ids.has(credit.usuario_id)) {
        // Linked account no longer listed (inactive): keep the link visible until changed.
        const legacy = element("option", "", `Conta #${credit.usuario_id} (inativa)`);
        legacy.value = String(credit.usuario_id);
        person.append(legacy);
    }
    producers.forEach(producer => {
        const option = element("option", "", `Produtor: ${producer.username}`);
        option.value = String(producer.id);
        person.append(option);
    });
    person.value = Number.isInteger(credit.usuario_id) ? String(credit.usuario_id) : "";

    const name = element("input");
    name.type = "text";
    name.maxLength = 100;
    name.placeholder = "Nome exibido no site";
    name.setAttribute("aria-label", `Nome do crédito ${number}`);
    name.value = credit.nome || "";

    role.addEventListener("change", () => {
        credit.funcao = role.value;
        other.hidden = role.value !== "outra";
        if (other.hidden) credit.funcao_outra = null;
    });
    other.addEventListener("input", () => { credit.funcao_outra = other.value; });
    person.addEventListener("change", () => {
        credit.usuario_id = person.value ? Number(person.value) : null;
        const producer = producers.find(item => item.id === credit.usuario_id);
        if (producer && !name.value.trim()) {
            name.value = producer.username;
            credit.nome = producer.username;
        }
    });
    name.addEventListener("input", () => { credit.nome = name.value; });

    const actions = element("div", "portfolio-credits__actions");
    const up = element("button", "btn-small", "↑");
    up.type = "button";
    up.disabled = index === 0;
    up.setAttribute("aria-label", `Mover crédito ${number} para cima`);
    up.addEventListener("click", () => move(index, -1));
    const down = element("button", "btn-small", "↓");
    down.type = "button";
    down.disabled = index === rows.length - 1;
    down.setAttribute("aria-label", `Mover crédito ${number} para baixo`);
    down.addEventListener("click", () => move(index, 1));
    const remove = element("button", "btn-small btn-danger", "Remover");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remover crédito ${number}`);
    remove.addEventListener("click", () => {
        rows.splice(index, 1);
        render();
    });
    actions.append(up, down, remove);

    const roleCell = element("div", "portfolio-credits__role");
    roleCell.append(role, other);
    item.append(roleCell, person, name, actions);
    return item;
}

function move(index, offset) {
    const target = index + offset;
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    render();
}

export function setProducers(items) {
    producers = (Array.isArray(items) ? items : [])
        .filter(item => Number.isInteger(item?.id) && item.ativo !== false)
        .sort((a, b) => String(a.username).localeCompare(String(b.username), "pt-BR"));
}

export function setCredits(credits) {
    rows = normalizeCredits(credits).map(credit => ({ ...credit }));
    render();
}

export function addCredit() {
    if (rows.length >= MAX_CREDITS) return;
    rows.push({ funcao: "producao", funcao_outra: null, nome: "", usuario_id: null });
    render();
    const inputs = list()?.querySelectorAll("li.portfolio-credits__item select");
    inputs?.[inputs.length - 2]?.focus();
}

/** Returns the API payload or throws a readable validation error. */
export function readCredits() {
    const credits = normalizeCredits(rows);
    credits.forEach((credit, index) => {
        if (!credit.nome) throw new Error(`Informe o nome do crédito ${index + 1}.`);
        if (credit.funcao === "outra" && !credit.funcao_outra) {
            throw new Error(`Descreva a função do crédito ${index + 1}.`);
        }
    });
    return credits;
}

export function bindCreditControls() {
    const add = document.getElementById("proj_credito_add");
    if (add && add.dataset.bound !== "true") {
        add.dataset.bound = "true";
        add.addEventListener("click", addCredit);
    }
}
