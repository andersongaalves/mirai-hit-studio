import {
    createButtonElement,
    createBadgeElement,
    createDivElement,
    createProgressElement,
    createProducaoCardElement,
    createTableCellElement,
    createTableElement,
    createTextElement,
} from "./producoes_dom.js";
import {
    calcularProgresso,
    classificarPrazo,
    formatarPrazo,
    obterPrazoVariant,
    obterStatusLabel,
    obterStatusVariant,
} from "./producoes_utils.js";
import { renderAdminState } from "../ui.js";

const TABLE_HEADERS = [
    { label: "Cliente e serviço" },
    { label: "Responsável" },
    { label: "Status" },
    { label: "Progresso" },
    { label: "Prazo" },
    { label: "Ações", className: "admin-table__cell--actions" },
];

function criarViewModel(item) {
    const progress = calcularProgresso(item.etapas);
    const prazo = classificarPrazo(item.prazo_entrega, item.status);
    return {
        item,
        cliente: item.cliente || "Cliente não informado",
        servico: item.servico || item.titulo || "Serviço não informado",
        responsavel: item.produtor_nome
            || (item.produtor_id ? `Usuário #${item.produtor_id}` : "Não definido"),
        status: obterStatusLabel(item.status),
        statusVariant: obterStatusVariant(item.status),
        progress,
        progresso: progress.total
            ? `${progress.concluidas}/${progress.total} etapas (${progress.percentual}%)`
            : "Etapas não definidas",
        prazo,
        prazoLabel: formatarPrazo(item.prazo_entrega, item.status),
        prazoVariant: obterPrazoVariant(prazo.tipo),
    };
}

function criarBotaoDetalhes(viewModel, handlers) {
    const button = createButtonElement("Ver detalhes");
    button.setAttribute("aria-label", `Ver detalhes da produção de ${viewModel.cliente}`);
    button.onclick = () => handlers.onVisualizar?.(viewModel.item.id);
    return button;
}

function criarTabela(viewModels, handlers) {
    const { wrapper, body } = createTableElement(TABLE_HEADERS);
    viewModels.forEach((viewModel) => {
        const row = document.createElement("tr");
        const principal = createTableCellElement("producao-primary");
        const responsavel = createTableCellElement();
        const status = createTableCellElement();
        const progresso = createTableCellElement();
        const prazo = createTableCellElement();
        const actions = createTableCellElement("admin-table__cell--actions");

        principal.append(
            createTextElement("strong", viewModel.cliente),
            createTextElement("span", viewModel.servico, "producao-secondary"),
            createTextElement("span", `Produção #${viewModel.item.id}`, "producao-secondary"),
        );
        responsavel.textContent = viewModel.responsavel;
        status.appendChild(createBadgeElement(viewModel.status, viewModel.statusVariant));
        progresso.appendChild(createProgressElement(viewModel.progress, viewModel.progresso));
        prazo.appendChild(createBadgeElement(
            viewModel.prazoLabel,
            viewModel.prazoVariant,
            "producao-prazo",
        ));
        actions.appendChild(criarBotaoDetalhes(viewModel, handlers));
        row.dataset.status = viewModel.item.status || "";
        row.dataset.prazo = viewModel.prazo.tipo;
        row.append(principal, responsavel, status, progresso, prazo, actions);
        body.appendChild(row);
    });
    return wrapper;
}

function criarCard(viewModel, handlers) {
    const { card, header, content, actions } = createProducaoCardElement();
    const title = createDivElement("admin-entity-card__title");
    const metadata = createDivElement("admin-entity-card__meta");

    title.append(
        createTextElement("strong", viewModel.cliente),
        createBadgeElement(`Produção #${viewModel.item.id}`, "neutral"),
    );
    header.append(
        title,
        createBadgeElement(viewModel.status, viewModel.statusVariant),
    );
    metadata.append(
        createTextElement("span", `Serviço: ${viewModel.servico}`),
        createTextElement("span", `Responsável: ${viewModel.responsavel}`),
    );
    content.append(
        metadata,
        createBadgeElement(viewModel.prazoLabel, viewModel.prazoVariant, "producao-prazo"),
        createProgressElement(viewModel.progress, viewModel.progresso),
    );
    actions.appendChild(criarBotaoDetalhes(viewModel, handlers));
    card.dataset.status = viewModel.item.status || "";
    card.dataset.prazo = viewModel.prazo.tipo;
    card.setAttribute("aria-label", `${viewModel.cliente}. ${viewModel.status}`);
    return card;
}

function criarCards(viewModels, handlers) {
    const container = createDivElement("producoes-mobile-view");
    viewModels.forEach((viewModel) => {
        container.appendChild(criarCard(viewModel, handlers));
    });
    return container;
}

export function renderizarLoading() {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    renderAdminState(container, "loading", "Carregando produções...");
}

export function renderizarErro(message) {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    renderAdminState(
        container,
        "error",
        message || "Não foi possível carregar as produções.",
    );
}

export function renderizarProducoes(producoes, handlers = {}, options = {}) {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    container.replaceChildren();

    if (!producoes.length) {
        renderAdminState(
            container,
            "empty",
            options.filtrosAtivos
                ? "Nenhuma produção corresponde aos filtros."
                : "Nenhuma produção encontrada.",
        );
        return;
    }

    const viewModels = producoes.map(criarViewModel);
    container.append(
        criarTabela(viewModels, handlers),
        criarCards(viewModels, handlers),
    );
}

export function renderizarResumo(total, visiveis, filtrosAtivos) {
    const summary = document.getElementById("producoes-summary");
    if (!summary) return;
    if (!Number.isFinite(total)) {
        summary.textContent = "";
        return;
    }
    const noun = total === 1 ? "produção" : "produções";
    summary.textContent = filtrosAtivos
        ? `${visiveis} de ${total} ${noun}`
        : `${total} ${noun}`;
}
