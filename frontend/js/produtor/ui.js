import { deliveriesSection, stageLabel } from "../modules/final_deliveries.js";
import { applyStageFiles, resetStageFiles, stageChoices, stageField, stageFieldValue } from "../modules/stage_files.js";
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
            || ((name === "catalog" || name === "catalog-beat") && link.dataset.route === "beats");
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

// Inline edit form used by files and final deliveries. Sends only the fields that changed.
function editPanel({ title, fields, note = "", onSave, onCancel }) {
    const form = element("form", "edit-panel");
    form.hidden = true;
    form.setAttribute("aria-label", title);
    const grid = element("div", "edit-panel__grid");
    const controls = new Map();
    fields.forEach(field => {
        const label = element("label", `portal-field${field.full ? " edit-panel__full" : ""}`);
        label.append(element("span", "portal-field__label", field.label));
        let control;
        if (field.type === "textarea") {
            control = element("textarea");
            control.rows = field.rows || 3;
        } else if (field.type === "stage") {
            control = element("select");
        } else {
            control = element("input");
            control.type = field.type || "text";
            if (field.min != null) control.min = String(field.min);
            if (field.max != null) control.max = String(field.max);
        }
        control.name = field.name;
        if (field.maxLength) control.maxLength = field.maxLength;
        if (field.required) control.required = true;
        label.append(control);
        if (field.help) label.append(element("small", "", field.help));
        grid.append(label);
        controls.set(field.name, { field, control, label });
    });
    const error = element("p", "edit-panel__error");
    error.setAttribute("role", "alert");
    const actions = element("div", "edit-panel__actions");
    const cancel = element("button", "btn-outline btn-small", "Cancelar");
    cancel.type = "button";
    const save = element("button", "btn-cta btn-small", "Salvar alterações");
    save.type = "submit";
    actions.append(cancel, save);
    form.append(grid);
    if (note) form.append(element("p", "edit-panel__note", note));
    form.append(error, actions);

    const initial = field => (field.value == null ? "" : String(field.value));
    const fill = () => {
        controls.forEach(({ field, control, label }) => {
            if (field.type === "stage") {
                const choices = stageChoices();
                label.hidden = choices.length === 0;
                control.replaceChildren(new Option("Geral (sem etapa)", ""), ...choices.map(choice => new Option(choice.label, String(choice.id))));
            }
            control.value = initial(field);
        });
        error.textContent = "";
    };
    const close = () => { form.hidden = true; onCancel?.(); };
    cancel.addEventListener("click", close);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const changes = {};
        controls.forEach(({ field, control }) => {
            if (control.value === initial(field)) return;
            const raw = control.value.trim();
            if (field.type === "stage" || field.type === "number") changes[field.name] = raw ? Number(raw) : null;
            else if (field.list) changes[field.name] = raw.split("\n").map(line => line.trim()).filter(Boolean);
            else changes[field.name] = raw;
        });
        if (!Object.keys(changes).length) { close(); return; }
        save.disabled = true;
        error.textContent = "";
        try {
            await onSave(changes);
        } catch (saveError) {
            error.textContent = saveError.message || "Não foi possível salvar.";
        } finally {
            save.disabled = false;
        }
    });
    return {
        element: form,
        open() {
            fill();
            form.hidden = false;
            form.querySelector("input, select, textarea")?.focus();
        },
    };
}

