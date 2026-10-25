// AUD6-S02-003: every panel signs in through /acesso and returns to where it was.
const PANEL_PATHS = Object.freeze({
    admin: /^\/admin(?:\.html)?(?:\/|$)/,
    produtor: /^\/(?:portal-)?produtor(?:\.html)?(?:\/|$)/,
    cliente: /^\/(?:portal-)?cliente(?:\.html)?(?:\/|$)/,
});

function sameOriginPath(value, origin) {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
        return null;
    }
    try {
        const target = new URL(value, origin);
        return target.origin === origin ? target : null;
    } catch {
        return null;
    }
}

export function safeNextFor(role, value, origin = window.location.origin) {
    const target = sameOriginPath(value, origin);
    const pattern = PANEL_PATHS[role];
    if (!target || !pattern?.test(target.pathname)) return null;
    return `${target.pathname}${target.search}${target.hash}`;
}

export function roleForNext(value, origin = window.location.origin) {
    const target = sameOriginPath(value, origin);
    if (!target) return null;
    return Object.keys(PANEL_PATHS).find(role => PANEL_PATHS[role].test(target.pathname)) || null;
}

export function safeClientNext(value, origin = window.location.origin) {
    return safeNextFor("cliente", value, origin);
}

export function accessPath(next, reason = null) {
    const query = new URLSearchParams();
    if (next) query.set("next", next);
    if (reason) query.set("motivo", reason);
    const text = query.toString();
    return text ? `/acesso?${text}` : "/acesso";
}
