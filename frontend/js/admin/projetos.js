import * as API from "../api.js";
import { authFetch } from "./auth.js";

let projetos = [];

export async function carregarPortfolio() {

    projetos = await API.getAPI("projetos");

    const container = document.getElementById("portfolio-list");

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

    document.getElementById("proj_id").value = projeto.id;

    document.getElementById("proj_titulo").value = projeto.titulo;

    document.getElementById("proj_artista").value = projeto.artista;

    document.getElementById("proj_categoria").value = projeto.categoria;

    document.getElementById("proj_audio").value = projeto.link_audio;

    document.getElementById("proj_capa").value = projeto.link_capa;

    document.getElementById("proj_descricao").value = projeto.descricao;

    document.getElementById("proj_destaque").checked = projeto.destaque;

    document

        .getElementById("modal-projeto")

        .classList

        .remove("hidden");

}

export async function salvarProjeto() {

    const id = document.getElementById("proj_id").value;
    const payload = {

        titulo:
            document.getElementById("proj_titulo").value,

        artista:
            document.getElementById("proj_artista").value,

        categoria:
            document.getElementById("proj_categoria").value,

        link_audio:
            document.getElementById("proj_audio").value,

        link_capa:
            document.getElementById("proj_capa").value,

        descricao:
            document.getElementById("proj_descricao").value,

        destaque:
            document.getElementById("proj_destaque").checked

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
        alert("Erro ao salvar projeto.");
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

    document.getElementById("proj_id").value = "";
    document.getElementById("proj_titulo").value = "";
    document.getElementById("proj_artista").value = "";
    document.getElementById("proj_categoria").value = "";
    document.getElementById("proj_audio").value = "";
    document.getElementById("proj_capa").value = "";
    document.getElementById("proj_descricao").value = "";
    document.getElementById("proj_destaque").checked = false;

}