import { renderAdminState } from "../ui.js";

const LABELS = {
    site: "Site", email: "E-mail", open: "Aberta", waiting_human: "Aguardando atendimento", closed: "Encerrada",
    autonomous: "Autônomo", copilot: "Copiloto", human: "Humano",
    manual_request: "Solicitação de atendente", provider_failure: "Falha do provedor", low_confidence: "Baixa confiança",
    tool_failure: "Falha de ferramenta", negotiation: "Negociação", discount: "Desconto", payment_issue: "Problema de pagamento",
    custom_pricing: "Preço personalizado", complaint: "Reclamação", other: "Outro motivo",
    service_or_interest: "serviço ou interesse", contact_name: "nome", contact_email: "e-mail",
};

function label(value) { return LABELS[value] || value || "Não informado"; }

function text(tag, value, className = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value ?? "";
    return element;
}

function badge(value, variant = "neutral") {
    const element = text("span", label(value), `admin-badge admin-badge--${variant}`);
    return element;
}

function button(value, className = "btn-small") {
    const element = text("button", value, className);
    element.type = "button";
    return element;
}

function statusVariant(status) {
    return status === "waiting_human" ? "warning" : status === "closed" ? "neutral" : "info";
}

function modeVariant(mode) { return mode === "copilot" ? "info" : mode === "human" ? "warning" : "neutral"; }

function formattedDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

export function renderList(container, page, handlers) {
    container.replaceChildren();
    if (!page.items.length) {
        renderAdminState(container, "empty", "Nenhuma conversa encontrada.");
        return;
    }
    const list = document.createElement("div");
    list.className = "inbox-conversation-list";
    page.items.forEach((item) => {
        const article = document.createElement("article");
        article.className = "inbox-conversation-item";
        article.dataset.conversationId = item.id;
        if (handlers.selectedId === item.id) article.classList.add("is-selected");
        const header = document.createElement("div");
        header.className = "inbox-conversation-item__header";
        header.append(text("strong", item.cliente_nome || item.email_subject || `Conversa ${item.id.slice(0, 8)}`));
        header.append(badge(item.channel, "neutral"), badge(item.status, statusVariant(item.status)));
        const meta = text("p", item.last_message_preview || "Sem mensagens", "inbox-conversation-item__preview");
        const details = text("p", `${label(item.mode)} · ${item.assigned_username || "Não assumida"}`, "inbox-conversation-item__meta");
        const time = text("time", formattedDate(item.last_message_at || item.updated_at), "inbox-conversation-item__meta");
        time.dateTime = item.last_message_at || item.updated_at;
        if (item.handoff_reason) article.append(badge(item.handoff_reason, "warning"));
        const open = button("Abrir conversa");
        open.setAttribute("aria-label", `Abrir conversa ${item.cliente_nome || item.id}`);
        open.addEventListener("click", () => handlers.onOpen(item.id));
        article.append(header, meta, details, time, open);
        list.appendChild(article);
    });
    container.appendChild(list);
}

export function renderPagination(container, page, onPage) {
    container.replaceChildren();
    if (page.pages <= 1) { container.classList.add("hidden"); return; }
    container.classList.remove("hidden");
    const previous = button("Anterior");
    previous.disabled = page.page <= 1;
    previous.addEventListener("click", () => onPage(page.page - 1));
    const current = text("span", `Página ${page.page} de ${page.pages}`, "inbox-pagination__label");
    const next = button("Próxima");
    next.disabled = page.page >= page.pages;
    next.addEventListener("click", () => onPage(page.page + 1));
    container.append(previous, current, next);
}

function createMessage(message, handlers) {
    const article = document.createElement("article");
    article.className = `inbox-message inbox-message--${message.direction} inbox-message--${message.kind}`;
    article.append(
        text("strong", message.kind === "suggestion" ? "Sugestão da IA" : message.kind === "reply" ? "IA" : message.direction === "inbound" ? "Cliente" : "Atendente"),
        text("p", message.content),
    );
    if (message.delivery === "pending") {
        article.append(text("small", "Aguardando confirmação de envio"));
        if (message.kind === "message") {
            const retry = button("Tentar enviar novamente");
            retry.disabled = !handlers.canAct || handlers.sending;
            retry.addEventListener("click", () => handlers.onRetry(message.id));
            article.appendChild(retry);
        }
    }
    return article;
}

