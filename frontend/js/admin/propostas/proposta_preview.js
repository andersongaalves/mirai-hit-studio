import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";

import {
    calcularSubtotalItem,
    escapeHtml,
    PROPOSTA_LOGO_SRC
} from "./proposta_utils.js";

import {
    getTotalItens
} from "./proposta_state.js";

function renderizarPagamentoCard({
    titulo,
    link,
    descricao = "",
    oculto = false
}) {
    if (oculto) return "";

    return `
        <div class="proposta-payment-card">
            <div>
                <strong>${escapeHtml(titulo)}</strong>
                <p>${escapeHtml(descricao)}</p>
                <small>${link ? escapeHtml(link) : "Link ainda não informado"}</small>
            </div>
            <div class="proposta-qr-placeholder">
                QR Code
            </div>
        </div>
    `;
}

export function renderizarPreview(proposta, orcamento) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    const itens = proposta.itens ?? [];
    const pagamento = proposta.pagamento ?? {};

    container.innerHTML = `
        <div class="admin-info proposta-preview">
            <header class="proposta-preview-header">
                <img
                    src="${PROPOSTA_LOGO_SRC}"
                    alt="Mirai Hit Studio"
                    class="proposta-preview-logo"
                >
                <div>
                    <h2>Proposta Comercial</h2>
                    <p>${escapeHtml(proposta.numero || "Número gerado ao salvar")}</p>
                </div>
            </header>

            <section>
                <h3>Cliente</h3>
                <p><strong>Nome:</strong> ${escapeHtml(orcamento?.nome_cliente)}</p>
                <p><strong>Email:</strong> ${escapeHtml(orcamento?.email)}</p>
                <p><strong>WhatsApp:</strong> ${escapeHtml(orcamento?.whatsapp)}</p>
            </section>

            <section>
                <h3>Objeto</h3>
                <p><strong>Data:</strong> ${escapeHtml(proposta.data)}</p>
                <p><strong>Prestador:</strong> ${escapeHtml(proposta.prestador)}</p>
                <p><strong>ID do produtor responsável:</strong> ${escapeHtml(proposta.produtor_id)}</p>
                <p><strong>Objeto:</strong> ${escapeHtml(proposta.objeto)}</p>
                <p>${escapeHtml(proposta.descricao).replaceAll("\n", "<br>")}</p>
            </section>

            <section>
                <h3>Itens da Proposta</h3>
                <table class="proposta-preview-table">
                    <thead>
                        <tr>
                            <th>Descrição</th>
                            <th>Qtd.</th>
                            <th>Unitário</th>
                            <th>Desconto</th>
                            <th>Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${itens.map(item => `
                            <tr>
                                <td>${escapeHtml(item.descricao)}</td>
                                <td>${item.quantidade ?? 0}</td>
                                <td>${money(item.valor_unitario ?? 0)}</td>
                                <td>${money(item.desconto ?? 0)}</td>
                                <td>${money(calcularSubtotalItem(item))}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
                <p><strong>Total:</strong> ${money(getTotalItens())}</p>
            </section>

            <section>
                <h3>Condições Comerciais</h3>
                <p>${escapeHtml(proposta.condicoes).replaceAll("\n", "<br>")}</p>
            </section>

            <section>
                <h3>Pagamento</h3>
                <p><strong>Entrada / Parcial 1:</strong> ${money(pagamento.entrada ?? 0)}</p>
                <p><strong>Restante:</strong> ${money(pagamento.restante ?? 0)}</p>
                <p><strong>Prazo:</strong> ${escapeHtml(pagamento.prazo)}</p>
                <p><strong>Validade:</strong> ${escapeHtml(pagamento.validade)}</p>

                <div class="proposta-payment-grid">
                    ${(proposta.pagamentos ?? []).map(item => renderizarPagamentoCard({
                        titulo: item.titulo, link: item.url, oculto: !item.habilitado
                    })).join("")}
                </div>

                <p><strong>PIX:</strong> ${escapeHtml(pagamento.pix)}</p>
                <p><strong>Mercado Pago:</strong> ${escapeHtml(pagamento.mercado_pago)}</p>
                <p>${escapeHtml(pagamento.observacoes).replaceAll("\n", "<br>")}</p>
            </section>
        </div>
    `;
}
