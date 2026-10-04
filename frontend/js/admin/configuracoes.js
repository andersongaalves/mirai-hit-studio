import * as API from "../api.js";

import { authFetch } from "./auth.js";

import * as Notify from "../utils/notifications.js";

import { $ } from "../utils/dom.js";

// ===========================
// CAMPOS
// ===========================

const CONFIG_FIELDS = [
    "desconto",

    "val_extra_duracao",

    "val_extra_pessoa",

    "val_extra_canal_voz",

    "val_extra_canal_inst",

    "val_extra_melodia",

    "val_extra_revisao",

    "val_inst_hibrido",

    "val_inst_gravado",

    "val_prazo_urgente",

    "val_prazo_express",

    "val_lease_desconto",
];

const CONFIG_INPUT_IDS = { desconto: "cfg_desconto" };
const configInput = (campo) => $(CONFIG_INPUT_IDS[campo] || campo);
let segmentCatalog = { segments: [], revision: "" };
let segmentControlsBound = false;

// ===========================
// LOAD
// ===========================

export async function carregarConfiguracoes() {
    try {
        const response = await authFetch("/config");
        if (!response.ok) throw new Error("Erro ao carregar configurações.");
        const config = await response.json();

        preencherFormulario(config);
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao carregar configurações.");
    }
    await carregarSegmentosPortfolio();
}

async function responseMessage(response, fallback) {
    const body = await response.json().catch(() => null);
    if (typeof body?.detail === "string") return body.detail;
    return fallback;
}

function notifyCatalogChanged() {
    document.dispatchEvent(new CustomEvent("portfolio-segments:changed", {
        detail: { segments: segmentCatalog.segments },
    }));
}

function setSegmentCatalog(catalog) {
    segmentCatalog = catalog;
    renderSegmentCatalog();
    notifyCatalogChanged();
}

async function segmentMutation(endpoint, method, payload) {
    const response = await authFetch(endpoint, {
        method,
        body: JSON.stringify({ ...payload, expected_revision: segmentCatalog.revision }),
    });
    if (!response.ok) throw new Error(await responseMessage(response, "Erro ao atualizar segmentos."));
    setSegmentCatalog(await response.json());
}

function segmentButton(text, label, action, disabled = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.setAttribute("aria-label", label);
    button.disabled = disabled;
    button.addEventListener("click", action);
    return button;
}

function renderSegmentCatalog() {
    const container = $("portfolio-segments-list");
    const status = $("portfolio-segments-status");
    if (!container || !status) return;
    container.replaceChildren();
    status.textContent = segmentCatalog.segments.length
        ? `${segmentCatalog.segments.length} segmento(s) cadastrado(s).`
        : "Nenhum segmento cadastrado.";

    segmentCatalog.segments.forEach((segment, index) => {
        const row = document.createElement("div");
        row.className = "portfolio-segment-row";
        row.dataset.segmentId = segment.id;

        const label = document.createElement("input");
        label.type = "text";
        label.value = segment.label;
        label.maxLength = 80;
        label.setAttribute("aria-label", `Nome de ${segment.label}`);

        const meta = document.createElement("span");
        meta.className = "portfolio-segment-row__meta";
        meta.textContent = `${segment.id} · ${segment.usage_count} projeto(s)`;

        const active = document.createElement("label");
        active.className = "admin-checkbox";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = segment.active;
        checkbox.addEventListener("change", async () => {
            try {
                await segmentMutation(`/config/portfolio-segments/${segment.id}`, "PATCH", { active: checkbox.checked });
                Notify.success("Disponibilidade atualizada.");
            } catch (error) {
                checkbox.checked = segment.active;
                Notify.error(error.message);
            }
        });
        active.append(checkbox, document.createTextNode("Ativo"));

        const actions = document.createElement("div");
        actions.className = "portfolio-segment-row__actions";
        actions.append(
            segmentButton("↑", `Mover ${segment.label} para cima`, () => moverSegmento(index, -1), index === 0),
            segmentButton("↓", `Mover ${segment.label} para baixo`, () => moverSegmento(index, 1), index === segmentCatalog.segments.length - 1),
            segmentButton("Salvar", `Salvar nome de ${segment.label}`, async () => {
                try {
                    await segmentMutation(`/config/portfolio-segments/${segment.id}`, "PATCH", { label: label.value });
                    Notify.success("Nome atualizado.");
                } catch (error) {
                    label.value = segment.label;
                    Notify.error(error.message);
                }
            }),
            segmentButton("Remover", `Remover ${segment.label}`, async () => {
                try {
                    await segmentMutation(`/config/portfolio-segments/${segment.id}`, "DELETE", {});
                    Notify.success("Segmento removido.");
                } catch (error) {
                    Notify.error(error.message);
                }
            }, segment.usage_count > 0),
        );
        row.append(label, meta, active, actions);
        container.append(row);
    });
}

async function moverSegmento(index, offset) {
    const reordered = segmentCatalog.segments.map(segment => segment.id);
    const target = index + offset;
    if (target < 0 || target >= reordered.length) return;
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    try {
        await segmentMutation("/config/portfolio-segments/order", "PUT", { segment_ids: reordered });
    } catch (error) {
        Notify.error(error.message);
    }
}

function bindSegmentControls() {
    if (segmentControlsBound) return;
    segmentControlsBound = true;
    $("portfolio-segment-add")?.addEventListener("submit", async event => {
        event.preventDefault();
        const input = $("portfolio-segment-label");
        try {
            await segmentMutation("/config/portfolio-segments", "POST", { label: input.value });
            input.value = "";
            Notify.success("Segmento adicionado.");
        } catch (error) {
            Notify.error(error.message);
        }
    });
}

export async function carregarSegmentosPortfolio() {
    bindSegmentControls();
    try {
        const response = await authFetch("/config/portfolio-segments");
        if (!response.ok) throw new Error(await responseMessage(response, "Erro ao carregar segmentos."));
        setSegmentCatalog(await response.json());
    } catch (error) {
        console.error(error);
        Notify.error(error.message || "Erro ao carregar segmentos.");
    }
}

// ===========================
// FORM
// ===========================

function preencherFormulario(config) {
    CONFIG_FIELDS.forEach((campo) => {
        const input = configInput(campo);

        if (!input) {
            return;
        }

        input.value = config[campo] ?? "";
    });
}

// ===========================
// PAYLOAD
// ===========================

function gerarPayload() {
    const payload = {};

    CONFIG_FIELDS.forEach((campo) => {
        const input = configInput(campo);
        const valor = input?.value.trim();
        if (!valor || !Number.isFinite(Number(valor))) {
            throw new Error(`Informe um número válido para ${campo}.`);
        }
        payload[campo] = Number(valor);
    });

    return payload;
}

// ===========================
// SAVE
// ===========================

export async function salvarConfiguracoesExtras() {
    try {
        const response = await authFetch(
            "/config",

            {
                method: "PUT",

                body: JSON.stringify(gerarPayload()),
            },
        );

        if (!response.ok) {
            throw new Error("Erro ao salvar configurações");
        }

        Notify.success("Configurações atualizadas.");
    } catch (error) {
        console.error(error);

        Notify.error(error.message || "Erro ao salvar.");
    }
}
