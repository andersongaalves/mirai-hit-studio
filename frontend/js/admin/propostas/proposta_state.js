import {
    calcularTotalItens
} from "./proposta_utils.js";
import { mapResponseToState, buildPropostaPayload } from "./proposta_mapper.js";

const links = {
    pagamento_completo_url: "integral",
    pagamento_parcial_1_url: "parcial_1",
    pagamento_parcial_2_url: "parcial_2"
};
const criarCamposLocais = () => ({
    prestador: "Mirai Hit Studio", entrada: 0, prazo: "", validade: "",
    pix: "", mercado_pago: "", observacoes: ""
});

export const propostaState = {
    orcamento: null,
    proposta: null,
    abaAtiva: "cliente",
    dirty: false,
    carregando: false,
    salvando: false,
    gerando: false,
    processando: false,
    // Editor-only fields have no storage contract in the current model.
    ui: { locais: criarCamposLocais(), totaisVisuais: {} }
};

function toNumber(value) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number
        : 0;
}

function normalizarItem(item = {}) {
    return {
        descricao: item.descricao ?? "",
        quantidade: toNumber(item.quantidade || 0),
        valor_unitario: toNumber(item.valor_unitario || 0),
        desconto: toNumber(item.desconto || 0),
        servico_id: Number.isInteger(item.servico_id) ? item.servico_id : null,
        combo_id: Number.isInteger(item.combo_id) ? item.combo_id : null,
        beat_id: Number.isInteger(item.beat_id) ? item.beat_id : null,
        licenca_beat: item.licenca_beat ?? null
    };
}

function marcarAlterado() {
    propostaState.dirty = JSON.stringify(getPropostaPayload()) !== propostaState.ui.payloadSalvo;
}

export function podeEditar() {
    return propostaState.proposta?.status === "rascunho" && !propostaState.carregando && !propostaState.salvando && !propostaState.gerando && !propostaState.processando;
}

export function resetPropostaState() {
    propostaState.orcamento = null;
    propostaState.proposta = null;
    propostaState.abaAtiva = "cliente";
    propostaState.dirty = false;
    propostaState.carregando = false;
    propostaState.salvando = false;
    propostaState.gerando = false;
    propostaState.processando = false;
    propostaState.ui = { locais: criarCamposLocais(), totaisVisuais: {} };
}

export function setProposta(proposta) {
    const mapped = mapResponseToState(proposta);
    propostaState.proposta = mapped.proposta;
    propostaState.orcamento = mapped.orcamento;
    propostaState.ui = { locais: criarCamposLocais(), totaisVisuais: {} };
    propostaState.dirty = false;
    propostaState.ui.payloadSalvo = JSON.stringify(getPropostaPayload());
    sincronizarTotais();
}

export function atualizarCampoProposta(campo, valor) {
    if (!podeEditar()) return;

    if (["finalidade", "produtor_id", "objeto", "descricao", "politica_pagamento", "condicoes"].includes(campo)) {
        propostaState.proposta[campo] = campo === "produtor_id"
            ? (valor === "" ? null : Number(valor)) : valor;
    } else return;
    marcarAlterado();
}

export function atualizarPagamento(campo, valor) {
    if (!podeEditar()) return;

    const tipo = links[campo] || (campo === "parcial_2_disponivel" ? "parcial_2" : null);
    if (tipo) {
        const pagamentos = propostaState.proposta.pagamentos;
        let pagamento = pagamentos.find(item => item.tipo === tipo);
        if (!pagamento) {
            pagamento = { tipo, titulo: tipo === "integral" ? "Pagamento completo" : `Pagamento ${tipo.replace("_", " ")}`, url: "", habilitado: false };
            pagamentos.push(pagamento);
        }
        if (campo === "parcial_2_disponivel") pagamento.habilitado = Boolean(valor);
        else {
            pagamento.url = valor;
            if (tipo !== "parcial_2") pagamento.habilitado = Boolean(valor);
        }
    } else return;

    marcarAlterado();
}

