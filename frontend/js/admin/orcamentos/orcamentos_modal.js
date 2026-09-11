import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";
import { formatStatus } from "./orcamentos_utils.js";

let orcamentoAtual = null;

function setText(id, value = "") {
    const element = $(id);

    if (element) {
        element.textContent = value ?? "";
    }
}

function setValue(id, value = "") {
    const element = $(id);

    if (element) {
        element.value = value ?? "";
    }
}

function setHref(id, value = "") {
    const element = $(id);

    if (!element) return;

    if (value) {
        element.href = value;
        return;
    }

    element.removeAttribute("href");
}

export function abrirModalOrcamento(orcamento) {
    if (!orcamento) return;

    orcamentoAtual = orcamento;

    setText("orc_nome", orcamento.nome_cliente);
    setText("orc_email", orcamento.email);
    setText("orc_produtor", orcamento.produtor?.username ?? "Sem produtor");
    setText("orc_whatsapp", orcamento.whatsapp);
    setText("orc_servico", orcamento.servico);
    setText("orc_valor", money(orcamento.valor_total));
    setText("orc_data", orcamento.data_solicitacao);
    setValue("orc_detalhes", orcamento.detalhes);
    setText("orc_status", formatStatus(orcamento.status));
    setValue("orc_observacoes", orcamento.observacoes);
    setHref("orc_guia", orcamento.link_guia);

    $("modal-orcamento")?.classList.remove("hidden");
}

export function registrarEventosModal({ onSalvarObservacoes = () => {} } = {}) {
    const btn = $("btn-save-observacoes");

    if (!btn) return;

    btn.onclick = () => {
        const observacoes = $("orc_observacoes");

        if (!orcamentoAtual || !observacoes) return;

        onSalvarObservacoes(orcamentoAtual.id, observacoes.value);
    };
}

export function fecharModalOrcamento() {
    orcamentoAtual = null;

    $("modal-orcamento")?.classList.add("hidden");
}