export function renderDetail(container, detail, handlers) {
    container.replaceChildren();
    if (!detail) return;
    const header = document.createElement("header");
    header.className = "inbox-detail__header";
    const title = text("h2", detail.cliente_nome || detail.email_subject || `Conversa ${detail.id.slice(0, 8)}`);
    title.id = "inbox-detail-title";
    const close = button("Fechar painel", "btn-small btn-outline");
    close.addEventListener("click", handlers.onBack);
    header.append(title, close);
    const summary = document.createElement("div");
    summary.className = "inbox-detail__summary";
    summary.append(badge(detail.channel), badge(detail.status, statusVariant(detail.status)), badge(detail.mode, modeVariant(detail.mode)));
    if (detail.handoff_reason) summary.append(badge(detail.handoff_reason, "warning"));
    summary.append(text("p", detail.cliente_email || detail.sender_reference || "Contato não identificado"));

    const briefing = document.createElement("section");
    briefing.className = "inbox-briefing";
    briefing.append(text("h3", "Briefing"));
    if (detail.briefing) {
        const data = detail.briefing;
        briefing.append(badge(data.status === "submitted" ? "Enviado" : "Rascunho", data.status === "submitted" ? "success" : "info"));
        const fields = [
            ["Serviço", data.service_name || data.interest], ["Nome", data.contact_name],
            ["E-mail", data.contact_email], ["Telefone", data.contact_phone],
            ["Tipo de projeto", data.details?.project_type], ["Estilo", data.details?.style],
            ["Faixas/stems", data.details?.track_count], ["Prazo desejado", data.details?.requested_deadline],
            ["Objetivo", data.details?.goal], ["Referências", data.details?.references?.join(", ")],
            ["Detalhes", data.details?.notes], ["Orçamento", data.orcamento_id ? `#${data.orcamento_id}` : null],
        ];
        fields.filter(([, value]) => value !== null && value !== undefined && value !== "")
            .forEach(([name, value]) => briefing.append(text("p", `${name}: ${value}`)));
        if (data.missing_fields?.length) briefing.append(text("p", `Faltam: ${data.missing_fields.map(label).join(", ")}`));
    } else briefing.append(text("p", "Briefing ainda não iniciado."));

    const actions = document.createElement("div");
    actions.className = "inbox-detail__actions";
    if (!detail.assigned_user_id) {
        const assign = button("Assumir atendimento", "btn-cta");
        assign.addEventListener("click", handlers.onAssign);
        actions.appendChild(assign);
    }
    const mode = document.createElement("select");
    mode.id = "inbox-mode-select";
    mode.disabled = detail.status === "closed" || !handlers.canAct;
    ["autonomous", "copilot", "human"].forEach((value) => {
        const option = text("option", label(value)); option.value = value; option.selected = value === detail.mode;
        option.disabled = value === "autonomous" && detail.mode !== "autonomous";
        mode.appendChild(option);
    });
    mode.addEventListener("change", () => handlers.onMode(mode.value));
    const modeLabel = text("label", "Modo", "inbox-mode-label");
    modeLabel.htmlFor = mode.id;
    actions.append(modeLabel, mode);
    if (detail.mode === "copilot") {
        const suggest = button("Gerar sugestão", "btn-small");
        suggest.disabled = detail.status === "closed" || !handlers.canAct || handlers.suggesting;
        suggest.addEventListener("click", handlers.onSuggest);
        actions.appendChild(suggest);
    }
    const currentSuggestion = [...detail.messages].reverse().find((message) => message.kind === "suggestion");
    if (currentSuggestion) {
        const regenerate = button("Regenerar sugestão");
        regenerate.disabled = !handlers.canAct || handlers.suggesting;
        regenerate.addEventListener("click", handlers.onSuggest);
        const ignore = button("Ignorar sugestão");
        ignore.disabled = !handlers.canAct || handlers.suggesting;
        ignore.addEventListener("click", () => handlers.onIgnore(currentSuggestion.id));
        actions.append(regenerate, ignore);
    }
    const closeConversation = button("Encerrar", "btn-small btn-danger");
    closeConversation.disabled = detail.status === "closed" || !handlers.canAct;
    closeConversation.addEventListener("click", handlers.onClose);
    actions.appendChild(closeConversation);

    const messages = document.createElement("div");
    messages.className = "inbox-messages";
    if (detail.has_more_messages) {
        const older = button("Carregar anteriores");
        older.addEventListener("click", () => handlers.onOlder(detail.next_before));
        messages.appendChild(older);
    }
    detail.messages.forEach((message) => messages.appendChild(createMessage(message, handlers)));
    const composer = document.createElement("form");
    composer.className = "inbox-composer";
    const textarea = document.createElement("textarea");
    textarea.id = "inbox-reply-text";
    textarea.maxLength = 8000;
    textarea.placeholder = "Escreva uma resposta...";
    const suggestion = currentSuggestion;
    if (suggestion) textarea.value = suggestion.content;
    const send = button("Enviar resposta", "btn-cta");
    send.type = "submit";
    send.disabled = detail.status === "closed" || !handlers.canAct || handlers.sending;
    textarea.disabled = send.disabled;
    const replyLabel = text("label", "Resposta humana");
    replyLabel.htmlFor = textarea.id;
    composer.append(replyLabel, textarea, send);
    composer.addEventListener("submit", (event) => {
        event.preventDefault();
        handlers.onSend(textarea.value, suggestion?.id || null);
    });
    container.append(header, summary, briefing, actions, messages, composer);
}

export function renderError(container, message) { renderAdminState(container, "error", message); }
