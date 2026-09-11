import { $ } from "../../utils/dom.js";
import { escapeHtml } from "./proposta_utils.js";

export function renderizarCliente(orcamento) {
    const container = $("proposta-content");

    if (!container || !orcamento) return;

    container.innerHTML = `
        <div class="admin-info">
            <p><strong>Nome:</strong> ${escapeHtml(orcamento.nome_cliente)}</p>
            <p><strong>Email:</strong> ${escapeHtml(orcamento.email)}</p>
            <p><strong>Whatsapp:</strong> ${escapeHtml(orcamento.whatsapp)}</p>
            <p><strong>Serviço solicitado:</strong> ${escapeHtml(orcamento.servico)}</p>
            <p><strong>Detalhes enviados:</strong></p>
            <textarea readonly rows="8" style="width:100%; resize:none;">${escapeHtml(orcamento.detalhes)}</textarea>
        </div>
    `;
}
