// Roadmap 3.0, 5.03: message thread of a production, shared by the three portals.
// Everything is rendered as text; the server enforces visibility and ownership.

const AUTHOR_LABELS = {
    cliente: { cliente: "Você", produtor: "Produção", admin: "Equipe Mirai" },
    produtor: { cliente: "Cliente", produtor: "Produtor", admin: "Equipe Mirai" },
    admin: { cliente: "Cliente", produtor: "Produtor", admin: "Equipe Mirai" },
};

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function formatDateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? ""
        : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function authorLabel(role, message) {
    if (message.enviado_por_mim) return "Você";
    return AUTHOR_LABELS[role]?.[message.autor_papel] || "Equipe";
}

/**
 * Builds the messages panel.
 * options: { role, messages, files, onSend(payload) -> Promise<void>, error }
 * `files` are the files the viewer can already see (used for the optional link).
 */
export function messagesPanel({ role, messages, files = [], onSend, error = "", heading = true }) {
    const panel = element("section", "production-messages");
    panel.setAttribute("aria-label", "Mensagens da produção");
    if (heading) panel.append(element("h2", "", "Mensagens"));

    if (error) panel.append(element("p", "production-messages__error", error));

    const byId = new Map(messages.map(item => [item.id, item]));
    const list = element("ol", "production-messages__list");
    if (!messages.length) list.append(element("li", "production-messages__empty", "Nenhuma mensagem ainda."));
    let replyTo = null;
    const replyBanner = element("p", "production-messages__replying hidden");

    messages.forEach(message => {
        const item = element("li", "production-message");
        if (message.enviado_por_mim) item.classList.add("production-message--mine");
        if (message.audiencia === "equipe") item.classList.add("production-message--team");
        const header = element("p", "production-message__meta");
        header.append(element("strong", "", authorLabel(role, message)), element("span", "", formatDateTime(message.created_at)));
        if (message.audiencia === "equipe") header.append(element("span", "production-message__badge", "Interna"));
        item.append(header);
        const parent = message.responde_a_id ? byId.get(message.responde_a_id) : null;
        if (parent) {
            const quote = parent.texto.length > 90 ? `${parent.texto.slice(0, 90)}…` : parent.texto;
            item.append(element("p", "production-message__quote", `Em resposta a: ${quote}`));
        }
        item.append(element("p", "production-message__text", message.texto));
        if (message.arquivo) {
            item.append(element(
                "p",
                "production-message__file",
                `Arquivo: ${message.arquivo.nome_exibicao} (v${message.arquivo.versao})`,
            ));
        }
        const reply = element("button", "btn-outline production-message__reply", "Responder");
        reply.type = "button";
        reply.addEventListener("click", () => {
            replyTo = message;
            replyBanner.textContent = `Respondendo a ${authorLabel(role, message)}: ${message.texto.slice(0, 60)}`;
            replyBanner.classList.remove("hidden");
            textarea.focus();
        });
        item.append(reply);
        list.append(item);
    });
    panel.append(list);

    const form = element("form", "production-messages__form");
    const textarea = element("textarea", "production-messages__input");
    textarea.rows = 3;
    textarea.maxLength = 2000;
    textarea.required = true;
    textarea.setAttribute("aria-label", "Escreva uma mensagem");
    textarea.placeholder = "Escreva uma mensagem";

    const fileSelect = element("select");
    fileSelect.setAttribute("aria-label", "Anexar referência a um arquivo");
    fileSelect.append(new Option("Sem arquivo", ""));
    files.forEach(file => fileSelect.append(new Option(`${file.nome_exibicao} (v${file.versao})`, String(file.id))));

    const controls = element("div", "production-messages__controls");
    controls.append(fileSelect);
    let audience = null;
    if (role !== "cliente") {
        audience = element("select");
        audience.setAttribute("aria-label", "Quem pode ver");
        audience.append(new Option("Visível ao cliente", "todos"), new Option("Interna (só equipe)", "equipe"));
        controls.append(audience);
    }
    const cancelReply = element("button", "btn-outline", "Cancelar resposta");
    cancelReply.type = "button";
    cancelReply.addEventListener("click", () => {
        replyTo = null;
        replyBanner.classList.add("hidden");
    });
    replyBanner.append(" ", cancelReply);
    const submit = element("button", "btn-cta", "Enviar mensagem");
    submit.type = "submit";
    controls.append(submit);
    const feedback = element("p", "production-messages__feedback");
    feedback.setAttribute("role", "status");

    form.append(replyBanner, textarea, controls, feedback);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        const texto = textarea.value.trim();
        if (!texto || form.dataset.busy === "true") return;
        form.dataset.busy = "true";
        submit.disabled = true;
        feedback.textContent = "Enviando...";
        try {
            await onSend({
                texto,
                audiencia: audience ? audience.value : "todos",
                responde_a_id: replyTo ? replyTo.id : null,
                arquivo_id: fileSelect.value ? Number(fileSelect.value) : null,
            });
        } catch (sendError) {
            feedback.textContent = sendError.message || "Não foi possível enviar a mensagem.";
        } finally {
            form.dataset.busy = "false";
            submit.disabled = false;
        }
    });
    panel.append(form);
    return panel;
}
