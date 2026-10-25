import { $ } from "../../utils/dom.js";
import { formatEstimatedValue, formatStatus } from "./orcamentos_utils.js";
import { safeURL } from "../../utils/security.js";
import { closeAdminModal, openAdminModal } from "../admin_modal.js";

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
    value = safeURL(value);
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
    // AUD6-S09-002: a budget linked to a client opens the client page.
    const clientButton = document.getElementById("orc_cliente_abrir");
    if (clientButton) {
        const clientId = orcamento.cliente_id;
        clientButton.classList.toggle("hidden", !Number.isInteger(clientId));
        clientButton.onclick = Number.isInteger(clientId) ? async () => {
            fecharModalOrcamento();
            await window.mostrarSecao?.("section-clientes");
            const { abrirCliente } = await import("../clientes/clientes.js");
            await abrirCliente(clientId);
        } : null;
    }
    setText("orc_email", orcamento.email);
    setText("orc_produtor", orcamento.produtor?.username ?? "Sem produtor");
    setText("orc_whatsapp", orcamento.whatsapp);
    setText("orc_servico", orcamento.servico);
    setText("orc_valor", formatEstimatedValue(orcamento.valor_total));
    setText("orc_data", orcamento.data_solicitacao);
    setValue("orc_detalhes", orcamento.detalhes);
    setText("orc_status", formatStatus(orcamento.status));
    setValue("orc_observacoes", orcamento.observacoes);
    setHref("orc_guia", orcamento.link_guia);

    openAdminModal("modal-orcamento", {
        onRequestClose: fecharModalOrcamento,
    });
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

    closeAdminModal("modal-orcamento");
}
