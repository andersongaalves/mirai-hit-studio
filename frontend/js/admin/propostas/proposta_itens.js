import { $ } from "../../utils/dom.js";
import { money } from "../../utils/format.js";
import { authFetch } from "../auth.js";

import {
    adicionarItem,
    adicionarItemCatalogo,
    desvincularItem,
    removerItem,
    atualizarItem,
    getTotalItens,
    podeEditar
} from "./proposta_state.js";

import {
    calcularSubtotalItem,
    escapeHtml
} from "./proposta_utils.js";

// Roadmap 3.0, 5.05: catalog services are loaded once per page; failures keep manual items.
const catalogo = { servicos: null, erro: false, pedido: null };

function carregarCatalogo() {
    if (catalogo.servicos || catalogo.pedido) return catalogo.pedido ?? Promise.resolve(catalogo.servicos);
    catalogo.pedido = authFetch("/servicos")
        .then(async response => {
            const data = await response.json().catch(() => null);
            if (!response.ok || !Array.isArray(data)) throw new Error("catalogo_indisponivel");
            catalogo.servicos = data.filter(servico => Number.isInteger(servico?.id) && servico.nome);
            catalogo.erro = false;
            return catalogo.servicos;
        })
        .catch(() => {
            catalogo.erro = true;
            return null;
        })
        .finally(() => { catalogo.pedido = null; });
    return catalogo.pedido;
}

function servicoPorId(id) {
    return catalogo.servicos?.find(servico => servico.id === id) ?? null;
}

function origemCatalogo(item) {
    if (!Number.isInteger(item.servico_id)) return "";
    const servico = servicoPorId(item.servico_id);
    const nome = servico ? servico.nome : `Serviço #${item.servico_id}`;
    const base = servico ? Number(servico.valor_base) : null;
    const negociado = base !== null && Math.abs(Number(item.valor_unitario || 0) - base) > 0.004;
    return `
        <p class="proposta-item-origem" data-origem>
            <span>Catálogo: <strong>${escapeHtml(nome)}</strong>${base !== null ? ` · preço base ${money(base)}` : ""}</span>
            ${negociado ? '<span class="proposta-item-origem__tag">Preço negociado</span>' : ""}
            <button class="btn-small" type="button" data-desvincular>Desvincular</button>
        </p>`;
}

function preencherSeletor(select, button, aviso) {
    if (!select) return;
    if (catalogo.erro) {
        aviso.textContent = "Catálogo indisponível no momento; os itens manuais continuam disponíveis.";
        select.disabled = true;
        button.disabled = true;
        return;
    }
    const servicos = catalogo.servicos ?? [];
    select.replaceChildren(new Option(servicos.length ? "Escolha um serviço do catálogo" : "Nenhum serviço no catálogo", ""));
    servicos.forEach(servico => select.append(
        new Option(`${servico.nome} — ${money(servico.valor_base)}`, String(servico.id))
    ));
    const editavel = podeEditar();
    select.disabled = !editavel || !servicos.length;
    button.disabled = true;
    select.onchange = () => { button.disabled = !editavel || !select.value; };
}

