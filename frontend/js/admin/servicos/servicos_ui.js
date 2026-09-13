import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";
import { renderAdminState } from "../ui.js";

import {
    createServicoCardElement,
    createButtonElement,
    createTextElement,
} from "./servicos_dom.js";

const emptyHandlers = {
    onEditar: () => {},
    onDeletar: () => {},
};

export function renderizarServicos(servicos = [], handlers = {}) {
    const container = $("lista-servicos");

    if (!container) return;

    container.replaceChildren();

    if (!servicos.length) {
        renderAdminState(container, "empty", "Nenhum serviço cadastrado.");
        return;
    }

    const activeHandlers = {
        ...emptyHandlers,
        ...handlers,
    };

    servicos.forEach((servico) => {
        container.appendChild(createServicoCard(servico, activeHandlers));
    });
}

function createServicoCard(servico, handlers) {
    const { card, info, actions } = createServicoCardElement();

    info.append(
        createTextElement("strong", servico.nome + " "),
        createTextElement(
            "span",
            `${servico.categoria} | ${money(servico.valor_base)}`,
        ),
    );

    actions.append(
        createEditButton(servico, handlers),
        createDeleteButton(servico, handlers),
    );

    return card;
}

function createEditButton(servico, handlers) {
    const button = createButtonElement({
        text: "Editar",
    });

    button.onclick = () => {
        handlers.onEditar(servico.id);
    };

    return button;
}

function createDeleteButton(servico, handlers) {
    const button = createButtonElement({
        text: "Excluir",
        className: "btn-small btn-danger",
    });

    button.onclick = () => {
        handlers.onDeletar(servico.id);
    };

    return button;
}
