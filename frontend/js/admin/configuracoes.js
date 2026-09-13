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
