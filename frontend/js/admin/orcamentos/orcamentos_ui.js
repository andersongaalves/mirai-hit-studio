import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";

import {
    createOrcamentoCardElement,
    createButtonElement,
    createTextElement,
    createSelectElement
} from "./orcamentos_dom.js";

import {
    visualizarOrcamento,
    deletarOrcamento,
    alterarStatus,
    alterarProdutor
} from "./orcamentos.js";

import {
    STATUS_OPTIONS
} from "./orcamentos_utils.js";

import { orcamentosState } from "./orcamentos_state.js";

export function renderizarOrcamentos(orcamentos) {

    const container = $("orcamentos-list");

    if (!container) return;

    container.innerHTML = "";

    if (orcamentos.length === 0) {
        container.innerHTML = `
            <div class="admin-empty">
                Nenhum orçamento encontrado.
            </div>
        `;
        return;
    }


    orcamentos.forEach(item => {
        container.appendChild(
            createOrcamentoCard(item)
        );
    });
}


function createOrcamentoCard(item) {

    const {
        card,
        info,
        actions

    } = createOrcamentoCardElement();

    const status = createSelectElement({

        value: item.status,

        className: "status-select",

        options: STATUS_OPTIONS

    });

    status.onchange = e => {

        alterarStatus(

            item.id,

            e.target.value

        );

    };

    const produtor = createSelectElement({

        value: item.produtor_id ?? "",

        className: "produtor-select",

        options: [

            {
                value: "",
                label: "👤 Sem produtor"
            },

            ...orcamentosState.produtores.map(
                user => ({

                    value: user.id,

                    label: `👤 ${user.username}`

                })
            )

        ]

    });

    produtor.onchange = e => {

        alterarProdutor(

            item.id,

            e.target.value
                ? Number(e.target.value)
                : null

        );

    };

    const nome = createTextElement(
        "strong",
        item.nome_cliente
    );


    const servico = createTextElement(
        "p",
        item.servico
    );


    const valor = createTextElement(
        "span",
        `R$ ${money(item.valor_total)}`
    );


    info.append(
        status,
        produtor,
        nome,
        servico,
        valor
    );


    const btnVer = createButtonElement({
        text: "Ver"
    });


    btnVer.onclick = () => {
        visualizarOrcamento(
            item.id
        );
    };


    const btnExcluir = createButtonElement({
        text: "Excluir",
        className: "btn-danger"
    });

    btnExcluir.onclick = () => {
        deletarOrcamento(
            item.id
        );
    };


    actions.append(
        btnVer,
        btnExcluir
    );

    return card;
}