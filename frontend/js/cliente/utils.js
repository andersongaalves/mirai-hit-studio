export const FINAL_STATUSES = new Set(["finalizado", "entregue"]);

export const STATUS = {
    aguardando_inicio: { label: "Aguardando início", variant: "neutral" },
    em_producao: { label: "Em produção", variant: "info" },
    revisao: { label: "Aguardando avaliação", variant: "review" },
    finalizado: { label: "Finalizado", variant: "success" },
    entregue: { label: "Entregue", variant: "success" },
};

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

export function formatMoney(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })
        .format(Number(value || 0));
}

export function deadlineState(production, now = new Date()) {
    if (FINAL_STATUSES.has(production.status)) return { label: "Concluído", kind: "success", timestamp: Infinity };
    const deadline = production.prazo_entrega ? new Date(production.prazo_entrega) : null;
    if (!deadline || Number.isNaN(deadline.getTime())) return { label: "Prazo não informado", kind: "neutral", timestamp: Infinity };
    const days = Math.ceil((deadline.getTime() - now.getTime()) / 86400000);
    if (days < 0) return { label: "Prazo em acompanhamento", kind: "warning", timestamp: deadline.getTime() };
    if (days === 0) return { label: "Prazo previsto para hoje", kind: "warning", timestamp: deadline.getTime() };
    return { label: `Prazo em ${days} dia${days === 1 ? "" : "s"}`, kind: days <= 3 ? "warning" : "info", timestamp: deadline.getTime() };
}

export function summarize(productions, finances) {
    return {
        active: productions.filter(item => !FINAL_STATUSES.has(item.status)).length,
        completed: productions.filter(item => FINAL_STATUSES.has(item.status)).length,
        review: productions.filter(item => item.status === "revisao").length,
        pendingPayment: [...finances.values()].filter(item => Number(item?.cobranca?.saldo_pendente || 0) > 0).length,
    };
}

export function filterAndSort(productions, status, order, now = new Date()) {
    const filtered = productions.filter(item => {
        if (status === "ativos") return !FINAL_STATUSES.has(item.status);
        if (status === "concluidos") return FINAL_STATUSES.has(item.status);
        if (status === "revisao") return item.status === "revisao";
        return true;
    });
    return filtered.sort((a, b) => {
        if (order === "recente") return new Date(b.updated_at) - new Date(a.updated_at);
        const byDeadline = deadlineState(a, now).timestamp - deadlineState(b, now).timestamp;
        return byDeadline || Number(b.id) - Number(a.id);
    });
}

export function nextAction(production, finance) {
    if (Number(finance?.cobranca?.saldo_pendente || 0) > 0) return "Pagamento pendente";
    if (production.status === "aguardando_inicio") return "Aguardando início pela equipe";
    if (production.status === "em_producao") return "Produção em andamento";
    if (production.status === "revisao") return "Avaliação em andamento";
    if (production.status === "finalizado") return "Entrega em preparação";
    if (production.status === "entregue") return "Entrega disponível";
    return "Acompanhe as atualizações do projeto";
}
