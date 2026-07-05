import {
    createProducaoCardElement,
    createTextElement,
    createSelectElement,
} from "./producoes_dom.js";

import { STATUS_PRODUCAO, calcularPrazo } from "./producoes_utils.js";

import { alterarStatus, visualizarProducao } from "./producoes.js";

export function renderizarProducoes(producoes) {
    const container = document.getElementById("producoes-list");

    if (!container) return;

    container.innerHTML = "";

    if (producoes.length === 0) {
        container.innerHTML = `
            <div class="admin-empty">
                Nenhuma produção encontrada.
            </div>
        `;

        return;
    }

    producoes.forEach((item) => {
        container.appendChild(criarCardProducao(item));
    });
}

function criarCardProducao(item) {
    const { card, info, actions } = createProducaoCardElement();

    const status = createSelectElement({
        value: item.status,

        className: "status-select",

        options: STATUS_PRODUCAO,
    });

    status.onchange = (e) => {
        alterarStatus(
            item.id,

            e.target.value,
        );
    };

    const titulo = createTextElement(
        "strong",

        item.titulo,
    );

    const cliente = createTextElement(
        "p",

        `Cliente: ${item.cliente}`,
    );

    const servico = createTextElement(
        "span",

        item.servico,
    );

    const prazo = createTextElement(
        "p",

        calcularPrazo(item.prazo_entrega),

        "producao-prazo",
    );

    info.append(
        status,

        titulo,

        cliente,

        servico,

        prazo,
    );

    const btnVer = document.createElement("button");

    btnVer.textContent = "Ver";

    btnVer.onclick = () => {
        visualizarProducao(item.id);
    };

    actions.append(btnVer);

    return card;
}
