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
    $("proj_audio_before").value = "";
    $("proj_audio_after").value = "";

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
        titulo: $("proj_titulo").value.trim(),

        artista: $("proj_artista").value.trim(),

        categoria: $("proj_categoria").value.trim(),

        vertical: $("proj_vertical").value || null,

        segmentos_json: $("proj_segmentos").value
            .split(",")
            .map((segmento) => segmento.trim().toLowerCase())
            .filter(Boolean),

        case_type: $("proj_case_type").value || null,

        link_audio: $("proj_audio").value.trim(),

        link_capa: $("proj_capa").value.trim(),

        descricao: $("proj_descricao").value,

        destaque: $("proj_destaque").checked,

        show_mix_comparison_on_landing: showComparison,

        landing_order: showComparison ? order : null,
    };
}

function projetoChanges(payload, project) {
    const original = {
        titulo: project.titulo,
        artista: project.artista,
        categoria: project.categoria,
        vertical: project.vertical || null,
        segmentos_json: Array.isArray(project.segmentos_json) ? project.segmentos_json : [],
        case_type: project.case_type || null,
        link_audio: project.link_audio,
        link_capa: project.link_capa,
        descricao: project.descricao,
        destaque: Boolean(project.destaque),
        show_mix_comparison_on_landing: Boolean(project.show_mix_comparison_on_landing),
        landing_order: project.show_mix_comparison_on_landing
            ? project.landing_order || 1
            : null,
    };

    return Object.fromEntries(Object.entries(payload).filter(([field, value]) => (
        JSON.stringify(value) !== JSON.stringify(original[field])
    )));
}

const PROJECT_FIELD_LABELS = {
    titulo: "Título",
    artista: "Artista",
    categoria: "Categoria",
    vertical: "Vertical",
    segmentos_json: "Segmentos",
    case_type: "Tipo do projeto",
    link_audio: "Link do áudio",
    link_capa: "Link da capa",
    descricao: "Descrição",
    destaque: "Destaque",
    show_mix_comparison_on_landing: "Comparação A/B",
    landing_order: "Ordem da comparação A/B",
};

function validationErrorMessage(error) {
    const type = String(error?.type || "");
    const message = String(error?.msg || "");
    if (type === "missing") return "campo obrigatório.";
    if (type === "string_too_short") return "texto abaixo do tamanho mínimo.";
    if (type === "string_too_long") return "texto acima do tamanho máximo.";
    if (type === "literal_error") return "selecione uma opção válida.";
    if (type === "less_than_equal" || type === "greater_than_equal") {
        return "valor fora do intervalo permitido.";
    }
    if (message.includes("duplicate_segment")) return "remova segmentos duplicados.";
    if (message.includes("invalid_segment")) {
        return "use slugs em minúsculas, com letras, números ou sublinhado.";
    }
    if (message.includes("invalid_url") || message.includes("url")) {
        return "informe uma URL HTTP ou HTTPS válida.";
    }
    return "valor inválido.";
}

function responseDetail(detail, fallback) {
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (!Array.isArray(detail)) return fallback;

    const messages = detail.map((error) => {
        const location = Array.isArray(error?.loc)
            ? error.loc.filter((part) => part !== "body")
            : [];
        const field = location.find((part) => typeof part === "string");
        const label = PROJECT_FIELD_LABELS[field] || "Formulário";
        return `${label}: ${validationErrorMessage(error)}`;
    });
    const unique = [...new Set(messages)];
    return unique.length ? unique.join(" ") : fallback;
}

async function responseError(response, fallback) {
    const body = await response.json().catch(() => null);
    return new Error(responseDetail(body?.detail, fallback));
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
    const originalProject = originalId
        ? projetos.find((item) => item.id === Number(originalId))
        : null;
    const beforeFile = selectedAudio("before");
    const afterFile = selectedAudio("after");
    const wantsHighlight = $("proj_mix_landing").checked;
    const order = Number($("proj_mix_order").value) || 1;
    const hasUploads = Boolean(beforeFile || afterFile);

    try {
        if (originalId && !originalProject) {
            throw new Error("O projeto não está mais disponível. Atualize a lista e tente novamente.");
        }

        const requestedPayload = projetoPayload(wantsHighlight, order);
        const initialPayload = originalProject
            ? projetoChanges(requestedPayload, originalProject)
            : { ...requestedPayload };
        if (hasUploads && wantsHighlight) {
            initialPayload.show_mix_comparison_on_landing = false;
            initialPayload.landing_order = null;
        }

        let project = originalProject;
        let response;
        if (!originalId || Object.keys(initialPayload).length) {
            response = await authFetch(
                originalId ? `/projetos/${originalId}` : "/projetos",
                {
                    method: originalId ? "PUT" : "POST",
                    body: JSON.stringify(initialPayload),
                },
            );
            if (!response.ok) {
                throw await responseError(response, "Erro ao salvar projeto.");
            }
            project = await response.json();
        }

        await uploadAudio(project.id, "before", beforeFile);
        await uploadAudio(project.id, "after", afterFile);

        if (hasUploads && wantsHighlight) {
            response = await authFetch(`/projetos/${project.id}`, {
                method: "PUT",
                body: JSON.stringify({
                    show_mix_comparison_on_landing: true,
                    landing_order: order,
                }),
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
