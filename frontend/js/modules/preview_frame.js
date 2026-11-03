// Admin preview: the Admin shows any screen of the site and the portals in a frame.
// Inside that frame, the portals use a short read-only session that the Admin opened
// for a chosen account; it lives in this tab only (sessionStorage), never replaces a
// real sign-in, and the site does not count these visits in its analytics.
const PREFIX = "mirai.preview.";

export const PREVIEW_PORTALS = Object.freeze(["cliente", "produtor"]);

/** True inside the Admin's preview frame (same site, framed by /admin). */
export function inAdminPreview(win = window) {
    try {
        return win.top !== win.self
            && win.top.location.origin === win.location.origin
            && /^\/admin(?:\.html)?(?:\/|$)/.test(win.top.location.pathname);
    } catch {
        return false;
    }
}

function storage() {
    try { return window.sessionStorage; } catch { return null; }
}

export function previewSession(portal) {
    try { return JSON.parse(storage()?.getItem(PREFIX + portal) || "null"); } catch { return null; }
}

export function previewToken(portal) {
    const session = previewSession(portal);
    return session && typeof session.token === "string" && Date.parse(session.expira_em) > Date.now() ? session.token : null;
}

export function savePreviewSession(portal, session) {
    try { storage()?.setItem(PREFIX + portal, JSON.stringify(session)); } catch { /* the frame shows the sign-in notice */ }
}

export function clearPreviewSessions() {
    PREVIEW_PORTALS.forEach(portal => { try { storage()?.removeItem(PREFIX + portal); } catch { /* nothing stored */ } });
}

export const PREVIEW_READ_ONLY = "Modo de visualização do Admin: nada pode ser enviado ou alterado.";

/** A strip at the top of the framed portal saying whose view this is. */
export function showPreviewBanner(portal) {
    if (document.getElementById("admin-preview-banner")) return;
    const session = previewSession(portal);
    const banner = document.createElement("div");
    banner.id = "admin-preview-banner";
    banner.setAttribute("role", "status");
    banner.textContent = `Visualização do Admin · ${session?.conta?.nome || "conta"} · somente leitura`;
    Object.assign(banner.style, {
        position: "fixed", left: "0", right: "0", bottom: "0", zIndex: "9999", padding: "6px 12px", textAlign: "center",
        pointerEvents: "none",
        font: "700 12px/1.4 Arial, sans-serif", letterSpacing: "0.04em", color: "#071018", background: "#ffc861",
    });
    document.body.append(banner);
}

/** Shown in the frame instead of the sign-in page when the preview session is over. */
export function showPreviewEnded() {
    const box = document.createElement("div");
    box.setAttribute("role", "status");
    Object.assign(box.style, {
        position: "fixed", inset: "0", zIndex: "10000", display: "grid", placeItems: "center", padding: "24px",
        textAlign: "center", font: "16px/1.5 Arial, sans-serif", color: "#e8eef7", background: "#071018",
    });
    box.textContent = "A sessão de visualização terminou ou ainda não foi aberta. Escolha a conta de novo no Admin.";
    document.body.append(box);
}