function fileItem(file, handlers) {
    const onDownload = handlers.onDownload;
    const item = element("li", "producer-file");
    item.dataset.etapaId = file.etapa_id == null ? "" : String(file.etapa_id);
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
    if (own && handlers.onEditFile) {
        // The producer corrects a file they sent: name, stage and note.
        const edit = element("button", "btn-outline btn-small", "Editar");
        edit.type = "button";
        edit.setAttribute("aria-label", `Editar ${file.nome_exibicao}`);
        const panel = editPanel({
            title: `Editar ${file.nome_exibicao}`,
            fields: [
                { name: "nome_exibicao", label: "Nome do arquivo", value: file.nome_exibicao, maxLength: 180, required: true },
                { name: "etapa_id", label: "Etapa", type: "stage", value: file.etapa_id },
                { name: "observacao", label: "Observação", type: "textarea", value: file.observacao || "", maxLength: 1000, full: true },
            ],
            onCancel: () => { edit.hidden = false; },
            onSave: values => handlers.onEditFile(file, values),
        });
        edit.addEventListener("click", () => { panel.open(); edit.hidden = true; });
        info.append(edit, panel.element);
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
    const actions = element("div", "producer-file__actions");
    actions.append(button);
    if (
        own
        && ["previa", "entrega"].includes(file.tipo)
        && !handlers.replacedIds?.has(file.id)
        && handlers.onDelete
    ) {
        const remove = element("button", "btn-small btn-danger", file.tipo === "previa" ? "Excluir prévia" : "Excluir arquivo");
        remove.type = "button";
        remove.addEventListener("click", () => handlers.onDelete(file, remove));
        actions.append(remove);
    }
    item.append(info, actions);
    if (handlers.onListen && podeOuvir(file) && file.processamento_tag !== "pendente") {
        info.append(controlesOuvir(file, {
            opcoes: opcoesEstudio(file),
            load: versao => handlers.onListen(file, versao),
            onError: error => setAlert(error.message, true),
        }));
    }
    return item;
}

function deliveryFilePicker(name, label, accept, required = false) {
    const wrapper = element("label", "final-delivery-form__field");
    wrapper.append(element("span", "", label));
    const input = element("input");
    input.type = "file";
    input.name = name;
    input.accept = accept;
    input.required = required;
    const picker = element("span", "producer-upload__picker");
    const button = element("span", "producer-upload__pick-button", "Escolher arquivo");
    const filename = element("span", "producer-upload__filename", "Nenhum arquivo selecionado");
    input.addEventListener("change", () => {
        filename.textContent = input.files[0]?.name || "Nenhum arquivo selecionado";
        filename.title = filename.textContent;
    });
    picker.append(input, button, filename);
    wrapper.append(picker);
    return { wrapper, input };
}

function deliveryCard(delivery, handlers) {
    const card = element("article", "final-delivery-card");
    card.dataset.etapaId = delivery.etapa_id == null ? "" : String(delivery.etapa_id);
    card.append(
        stageLabel(delivery),
        element("span", "final-delivery-card__type", delivery.categoria === "instrumental" ? "Beat exclusivo" : "Entrega final"),
        element("h3", "", delivery.titulo),
    );
    if (delivery.categoria === "instrumental" && delivery.bpm && delivery.tonalidade) {
        card.append(element("p", "file-note", `${delivery.bpm} BPM · ${delivery.tonalidade}`));
    }
    if (delivery.observacao) card.append(element("p", "file-note", delivery.observacao));
    // Listen to the MP3 and, when present, the WAV of the package without downloading.
    const sources = [[delivery.arquivo_principal, "MP3"], [delivery.wav_arquivo, "WAV"]]
        .filter(([file]) => file && podeOuvir(file));
    if (handlers.onListen && sources.length) {
        const byKey = new Map(sources.map(([file, label]) => [label, file]));
        card.append(controlesOuvir(sources[0][0], {
            opcoes: sources.map(([, label]) => ({ versao: label, rotulo: label })),
            load: key => handlers.onListen(byKey.get(key), null),
            onError: error => setAlert(error.message, true),
        }));
    }
    const actions = element("div", "final-delivery-card__actions");
    const addFile = (file, label) => {
        if (!file) return;
        const button = element("button", "btn-outline", label);
        button.type = "button";
        button.addEventListener("click", () => handlers.onDownload(file.id, button));
        actions.append(button);
    };
    addFile(delivery.arquivo_principal, delivery.categoria === "instrumental" ? "Baixar MP3" : "Baixar arquivo");
    addFile(delivery.wav_arquivo, "Baixar WAV");
    addFile(delivery.multitrack_arquivo, "Baixar multitrack");
    if (delivery.multitrack_disponivel && !delivery.multitrack_arquivo) {
        const link = element("button", "btn-outline", "Abrir multitrack");
        link.type = "button";
        link.addEventListener("click", () => handlers.onDeliveryLink(delivery, link));
        actions.append(link);
    }
    addFile(delivery.licenca_arquivo, "Baixar licença");
    card.append(actions, element("small", "", `Enviada em ${formatDate(delivery.created_at, true)}`));
    // Corrections by the producer: edit and delete, side by side below the files.
    const manage = element("div", "final-delivery-card__manage");
    if (handlers.onDeleteDelivery && !handlers.deliveryLocked) {
        const remove = element("button", "btn-small btn-danger final-delivery-card__delete", "Excluir entrega");
        remove.type = "button";
        remove.setAttribute("aria-label", `Excluir entrega ${delivery.titulo}`);
        remove.addEventListener("click", () => handlers.onDeleteDelivery(delivery, remove));
        manage.append(remove);
    }
    if (handlers.onEditDelivery && !handlers.deliveryLocked) {
        const instrumental = delivery.categoria === "instrumental";
        const edit = element("button", "btn-outline btn-small final-delivery-card__edit", "Editar entrega");
        edit.type = "button";
        edit.setAttribute("aria-label", `Editar entrega ${delivery.titulo}`);
        const panel = editPanel({
            title: `Editar entrega ${delivery.titulo}`,
            fields: [
                { name: "titulo", label: instrumental ? "Título do beat" : "Título da entrega", value: delivery.titulo, maxLength: 150, required: true, full: true },
                ...(instrumental ? [
                    { name: "bpm", label: "BPM", type: "number", value: delivery.bpm, min: 20, max: 300, required: true },
                    { name: "tonalidade", label: "Tom / Key", value: delivery.tonalidade, maxLength: 20, required: true },
                    { name: "creditos_adicionais", label: "Créditos adicionais", type: "textarea", list: true, full: true,
                      value: (delivery.creditos_adicionais || []).join("\n"), help: "Um nome por linha, até 10." },
                ] : []),
                { name: "etapa_id", label: "Etapa", type: "stage", value: delivery.etapa_id },
                { name: "observacao", label: "Observação", type: "textarea", value: delivery.observacao || "", maxLength: 1000, full: true },
            ],
            note: instrumental
                ? "Mudar título, BPM, tom ou créditos emite uma nova versão da licença. Para trocar arquivos, envie uma nova entrega."
                : "Para trocar arquivos, envie uma nova entrega.",
            onCancel: () => { edit.hidden = false; },
            onSave: changes => handlers.onEditDelivery(delivery, changes),
        });
        edit.addEventListener("click", () => { panel.open(); edit.hidden = true; });
        manage.prepend(edit);
        if (manage.children.length) card.append(manage);
        card.append(panel.element);
    } else if (manage.children.length) {
        card.append(manage);
    }
    return card;
}

function finalDeliveryForm(production, handlers) {
    const disclosure = element("details", "final-delivery-disclosure");
    disclosure.append(element("summary", "", "Enviar entrega final"));
    const form = element("form", "producer-upload final-delivery-form");
    const categoryLabel = element("label", "final-delivery-form__field");
    categoryLabel.append(element("span", "", "Tipo de entrega"));
    const category = element("select");
    category.name = "categoria";
    [["instrumental", "Beat exclusivo"], ["outro", "Outro tipo de entrega"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        category.append(option);
    });
    categoryLabel.append(category);
    const titleLabel = element("label", "final-delivery-form__field");
    const titleText = element("span", "", "Título do beat");
    titleLabel.append(titleText);
    const title = element("input");
    title.name = "titulo";
    title.maxLength = 150;
    title.required = true;
    titleLabel.append(title);
    const main = deliveryFilePicker("arquivo_principal", "MP3 final", ".mp3,audio/mpeg", true);
    const instrumental = element("div", "final-delivery-form__instrumental");
    const bpmLabel = element("label", "final-delivery-form__field");
    bpmLabel.append(element("span", "", "BPM"));
    const bpm = element("input");
    bpm.name = "bpm";
    bpm.type = "number";
    bpm.min = "20";
    bpm.max = "300";
    bpm.step = "1";
    bpmLabel.append(bpm);
    const keyLabel = element("label", "final-delivery-form__field");
    keyLabel.append(element("span", "", "Key / Tom"));
    const key = element("input");
    key.name = "tonalidade";
    key.maxLength = 20;
    key.placeholder = "Ex.: C# menor";
    keyLabel.append(key);
    const creditsLabel = element("label", "final-delivery-form__field final-delivery-form__full");
    creditsLabel.append(element("span", "", "Compositores/programadores adicionais (opcional)"));
    const credits = element("textarea");
    credits.name = "creditos_adicionais";
    credits.maxLength = 1200;
    credits.rows = 3;
    credits.placeholder = "Um nome por linha";
    creditsLabel.append(credits);
    const wav = deliveryFilePicker("wav", "WAV final", ".wav,audio/wav,audio/x-wav", true);
    const sourceLabel = element("label", "final-delivery-form__field");
    sourceLabel.append(element("span", "", "Origem do multitrack"));
    const source = element("select");
    source.name = "multitrack_origem";
    [["link", "Link HTTPS"], ["arquivo", "Arquivo ZIP ou RAR"]].forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        source.append(option);
    });
    sourceLabel.append(source);
    const linkLabel = element("label", "final-delivery-form__field");
    linkLabel.append(element("span", "", "Link HTTPS do multitrack"));
    const multitrackUrl = element("input");
    multitrackUrl.type = "url";
    multitrackUrl.name = "multitrack_url";
    multitrackUrl.maxLength = 2000;
    multitrackUrl.placeholder = "https://drive.google.com/...";
    linkLabel.append(multitrackUrl);
    const archive = deliveryFilePicker("multitrack", "Multitrack", ".zip,.rar,application/zip,application/vnd.rar");
    const licenseHint = element(
        "p",
        "final-delivery-form__hint",
        "A licença exclusiva, em nome do cliente, será gerada automaticamente.",
    );
    instrumental.append(bpmLabel, keyLabel, creditsLabel, wav.wrapper, sourceLabel, linkLabel, archive.wrapper, licenseHint);
    const noteLabel = element("label", "final-delivery-form__field final-delivery-form__full");
    noteLabel.append(element("span", "", "Observação (opcional)"));
    const note = element("textarea");
    note.name = "observacao";
    note.maxLength = 1000;
    note.rows = 3;
    noteLabel.append(note);
    const hint = element("p", "final-delivery-form__hint", "Os arquivos e o link ficam privados e são liberados ao cliente conforme a situação financeira da produção.");
    const submit = element("button", "btn-cta", "Enviar pacote final");
    submit.type = "submit";

    const sync = () => {
        const isInstrumental = category.value === "instrumental";
        instrumental.hidden = !isInstrumental;
        [...instrumental.querySelectorAll("input, select, textarea")].forEach(field => { field.disabled = !isInstrumental; });
        main.wrapper.querySelector("span").textContent = isInstrumental ? "MP3 final" : "Arquivo principal";
        titleText.textContent = isInstrumental ? "Título do beat" : "Título da entrega";
        main.input.accept = isInstrumental ? ".mp3,audio/mpeg" : ".pdf,.zip,.rar,.mp3,.wav,.flac,.m4a,.mp4";
        const byLink = source.value === "link";
        linkLabel.hidden = !byLink;
        multitrackUrl.disabled = !isInstrumental || !byLink;
        multitrackUrl.required = isInstrumental && byLink;
        archive.wrapper.hidden = byLink;
        archive.input.disabled = !isInstrumental || byLink;
        archive.input.required = isInstrumental && !byLink;
        wav.input.required = isInstrumental;
        bpm.required = isInstrumental;
        key.required = isInstrumental;
    };
    category.addEventListener("change", sync);
    source.addEventListener("change", sync);
    sync();
    const stage = stageField("final-delivery-form__field");
    form.append(categoryLabel, titleLabel, stage, main.wrapper, instrumental, noteLabel, hint, submit);
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const data = new FormData(form);
        data.delete("multitrack_origem");
        if (!stageFieldValue(form)) data.delete("etapa_id");
        data.set("request_id", crypto.randomUUID());
        handlers.onDelivery(production, data, submit, form, disclosure);
    });
    disclosure.append(form);
    return disclosure;
}

