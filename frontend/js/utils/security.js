export function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

export function safeURL(value) {
    if (typeof value !== "string" || /[\s\u0000-\u001f]/.test(value)) return "";
    try {
        const url = new URL(value);
        return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
    } catch { return ""; }
}

export function serviceStructure(value) {
    try {
        const data = typeof value === "string" ? JSON.parse(value || "{}") : value;
        if (!data || typeof data !== "object" || Array.isArray(data)) return null;
        if (data.intro != null && typeof data.intro !== "string") return null;
        if (!Array.isArray(data.sections ?? []) || !Array.isArray(data.benefits ?? [])) return null;
        if ((data.sections?.length ?? 0) > 30 || (data.benefits?.length ?? 0) > 100) return null;
        if ((data.benefits ?? []).some(x => typeof x !== "string")) return null;
        if ((data.sections ?? []).some(s => !s || typeof s.title !== "string" || typeof (s.icon ?? "") !== "string"
            || !Array.isArray(s.items) || s.items.length > 100 || s.items.some(x => typeof x !== "string"))) return null;
        return { intro: data.intro ?? "", sections: data.sections ?? [], benefits: data.benefits ?? [] };
    } catch { return null; }
}
