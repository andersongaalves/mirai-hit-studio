import { controlesOuvir, opcoesEstudio, podeOuvir } from "../modules/ouvir_arquivo.js";
import { deadlineState, filterAndSort, formatDate, nextAction, parseEtapas, statusInfo, summarize } from "./utils.js";

let currentUserId = null;

export function setCurrentUserId(id) {
    currentUserId = typeof id === "number" ? id : null;
}

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
    // AUD6-S08-001: "Beats" is one area with two tabs (Meus beats, Catálogo).
    document.querySelectorAll("[data-route]").forEach(link => {
        const current = link.dataset.route === name
            || (name === "detail" && link.dataset.route === "producoes")
            || (name === "catalog" && link.dataset.route === "beats");
        if (current) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
    document.querySelectorAll("[data-route-tab]").forEach(tab => {
        if (tab.dataset.routeTab === name) tab.setAttribute("aria-current", "page");
        else tab.removeAttribute("aria-current");
    });
}

const currency = value => new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
}).format(Number(value || 0));

// Roadmap 5.01: presentation settings published by the admin; backend stays authoritative.
const DEFAULT_INDICATORS = ["ativas", "revisao", "vencidos", "a_receber", "pago"];
let portalSettings = null;

export function applySettings(settings) {
    portalSettings = settings || null;
    const notice = document.getElementById("producer-notice");
    const aviso = settings?.aviso;
    const showNotice = Boolean(aviso?.ativo && aviso.texto);
    notice.textContent = showNotice ? aviso.texto : "";
    notice.dataset.level = showNotice ? aviso.nivel : "";
    notice.classList.toggle("hidden", !showNotice);
    if (settings?.textos) {
        const lead = document.getElementById("producer-dashboard-lead");
        lead.textContent = settings.textos.descricao_dashboard;
        lead.classList.toggle("hidden", !settings.textos.descricao_dashboard);
        const help = document.getElementById("producer-finance-help");
        help.textContent = settings.textos.ajuda_financeiro;
        help.classList.toggle("hidden", !settings.textos.ajuda_financeiro);
    }
}

