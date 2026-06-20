import * as API from "../api.js";
import { authFetch } from "./auth.js";

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

    const container = document.getElementById("lista-servicos");

    if (!container) return;

    container.innerHTML = "";


    listaServicos.forEach(servico => {

        container.innerHTML += `

            <div class="admin-list-item">

                <span>

                    <strong>${servico.nome}</strong>

                    | ${servico.categoria}

                    | R$ ${servico.valor_base.toFixed(2)}

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

    document
        .getElementById("editor-servico")
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

    document.getElementById("srv_id").value = servico.id;

    document.getElementById("srv_nome").value = servico.nome;

    document.getElementById("srv_subtitulo").value =
        servico.subtitulo ?? "";

    document.getElementById("srv_valor").value =
        servico.valor_base;

    document.getElementById("srv_categoria").value =
        servico.categoria;

    document.getElementById("srv_aplica_desconto").value =
        String(servico.aplica_desconto);

    document.getElementById("srv_descricao").value =
        servico.descricao_servico ?? "";

    parametros = servico.parametros
        ? servico.parametros.split(",")
        : [];

    renderizarParametros();

}

export function adicionarParametro() {

    const valor = document
        .getElementById("param_selector")
        .value;

    if (parametros.includes(valor)) {

        alert("Parâmetro já existe.");

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

    const container = document.getElementById(
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

    const id = document.getElementById("srv_id").value;

    const payload = {

        nome: document.getElementById("srv_nome").value,

        subtitulo: document.getElementById("srv_subtitulo").value,

        valor_base: Number(

            document.getElementById("srv_valor").value

        ),

        categoria: document.getElementById("srv_categoria").value,

        aplica_desconto:

            document.getElementById(

                "srv_aplica_desconto"

            ).value === "true",

        parametros: parametros.join(","),

        descricao_servico:

            document.getElementById(

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

        alert("Erro ao salvar serviço.");

        return;

    }

    document
        .getElementById("editor-servico")
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

    document.getElementById("srv_id").value = "";

    document.getElementById("srv_nome").value = "";

    document.getElementById("srv_subtitulo").value = "";

    document.getElementById("srv_valor").value = 0;

    document.getElementById("srv_descricao").value = "";

    parametros = [];

    renderizarParametros();

}

export function inicializarParametros() {

    const select = document.getElementById("param_selector");

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