export function atualizarItem(index, campo, valor) {
    if (!podeEditar()) return;
    if (!propostaState.proposta?.itens[index]) return;
    if (!["descricao", "quantidade", "valor_unitario", "desconto"].includes(campo)) return;

    propostaState.proposta.itens[index][campo] = valor;

    marcarAlterado();
    sincronizarTotais();
}

export function adicionarItem() {
    if (!podeEditar()) return;

    propostaState.proposta.itens.push(
        normalizarItem({
            quantidade: 1
        })
    );

    marcarAlterado();
    sincronizarTotais();
}

// Roadmap 3.0, 5.05/5.08: a catalog line (service or combo) starts at the reference price;
// the admin negotiates it. A line points to a service or to a combo, never both.
export function adicionarItemCatalogo(entrada, tipo = "servico") {
    if (!podeEditar() || !Number.isInteger(entrada?.id)) return;

    propostaState.proposta.itens.push(
        normalizarItem(tipo === "beat" ? {
            descricao: `${entrada.titulo} (${entrada.licenca_beat === "exclusivo" ? "Exclusivo" : "Lease"})`,
            quantidade: 1,
            valor_unitario: entrada.valor,
            beat_id: entrada.id,
            licenca_beat: entrada.licenca_beat
        } : tipo === "combo" ? {
            descricao: entrada.nome,
            quantidade: 1,
            valor_unitario: entrada.preco_catalogo?.preco_vigente ?? entrada.preco_base,
            combo_id: entrada.id
        } : {
            descricao: entrada.nome,
            quantidade: 1,
            valor_unitario: entrada.preco_catalogo?.preco_vigente ?? entrada.valor_base,
            servico_id: entrada.id
        })
    );

    marcarAlterado();
    sincronizarTotais();
}

export function desvincularItem(index) {
    if (!podeEditar() || !propostaState.proposta?.itens[index]) return;

    propostaState.proposta.itens[index].servico_id = null;
    propostaState.proposta.itens[index].combo_id = null;
    propostaState.proposta.itens[index].beat_id = null;
    propostaState.proposta.itens[index].licenca_beat = null;
    marcarAlterado();
}

export function removerItem(index) {
    if (!podeEditar()) return;

    propostaState.proposta.itens.splice(index, 1);
    marcarAlterado();
    sincronizarTotais();
}

export function getItens() {
    return propostaState.proposta?.itens ?? [];
}

export function getTotalItens() {
    if (!propostaState.dirty && propostaState.proposta?.totais?.total != null) {
        return Number(propostaState.proposta.totais.total);
    }
    return calcularTotalItens(
        getItens()
    );
}

export function sincronizarTotais() {
    if (!propostaState.proposta) return;

    const total = getTotalItens();
    const pagamento = propostaState.ui.totaisVisuais;
    const entrada = toNumber(propostaState.ui.locais.entrada);

    pagamento.valor_total = total;
    pagamento.restante = Math.max(
        0,
        total - entrada
    );
}

export function getPropostaPayload() {
    return propostaState.proposta ? buildPropostaPayload(propostaState.proposta) : null;
}

// Compatibility view for existing tabs, not a persistence object.
export function getEditorProposta() {
    const proposta = propostaState.proposta;
    if (!proposta) return null;
    const pagamento = { ...propostaState.ui.locais, ...propostaState.ui.totaisVisuais };
    for (const [campo, tipo] of Object.entries(links)) {
        const item = proposta.pagamentos?.find(item => item.tipo === tipo);
        pagamento[campo] = item?.url ?? "";
        if (tipo === "parcial_2") pagamento.parcial_2_disponivel = item?.habilitado ?? false;
    }
    return { ...proposta, pagamento, prestador: propostaState.ui.locais.prestador,
        data: proposta.created_at?.slice(0, 10) ?? "" };
}
