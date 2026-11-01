import { $ } from "../../utils/dom.js";
import { escapeHtml } from "./proposta_utils.js";

export function renderizarCliente(snapshot) {
    const container = $("proposta-content");

    if (!container || !snapshot) return;
    const { cliente, orcamento } = snapshot;

    container.innerHTML = `
        <dl class="admin-detail-list">
            <div><dt>Nome</dt><dd>${escapeHtml(cliente.nome)}</dd></div>
            <div><dt>E-mail</dt><dd>${escapeHtml(cliente.email)}</dd></div>
            <div><dt>WhatsApp</dt><dd>${escapeHtml(cliente.whatsapp)}</dd></div>
            <div><dt>Serviço solicitado</dt><dd>${escapeHtml(orcamento.servico)}</dd></div>
        </dl>
        <label class="admin-form-field">Detalhes enviados
            <textarea readonly rows="8">${escapeHtml(orcamento.detalhes)}</textarea>
        </label>
    `;
}
