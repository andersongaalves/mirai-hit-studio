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
        desconto: toNumber(item.desconto || 0)
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

    if (["produtor_id", "objeto", "descricao", "condicoes"].includes(campo)) {
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
