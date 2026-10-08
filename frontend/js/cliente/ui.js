import {
    FINAL_STATUSES,
    deadlineState,
    filterAndSort,
    formatDate,
    formatMoney,
    nextAction,
    parseEtapas,
    statusInfo,
    summarize,
} from "./utils.js";

const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
};

const empty = message => element("div", "producer-empty", message);

function emptyProjects() {
    const state = empty("Você ainda não possui projetos vinculados.");
    const action = element("a", "btn-cta", "Começar um projeto");
    action.href = "/orcamento";
    state.append(action);
    return state;
}

function badge(production) {
    const info = statusInfo(production.status);
    return element("span", `badge badge-${info.variant}`, info.label);
}

function productionCard(production, finance, onOpen) {
    const card = element("article", "producer-card");
    const meta = element("div", "producer-card__meta");
    meta.append(badge(production), element("span", "", production.servico));
    const footer = element("div", "producer-card__footer");
    const deadline = deadlineState(production);
    const action = element("div");
    action.append(
        element("span", `badge badge-${deadline.kind}`, deadline.label),
        element("p", "client-next-action", nextAction(production, finance)),
    );
    const button = element("button", "btn-outline", "Abrir projeto");
    button.type = "button";
    button.addEventListener("click", () => onOpen(production.id));
    footer.append(action, button);
    card.append(element("h3", "", production.titulo), meta, footer);
    return card;
}

