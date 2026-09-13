import {
    createButtonElement,
    createDivElement,
    createProducaoCardElement,
    createSelectElement,
    createTextElement,
} from "./producoes_dom.js";
import {
    STATUS_PRODUCAO,
    calcularProgresso,
    classificarPrazo,
    formatarPrazo,
    obterStatusLabel,
} from "./producoes_utils.js";

export function renderizarLoading() {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    container.replaceChildren(
        createTextElement("div", "Carregando produções...", "admin-loading"),
    );
}

export function renderizarErro(message) {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    const box = createTextElement(
        "div",
        message || "Não foi possível carregar as produções.",
        "admin-error",
    );
    box.setAttribute("role", "alert");
    container.replaceChildren(box);
}

export function renderizarProducoes(producoes, handlers = {}) {
    const container = document.getElementById("producoes-list");
    if (!container) return;
    container.replaceChildren();

    if (!producoes.length) {
        container.appendChild(
            createTextElement("div", "Nenhuma produção encontrada.", "admin-empty"),
        );
        return;
    }

    producoes.forEach((item) => {
        container.appendChild(criarCardProducao(item, handlers));
    });
}

function criarCardProducao(item, handlers) {
    const { card, info, actions } = createProducaoCardElement();
    const status = createSelectElement({
        value: item.status,
        className: "status-select",
        options: STATUS_PRODUCAO,
        ariaLabel: `Alterar status de ${item.titulo || "produção"}`,
    });

    status.onchange = async () => {
        const anterior = item.status;
        status.disabled = true;
        const saved = await handlers.onAlterarStatus?.(item.id, status.value);
        if (!saved) status.value = anterior;
        status.disabled = false;
    };

    const tituloRow = createDivElement("producao-title-row");
    tituloRow.append(
        createTextElement("strong", item.titulo || `Produção #${item.id}`),
        createTextElement("span", `#${item.id}`, "badge"),
    );

    const metadata = createDivElement("producao-metadata");
    metadata.append(
        createTextElement("span", `Cliente: ${item.cliente || "Não informado"}`),
        createTextElement("span", `Serviço: ${item.servico || "Não informado"}`),
        createTextElement(
            "span",
            `Responsável: ${item.produtor_nome || (item.produtor_id ? `#${item.produtor_id}` : "Não definido")}`,
        ),
    );

    const progresso = calcularProgresso(item.etapas);
    const progressoText = progresso.total
        ? `${progresso.concluidas}/${progresso.total} etapas (${progresso.percentual}%)`
        : "Etapas ainda não definidas";
    const progressoElement = createTextElement(
        "span",
        progressoText,
        "producao-progress",
    );
    if (progresso.total) {
        progressoElement.setAttribute("role", "progressbar");
        progressoElement.setAttribute("aria-valuenow", String(progresso.percentual));
        progressoElement.setAttribute("aria-valuemin", "0");
        progressoElement.setAttribute("aria-valuemax", "100");
    }

    const prazoInfo = classificarPrazo(item.prazo_entrega, item.status);
    const prazo = createTextElement(
        "span",
        formatarPrazo(item.prazo_entrega, item.status),
        `badge producao-prazo prazo-${prazoInfo.tipo}`,
    );

    info.append(tituloRow, metadata, progressoElement, prazo);
    actions.append(status);

    const btnVer = createButtonElement("Detalhes");
    btnVer.onclick = () => handlers.onVisualizar?.(item.id);
    actions.append(btnVer);

    card.dataset.status = item.status || "";
    card.dataset.prazo = prazoInfo.tipo;
    card.setAttribute("aria-label", `${item.titulo}. ${obterStatusLabel(item.status)}`);
    return card;
}
