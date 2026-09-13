import { $ } from "../../utils/dom.js";
import { createButtonElement } from "./producoes_dom.js";
import {
    STATUS_PRODUCAO,
    classificarPrazo,
    formatarData,
    formatarPrazo,
    parseEtapas,
    paraDatetimeLocal,
} from "./producoes_utils.js";

let producaoAtual = null;
let handlersAtuais = {};

function setText(id, value, fallback = "Não informado") {
    const element = $(id);
    if (element) element.textContent = value || fallback;
}

async function executar(button, action) {
    if (!button || button.disabled) return null;
    button.disabled = true;
    try {
        return await action();
    } finally {
        button.disabled = false;
    }
}

function renderizarStatus() {
    const select = $("prod_status");
    if (!select) return;
    select.replaceChildren();

    const options = STATUS_PRODUCAO.some(
        (item) => item.value === producaoAtual.status,
    )
        ? STATUS_PRODUCAO
        : [
            {
                value: producaoAtual.status,
                label: `Status desconhecido: ${producaoAtual.status}`,
            },
            ...STATUS_PRODUCAO,
        ];

    options.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.value;
        option.textContent = item.label;
        option.selected = item.value === producaoAtual.status;
        select.appendChild(option);
    });

    select.onchange = async () => {
        const anterior = producaoAtual.status;
        const atualizado = await executar(
            select,
            () => handlersAtuais.onAlterarStatus?.(producaoAtual.id, select.value),
        );
        if (!atualizado) select.value = anterior;
    };
}

function renderizarEtapas() {
    const container = $("prod_etapas");
    if (!container) return;
    container.replaceChildren();

    const etapas = parseEtapas(producaoAtual.etapas);
    if (!etapas.length) {
        container.appendChild(
            Object.assign(document.createElement("p"), {
                textContent: "Nenhuma etapa definida.",
                className: "admin-empty",
            }),
        );
        return;
    }

    etapas.forEach((etapa, index) => {
        const row = document.createElement("div");
        row.className = "producao-etapa-row";

        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = etapa.feito;
        const nome = document.createElement("span");
        nome.textContent = etapa.nome;
        label.append(checkbox, nome);

        checkbox.onchange = async () => {
            const novasEtapas = etapas.map((item, itemIndex) => (
                itemIndex === index
                    ? { ...item, feito: checkbox.checked }
                    : item
            ));
            checkbox.disabled = true;
            const atualizado = await handlersAtuais.onSalvarEtapas?.(
                producaoAtual.id,
                novasEtapas,
            );
            if (!atualizado) checkbox.checked = !checkbox.checked;
            checkbox.disabled = false;
        };

        const remover = createButtonElement("Remover", "btn-small btn-danger");
        remover.setAttribute("aria-label", `Remover etapa ${etapa.nome}`);
        remover.onclick = () => executar(remover, () => (
            handlersAtuais.onSalvarEtapas?.(
                producaoAtual.id,
                etapas.filter((_, itemIndex) => itemIndex !== index),
            )
        ));

        row.append(label, remover);
        container.appendChild(row);
    });
}

function renderizarResumo() {
    setText("prod_id", producaoAtual.id ? `Produção #${producaoAtual.id}` : "");
    setText("prod_titulo", producaoAtual.titulo);
    setText("prod_cliente", producaoAtual.cliente);
    setText("prod_email", producaoAtual.cliente_email);
    setText("prod_servico", producaoAtual.servico);
    setText("prod_data", formatarData(producaoAtual.created_at));
    setText(
        "prod_produtor",
        producaoAtual.produtor_nome
            || (producaoAtual.produtor_id ? `Usuário #${producaoAtual.produtor_id}` : ""),
    );
    setText(
        "prod_orcamento",
        producaoAtual.orcamento_id ? `Orçamento #${producaoAtual.orcamento_id}` : "",
    );
    setText(
        "prod_proposta",
        producaoAtual.proposta_numero
            ? `${producaoAtual.proposta_numero} (#${producaoAtual.proposta_id})`
            : "",
    );
    setText(
        "prod_prazo_status",
        formatarPrazo(producaoAtual.prazo_entrega, producaoAtual.status),
    );

    const prazoStatus = $("prod_prazo_status");
    if (prazoStatus) {
        prazoStatus.className = `prazo-${classificarPrazo(
            producaoAtual.prazo_entrega,
            producaoAtual.status,
        ).tipo}`;
    }

    const observacoes = $("prod_observacoes");
    if (observacoes) observacoes.value = producaoAtual.observacoes || "";

    const prazo = $("prod_prazo");
    if (prazo) prazo.value = paraDatetimeLocal(producaoAtual.prazo_entrega);

    renderizarStatus();
    renderizarEtapas();
}

function registrarAcoes() {
    const prazo = $("prod_prazo");
    const salvarPrazo = $("btn-save-prazo");
    if (salvarPrazo) {
        salvarPrazo.onclick = () => executar(salvarPrazo, () => {
            const iso = prazo?.value ? new Date(prazo.value).toISOString() : null;
            return handlersAtuais.onSalvarPrazo?.(producaoAtual.id, iso);
        });
    }

    const observacoes = $("prod_observacoes");
    const salvarObservacoes = $("btn-save-observacoes");
    if (salvarObservacoes) {
        salvarObservacoes.onclick = () => executar(
            salvarObservacoes,
            () => handlersAtuais.onSalvarObservacoes?.(
                producaoAtual.id,
                observacoes?.value || "",
            ),
        );
    }

    const novaEtapa = $("prod_nova_etapa");
    const adicionarEtapa = $("btn-add-etapa");
    if (adicionarEtapa) {
        adicionarEtapa.onclick = () => executar(adicionarEtapa, async () => {
            const nome = novaEtapa?.value.trim();
            if (!nome) {
                novaEtapa?.focus();
                return null;
            }
            const atualizado = await handlersAtuais.onSalvarEtapas?.(
                producaoAtual.id,
                [...parseEtapas(producaoAtual.etapas), { nome, feito: false }],
            );
            if (atualizado && novaEtapa) novaEtapa.value = "";
            return atualizado;
        });
    }
}

export function abrirModalProducao(producao, handlers = {}) {
    if (!producao) return;
    producaoAtual = { ...producao };
    handlersAtuais = handlers;
    renderizarResumo();
    registrarAcoes();
    $("modal-producao")?.classList.remove("hidden");
}

export function atualizarModalProducao(producao) {
    if (!producaoAtual || producaoAtual.id !== producao?.id) return;
    producaoAtual = { ...producaoAtual, ...producao };
    renderizarResumo();
    registrarAcoes();
}

export function fecharModalProducao() {
    producaoAtual = null;
    handlersAtuais = {};
    $("modal-producao")?.classList.add("hidden");
}
