// "Orçamentos" > receiving switch: pauses new quote requests from the site (calculator and
// assistant) while the studio has too many projects, with an optional message shown to
// visitors. Existing requests, proposals and productions are not affected.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { confirmarAcao } from "../../modules/confirm_dialog.js";

const MAX = 500;

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

async function request(method, body) {
    const response = await authFetch("/orcamentos/recebimento", {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail?.message || data?.detail || "Não foi possível atualizar o recebimento de pedidos.");
    return data;
}

function desde(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function render(root, estado, padrao) {
    const pausado = Boolean(estado.pausado);
    root.removeAttribute("aria-busy");
    root.classList.toggle("is-paused", pausado);

    const status = el("div", "admin-intake__status");
    const dot = el("span", "admin-intake__dot");
    dot.setAttribute("aria-hidden", "true");
    const text = el("div", "admin-intake__text");
    const title = el("h2", "", pausado ? "Novos pedidos pausados" : "Recebendo pedidos");
    title.id = "orcamentos-recebimento-title";
    const when = desde(estado.desde);
    text.append(title, el("p", "", pausado
        ? `A calculadora e o assistente mostram o aviso abaixo em vez do formulário${when ? ` (desde ${when})` : ""}. Pedidos, propostas e produções em andamento seguem normalmente.`
        : "A calculadora e o assistente do site aceitam novos pedidos de orçamento. Pause quando houver projetos demais em andamento."));
    status.append(dot, text);

    const field = el("label", "admin-intake__field");
    const message = el("textarea");
    message.id = "orcamentos-pausa-mensagem";
    message.rows = 3;
    message.maxLength = MAX;
    message.placeholder = padrao;
    message.value = estado.mensagem_personalizada || "";
    const counter = el("small", "admin-intake__counter");
    const count = () => { counter.textContent = `${message.value.length}/${MAX}`; };
    message.addEventListener("input", count);
    count();
    field.append(el("span", "", "Aviso para os visitantes"), message,
        el("small", "", "Opcional. Em branco, o site usa a mensagem padrão mostrada aqui."), counter);

    const actions = el("div", "admin-intake__actions");
    const toggle = el("button", pausado ? "btn-cta" : "btn-outline admin-intake__pause", pausado ? "Retomar pedidos" : "Pausar novos pedidos");
    toggle.type = "button";
    actions.append(toggle);
    let save = null;
    if (pausado) {
        save = el("button", "btn-outline", "Salvar aviso");
        save.type = "button";
        actions.append(save);
    }
    const busy = value => [toggle, save].forEach(button => { if (button) button.disabled = value; });

    async function send(nextPaused, successMessage) {
        busy(true);
        try {
            const atualizado = await request("PUT", { pausado: nextPaused, mensagem: message.value.trim() || null });
            render(root, atualizado, padrao);
            Notify.success(successMessage);
        } catch (error) {
            Notify.error(error.message);
            busy(false);
        }
    }

    toggle.addEventListener("click", async () => {
        if (!pausado) {
            const ok = await confirmarAcao({
                titulo: "Pausar novos pedidos?",
                consequencias: [
                    "A calculadora mostra o aviso de agenda cheia no lugar do formulário.",
                    "O assistente do site deixa de registrar novos briefings.",
                    "Pedidos, propostas e produções já existentes não mudam.",
                ],
                palavra: null,
                botao: "Pausar pedidos",
                tom: "aviso",
            });
            if (!ok) return;
            await send(true, "Novos pedidos pausados.");
        } else {
            await send(false, "Pedidos retomados.");
        }
    });
    save?.addEventListener("click", () => send(true, "Aviso atualizado."));

    root.replaceChildren(status, field, actions);
}

export async function initRecebimento() {
    const root = document.getElementById("orcamentos-recebimento");
    if (!root || root.dataset.initialized) return;
    root.dataset.initialized = "true";
    try {
        const estado = await request("GET");
        render(root, estado, estado.mensagem_padrao || "");
    } catch (error) {
        root.removeAttribute("aria-busy");
        root.dataset.initialized = "";
        root.replaceChildren(el("p", "admin-intake__error", error.message));
    }
}