export function renderDashboard(productions, payouts = []) {
    const metrics = document.getElementById("producer-metrics");
    metrics.replaceChildren();
    const summary = summarize(productions);
    const receivable = payouts.filter(item => item.por_etapa ? item.status === "a_receber" : item.status !== "pago")
        .reduce((total, item) => total + Number(item.valor_combinado), 0);
    const paid = payouts.filter(item => item.status === "pago")
        .reduce((total, item) => total + Number(item.valor_combinado), 0);
    const available = {
        ativas: ["Produções ativas", summary.active, ""],
        revisao: ["Em revisão", summary.review, ""],
        vencidos: ["Prazos vencidos", summary.overdue, summary.overdue ? "producer-metric--attention" : ""],
        a_receber: ["A receber", currency(receivable), ""],
        pago: ["Total pago", currency(paid), ""],
    };
    (portalSettings?.indicadores || DEFAULT_INDICATORS)
        .filter(key => available[key])
        .map(key => available[key])
        .forEach(([label, value, variant]) => {
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

function fileItem(file, handlers) {
    const onDownload = handlers.onDownload;
    const item = element("li", "producer-file");
    const info = element("div");
    info.append(
        element("strong", "", file.nome_exibicao),
        element("span", "", `${file.tipo} · versão ${file.versao} · ${Math.ceil(file.tamanho_bytes / 1024)} KB`),
    );
    const own = file.remetente_usuario_id === currentUserId;
    const note = element("p", "file-note");
    const showNote = () => {
        note.textContent = file.observacao ? `${own ? "Sua observação" : "Observação"}: ${file.observacao}` : "";
        note.hidden = !file.observacao;
    };
    showNote();
    info.append(note);
    if (own && handlers.onEditNote) {
        // The producer can fix or complete the note of a file they sent.
        const edit = element("button", "btn-outline btn-small", file.observacao ? "Editar observação" : "Adicionar observação");
        edit.type = "button";
        const form = element("form", "file-note-form");
        form.hidden = true;
        const label = element("label", "", "Observação");
        const text = element("textarea");
        text.maxLength = 1000;
        text.rows = 3;
        label.append(text);
        const save = element("button", "btn-cta btn-small", "Salvar");
        save.type = "submit";
        const cancel = element("button", "btn-outline btn-small", "Cancelar");
        cancel.type = "button";
        form.append(label, save, cancel);
        const close = () => { form.hidden = true; edit.hidden = false; };
        edit.addEventListener("click", () => {
            text.value = file.observacao || "";
            form.hidden = false;
            edit.hidden = true;
            text.focus();
        });
        cancel.addEventListener("click", close);
        form.addEventListener("submit", async event => {
            event.preventDefault();
            save.disabled = true;
            try {
                const updated = await handlers.onEditNote(file, text.value.trim());
                file.observacao = updated?.observacao ?? null;
                showNote();
                edit.textContent = file.observacao ? "Editar observação" : "Adicionar observação";
                close();
                setAlert("Observação salva.");
            } catch (error) {
                setAlert(error.message, true);
            } finally {
                save.disabled = false;
            }
        });
        info.append(edit, form);
    }
    if (file.tipo === "previa") {
        info.append(element(
            "span",
            file.visivel_cliente ? "producer-file__shared" : "",
            file.processamento_tag === "pendente" ? "Processando versão com tag"
                : file.processamento_tag === "erro" ? "Falha ao processar tag. Solicite revisão ao estúdio."
                : file.visivel_cliente ? "Compartilhada com o cliente" : "Não compartilhada com o cliente",
        ));
    }
    const button = element("button", "btn-outline", "Baixar");
    button.type = "button";
    button.addEventListener("click", () => onDownload(file.id, button));
    item.append(info, button);
    if (handlers.onListen && podeOuvir(file) && file.processamento_tag !== "pendente") {
        info.append(controlesOuvir(file, {
            opcoes: opcoesEstudio(file),
            load: versao => handlers.onListen(file, versao),
            onError: error => setAlert(error.message, true),
        }));
    }
    return item;
}

function filesPanel(production, files, handlers) {
    const panel = element("section", "producer-files");
    panel.append(element("h2", "", "Arquivos"));
    const list = element("ul", "producer-file-list");
    if (!files.length) list.append(element("li", "producer-empty", "Nenhum arquivo disponível."));
    else files.forEach(file => list.append(fileItem(file, handlers)));
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
    // AUD6-S08-003: same Portuguese picker as the client portal, not the browser's own.
    const filePicker = element("label", "producer-upload__picker");
    const fileButton = element("span", "producer-upload__pick-button", "Escolher arquivo");
    const fileName = element("span", "producer-upload__filename", "Nenhum arquivo selecionado");
    fileName.title = fileName.textContent;
    input.addEventListener("change", () => {
        fileName.textContent = input.files[0]?.name || "Nenhum arquivo selecionado";
        fileName.title = fileName.textContent;
    });
    filePicker.append(input, fileButton, fileName);
    const replaces = element("select");
    replaces.setAttribute("aria-label", "Versão substituída");
    const noReplacement = element("option", "", "Nova versão independente");
    noReplacement.value = "";
    replaces.append(noReplacement);
    // Offer only the newest version of the selected type; the backend rejects others.
    const replaced = new Set(files.map(file => file.substitui_arquivo_id).filter(id => id != null));
    const updateReplacementOptions = () => {
        replaces.replaceChildren(noReplacement);
        files
            .filter(file => file.tipo === type.value && !replaced.has(file.id))
            .forEach(file => {
                const option = element("option", "", `Substituir ${file.nome_exibicao} (v${file.versao})`);
                option.value = String(file.id);
                replaces.append(option);
            });
    };
    type.addEventListener("change", updateReplacementOptions);
    updateReplacementOptions();
    const note = element("textarea", "producer-upload__note");
    note.rows = 2;
    note.maxLength = 1000;
    note.placeholder = "Observação para esta versão (opcional)";
    note.setAttribute("aria-label", "Observação para esta versão");
    const submit = element("button", "btn-cta", "Enviar arquivo");
    submit.type = "submit";
    const quotaHint = element("p", "file-quota-hint hidden");
    quotaHint.dataset.quotaHint = "";
    quotaHint.setAttribute("aria-live", "polite");
    form.append(type, filePicker, replaces, quotaHint, note, submit);
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (input.files[0]) handlers.onUpload(production, input.files[0], type.value, replaces.value || null, submit, note.value);
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
    const contact = production.contato_cliente;
    if (contact) {
        const panel = element("section", "producer-client-contact");
        panel.append(element("h3", "", "Contato do cliente"), element("p", "", contact.nome));
        if (contact.email) {
            const email = element("a", "", contact.email);
            email.href = `mailto:${encodeURIComponent(contact.email)}`;
            const line = element("p");
            line.append(email);
            panel.append(line);
        }
        if (contact.whatsapp) {
            const digits = String(contact.whatsapp).replace(/\D/g, "");
            const international = [10, 11].includes(digits.length) ? `55${digits}` : digits;
            const line = element("p", "", `Telefone / WhatsApp: ${contact.whatsapp}`);
            if (/^\d{12,15}$/.test(international)) {
                const link = element("a", "", "Abrir WhatsApp");
                link.href = `https://wa.me/${international}`;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                line.append(document.createTextNode(" "), link);
            }
            panel.append(line);
        }
        overview.append(panel);
    }

    const progress = element("section", "producer-detail__panel");
    progress.id = "production-stages-panel";
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
    // Roadmap 5.07: stage owners do not change the overall progress; the coordinator does.
    const action = production.coordenador === false ? null : nextAction(production.status);
    if (production.coordenador === false) {
        detail.append(element(
            "p",
            "producer-detail__role",
            "Você participa desta produção pelas etapas atribuídas a você. O andamento geral fica com o produtor coordenador.",
        ));
    }
    if (action) {
        // AUD6-S08-005: the overall action sits with the production summary and says
        // that it covers the whole production; each stage keeps its own buttons.
        const actions = element("div", "producer-detail__actions producer-detail__actions--overall");
        actions.append(element("p", "producer-detail__actions-note",
            "Andamento da produção completa. Para uma etapa, use os botões dentro dela."));
        const button = element("button", "btn-cta", action.label);
        button.type = "button";
        button.addEventListener("click", () => handlers.onStatus(production.id, action.status, button));
        actions.append(button);
        overview.append(actions);
    }
    const messagesSlot = element("div");
    messagesSlot.id = "production-messages-slot";
    detail.append(filesPanel(production, files, handlers), messagesSlot);
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
            element("span", `badge badge-${payout.status === "pago" ? "success" : "warning"}`,
                ({ previsto: "Previsto", bloqueado: "Bloqueado", a_receber: "A receber", pago: "Pago" })[payout.status] || payout.status),
            element("p", "", payout.pago_em ? `Pago em ${formatDate(payout.pago_em, true)}` : payout.bloqueio || "Pagamento manual via Pix"),
        );
        if (payout.por_etapa) card.append(element("p", "", payout.etapa_nome));
        if (payout.comprovante_arquivo_id) {
            const button = element("button", "btn-outline", "Baixar comprovante");
            button.type = "button";
            button.addEventListener("click", () => onReceipt(payout.id, button, Boolean(payout.por_etapa)));
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