export function showView(name) {
    document.querySelectorAll(".producer-view").forEach(view => view.classList.add("hidden"));
    document.getElementById(`client-${name}`)?.classList.remove("hidden");
    document.querySelectorAll("[data-route]").forEach(link => {
        const current = link.dataset.route === name || (name === "detail" && link.dataset.route === "projects");
        if (current) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}

export function renderDashboard(productions, finances) {
    const metrics = document.getElementById("client-metrics");
    metrics.replaceChildren();
    const summary = summarize(productions, finances);
    [
        ["Projetos em andamento", summary.active],
        ["Projetos concluídos", summary.completed],
        ["Em avaliação", summary.review],
        ["Pagamentos pendentes", summary.pendingPayment],
    ].forEach(([label, value]) => {
        const metric = element("dl", "producer-metric");
        metric.append(element("dt", "", label), element("dd", "", String(value)));
        metrics.append(metric);
    });

    const actions = document.getElementById("client-actions");
    actions.replaceChildren();
    const active = productions.filter(item => !FINAL_STATUSES.has(item.status)).slice(0, 4);
    if (!active.length) actions.append(productions.length
        ? empty("Você não possui projetos em andamento.")
        : emptyProjects());
    else active.forEach(item => actions.append(productionCard(
        item,
        finances.get(item.id),
        id => window.dispatchEvent(new CustomEvent("client:open", { detail: id })),
    )));
}

export function renderList(productions, finances, filters, onOpen) {
    const list = document.getElementById("client-list");
    list.replaceChildren();
    const items = filterAndSort(productions, filters.status, filters.order);
    if (!items.length) {
        list.append(productions.length
            ? empty("Nenhum projeto corresponde aos filtros.")
            : emptyProjects());
        return;
    }
    items.forEach(item => list.append(productionCard(item, finances.get(item.id), onOpen)));
}

function fileItem(file, handlers) {
    const item = element("li", "producer-file");
    const info = element("div");
    info.append(
        element("strong", "", file.nome_exibicao),
        element("span", "", `Versão ${file.versao} · ${Math.ceil(file.tamanho_bytes / 1024)} KB · ${formatDate(file.created_at, true)}`),
    );
    const actions = element("div", "client-file__actions");
    const player = element("div");
    if (file.tipo === "previa" && /^(audio|video)\//.test(file.mime_type)) {
        const play = element("button", "btn-outline", "Reproduzir");
        play.type = "button";
        play.addEventListener("click", () => handlers.onPreview(file, player, play));
        actions.append(play);
    }
    const download = element("button", "btn-outline", "Baixar");
    download.type = "button";
    download.addEventListener("click", () => handlers.onDownload(file.id, download));
    actions.append(download);
    item.append(info, actions, player);
    return item;
}

function fileGroup(title, files, handlers) {
    const group = element("section", "client-file-group");
    group.append(element("h3", "", title));
    const list = element("ul", "producer-file-list");
    if (!files.length) list.append(element("li", "producer-empty", "Nenhum arquivo liberado."));
    else files.forEach(file => list.append(fileItem(file, handlers)));
    group.append(list);
    return group;
}

function filesPanel(production, files, handlers) {
    const panel = element("section", "producer-files");
    panel.append(element("h2", "", "Arquivos e entregas"));
    panel.append(
        fileGroup("Prévias", files.filter(file => file.tipo === "previa"), handlers),
        fileGroup("Entregas finais", files.filter(file => file.tipo === "entrega"), handlers),
        fileGroup("Materiais e referências", files.filter(file => ["material", "referencia"].includes(file.tipo)), handlers),
    );

    if (!FINAL_STATUSES.has(production.status)) {
        const form = element("form", "producer-upload");
        const type = element("select");
        [["material", "Material"], ["referencia", "Referência"]].forEach(([value, label]) => {
            const option = element("option", "", label);
            option.value = value;
            type.append(option);
        });
        type.setAttribute("aria-label", "Tipo de arquivo");
        const input = element("input");
        input.type = "file";
        input.required = true;
        input.accept = ".pdf,.zip,.mp3,.wav,.flac,.m4a,.mp4";
        input.setAttribute("aria-label", "Arquivo para enviar");
        const replaces = element("select");
        replaces.setAttribute("aria-label", "Versão substituída");
        const updateReplacementOptions = () => {
            replaces.replaceChildren();
            const independent = element("option", "", "Novo arquivo");
            independent.value = "";
            replaces.append(independent);
            files.filter(file => file.enviado_por_mim && file.tipo === type.value).forEach(file => {
                const option = element("option", "", `Nova versão de ${file.nome_exibicao} (v${file.versao})`);
                option.value = String(file.id);
                replaces.append(option);
            });
        };
        type.addEventListener("change", updateReplacementOptions);
        updateReplacementOptions();
        const submit = element("button", "btn-cta", "Enviar arquivo");
        submit.type = "submit";
        form.append(type, input, replaces, submit);
        form.addEventListener("submit", event => {
            event.preventDefault();
            if (input.files[0]) handlers.onUpload(production, input.files[0], type.value, replaces.value || null, submit);
        });
        panel.append(form);
    }
    return panel;
}

function financePanel(finance) {
    const panel = element("section", "producer-files");
    panel.append(element("h2", "", "Pagamento"));
    if (!finance?.cobranca) {
        panel.append(element("p", "producer-help", "Nenhuma cobrança está vinculada a este projeto."));
        return panel;
    }
    const charge = finance.cobranca;
    const readableStatus = String(charge.status || "Não informado")
        .replaceAll("_", " ")
        .replace(/^./, character => character.toUpperCase());
    const grid = element("div", "client-finance-grid");
    [
        ["Situação", readableStatus],
        ["Valor cobrado", formatMoney(charge.valor_total)],
        ["Valor pago", formatMoney(charge.valor_pago)],
        ["Saldo pendente", formatMoney(charge.saldo_pendente)],
        ["Vencimento", formatDate(charge.vencimento)],
    ].forEach(([label, value]) => {
        const item = element("div", "client-finance-item");
        item.append(element("span", "", label), element("strong", "", value));
        grid.append(item);
    });
    panel.append(grid);
    if (finance.checkout_url) {
        try {
            const url = new URL(finance.checkout_url);
            if (["http:", "https:"].includes(url.protocol)) {
                const link = element("a", "btn-cta client-payment-action", "Ir para pagamento");
                link.href = url.href;
                panel.append(link);
            }
        } catch { /* Invalid URLs are intentionally not rendered. */ }
    }
    return panel;
}

export function renderDetail(production, files, finance, handlers) {
    const root = document.getElementById("client-detail-content");
    root.replaceChildren();
    const detail = element("article", "producer-detail");
    const title = element("h1", "", production.titulo);
    title.id = "detail-title";
    const meta = element("div", "producer-detail__meta");
    meta.append(
        badge(production),
        element("span", "", production.servico),
        element("span", "", `Atualizado em ${formatDate(production.updated_at, true)}`),
    );
    const grid = element("div", "producer-detail__grid");
    const overview = element("section", "producer-detail__panel");
    overview.append(
        element("h2", "", "Informações"),
        element("p", "", `Prazo: ${formatDate(production.prazo_entrega)}`),
        element("p", "", nextAction(production, finance)),
    );
    const progress = element("section", "producer-detail__panel");
    progress.append(element("h2", "", "Etapas"));
    const stages = parseEtapas(production.etapas);
    if (!stages.length) progress.append(element("p", "", "As etapas ainda não foram definidas."));
    else {
        const list = element("ul", "producer-progress");
        stages.forEach(stage => list.append(element("li", stage.feito ? "is-complete" : "", stage.nome)));
        progress.append(list);
    }
    grid.append(overview, progress);
    detail.append(title, meta, grid, filesPanel(production, files, handlers), financePanel(finance));
    root.append(detail);
}

const PROPOSAL_STATUS = Object.freeze({
    enviada: { label: "Aguardando resposta", variant: "review" },
    aceita: { label: "Aceita", variant: "success" },
    recusada: { label: "Recusada", variant: "neutral" },
});

function proposalBadge(proposal) {
    const info = PROPOSAL_STATUS[proposal.status] || { label: "Indisponível", variant: "neutral" };
    return element("span", `badge badge-${info.variant}`, info.label);
}

function proposalPolicy(value) {
    return value === "integral" ? "Pagamento integral" : "Entrada de 50% + saldo";
}

function proposalCard(proposal, onOpen) {
    const card = element("article", "producer-card client-proposal-card");
    const meta = element("div", "producer-card__meta");
    meta.append(
        proposalBadge(proposal),
        element("span", "", proposal.numero),
        element("span", "", proposalPolicy(proposal.politica_pagamento)),
    );
    const footer = element("div", "producer-card__footer");
    footer.append(
        element("strong", "client-proposal-total", formatMoney(proposal.totais.total)),
    );
    const button = element("button", "btn-outline", "Abrir proposta");
    button.type = "button";
    button.addEventListener("click", () => onOpen(proposal.id));
    footer.append(button);
    card.append(element("h3", "", proposal.objeto || proposal.servico), meta, footer);
    return card;
}

export function renderProposalSummary(proposals, onOpen) {
    const section = document.getElementById("client-proposal-summary");
    const list = document.getElementById("client-proposal-actions");
    list.replaceChildren();
    const pending = proposals.filter(item => item.status === "enviada");
    section.classList.toggle("hidden", !pending.length);
    pending.slice(0, 3).forEach(item => list.append(proposalCard(item, onOpen)));
}

export function renderProposalList(proposals, onOpen) {
    const list = document.getElementById("client-proposal-list");
    list.replaceChildren();
    if (!proposals.length) {
        list.append(empty("Você ainda não possui propostas disponíveis."));
        return;
    }
    proposals.forEach(item => list.append(proposalCard(item, onOpen)));
}

export function renderProposalDetail(proposal, handlers) {
    const root = document.getElementById("client-proposal-detail-content");
    root.replaceChildren();
    const detail = element("article", "producer-detail client-proposal-detail");
    const title = element("h1", "", proposal.objeto || proposal.servico);
    title.id = "proposal-detail-title";
    const meta = element("div", "producer-detail__meta");
    meta.append(
        proposalBadge(proposal),
        element("span", "", proposal.numero),
        element("span", "", `Versão ${proposal.versao}`),
        element("span", "", proposalPolicy(proposal.politica_pagamento)),
    );

    const description = element("section", "producer-detail__panel client-proposal-copy");
    description.append(
        element("h2", "", "Proposta"),
        element("p", "", proposal.descricao || "Sem descrição adicional."),
    );
    const conditions = element("section", "producer-detail__panel client-proposal-copy");
    conditions.append(
        element("h2", "", "Condições"),
        element("p", "", proposal.condicoes || "Consulte a equipe Mirai."),
    );

    const items = element("section", "producer-files client-proposal-items");
    items.append(element("h2", "", "Itens e valores"));
    const table = element("div", "client-proposal-table");
    proposal.itens.forEach(item => {
        const row = element("div", "client-proposal-row");
        const lineTotal = Number(item.quantidade) * Number(item.valor_unitario) - Number(item.desconto || 0);
        row.append(
            element("span", "", item.descricao),
            element("span", "", `${item.quantidade} × ${formatMoney(item.valor_unitario)}`),
            element("strong", "", formatMoney(lineTotal)),
        );
        table.append(row);
    });
    const total = element("div", "client-proposal-total-row");
    total.append(element("span", "", "Total"), element("strong", "", formatMoney(proposal.totais.total)));
    table.append(total);
    items.append(table);

    const actions = element("div", "client-proposal-actions");
    if (proposal.documento_disponivel) {
        const download = element("button", "btn-outline", "Baixar PDF");
        download.type = "button";
        download.addEventListener("click", () => handlers.onDownload(proposal, download));
        actions.append(download);
    }
    if (proposal.status === "enviada") {
        const refuse = element("button", "btn-outline", "Recusar");
        refuse.type = "button";
        refuse.addEventListener("click", () => handlers.onRefuse(proposal, refuse));
        const accept = element("button", "btn-cta", "Aceitar proposta");
        accept.type = "button";
        accept.addEventListener("click", () => handlers.onAccept(proposal, accept));
        actions.append(refuse, accept);
    }
    detail.append(title, meta, description, conditions, items, actions);
    root.append(detail);
}

export function setAlert(message = "", error = false) {
    const alert = document.getElementById("client-alert");
    alert.textContent = message;
    alert.classList.toggle("hidden", !message);
    alert.classList.toggle("producer-message--error", error);
}
