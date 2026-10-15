// Catalog rework: the service content is an intro, typed limits and short highlights.
import { builderState } from "./builder_state.js";
import { LIMIT_FIELDS, readStructure } from "../../modules/service_catalog.js";

const EMPTY_LIMITS = { faixas: null, duracao_min: null, revisoes: null, melodias: null, artistas: null };

export function resetBuilder() {
    builderState.intro = "";
    builderState.destaques = [];
    builderState.limites = { ...EMPTY_LIMITS };
}

/** Loads any stored structure; legacy sections are converted (limits + highlights). */
export function carregarBuilder(json) {
    resetBuilder();
    if (!json) return;
    const dados = readStructure(json);
    builderState.intro = dados.intro;
    builderState.destaques = [...dados.destaques];
    builderState.limites = { ...dados.limites };
}

export function atualizarIntro(valor) {
    builderState.intro = valor;
}

/** Empty or invalid input means "no limit". */
export function atualizarLimite(campo, valor) {
    const field = LIMIT_FIELDS.find(item => item.key === campo);
    if (!field) return;
    const number = valor === "" ? null : Number(valor);
    builderState.limites[campo] = Number.isInteger(number) && number >= field.min && number <= field.max ? number : null;
}

export function atualizarDestaques(texto) {
    builderState.destaques = String(texto || "")
        .split("\n")
        .map(item => item.trim().slice(0, 200))
        .filter(Boolean)
        .slice(0, 20);
}

export function gerarJSON() {
    return JSON.stringify({
        versao: 2,
        intro: builderState.intro,
        destaques: builderState.destaques,
        limites: builderState.limites,
    });
}
