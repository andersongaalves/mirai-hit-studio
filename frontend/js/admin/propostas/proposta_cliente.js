import { $ } from "../../utils/dom.js";
import { escapeHtml } from "./proposta_utils.js";

export function renderizarCliente(snapshot) {
    const container = $("proposta-content");

    if (!container || !snapshot) return;
    const { cliente, orcamento } = snapshot;

    container.innerHTML = `
        <div class="admin-info">
            <p><strong>Nome:</strong> ${escapeHtml(cliente.nome)}</p>
            <p><strong>Email:</strong> ${escapeHtml(cliente.email)}</p>
            <p><strong>Whatsapp:</strong> ${escapeHtml(cliente.whatsapp)}</p>
            <p><strong>Serviço solicitado:</strong> ${escapeHtml(orcamento.servico)}</p>
            <p><strong>Detalhes enviados:</strong></p>
            <textarea readonly rows="8" style="width:100%; resize:none;">${escapeHtml(orcamento.detalhes)}</textarea>
        </div>
    `;
}
