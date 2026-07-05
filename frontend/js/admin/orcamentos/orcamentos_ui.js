import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";

import {
    createOrcamentoCardElement,
    createButtonElement,
    createTextElement,
    createSelectElement,
} from "./orcamentos_dom.js";

import { STATUS_OPTIONS } from "./orcamentos_utils.js";

const emptyHandlers = {
    onVisualizar: () => {},
    onDeletar: () => {},
    onAlterarStatus: () => {},
    onAlterarProdutor: () => {},
};

export function renderizarOrcamentos(
    orcamentos = [],
    { produtores = [], handlers = {} } = {},
) {
    const container = $("orcamentos-list");

    if (!container) return;

    container.innerHTML = "";

    if (!orcamentos.length) {
        container.innerHTML = `
            <div class="admin-empty">
                Nenhum orçamento encontrado.
            </div>
        `;
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
        createStatusSelect(item, handlers),
        createProdutorSelect(item, produtores, handlers),
        createTextElement("strong", item.nome_cliente),
        createTextElement("p", item.servico),
        createTextElement("span", money(item.valor_total)),
    );

    actions.append(...createActions(item, handlers));

    return card;
}

function createStatusSelect(item, handlers) {
    const select = createSelectElement({
        value: item.status,
        className: "status-select",
        options: STATUS_OPTIONS,
    });

    select.onchange = (e) => {
        handlers.onAlterarStatus(item.id, e.target.value);
    };

    return select;
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
    const btnVer = createButtonElement({
            text: "Ver",
            className: "btn-small"
        });

    btnVer.onclick = () => {
        handlers.onVisualizar(item.id);
    };

    const btnExcluir = createButtonElement({
        text: "Excluir",
        className: "btn-small btn-danger",
    });

    btnExcluir.onclick = () => {
        handlers.onDeletar(item.id);
    };

    return [btnVer, btnExcluir];
}