function formatarData(valor) {
    const data = new Date(valor);
    return Number.isNaN(data.getTime())
        ? ""
        : data.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// Read-only view of the frozen contract: what was sent is what production will use.
function renderizarSnapshot(snapshot) {
    if (!snapshot) return "";
    const origem = snapshot.origem === "aceite" ? "no aceite" : "no envio";
    const itens = (snapshot.itens ?? []).map(item => {
        const etapas = item.etapas?.length
            ? `<table class="proposta-snapshot__etapas">
                    <thead><tr><th>Etapa</th><th>Peso</th><th>Valor</th></tr></thead>
                    <tbody>${item.etapas.map(etapa => `
                        <tr>
                            <td>${escapeHtml(etapa.nome)}${etapa.administrativa ? " <small>(administrativa)</small>" : ""}</td>
                            <td>${escapeHtml(String(etapa.peso_percentual).replace(".", ","))}%</td>
                            <td>${money(etapa.valor)}</td>
                        </tr>`).join("")}
                    </tbody>
               </table>`
            : `<p class="proposta-snapshot__sem-etapas">${item.servico_id ? "Serviço sem etapas no catálogo na data do congelamento." : "Item avulso, sem etapas de catálogo."}</p>`;
        const catalogoInfo = item.servico_nome
            ? `Catálogo: ${escapeHtml(item.servico_nome)} · preço base ${money(item.preco_catalogo)}`
            : (item.servico_id ? "Serviço do catálogo indisponível no congelamento" : "Item avulso");
        return `
            <div class="proposta-snapshot__item">
                <p><strong>${item.indice}. ${escapeHtml(item.descricao)}</strong> — contratado ${money(item.valor_contratado)}</p>
                <p class="proposta-snapshot__meta">${catalogoInfo}</p>
                ${etapas}
            </div>`;
    }).join("");
    return `
        <section class="proposta-snapshot" id="proposta-snapshot" aria-label="Valores congelados">
            <h4>Valores congelados ${origem}</h4>
            <p class="proposta-snapshot__meta">Congelado em ${escapeHtml(formatarData(snapshot.congelado_em))} ·
                versão ${escapeHtml(String(snapshot.proposta_versao))} · total ${money(snapshot.total)}.
                Alterações posteriores no catálogo não mudam estes valores.</p>
            ${itens}
        </section>`;
}

export function renderizarItens(proposta, onRefresh = () => {}, onChange = () => {}) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    const itens = proposta.itens ?? [];

    container.innerHTML = `
        <div class="admin-info">
            <div class="proposta-catalogo">
                <label for="proposta-catalogo-servico">Serviço do catálogo</label>
                <div class="proposta-catalogo__controls">
                    <select id="proposta-catalogo-servico" disabled>
                        <option value="">Carregando catálogo…</option>
                    </select>
                    <button id="btn-add-proposta-catalogo" class="btn-small" type="button" disabled>
                        + Adicionar serviço
                    </button>
                </div>
                <p class="proposta-catalogo__aviso" id="proposta-catalogo-aviso" role="status"></p>
            </div>
            <div id="proposta-itens-list"></div>
            <button id="btn-add-proposta-item" class="btn-small" type="button">
                + Adicionar item
            </button>
            <p><strong>Total:</strong> <span id="proposta-itens-total">${money(getTotalItens())}</span></p>
            ${renderizarSnapshot(proposta.snapshot_economico)}
        </div>
    `;

    const list = $("proposta-itens-list");

    itens.forEach((item, index) => {
        const row = document.createElement("div");

        row.className = "admin-list-item proposta-item-row";
        row.innerHTML = `
            <div class="form-group">
                <label>Descrição</label>
                <input data-campo="descricao" value="${escapeHtml(item.descricao)}">
            </div>
            <div class="form-group">
                <label>Qtd.</label>
                <input data-campo="quantidade" type="number" min="0" step="any" value="${escapeHtml(item.quantidade ?? 0)}">
            </div>
            <div class="form-group">
                <label>Valor unitário</label>
                <input data-campo="valor_unitario" type="number" min="0" step="0.01" value="${escapeHtml(item.valor_unitario ?? 0)}">
            </div>
            <div class="form-group">
                <label>Desconto</label>
                <input data-campo="desconto" type="number" min="0" step="0.01" value="${escapeHtml(item.desconto ?? 0)}">
            </div>
            <span data-subtotal>${money(calcularSubtotalItem(item))}</span>
            <button class="btn-small btn-danger" type="button" data-remover>Remover</button>
            ${origemCatalogo(item)}
        `;

        row.querySelectorAll("input").forEach(input => {
            input.oninput = e => {
                const campo = e.target.dataset.campo;
                const value = e.target.value;

                atualizarItem(index, campo, value);
                row.querySelector("[data-subtotal]").textContent = money(calcularSubtotalItem(item));
                $("proposta-itens-total").textContent = money(getTotalItens());
                const tag = row.querySelector(".proposta-item-origem__tag");
                const servico = servicoPorId(item.servico_id);
                if (campo === "valor_unitario" && servico) {
                    const negociado = Math.abs(Number(item.valor_unitario || 0) - Number(servico.valor_base)) > 0.004;
                    if (negociado && !tag) {
                        const novo = document.createElement("span");
                        novo.className = "proposta-item-origem__tag";
                        novo.textContent = "Preço negociado";
                        row.querySelector("[data-origem] span").after(novo);
                    } else if (!negociado && tag) tag.remove();
                }
                onChange();
            };
        });

        row.querySelector("[data-remover]").onclick = () => {
            removerItem(index);
            onRefresh();
        };

        const desvincular = row.querySelector("[data-desvincular]");
        if (desvincular) {
            desvincular.disabled = !podeEditar();
            desvincular.onclick = () => {
                desvincularItem(index);
                onRefresh();
                onChange();
            };
        }

        list.appendChild(row);
    });

    $("btn-add-proposta-item").onclick = () => {
        adicionarItem();
        onRefresh();
    };

    const select = $("proposta-catalogo-servico");
    const button = $("btn-add-proposta-catalogo");
    const aviso = $("proposta-catalogo-aviso");
    button.onclick = () => {
        const servico = servicoPorId(Number(select.value));
        if (!servico) return;
        adicionarItemCatalogo(servico);
        onRefresh();
        onChange();
    };
    const precisaRecarregarOrigem = !catalogo.servicos && itens.some(item => Number.isInteger(item.servico_id));
    carregarCatalogo().then(() => {
        if (!document.body.contains(select)) return;
        // Origin labels need the catalog names; redraw once when they first arrive.
        if (precisaRecarregarOrigem && catalogo.servicos) {
            onRefresh();
            return;
        }
        preencherSeletor(select, button, aviso);
    });
}
