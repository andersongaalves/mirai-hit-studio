import * as API from "../api.js";

import { authFetch } from "./auth.js";

import * as Notify from "../utils/notifications.js";

import { $, clear } from "../utils/dom.js";
import { closeAdminModal, openAdminModal } from "./admin_modal.js";

// ===========================
// STATE
// ===========================

let projetos = [];
let segmentCatalog = [];
let audioState = { beforeUrl: null, afterUrl: null, objectUrls: [] };
let coverObjectUrl = null;
document.addEventListener("admin:logout", () => { projetos = []; segmentCatalog = []; });
document.addEventListener("portfolio-segments:changed", event => {
    segmentCatalog = Array.isArray(event.detail?.segments) ? event.detail.segments : [];
    const current = selectedSegmentIds();
    if ($("modal-projeto") && !$("modal-projeto").classList.contains("hidden")) {
        renderSegmentPicker(current);
    }
});

// ===========================
// LOAD
// ===========================

export async function carregarPortfolio() {
    try {
        const [response, segmentResponse] = await Promise.all([
            authFetch("/projetos/admin"),
            authFetch("/config/portfolio-segments"),
        ]);
        if (!response.ok || !segmentResponse.ok) throw new Error("Erro ao carregar projetos.");
        projetos = await response.json();
        segmentCatalog = (await segmentResponse.json()).segments || [];

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

function bindCoverControls() {
    const input = $("proj_capa_upload");
    if (input.dataset.bound === "true") return;
    input.dataset.bound = "true";
    input.addEventListener("change", () => {
        const file = selectedCover();
        if (!file) {
            setCoverPreview($("proj_capa").value.trim());
            return;
        }
        coverObjectUrl = URL.createObjectURL(file);
        const preview = $("proj_capa_preview");
        preview.src = coverObjectUrl;
        preview.hidden = false;
    });
    $("proj_capa_remove").addEventListener("click", removerCapa);
}

export function novoProjeto() {
    limparFormulario();

    bindAudioControls();
    bindCoverControls();

    openAdminModal("modal-projeto", { onRequestClose: fecharModal });
}

export function editarProjeto(id) {
    const projeto = projetos.find((item) => item.id === id);

    if (!projeto) return;

    bindAudioControls();
    bindCoverControls();
    resetAudioState();
    $("proj_audio_before").value = "";
    $("proj_audio_after").value = "";

    $("proj_id").value = projeto.id;

    $("proj_titulo").value = projeto.titulo;

    $("proj_artista").value = projeto.artista;

    $("proj_categoria").value = projeto.categoria;

    $("proj_vertical").value = projeto.vertical || "";

    renderSegmentPicker(Array.isArray(projeto.segmentos_json) ? projeto.segmentos_json : []);

    $("proj_case_type").value = projeto.case_type || "";

    $("proj_audio").value = projeto.link_audio;

    $("proj_capa").value = projeto.link_capa;
    $("proj_capa_upload").value = "";
    setCoverPreview(projeto.link_capa);

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
    setCoverPreview(null);
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

        segmentos_json: selectedSegmentIds(),

        case_type: $("proj_case_type").value || null,

        link_audio: $("proj_audio").value.trim(),

        link_capa: $("proj_capa").value.trim(),

        descricao: $("proj_descricao").value,

        destaque: $("proj_destaque").checked,

        show_mix_comparison_on_landing: showComparison,

        landing_order: showComparison ? order : null,
    };
}

function setCoverPreview(url) {
    const preview = $("proj_capa_preview");
    if (coverObjectUrl) {
        URL.revokeObjectURL(coverObjectUrl);
        coverObjectUrl = null;
    }
    preview.src = url || "";
    preview.hidden = !url;
    $("proj_capa_remove").hidden = !url || !$("proj_id").value;
}

function selectedCover() {
    return $("proj_capa_upload").files?.[0] || null;
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

async function uploadImage(projectId, file) {
    if (!file) return null;
    const form = new FormData();
    form.append("imagem", file);
    const response = await authFetch(`/projetos/${projectId}/imagem`, {
        method: "POST",
        body: form,
    });
    if (!response.ok) throw await responseError(response, "Erro ao enviar capa.");
    return response.json();
}

export async function salvarProjeto() {
    const originalId = $("proj_id").value;
    const originalProject = originalId
        ? projetos.find((item) => item.id === Number(originalId))
        : null;
    const beforeFile = selectedAudio("before");
    const afterFile = selectedAudio("after");
    const coverFile = selectedCover();
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

        project = await uploadImage(project.id, coverFile) || project;
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

export async function removerCapa() {
    const projectId = $("proj_id").value;
    if (!projectId) {
        $("proj_capa").value = "";
        $("proj_capa_upload").value = "";
        setCoverPreview(null);
        return;
    }
    try {
        const response = await authFetch(`/projetos/${projectId}/imagem`, { method: "DELETE" });
        if (!response.ok) throw await responseError(response, "Erro ao remover capa.");
        const project = await response.json();
        $("proj_capa").value = project.link_capa || "";
        $("proj_capa_upload").value = "";
        setCoverPreview(project.link_capa);
        Notify.success("Capa removida.");
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
    bindCoverControls();
    resetAudioState();
    [
        "proj_id",

        "proj_titulo",

        "proj_artista",

        "proj_categoria",

        "proj_vertical",

        "proj_case_type",

        "proj_audio",

        "proj_capa",

        "proj_descricao",
    ].forEach((id) => {
        $(id).value = "";
    });

    $("proj_segmentos_busca").value = "";
    renderSegmentPicker([]);

    $("proj_destaque").checked = false;
    $("proj_audio_before").value = "";
    $("proj_audio_after").value = "";
    $("proj_capa_upload").value = "";
    $("proj_mix_landing").checked = false;
    $("proj_mix_order").value = "1";
    setAudioPreview("before", null);
    setAudioPreview("after", null);
    setCoverPreview(null);
    syncComparisonControls();
}

function selectedSegmentIds() {
    return [...document.querySelectorAll("#proj_segmentos_opcoes input:checked")]
        .map(input => input.value);
}

function filterSegmentOptions() {
    const query = $("proj_segmentos_busca").value.trim().toLocaleLowerCase("pt-BR");
    document.querySelectorAll(".portfolio-segment-option").forEach(option => {
        option.hidden = Boolean(query) && !option.dataset.search.includes(query);
    });
}

function renderSegmentPicker(selected) {
    const container = $("proj_segmentos_opcoes");
    const status = $("proj_segmentos_status");
    if (!container || !status) return;
    const selectedSet = new Set(selected);
    const known = new Set(segmentCatalog.map(segment => segment.id));
    const options = [...segmentCatalog];
    selectedSet.forEach(segmentId => {
        if (!known.has(segmentId)) {
            options.push({
                id: segmentId,
                label: segmentId.replaceAll("_", " "),
                active: false,
                usage_count: 1,
            });
        }
    });
    container.replaceChildren();
    options.forEach(segment => {
        const option = document.createElement("label");
        option.className = "portfolio-segment-option";
        option.dataset.search = `${segment.label} ${segment.id}`.toLocaleLowerCase("pt-BR");
        if (!segment.active) option.classList.add("portfolio-segment-option--inactive");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = segment.id;
        checkbox.checked = selectedSet.has(segment.id);
        checkbox.disabled = !segment.active && !checkbox.checked;
        checkbox.addEventListener("change", () => {
            if (!segment.active && !checkbox.checked) checkbox.disabled = true;
            status.textContent = `${selectedSegmentIds().length} selecionado(s).`;
        });
        const text = document.createElement("span");
        text.textContent = segment.active ? segment.label : `${segment.label} (inativo)`;
        option.append(checkbox, text);
        container.append(option);
    });
    status.textContent = options.length
        ? `${selectedSet.size} selecionado(s).`
        : "Cadastre segmentos em Configurações para classificá-los.";
    filterSegmentOptions();
}

$("proj_segmentos_busca")?.addEventListener("input", filterSegmentOptions);
$("proj_segmentos_busca")?.addEventListener("keydown", event => {
    if (event.key !== "ArrowDown") return;
    const first = document.querySelector(".portfolio-segment-option:not([hidden]) input:not(:disabled)");
    if (first) {
        event.preventDefault();
        first.focus();
    }
});