function filesPanel(production, files, deliveries, handlers) {
    const panel = element("section", "producer-files");
    panel.append(element("h2", "", "Arquivos e entregas"));
    const stageFilter = element("div", "stage-filter hidden");
    stageFilter.dataset.stageFilter = "";
    panel.append(stageFilter);
    if (deliveries.length) {
        // Delivered to the client: the delivery is final and can no longer be edited.
        const deliveryHandlers = { ...handlers, deliveryLocked: production.status === "entregue" || production.coordenador === false };
        panel.append(deliveriesSection(deliveries, delivery => deliveryCard(delivery, deliveryHandlers), {
            help: "A versão final de cada etapa. Enviar outra entrega final para a mesma etapa substitui a anterior.",
        }));
    }
    const linkedIds = new Set(deliveries.flatMap(delivery => [
        delivery.arquivo_principal?.id,
        delivery.wav_arquivo?.id,
        delivery.multitrack_arquivo?.id,
        delivery.licenca_arquivo?.id,
    ]).filter(Boolean));
    // Older versions of a delivery file (a reissued license) stay with the delivery.
    let grew = true;
    while (grew) {
        grew = false;
        files.forEach(file => {
            if (linkedIds.has(file.id) && file.substitui_arquivo_id != null && !linkedIds.has(file.substitui_arquivo_id)) {
                linkedIds.add(file.substitui_arquivo_id);
                grew = true;
            }
        });
    }
    const looseFiles = files.filter(file => !linkedIds.has(file.id));
    const replaced = new Set(files.map(file => file.substitui_arquivo_id).filter(id => id != null));
    const fileHandlers = { ...handlers, replacedIds: replaced };
    const list = element("ul", "producer-file-list");
    list.dataset.stageGroup = "";
    if (!looseFiles.length && !deliveries.length) list.append(element("li", "producer-empty", "Nenhum arquivo disponível."));
    else looseFiles.forEach(file => list.append(fileItem(file, fileHandlers)));
    if (looseFiles.length) panel.append(element("h3", "producer-files__subtitle", "Prévias e arquivos"));
    panel.append(list);

    const form = element("form", "producer-upload");
    const type = element("select");
    [["previa", "Prévia"]].forEach(([value, label]) => {
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
    // Visible captions; the controls keep their accessible names (aria-label).
    const field = (caption, control, className = "") => {
        const wrapper = element("div", `portal-field ${className}`.trim());
        wrapper.append(element("span", "portal-field__label", caption), control);
        return wrapper;
    };
    form.classList.add("producer-preview-form");
    const stage = stageField();
    form.append(
        field("Tipo", type),
        stage,
        field("Arquivo", filePicker),
        field("Substitui", replaces),
        quotaHint,
        field("Observação (opcional)", note, "portal-field--full"),
        submit,
    );
    form.addEventListener("submit", event => {
        event.preventDefault();
        if (input.files[0]) handlers.onUpload(production, input.files[0], type.value, replaces.value || null, submit, note.value, stageFieldValue(form));
    });
    const uploadDisclosure = element("details", "final-delivery-disclosure");
    uploadDisclosure.append(element("summary", "", "Enviar prévia"), form);
    panel.append(finalDeliveryForm(production, handlers), uploadDisclosure);
    return panel;
}

export function renderDetail(production, files, deliveriesOrHandlers, maybeHandlers) {
    const deliveries = Array.isArray(deliveriesOrHandlers) ? deliveriesOrHandlers : [];
    const handlers = maybeHandlers || deliveriesOrHandlers;
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
    resetStageFiles(production.id);
    detail.append(filesPanel(production, files, deliveries, handlers), messagesSlot);
    root.append(detail);
    applyStageFiles(root);
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
