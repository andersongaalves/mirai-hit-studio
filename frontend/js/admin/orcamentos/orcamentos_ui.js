import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";
import { renderAdminState } from "../ui.js";

import {
    createOrcamentoCardElement,
    createButtonElement,
    createTextElement,
    createSelectElement,
} from "./orcamentos_dom.js";

import { formatStatus } from "./orcamentos_utils.js";

const emptyHandlers = {
    onVisualizar: () => {},
    onDeletar: () => {},
    onAlterarProdutor: () => {},

    onAnalisar: () => {},
    onGerarProposta: () => {},
    onAprovar: () => {},
    onArquivar: () => {},
};

const STATUS_VARIANTS = {
    novo: "warning",
    em_analise: "info",
    proposta_enviada: "info",
    aprovado: "success",
    recusado: "danger",
    arquivado: "neutral",
};

export function renderizarOrcamentos(
    orcamentos = [],
    { produtores = [], handlers = {} } = {},
) {
    const container = $("orcamentos-list");

    if (!container) return;

    container.replaceChildren();

    if (!orcamentos.length) {
        renderAdminState(container, "empty", "Nenhum orçamento encontrado.");
        return;
    }

    const activeHandlers = {
        ...emptyHandlers,
        ...handlers,
    };

    orcamentos.forEach((item) => {
        container.appendChild(
            createOrcamentoCard(item, produtores, activeHandlers),
        );
    });
}

function createOrcamentoCard(item, produtores, handlers) {
    const { card, info, actions } = createOrcamentoCardElement();

    info.append(
        createProdutorSelect(item, produtores, handlers),

        createTextElement(
            "strong",
            item.nome_cliente,
        ),

        createTextElement(
            "span",
            formatStatus(item.status),
            `orcamento-status badge badge-${STATUS_VARIANTS[item.status] || "neutral"}`,
        ),

        createTextElement(
            "p",
            item.servico,
        ),

        createTextElement(
            "span",
            money(item.valor_total),
        ),
    );

    actions.append(...createActions(item, handlers));

    return card;
}

function createProdutorSelect(item, produtores, handlers) {
    const options = [
        {
            value: "",
            label: "👤 Sem produtor",
        },
        ...produtores.map((user) => ({
            value: user.id,
            label: `👤 ${user.username}`,
        })),
    ];

    const select = createSelectElement({
        value: item.produtor_id ?? "",
        className: "produtor-select",
        options,
    });

    select.onchange = (e) => {
        handlers.onAlterarProdutor(
            item.id,
            e.target.value ? Number(e.target.value) : null,
        );
    };

    return select;
}

function createActions(item, handlers) {
    const actions = [];

    const btnVer = createButtonElement({
        text: "Ver",
        className: "btn-small",
    });

    btnVer.onclick = () => handlers.onVisualizar(item.id);

    actions.push(btnVer);

    switch (item.status) {
        case "novo": {
            const btnAnalisar = createButtonElement({
                text: "Analisar",
                className: "btn-small",
            });

            btnAnalisar.onclick = () =>
                handlers.onAnalisar(item.id);

            actions.push(btnAnalisar);

            break;
        }

        case "em_analise": {
            const btnProposta = createButtonElement({
                text: "Abrir proposta",
                className: "btn-small",
            });

            btnProposta.onclick = () =>
                handlers.onGerarProposta(item.id);

            actions.push(btnProposta);

            break;
        }

        case "proposta_enviada": {
            const btnAprovar = createButtonElement({
                text: "Aprovar",
                className: "btn-small btn-success",
            });

            btnAprovar.onclick = () =>
                handlers.onAprovar(item.id);

            actions.push(btnAprovar);

            break;
        }

        default:
            break;
    }

    if (item.status !== "arquivado") {
        const btnArquivar = createButtonElement({
            text: "Arquivar",
            className: "btn-small",
        });

        btnArquivar.onclick = () =>
            handlers.onArquivar(item.id);

        actions.push(btnArquivar);
    }

    const btnExcluir = createButtonElement({
        text: "Excluir",
        className: "btn-small btn-danger",
    });

    btnExcluir.onclick = () =>
        handlers.onDeletar(item.id);

    actions.push(btnExcluir);

    return actions;
}
