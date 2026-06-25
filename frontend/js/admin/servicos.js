import * as API from "../api.js";
import { authFetch } from "./auth.js";
import * as Notify from "../utils/notifications.js";
import { money } from "../utils/format.js";
import { $, $$, $$$ } from "../utils/dom.js";

const DICIONARIO_PARAMETROS = {
    duracao: "Duração",
    pessoas: "Artistas",
    canais_voz: "Canais Voz",
    inst_aberto: "Inst Aberto",
    melodias: "Melodias",
    instrumentacao: "Tipo de Instrumentação",
    exclusividade: "Exclusividade",
    revisoes: "Revisões",
    prazo: "Prazo",
    descricao: "Caixa de Descrição",
    guia: "Link para Guia"
};

let listaServicos = [];
let parametros = [];

export async function carregarServicos() {

    listaServicos = await API.getAPI("servicos");

    const container = $("lista-servicos");

    if (!container) return;

    container.innerHTML = "";


    listaServicos.forEach(servico => {

        container.innerHTML += `

            <div class="admin-list-item">

                <span>

                    <strong>${servico.nome}</strong>

                    | ${servico.categoria}

                    | ${money(servico.valor_base)}

                </span>

                <div>

                    <button class="btn-small"

                        onclick="abrirEditorServico(${servico.id})">

                        Editar

                    </button>

                    <button class="btn-small btn-danger"

                        onclick="deletarServico(${servico.id})">

                        X

                    </button>

                </div>

            </div>

        `;

    });

}

export function abrirEditorServico(id = null) {

    $("editor-servico")
        .classList
        .remove("hidden");

    if (!id) {

        limparFormulario();

        return;

    }

    const servico = listaServicos.find(

        item => item.id === id

    );

    if (!servico) return;

    $("srv_id").value = servico.id;

    $("srv_nome").value = servico.nome;

    $("srv_subtitulo").value =
        servico.subtitulo ?? "";

    $("srv_valor").value =
        servico.valor_base;

    $("srv_categoria").value =
        servico.categoria;

    $("srv_aplica_desconto").value =
        String(servico.aplica_desconto);

    $("srv_descricao").value =
        servico.descricao_servico ?? "";

    parametros = servico.parametros
        ? servico.parametros.split(",")
        : [];

    renderizarParametros();

}

export function adicionarParametro() {

    const valor = $("param_selector")
        .value;

    if (parametros.includes(valor)) {

        Notify.warning("Parâmetro já existe.");

        return;

    }

    parametros.push(valor);

    renderizarParametros();

}

export function removerParametro(index) {

    parametros.splice(index, 1);

    renderizarParametros();

}

export function moverParametro(index, direcao) {

    const destino = index + direcao;

    if (destino < 0 || destino >= parametros.length) {

        return;

    }

    [

        parametros[index],

        parametros[destino]

    ] = [

        parametros[destino],

        parametros[index]

    ];

    renderizarParametros();

}

function renderizarParametros() {

    const container = $(
    "param_list_render"
    );

    if (!container) return;

    container.innerHTML = "";

    parametros.forEach((item, index) => {

        container.innerHTML += `

            <div class="admin-param-item">

                <span>

                    ${index + 1}. ${DICIONARIO_PARAMETROS[item]}

                </span>

                <button onclick="moverParametro(${index},-1)">⬆</button>

                <button onclick="moverParametro(${index},1)">⬇</button>

                <button onclick="removerParametro(${index})">

                    Remover

                </button>

            </div>

        `;

    });

}

export async function salvarServico() {

    const id = $("srv_id").value;

    const payload = {

        nome: $("srv_nome").value,

        subtitulo: $("srv_subtitulo").value,

        valor_base: Number(

            $("srv_valor").value

        ),

        categoria: $("srv_categoria").value,

        aplica_desconto:

            $(

                "srv_aplica_desconto"

            ).value === "true",

        parametros: parametros.join(","),

        descricao_servico:

            $(

                "srv_descricao"

            ).value

    };

    const response = await authFetch(

        id

            ? `/servicos/${id}`

            : "/servicos",

        {

            method: id ? "PUT" : "POST",

            body: JSON.stringify(payload)

        }

    );

    if (!response.ok) {

        Notify.error("Erro ao salvar serviço.");

        return;

    }

    $("editor-servico")
        .classList
        .add("hidden");

    carregarServicos();

}

export async function deletarServico(id) {

    if (!confirm("Deseja realmente excluir?")) {

        return;

    }

    await authFetch(

        `/servicos/${id}`,

        {

            method: "DELETE"

        }

    );

    carregarServicos();

}

function limparFormulario() {

    $("srv_id").value = "";

    $("srv_nome").value = "";

    $("srv_subtitulo").value = "";

    $("srv_valor").value = 0;

    $("srv_descricao").value = "";

    parametros = [];

    renderizarParametros();

}

export function inicializarParametros() {

    const select = $("param_selector");

    if (!select) return;

    select.innerHTML = "";

    Object.entries(DICIONARIO_PARAMETROS).forEach(([key, label]) => {

        select.innerHTML += `
            <option value="${key}">
                ${label}
            </option>
        `;

    });

}