export function safeClientNext(value, origin = window.location.origin) {
    if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
        return null;
    }
    try {
        const target = new URL(value, origin);
        if (target.origin !== origin || !/^\/cliente(?:\/|$)/.test(target.pathname)) return null;
        return `${target.pathname}${target.search}${target.hash}`;
    } catch {
        return null;
    }
}

export function accessPath(next) {
    return next ? `/acesso?next=${encodeURIComponent(next)}` : "/acesso";
}
