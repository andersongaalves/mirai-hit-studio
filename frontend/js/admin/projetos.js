import * as API from "../api.js";

import { authFetch } from "./auth.js";

import * as Notify from "../utils/notifications.js";

import { $, clear } from "../utils/dom.js";
import { closeAdminModal, openAdminModal } from "./admin_modal.js";

// ===========================
// STATE
// ===========================

let projetos = [];
document.addEventListener("admin:logout", () => { projetos = []; });

// ===========================
// LOAD
// ===========================

export async function carregarPortfolio() {
    try {
        const response = await authFetch("/projetos/admin");
        if (!response.ok) throw new Error("Erro ao carregar projetos.");
        projetos = await response.json();

        renderizarProjetos();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao carregar projetos.");
    }
}

// ===========================
// UI
// ===========================

function renderizarProjetos() {
    const container = $("portfolio-list");

    if (!container) return;

    clear(container);

    projetos.forEach((projeto) => {
        const card = document.createElement("div");

        card.className = "admin-list-item";

        const info = document.createElement("div");

        const titulo = document.createElement("strong");

        titulo.textContent = projeto.titulo;

        const artista = document.createElement("p");

        artista.textContent = projeto.artista;

        const classificacao = document.createElement("small");

        classificacao.textContent = [projeto.vertical, projeto.case_type]
            .filter(Boolean)
            .join(" · ") || "Aguardando classificação pública";

        info.append(
            titulo,

            artista,

            classificacao,
        );

        const destaque = document.createElement("div");

        destaque.textContent = projeto.destaque ? "⭐" : "";

        const actions = document.createElement("div");

        const editar = document.createElement("button");

        editar.textContent = "Editar";

        editar.onclick = () => editarProjeto(projeto.id);

        const excluir = document.createElement("button");

        excluir.textContent = "Excluir";

        excluir.className = "btn-danger";

        excluir.onclick = () => deletarProjeto(projeto.id);

        actions.append(
            editar,

            excluir,
        );

        card.append(
            info,

            destaque,

            actions,
        );

        container.appendChild(card);
    });
}

// ===========================
// MODAL
// ===========================

export function novoProjeto() {
    limparFormulario();

    openAdminModal("modal-projeto", { onRequestClose: fecharModal });
}

export function editarProjeto(id) {
    const projeto = projetos.find((item) => item.id === id);

    if (!projeto) return;

    $("proj_id").value = projeto.id;

    $("proj_titulo").value = projeto.titulo;

    $("proj_artista").value = projeto.artista;

    $("proj_categoria").value = projeto.categoria;

    $("proj_vertical").value = projeto.vertical || "";

    $("proj_segmentos").value = Array.isArray(projeto.segmentos_json)
        ? projeto.segmentos_json.join(", ")
        : "";

    $("proj_case_type").value = projeto.case_type || "";

    $("proj_audio").value = projeto.link_audio;

    $("proj_capa").value = projeto.link_capa;

    $("proj_descricao").value = projeto.descricao;

    $("proj_destaque").checked = projeto.destaque;

    openAdminModal("modal-projeto", { onRequestClose: fecharModal });
}

export function fecharModal() {
    closeAdminModal("modal-projeto");
}

// ===========================
// SAVE
// ===========================

export async function salvarProjeto() {
    const id = $("proj_id").value;

    const payload = {
        titulo: $("proj_titulo").value,

        artista: $("proj_artista").value,

        categoria: $("proj_categoria").value,

        vertical: $("proj_vertical").value || null,

        segmentos_json: $("proj_segmentos").value
            .split(",")
            .map((segmento) => segmento.trim().toLowerCase())
            .filter(Boolean),

        case_type: $("proj_case_type").value || null,

        link_audio: $("proj_audio").value,

        link_capa: $("proj_capa").value,

        descricao: $("proj_descricao").value,

        destaque: $("proj_destaque").checked,
    };

    try {
        const response = await authFetch(
            id ? `/projetos/${id}` : "/projetos",

            {
                method: id ? "PUT" : "POST",

                body: JSON.stringify(payload),
            },
        );

        if (!response.ok) {
            throw new Error("Erro ao salvar projeto");
        }

        Notify.success("Projeto salvo.");

        fecharModal();

        carregarPortfolio();
    } catch (error) {
        console.error(error);

        Notify.error(error.message);
    }
}

// ===========================
// DELETE
// ===========================

export async function deletarProjeto(id) {
    if (!confirm("Deseja excluir este projeto?")) {
        return;
    }

    await authFetch(
        `/projetos/${id}`,

        {
            method: "DELETE",
        },
    );

    Notify.success("Projeto removido.");

    carregarPortfolio();
}

// ===========================
// FORM
// ===========================

function limparFormulario() {
    [
        "proj_id",

        "proj_titulo",

        "proj_artista",

        "proj_categoria",

        "proj_vertical",

        "proj_segmentos",

        "proj_case_type",

        "proj_audio",

        "proj_capa",

        "proj_descricao",
    ].forEach((id) => {
        $(id).value = "";
    });

    $("proj_destaque").checked = false;
}
