import { track } from "../analytics.js";
import { chatRequest } from "./chat_api.js";
import { createChatView } from "./chat_dom.js";

const SESSION_KEY = "mirai.site_chat.v1";
const WAITING = "Esta conversa precisa de atendimento humano e ficou registrada. A equipe ainda não é notificada por este chat. Use a página de contato para falar com a Mirai.";

function readSession() {
    try {
        const data = JSON.parse(sessionStorage.getItem(SESSION_KEY));
        if (/^[\w-]{43}$/.test(data?.token) && Date.parse(data.expiresAt) > Date.now()) return data;
    } catch { /* Storage unavailable: keep the conversation only in memory. */ }
    return null;
}

export function initSiteChat() {
    if (document.getElementById("site-chat-launcher")) return;
    const view = createChatView();
    // Keep the launcher above consent/preferences without making chat depend on consent.
    const positionLauncher = () => {
        const banner = document.getElementById("analytics-consent-dialog");
        const rect = banner?.getBoundingClientRect();
        const overlaps = rect && rect.left < view.launcher.getBoundingClientRect().right;
        view.launcher.style.bottom = `${overlaps ? Math.max(76, innerHeight - rect.top + 12) : 76}px`;
    };
    const resize = new ResizeObserver(positionLauncher);
    resize.observe(document.body);
    const consentChanges = new MutationObserver(() => {
        const banner = document.getElementById("analytics-consent-dialog");
        if (banner) resize.observe(banner);
        positionLauncher();
    });
    consentChanges.observe(document.body, { childList: true });
    window.addEventListener("resize", positionLauncher);
    positionLauncher();
    let session = readSession(), pending = session?.pending || null;
    let busy = false, loaded = false, state = "open", retryAction = null;
    function persist() {
        try {
            if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...session, pending }));
            else sessionStorage.removeItem(SESSION_KEY);
        } catch { /* The current page still works without persistent storage. */ }
    }
    function controls() {
        view.input.disabled = busy || !loaded || state !== "open" || Boolean(pending);
        view.send.disabled = view.input.disabled || !view.input.value.trim();
        view.fresh.disabled = busy;
        view.retry.hidden = !retryAction || busy;
        view.form.setAttribute("aria-busy", String(busy));
    }
    function failure(error, retry) {
        if (error.status === 401) {
            session = null; pending = null; loaded = false; persist();
            view.messages.replaceChildren();
            view.status.textContent = "Sua sessão expirou. Inicie uma nova conversa.";
            retryAction = null;
        } else {
            view.status.textContent = error.status === 429 ? "Muitas tentativas. Aguarde um minuto e tente novamente."
                : "Não foi possível responder agora. Tente novamente.";
            retryAction = retry;
        }
    }
    async function load(fresh = false) {
        if (busy) return;
        busy = true; retryAction = null; controls();
        view.status.textContent = "Carregando conversa...";
        try {
            if (!session || fresh) {
                const result = await chatRequest("session", { payload: {} });
                session = { token: result.session_token, expiresAt: result.expires_at };
                pending = null; persist();
            }
            const history = await chatRequest("history", { token: session.token });
            view.messages.replaceChildren();
            for (const message of history.messages) view.append(message.role, message.text, message.message_id);
            if (pending && history.messages.some(message => message.role === "assistant" && message.message_id === pending.message_id)) {
                pending = null; persist();
            }
            state = history.status; loaded = true;
            if (state !== "open") { pending = null; persist(); }
            view.status.textContent = state === "waiting_human" ? WAITING : state === "closed"
                ? "Conversa encerrada. Você pode iniciar uma nova conversa."
                : pending ? "Há uma mensagem sem confirmação. Tente novamente para conferir a resposta."
                : "Como posso ajudar com seu projeto de áudio?";
            if (pending) retryAction = send;
        } catch (error) {
            failure(error, () => load(fresh));
        } finally {
            busy = false; controls();
        }
    }
    async function send() {
        if (busy || !loaded || state !== "open") return;
        const text = view.input.value.trim();
        if (!pending && (!text || text.length > 4000)) return;
        if (!pending) {
            pending = { message_id: crypto.randomUUID(), message: text };
            persist(); view.append("user", text, pending.message_id); view.input.value = "";
        }
        busy = true; retryAction = null; controls();
        view.status.textContent = "Pensando...";
        try {
            const result = await chatRequest("messages", { token: session.token, payload: pending });
            if (result.action === "error") throw new Error("response_unavailable");
            if (result.text) view.append("assistant", result.text, pending.message_id);
            state = result.status; pending = null; persist();
            track("ai_chat_message");
            view.status.textContent = state === "waiting_human" ? WAITING : state === "closed"
                ? "Conversa encerrada. Inicie uma nova conversa." : "";
            if (result.action === "handoff") track("ai_chat_handoff");
        } catch (error) {
            if (error.status === 409) {
                try {
                    const history = await chatRequest("history", { token: session.token });
                    if (history.status !== "open") {
                        state = history.status; pending = null; persist();
                        view.status.textContent = state === "waiting_human" ? WAITING : "Conversa encerrada. Inicie uma nova conversa.";
                        return;
                    }
                } catch { /* Keep the same pending ID if the status cannot be checked. */ }
            }
            failure(error, send);
        } finally {
            busy = false; controls();
            if (view.dialog.open && !view.input.disabled) view.input.focus({ preventScroll: true });
        }
    }
    view.launcher.addEventListener("click", () => {
        view.dialog.showModal();
        view.launcher.setAttribute("aria-expanded", "true");
        view.title.focus();
        track("ai_chat_open");
        if (!loaded) load();
    });
    view.close.addEventListener("click", () => view.dialog.close());
    view.dialog.addEventListener("keydown", event => {
        if (event.key !== "Tab") return;
        const focusable = [...view.dialog.querySelectorAll("button,textarea")]
            .filter(node => !node.disabled && !node.hidden && node.getClientRects().length);
        const first = focusable[0], last = focusable.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === view.title)) {
            event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault(); first?.focus();
        }
    });
    view.dialog.addEventListener("close", () => {
        view.launcher.setAttribute("aria-expanded", "false");
        view.launcher.focus({ preventScroll: true });
    });
    view.form.addEventListener("submit", event => { event.preventDefault(); send(); });
    view.input.addEventListener("input", controls);
    view.input.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); }
    });
    view.retry.addEventListener("click", () => retryAction?.());
    view.fresh.addEventListener("click", () => load(true));
    controls();
}
