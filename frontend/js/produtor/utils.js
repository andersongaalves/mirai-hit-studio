export const STATUS = {
    aguardando_inicio: { label: "Aguardando início", variant: "neutral" },
    em_producao: { label: "Em produção", variant: "info" },
    revisao: { label: "Em revisão", variant: "review" },
    finalizado: { label: "Finalizada", variant: "success" },
    entregue: { label: "Entregue", variant: "success" },
};

const FINAL = new Set(["finalizado", "entregue"]);

export function statusInfo(status) {
    return STATUS[status] || { label: "Status indisponível", variant: "neutral" };
}

export function parseEtapas(value) {
    try {
        const items = JSON.parse(value || "[]");
        if (!Array.isArray(items)) return [];
        return items.filter(item => item && typeof item.nome === "string").map(item => ({
            nome: item.nome.trim(),
            feito: item.feito === true,
        })).filter(item => item.nome);
    } catch {
        return [];
    }
}

export function formatDate(value, includeTime = false) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return "Não informado";
    return new Intl.DateTimeFormat("pt-BR", includeTime
        ? { dateStyle: "short", timeStyle: "short" }
        : { dateStyle: "medium" }).format(date);
}

export function deadlineState(production, now = new Date()) {
    if (FINAL.has(production.status)) return { label: "Concluída", kind: "success", timestamp: Infinity };
    const deadline = production.prazo_entrega ? new Date(production.prazo_entrega) : null;
    if (!deadline || Number.isNaN(deadline.getTime())) return { label: "Sem prazo", kind: "neutral", timestamp: Infinity };
    const days = Math.ceil((deadline.getTime() - now.getTime()) / 86400000);
    if (days < 0) return { label: `Atrasada há ${Math.abs(days)} dia${days === -1 ? "" : "s"}`, kind: "danger", timestamp: deadline.getTime() };
    if (days === 0) return { label: "Entrega hoje", kind: "warning", timestamp: deadline.getTime() };
    return { label: `${days} dia${days === 1 ? "" : "s"} até o prazo`, kind: days <= 3 ? "warning" : "info", timestamp: deadline.getTime() };
}

export function summarize(productions, now = new Date()) {
    const active = productions.filter(item => !FINAL.has(item.status));
    return {
        active: active.length,
        review: productions.filter(item => item.status === "revisao").length,
        overdue: active.filter(item => deadlineState(item, now).kind === "danger").length,
    };
}

export function filterAndSort(productions, status, order, now = new Date()) {
    const filtered = status === "todos"
        ? [...productions]
        : productions.filter(item => item.status === status);
    return filtered.sort((a, b) => {
        if (order === "recente") {
            return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        }
        const deadline = deadlineState(a, now).timestamp - deadlineState(b, now).timestamp;
        return deadline || Number(b.id) - Number(a.id);
    });
}

export function nextAction(status) {
    if (status === "aguardando_inicio") return { status: "em_producao", label: "Confirmar início" };
    if (status === "em_producao") return { status: "revisao", label: "Enviar para revisão" };
    if (status === "revisao") return { status: "em_producao", label: "Retomar ajustes" };
    return null;
}
