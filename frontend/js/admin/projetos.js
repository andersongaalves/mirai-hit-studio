import * as API from "../api.js";
import { authFetch } from "./auth.js";
import * as Notify from "../utils/notifications.js";
import { $, $$, $$$ } from "../utils/dom.js";

let projetos = [];

export async function carregarPortfolio() {

    projetos = await API.getAPI("projetos");

    const container = $("portfolio-list");

    if (!container) return;

    container.innerHTML = "";

    projetos.forEach(projeto => {

        container.innerHTML += `

            <div class="admin-list-item">

                <div>

                    <strong>${projeto.titulo}</strong>

                    <br>

                    ${projeto.artista}

                </div>

                <div>

                    ${projeto.destaque ? "⭐" : ""}

                </div>

                <div>

                    <button onclick="editarProjeto(${projeto.id})">

                        Editar

                    </button>

                    <button class="btn-danger"

                        onclick="deletarProjeto(${projeto.id})">

                        Excluir

                    </button>

                </div>

            </div>

        `;

    });

}

export function novoProjeto() {

    limparFormulario();

    document

        .getElementById("modal-projeto")

        .classList

        .remove("hidden");

}

export function editarProjeto(id) {

    const projeto = projetos.find(

        item => item.id === id

    );

    if (!projeto) return;

    $("proj_id").value = projeto.id;

    $("proj_titulo").value = projeto.titulo;

    $("proj_artista").value = projeto.artista;

    $("proj_categoria").value = projeto.categoria;

    $("proj_audio").value = projeto.link_audio;

    $("proj_capa").value = projeto.link_capa;

    $("proj_descricao").value = projeto.descricao;

    $("proj_destaque").checked = projeto.destaque;

    document

        .getElementById("modal-projeto")

        .classList

        .remove("hidden");

}

export async function salvarProjeto() {

    const id = $("proj_id").value;
    const payload = {

        titulo:
            $("proj_titulo").value,

        artista:
            $("proj_artista").value,

        categoria:
            $("proj_categoria").value,

        link_audio:
            $("proj_audio").value,

        link_capa:
            $("proj_capa").value,

        descricao:
            $("proj_descricao").value,

        destaque:
            $("proj_destaque").checked

    };

    const response = await authFetch(

        id
            ? `/projetos/${id}`
            : "/projetos",
        {
            method: id ? "PUT" : "POST",
            body: JSON.stringify(payload)
        }

    );

    if (!response.ok) {
        Notify.error("Erro ao salvar projeto.");
        return;

    }

    fecharModal();
    carregarPortfolio();

}

export async function deletarProjeto(id) {

    if (!confirm("Deseja excluir este projeto?")) {
        return;

    }

    await authFetch(
        `/projetos/${id}`,
        {
            method: "DELETE"
        }

    );
    carregarPortfolio();
}

export function fecharModal() {
    document
        .getElementById("modal-projeto")
        .classList
        .add("hidden");

}

function limparFormulario() {

    $("proj_id").value = "";
    $("proj_titulo").value = "";
    $("proj_artista").value = "";
    $("proj_categoria").value = "";
    $("proj_audio").value = "";
    $("proj_capa").value = "";
    $("proj_descricao").value = "";
    $("proj_destaque").checked = false;

}