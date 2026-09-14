const CAMPAIGN_LABELS = { draft: "Rascunho", sending: "Enviando", sent: "Enviada", failed: "Falhou" };


export function campaignLabel(status) {
    return CAMPAIGN_LABELS[status] || "Desconhecido";
}


export function badgeVariant(status) {
    if (status === "sent" || status === "active") return "success";
    if (status === "failed") return "danger";
    if (status === "sending") return "warning";
    return "neutral";
}


export function formatDate(value) {
    if (!value) return "Não informado";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Não informado" : date.toLocaleDateString("pt-BR");
}


export function filtrarSubscribers(items, filter) {
    const busca = filter.busca.trim().toLocaleLowerCase("pt-BR");
    return items.filter((item) => {
        const statusOk = filter.status === "todos"
            || (filter.status === "ativo" ? item.ativo : !item.ativo);
        return statusOk && (!busca || item.email.toLocaleLowerCase("pt-BR").includes(busca));
    });
}
