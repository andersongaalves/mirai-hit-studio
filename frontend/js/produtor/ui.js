import { deadlineState, filterAndSort, formatDate, nextAction, parseEtapas, statusInfo, summarize } from "./utils.js";

const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
};

function badge(production) {
    const info = statusInfo(production.status);
    return element("span", `badge badge-${info.variant}`, info.label);
}

function empty(message) {
    return element("div", "producer-empty", message);
}

function productionCard(production, onOpen) {
    const card = element("article", "producer-card");
    const title = element("h3", "", production.titulo);
    const meta = element("div", "producer-card__meta");
    meta.append(badge(production), element("span", "", production.servico), element("span", "", production.cliente));

    const footer = element("div", "producer-card__footer");
    const deadline = deadlineState(production);
    footer.append(element("span", `badge badge-${deadline.kind}`, deadline.label));
    const button = element("button", "btn-outline", "Abrir detalhes");
    button.type = "button";
    button.addEventListener("click", () => onOpen(production.id));
    footer.append(button);
    card.append(title, meta, footer);
    return card;
}

export function showView(name) {
    document.querySelectorAll(".producer-view").forEach(view => view.classList.add("hidden"));
    document.getElementById(`producer-${name}`)?.classList.remove("hidden");
    document.querySelectorAll("[data-route]").forEach(link => {
        const current = link.dataset.route === name || (name === "detail" && link.dataset.route === "producoes");
        if (current) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}

const currency = value => new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
}).format(Number(value || 0));

export function renderDashboard(productions, payouts = []) {
    const metrics = document.getElementById("producer-metrics");
    metrics.replaceChildren();
    const summary = summarize(productions);
    const receivable = payouts.filter(item => item.status !== "pago")
        .reduce((total, item) => total + Number(item.valor_combinado), 0);
    const paid = payouts.filter(item => item.status === "pago")
        .reduce((total, item) => total + Number(item.valor_combinado), 0);
    [
        ["Produções ativas", summary.active, ""],
        ["Em revisão", summary.review, ""],
        ["Prazos vencidos", summary.overdue, summary.overdue ? "producer-metric--attention" : ""],
        ["A receber", currency(receivable), ""],
        ["Total pago", currency(paid), ""],
    ].forEach(([label, value, variant]) => {
        const metric = element("dl", `producer-metric ${variant}`.trim());
        metric.append(element("dt", "", label), element("dd", "", String(value)));
        metrics.append(metric);
    });

    const deadlines = document.getElementById("producer-deadlines");
    deadlines.replaceChildren();
    const upcoming = productions
        .filter(item => !["finalizado", "entregue"].includes(item.status) && item.prazo_entrega)
        .sort((a, b) => new Date(a.prazo_entrega) - new Date(b.prazo_entrega))
        .slice(0, 4);
    if (!upcoming.length) deadlines.append(empty("Nenhuma produção ativa possui prazo definido."));
    else upcoming.forEach(item => deadlines.append(productionCard(item, id => window.dispatchEvent(new CustomEvent("producer:open", { detail: id })))))
}

export function renderList(productions, filters, onOpen) {
    const list = document.getElementById("producer-list");
    list.replaceChildren();
    const items = filterAndSort(productions, filters.status, filters.order);
    if (!items.length) {
        list.append(empty(productions.length ? "Nenhuma produção corresponde aos filtros." : "Você ainda não possui produções atribuídas."));
        return;
    }
    items.forEach(item => list.append(productionCard(item, onOpen)));
}

function fileItem(file, onDownload) {
    const item = element("li", "producer-file");
    const info = element("div");
    info.append(
        element("strong", "", file.nome_exibicao),
        element("span", "", `${file.tipo} · versão ${file.versao} · ${Math.ceil(file.tamanho_bytes / 1024)} KB`),
    );
    const button = element("button", "btn-outline", "Baixar");
    button.type = "button";
    button.addEventListener("click", () => onDownload(file.id, button));
    item.append(info, button);
    return item;
}

