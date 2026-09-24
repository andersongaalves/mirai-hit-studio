function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text) node.textContent = text;
    return node;
}

function button(text, className = "btn-small") {
    const node = element("button", className, text);
    node.type = "button";
    return node;
}

export function createChatView() {
    const launcher = button("Assistente Mirai", "site-chat-launcher btn-small");
    launcher.id = "site-chat-launcher";
    launcher.setAttribute("aria-controls", "site-chat");
    launcher.setAttribute("aria-expanded", "false");
    launcher.setAttribute("aria-haspopup", "dialog");
    const dialog = element("dialog", "site-chat");
    dialog.id = "site-chat";
    dialog.setAttribute("aria-labelledby", "site-chat-title");
    const header = element("header", "site-chat-header");
    const title = element("h2", "", "Assistente Mirai");
    title.id = "site-chat-title";
    title.tabIndex = -1;
    const close = button("Fechar");
    header.append(title, close);
    const intro = element("p", "site-chat-intro", "Atendimento por IA. Contato informado para orçamento é usado só para responder ao pedido, não para newsletter. Não envie dados de pagamento.");
    const messages = element("ol", "site-chat-messages");
    messages.setAttribute("aria-label", "Mensagens da conversa");
    messages.setAttribute("role", "log");
    messages.setAttribute("aria-live", "polite");
    const status = element("p", "site-chat-status");
    status.setAttribute("role", "status");
    const form = element("form", "site-chat-form");
    const label = element("label", "", "Sua mensagem");
    label.htmlFor = "site-chat-message";
    const input = element("textarea", "textarea");
    input.id = "site-chat-message";
    input.maxLength = 4000;
    input.rows = 2;
    input.required = true;
    const actions = element("div", "site-chat-actions");
    const send = button("Enviar", "btn-cta");
    send.type = "submit";
    const retry = button("Tentar novamente");
    retry.hidden = true;
    const fresh = button("Nova conversa");
    actions.append(send, retry, fresh);
    form.append(label, input, actions);
    dialog.append(header, intro, messages, status, form);
    document.body.append(launcher, dialog);
    function append(role, text, id, sender = "ai") {
        const key = id ? `${role}:${id}` : null;
        if (key && [...messages.children].some(row => row.dataset.messageKey === key)) return;
        const nearBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 80;
        const row = element("li", `site-chat-message site-chat-message--${role === "user" ? "user" : "assistant"}`);
        if (key) row.dataset.messageKey = key;
        row.append(element("strong", "", role === "user" ? "Você" : sender === "human" ? "Atendimento Mirai" : "Assistente Mirai"), element("p", "", text));
        messages.append(row);
        if (nearBottom) messages.scrollTop = messages.scrollHeight;
    }
    return { launcher, dialog, title, close, messages, status, form, input, send, retry, fresh, append };
}
