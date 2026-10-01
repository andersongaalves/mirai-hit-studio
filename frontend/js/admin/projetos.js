import * as API from "../api.js";

import { authFetch } from "./auth.js";

import * as Notify from "../utils/notifications.js";

import { $, clear } from "../utils/dom.js";
import { closeAdminModal, openAdminModal } from "./admin_modal.js";

// ===========================
// STATE
// ===========================

let projetos = [];
let audioState = { beforeUrl: null, afterUrl: null, objectUrls: [] };
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

        destaque.textContent = [
            projeto.destaque ? "Hit" : "",
            projeto.show_mix_comparison_on_landing ? `A/B ${projeto.landing_order}` : "",
        ].filter(Boolean).join(" · ");

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

function resetAudioState() {
    audioState.objectUrls.forEach((url) => URL.revokeObjectURL(url));
    audioState = { beforeUrl: null, afterUrl: null, objectUrls: [] };
}

function setAudioPreview(slot, url) {
    const preview = $(`proj_audio_${slot}_preview`);
    const remove = $(`proj_audio_${slot}_remove`);
    audioState[`${slot}Url`] = url || null;
    preview.pause();
    preview.removeAttribute("src");
    if (url) {
        preview.src = url;
        preview.hidden = false;
        remove.hidden = false;
    } else {
        preview.hidden = true;
        remove.hidden = true;
    }
    preview.load();
    syncComparisonControls();
}

function selectedAudio(slot) {
    return $(`proj_audio_${slot}`).files?.[0] || null;
}

function hasCompleteComparison() {
    return Boolean(
        (audioState.beforeUrl || selectedAudio("before"))
        && (audioState.afterUrl || selectedAudio("after")),
    );
}

function syncComparisonControls() {
    const toggle = $("proj_mix_landing");
    const order = $("proj_mix_order");
    const help = $("proj_mix_help");
    const projectId = Number($("proj_id").value) || null;
    const project = projetos.find((item) => item.id === projectId);
    const limitReached = projetos.filter((item) => (
        item.show_mix_comparison_on_landing && item.id !== projectId
    )).length >= 4;
    const complete = hasCompleteComparison();

    toggle.disabled = !complete || (limitReached && !project?.show_mix_comparison_on_landing);
    if (toggle.disabled) toggle.checked = false;
    order.disabled = !toggle.checked;
    help.textContent = limitReached && !project?.show_mix_comparison_on_landing
        ? "O limite de 4 comparações destacadas foi atingido."
        : complete
            ? "Os dois áudios estão prontos para comparação."
            : "É necessário adicionar os áudios Antes e Depois para destacar este projeto.";
}

function bindAudioControls() {
    const toggle = $("proj_mix_landing");
    if (toggle.dataset.bound === "true") return;
    toggle.dataset.bound = "true";
    toggle.addEventListener("change", syncComparisonControls);
    for (const slot of ["before", "after"]) {
        $(`proj_audio_${slot}`).addEventListener("change", () => {
            const file = selectedAudio(slot);
            if (file) {
                const url = URL.createObjectURL(file);
                audioState.objectUrls.push(url);
                setAudioPreview(slot, url);
            } else {
                setAudioPreview(slot, audioState[`${slot}Url`]);
            }
        });
        $(`proj_audio_${slot}_remove`).addEventListener("click", () => removerAudio(slot));
    }
}

export function novoProjeto() {
    limparFormulario();

    bindAudioControls();

    openAdminModal("modal-projeto", { onRequestClose: fecharModal });
}

export function editarProjeto(id) {
    const projeto = projetos.find((item) => item.id === id);

    if (!projeto) return;

    bindAudioControls();
    resetAudioState();

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

    setAudioPreview("before", projeto.audio_before_url);
    setAudioPreview("after", projeto.audio_after_url);
    $("proj_mix_landing").checked = projeto.show_mix_comparison_on_landing;
    $("proj_mix_order").value = String(projeto.landing_order || 1);
    syncComparisonControls();

    openAdminModal("modal-projeto", { onRequestClose: fecharModal });
}

export function fecharModal() {
    resetAudioState();
    closeAdminModal("modal-projeto");
}

// ===========================
// SAVE
// ===========================

function projetoPayload(showComparison, order) {
    return {
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

        show_mix_comparison_on_landing: showComparison,

        landing_order: showComparison ? order : null,
    };
}

async function responseError(response, fallback) {
    const body = await response.json().catch(() => null);
    return new Error(body?.detail || fallback);
}

async function uploadAudio(projectId, slot, file) {
    if (!file) return null;
    const form = new FormData();
    form.append("audio", file);
    const response = await authFetch(`/projetos/${projectId}/audio/${slot}`, {
        method: "POST",
        body: form,
    });
    if (!response.ok) throw await responseError(response, `Erro ao enviar áudio ${slot}.`);
    return response.json();
}

export async function salvarProjeto() {
    const originalId = $("proj_id").value;
    const beforeFile = selectedAudio("before");
    const afterFile = selectedAudio("after");
    const wantsHighlight = $("proj_mix_landing").checked;
    const order = Number($("proj_mix_order").value) || 1;
    const hasUploads = Boolean(beforeFile || afterFile);

    try {
        let response = await authFetch(
            originalId ? `/projetos/${originalId}` : "/projetos",

            {
                method: originalId ? "PUT" : "POST",

                body: JSON.stringify(projetoPayload(wantsHighlight && !hasUploads, order)),
            },
        );

        if (!response.ok) {
            throw await responseError(response, "Erro ao salvar projeto.");
        }

        let project = await response.json();
        await uploadAudio(project.id, "before", beforeFile);
        await uploadAudio(project.id, "after", afterFile);

        if (hasUploads && wantsHighlight) {
            response = await authFetch(`/projetos/${project.id}`, {
                method: "PUT",
                body: JSON.stringify(projetoPayload(true, order)),
            });
            if (!response.ok) throw await responseError(response, "Erro ao destacar comparação.");
            project = await response.json();
        }

        Notify.success("Projeto salvo.");

        fecharModal();

        carregarPortfolio();
    } catch (error) {
        console.error(error);

        Notify.error(error.message);
    }
}

export async function removerAudio(slot) {
    const projectId = $("proj_id").value;
    if (!projectId) {
        $(`proj_audio_${slot}`).value = "";
        setAudioPreview(slot, null);
        return;
    }
    try {
        const response = await authFetch(`/projetos/${projectId}/audio/${slot}`, { method: "DELETE" });
        if (!response.ok) throw await responseError(response, "Erro ao remover áudio.");
        const project = await response.json();
        $(`proj_audio_${slot}`).value = "";
        $("proj_mix_landing").checked = project.show_mix_comparison_on_landing;
        $("proj_mix_order").value = String(project.landing_order || 1);
        setAudioPreview(slot, null);
        Notify.success("Áudio removido.");
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
    bindAudioControls();
    resetAudioState();
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
    $("proj_audio_before").value = "";
    $("proj_audio_after").value = "";
    $("proj_mix_landing").checked = false;
    $("proj_mix_order").value = "1";
    setAudioPreview("before", null);
    setAudioPreview("after", null);
    syncComparisonControls();
}
