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

// Roadmap 3.0, 5.05/5.08: catalog services and combos are loaded once per page; failures keep
// manual items. Combos are optional: if they fail, services still work.
const catalogo = { servicos: null, combos: [], beats: [], erro: false, pedido: null };

async function listar(path) {
    const response = await authFetch(path);
    const data = await response.json().catch(() => null);
    if (!response.ok || !Array.isArray(data)) throw new Error("catalogo_indisponivel");
    return data;
}

function carregarCatalogo() {
    if (catalogo.servicos || catalogo.pedido) return catalogo.pedido ?? Promise.resolve(catalogo.servicos);
    catalogo.pedido = Promise.all([listar("/servicos"), listar("/combos").catch(() => []), listar("/admin/beats").catch(() => [])])
        .then(([servicos, combos, beats]) => {
            catalogo.servicos = servicos.filter(servico => Number.isInteger(servico?.id) && servico.nome);
            catalogo.combos = combos.filter(combo => Number.isInteger(combo?.id) && combo.nome);
            catalogo.beats = beats.filter(beat => Number.isInteger(beat?.id) && beat.status === "aprovado" && beat.ativo);
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

function comboPorId(id) {
    return catalogo.combos.find(combo => combo.id === id) ?? null;
}

// Reference price of the line's catalog origin (service base price or combo reference price).
function precoReferencia(item) {
    if (Number.isInteger(item.beat_id)) {
        const beat = catalogo.beats.find(row => row.id === item.beat_id);
        const field = { lease: "preco_lease", lease_mp3: "preco_lease", lease_wav: "preco_wav", multitrack: "preco_multitrack", exclusivo: "preco_exclusivo" }[item.licenca_beat];
        return beat && field ? Number(beat[field]) : null;
    }
    if (Number.isInteger(item.combo_id)) {
        const combo = comboPorId(item.combo_id);
        return combo ? Number(combo.preco_catalogo?.preco_vigente ?? combo.preco_base) : null;
    }
    const servico = Number.isInteger(item.servico_id) ? servicoPorId(item.servico_id) : null;
    return servico ? Number(servico.preco_catalogo?.preco_vigente ?? servico.valor_base) : null;
}

function origemCatalogo(item) {
    if (Number.isInteger(item.beat_id)) {
        const beat = catalogo.beats.find(row => row.id === item.beat_id);
        return `<p class="proposta-item-origem" data-origem><span>Beat: <strong>${escapeHtml(beat?.titulo ?? `#${item.beat_id}`)}</strong> · ${escapeHtml(item.licenca_beat ?? "")}${precoReferencia(item) !== null ? ` · ${money(precoReferencia(item))}` : ""}</span><button class="btn-small" type="button" data-desvincular>Desvincular</button></p>`;
    }
    const ehCombo = Number.isInteger(item.combo_id);
    if (!ehCombo && !Number.isInteger(item.servico_id)) return "";
    const entrada = ehCombo ? comboPorId(item.combo_id) : servicoPorId(item.servico_id);
    const nome = entrada ? entrada.nome : (ehCombo ? `Combo #${item.combo_id}` : `Serviço #${item.servico_id}`);
    const base = precoReferencia(item);
    const negociado = base !== null && Math.abs(Number(item.valor_unitario || 0) - base) > 0.004;
    const rotulo = ehCombo ? "Combo" : "Catálogo";
    const preco = entrada?.preco_catalogo ? "preço vigente" : ehCombo ? "preço de referência" : "preço base";
    const servicos = ehCombo && entrada?.servicos?.length
        ? ` · ${entrada.servicos.map(servico => escapeHtml(servico.nome)).join(" + ")}` : "";
    return `
        <p class="proposta-item-origem" data-origem>
            <span>${rotulo}: <strong>${escapeHtml(nome)}</strong>${base !== null ? ` · ${preco} ${money(base)}` : ""}${servicos}</span>
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
    const combos = catalogo.combos.filter(combo => combo.ativo !== false);
    const vazio = !servicos.length && !combos.length && !catalogo.beats.length;
    select.replaceChildren(new Option(vazio ? "Nenhum serviço no catálogo" : "Escolha um serviço ou combo do catálogo", ""));
    const grupoServicos = document.createElement("optgroup");
    grupoServicos.label = "Serviços";
    servicos.forEach(servico => grupoServicos.append(
        new Option(`${servico.nome} — ${money(servico.preco_catalogo?.preco_vigente ?? servico.valor_base)}`, `s:${servico.id}`)
    ));
    if (servicos.length) select.append(grupoServicos);
    // 5.08: only active combos can enter new proposal lines.
    if (combos.length) {
        const grupoCombos = document.createElement("optgroup");
        grupoCombos.label = "Combos";
        combos.forEach(combo => grupoCombos.append(
            new Option(`${combo.nome} — ${money(combo.preco_catalogo?.preco_vigente ?? combo.preco_base)}`, `c:${combo.id}`)
        ));
        select.append(grupoCombos);
    }
    if (catalogo.beats.length) {
        const group = document.createElement("optgroup"); group.label = "Beats";
        catalogo.beats.forEach(beat => {
            if (beat.preco_lease) group.append(new Option(`${beat.titulo} — MP3 lease ${money(beat.preco_lease)}`, `b:${beat.id}:${beat.formato_novo ? "lease_mp3" : "lease"}`));
            if (beat.preco_wav) group.append(new Option(`${beat.titulo} — WAV lease ${money(beat.preco_wav)}`, `b:${beat.id}:lease_wav`));
            if (beat.preco_multitrack) group.append(new Option(`${beat.titulo} — Multitrack ${money(beat.preco_multitrack)}`, `b:${beat.id}:multitrack`));
            if (beat.preco_exclusivo) group.append(new Option(`${beat.titulo} — Exclusivo ${money(beat.preco_exclusivo)}`, `b:${beat.id}:exclusivo`));
        });
        select.append(group);
    }
    const editavel = podeEditar();
    select.disabled = !editavel || vazio;
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
    const tabela = etapas => `<table class="proposta-snapshot__etapas">
                    <thead><tr><th>Etapa</th><th>Peso</th><th>Valor</th></tr></thead>
                    <tbody>${etapas.map(etapa => `
                        <tr>
                            <td>${escapeHtml(etapa.nome)}${etapa.administrativa ? " <small>(administrativa)</small>" : ""}</td>
                            <td>${escapeHtml(String(etapa.peso_percentual).replace(".", ","))}%</td>
                            <td>${money(etapa.valor)}</td>
                        </tr>`).join("")}
                    </tbody>
               </table>`;
    const itens = (snapshot.itens ?? []).map(item => {
        if (item.combo_id) {
            // 5.08: combo value -> services (by catalog price) -> stages (by weight).
            const componentes = (item.componentes ?? []).map(componente => {
                const etapas = (item.etapas ?? []).filter(etapa => etapa.componente_indice === componente.indice);
                return `
                    <div class="proposta-snapshot__componente">
                        <p>${escapeHtml(componente.servico_nome)} — ${money(componente.valor_alocado)}
                            <small>(catálogo ${money(componente.preco_catalogo)})</small></p>
                        ${etapas.length ? tabela(etapas) : '<p class="proposta-snapshot__sem-etapas">Serviço sem etapas no catálogo na data do congelamento.</p>'}
                    </div>`;
            }).join("");
            const comboInfo = item.combo_nome
                ? `Combo: ${escapeHtml(item.combo_nome)} · preço de referência ${money(item.preco_catalogo)}`
                : "Combo indisponível no congelamento";
            return `
            <div class="proposta-snapshot__item">
                <p><strong>${item.indice}. ${escapeHtml(item.descricao)}</strong> — contratado ${money(item.valor_contratado)}</p>
                <p class="proposta-snapshot__meta">${comboInfo}</p>
                ${componentes || '<p class="proposta-snapshot__sem-etapas">Sem serviços no combo na data do congelamento.</p>'}
            </div>`;
        }
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
                const referencia = precoReferencia(item);
                if (campo === "valor_unitario" && referencia !== null) {
                    const negociado = Math.abs(Number(item.valor_unitario || 0) - referencia) > 0.004;
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
        const [tipo, id, licenca] = String(select.value).split(":");
        const entrada = tipo === "b" ? catalogo.beats.find(beat => beat.id === Number(id)) : tipo === "c" ? comboPorId(Number(id)) : servicoPorId(Number(id));
        if (!entrada) return;
        const beatPrice = { lease: entrada.preco_lease, lease_mp3: entrada.preco_lease, lease_wav: entrada.preco_wav, multitrack: entrada.preco_multitrack, exclusivo: entrada.preco_exclusivo }[licenca];
        adicionarItemCatalogo(tipo === "b" ? { ...entrada, licenca_beat: licenca, valor: beatPrice } : entrada, tipo === "b" ? "beat" : tipo === "c" ? "combo" : "servico");
        onRefresh();
        onChange();
    };
    const precisaRecarregarOrigem = !catalogo.servicos
        && itens.some(item => Number.isInteger(item.servico_id) || Number.isInteger(item.combo_id) || Number.isInteger(item.beat_id));
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