function filesPanel(production, files, handlers) {
    const panel = element("section", "producer-files");
    panel.append(element("h2", "", "Arquivos"));
    const list = element("ul", "producer-file-list");
    if (!files.length) list.append(element("li", "producer-empty", "Nenhum arquivo autorizado disponível."));
    else files.forEach(file => list.append(fileItem(file, handlers.onDownload)));
    panel.append(list);

    const form = element("form", "producer-upload");
    const type = element("select");
    [["previa", "Prévia"], ["entrega", "Entrega"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        type.append(option);
    });
    type.setAttribute("aria-label", "Tipo de arquivo");
    const input = element("input");
    input.type = "file";
    input.required = true;
    input.setAttribute("aria-label", "Arquivo para enviar");
    const replaces = element("select");
    replaces.setAttribute("aria-label", "Versão substituída");
    const noReplacement = element("option", "", "Nova versão independente");
    noReplacement.value = "";
    replaces.append(noReplacement);
    files.filter(file => ["previa", "entrega"].includes(file.tipo)).forEach(file => {
        const option = element("option", "", `Substituir ${file.nome_exibicao} (v${file.versao})`);
        option.value = String(file.id);
        replaces.append(option);
    });
    const submit = element("button", "btn-cta", "Enviar arquivo");
    submit.type = "submit";
    form.append(type, input, replaces, submit);
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (input.files[0]) handlers.onUpload(production, input.files[0], type.value, replaces.value || null, submit);
    });
    panel.append(form);
    return panel;
}

export function renderDetail(production, files, handlers) {
    const root = document.getElementById("producer-detail-content");
    root.replaceChildren();
    const detail = element("article", "producer-detail");
    const title = element("h1", "", production.titulo);
    title.id = "detail-title";

    const meta = element("div", "producer-detail__meta");
    meta.append(badge(production), element("span", "", production.servico), element("span", "", `Atualizada em ${formatDate(production.updated_at, true)}`));

    const grid = element("div", "producer-detail__grid");
    const overview = element("section", "producer-detail__panel");
    overview.append(
        element("h2", "", "Informações"),
        element("p", "", `Cliente: ${production.cliente}`),
        element("p", "", `Prazo: ${formatDate(production.prazo_entrega)}`),
    );

    const progress = element("section", "producer-detail__panel");
    progress.append(element("h2", "", "Etapas"));
    const stages = parseEtapas(production.etapas);
    if (!stages.length) progress.append(element("p", "", "As etapas ainda não foram definidas pelo Admin."));
    else {
        const list = element("ul", "producer-progress");
        stages.forEach(stage => list.append(element("li", stage.feito ? "is-complete" : "", stage.nome)));
        progress.append(list);
    }
    grid.append(overview, progress);

    detail.append(title, meta, grid);
    const action = nextAction(production.status);
    if (action) {
        const actions = element("div", "producer-detail__actions");
        const button = element("button", "btn-cta", action.label);
        button.type = "button";
        button.addEventListener("click", () => handlers.onStatus(production.id, action.status, button));
        actions.append(button);
        detail.append(actions);
    }
    detail.append(filesPanel(production, files, handlers));
    root.append(detail);
}

export function renderPayouts(payouts, onReceipt) {
    const root = document.getElementById("producer-payouts");
    root.replaceChildren();
    if (!payouts.length) {
        root.append(empty("Nenhum recebimento foi registrado para suas produções."));
        return;
    }
    payouts.forEach(payout => {
        const card = element("article", "producer-card producer-payout");
        card.append(
            element("h2", "", payout.producao_titulo || `Produção #${payout.producao_id}`),
            element("strong", "producer-payout__value", currency(payout.valor_combinado)),
            element("span", `badge badge-${payout.status === "pago" ? "success" : "warning"}`, payout.status),
            element("p", "", payout.pago_em ? `Pago em ${formatDate(payout.pago_em, true)}` : "Pagamento manual via Pix"),
        );
        if (payout.comprovante_arquivo_id) {
            const button = element("button", "btn-outline", "Baixar comprovante");
            button.type = "button";
            button.addEventListener("click", () => onReceipt(payout.id, button));
            card.append(button);
        }
        root.append(card);
    });
}

export function setAlert(message = "", error = false) {
    const alert = document.getElementById("producer-alert");
    alert.textContent = message;
    alert.classList.toggle("hidden", !message);
    alert.classList.toggle("producer-message--error", error);
}
