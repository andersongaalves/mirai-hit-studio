import { builderState } from "./builder_state.js";
import { serviceStructure } from "../../utils/security.js";

/* ============================================================
 * Helpers privados
 * ========================================================== */

function gerarId() {
    return crypto.randomUUID();
}

function obterSecao(id) {
    return builderState.sections.find((secao) => secao.id === id);
}

function criarSecao(dados = {}) {
    return {
        id: dados.id ?? gerarId(),
        icon: dados.icon ?? "",
        title: dados.title ?? "",
        open: dados.open ?? true,
        items: [...(dados.items ?? [""])],
    };
}

/* ============================================================
 * Estado
 * ========================================================== */

export function resetBuilder() {
    builderState.intro = "";
    builderState.sections = [];
    builderState.benefits = [];
}

export function carregarBuilder(json) {
    resetBuilder();

    if (!json) return;

    let dados = json;

    if (typeof json === "string") {
        try {
            dados = JSON.parse(json);
        } catch {
            return;
        }
    }

    dados = serviceStructure(dados);
    if (!dados) return;
    builderState.intro = dados.intro ?? "";

    builderState.sections = (dados.sections ?? []).map(criarSecao);

    builderState.benefits = [...(dados.benefits ?? [])];
}

/* ============================================================
 * Intro
 * ========================================================== */

export function atualizarIntro(valor) {
    builderState.intro = valor;
}

/* ============================================================
 * Seções
 * ========================================================== */

export function adicionarSecao() {
    builderState.sections.push(criarSecao());
}

export function removerSecao(id) {
    builderState.sections = builderState.sections.filter(
        (secao) => secao.id !== id,
    );
}

export function atualizarSecao(id, campo, valor) {
    const secao = obterSecao(id);

    if (!secao) return;

    secao[campo] = valor;
}

export function alternarSecao(id) {
    const secao = obterSecao(id);

    if (!secao) return;

    secao.open = !secao.open;
}

/* ============================================================
 * Itens
 * ========================================================== */

export function adicionarItem(idSecao) {
    const secao = obterSecao(idSecao);

    if (!secao) return;

    secao.items.push("");
}

export function atualizarItem(idSecao, index, valor) {
    const secao = obterSecao(idSecao);

    if (!secao) return;

    secao.items[index] = valor;
}

export function removerItem(idSecao, index) {
    const secao = obterSecao(idSecao);

    if (!secao) return;

    secao.items.splice(index, 1);
}

/* ============================================================
 * Benefícios
 * ========================================================== */

export function adicionarBeneficio() {
    builderState.benefits.push("");
}

export function atualizarBeneficio(index, valor) {
    builderState.benefits[index] = valor;
}

export function removerBeneficio(index) {
    builderState.benefits.splice(index, 1);
}

/* ============================================================
 * Serialização
 * ========================================================== */

export function gerarObjeto() {
    return {
        intro: builderState.intro,

        sections: builderState.sections.map((secao) => ({
            icon: secao.icon,

            title: secao.title,

            items: secao.items.filter((item) => item.trim()),
        })),

        benefits: builderState.benefits.filter((item) => item.trim()),
    };
}

export function gerarJSON() {
    return JSON.stringify(gerarObjeto());
}

/* ============================================================
 * Utilidades
 * ========================================================== */

export function obterState() {
    return builderState;
}
