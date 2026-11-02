// Pop-ups sent by the Admin: a small centered box with an X in the corner. The same
// builder renders the Admin's live preview, so what is previewed is what is shown.
import { authFetch } from "../admin/auth.js";

const SEEN_PREFIX = "mirai.popup.sessao.";

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function safeLink(url) {
    const value = String(url || "").trim();
    if (value.startsWith("https://")) return { href: value, external: true };
    if (value.startsWith("/") && !value.startsWith("//")) return { href: value, external: false };
    return null;
}

/** popup: { titulo, mensagem, tema, tamanho, botao_rotulo, botao_url }. */
export function buildPopup(popup, { preview = false, onClose } = {}) {
    const box = el("div", `portal-popup portal-popup--${popup.tema || "ciano"} portal-popup--${popup.tamanho || "pequeno"}`);
    const titleId = `portal-popup-title-${popup.id ?? "preview"}`;
    box.setAttribute("role", preview ? "group" : "dialog");
    if (!preview) box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", titleId);
    const close = el("button", "portal-popup__close");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.textContent = "×";
    const title = el("h2", "portal-popup__title", popup.titulo || "Título do pop-up");
    title.id = titleId;
    const message = el("p", "portal-popup__message", popup.mensagem || "Mensagem do pop-up.");
    box.append(close, title, message);
    const link = safeLink(popup.botao_url);
    if (popup.botao_rotulo && link) {
        const action = el("a", "btn-cta portal-popup__action", popup.botao_rotulo);
        action.href = link.href;
        if (link.external) {
            action.target = "_blank";
            action.rel = "noopener noreferrer";
        }
        if (preview) action.addEventListener("click", event => event.preventDefault());
        else action.addEventListener("click", () => onClose?.());
        box.append(action);
    }
    close.addEventListener("click", () => onClose?.());
    if (preview) return box;
    const overlay = el("div", "portal-popup-overlay");
    overlay.append(box);
    overlay.addEventListener("click", event => { if (event.target === overlay) onClose?.(); });
    return overlay;
}

function seenThisSession(popup) {
    try { return sessionStorage.getItem(SEEN_PREFIX + popup.id) === "1"; } catch { return false; }
}

function markSession(popup) {
    try { sessionStorage.setItem(SEEN_PREFIX + popup.id, "1"); } catch { /* private mode: shows again */ }
}

function show(popup) {
    return new Promise(resolve => {
        const previous = document.activeElement;
        let done = false;
        const finish = () => {
            if (done) return;
            done = true;
            document.removeEventListener("keydown", onKey);
            overlay.remove();
            if (popup.frequencia === "cada_sessao") markSession(popup);
            else authFetch(`/portal/popups/${popup.id}/fechar`, { method: "POST" }).catch(() => {});
            previous?.focus?.();
            resolve();
        };
        const onKey = event => { if (event.key === "Escape") finish(); };
        const overlay = buildPopup(popup, { onClose: finish });
        document.body.append(overlay);
        document.addEventListener("keydown", onKey);
        overlay.querySelector(".portal-popup__close").focus();
    });
}

let started = false;

/** Shows the active pop-ups of this portal, one after the other. */
export async function startPortalPopups() {
    if (started) return;
    started = true;
    let popups = [];
    try {
        const response = await authFetch("/portal/popups");
        if (!response.ok) return;
        popups = await response.json();
    } catch {
        return;
    }
    for (const popup of popups) {
        if (popup.frequencia === "cada_sessao" && seenThisSession(popup)) continue;
        await show(popup);
    }
}

document.addEventListener("admin:logout", () => { started = false; });
