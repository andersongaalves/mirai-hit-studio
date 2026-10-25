export function formatarDataDashboard(valor) {
    const data = new Date(valor);
    if (Number.isNaN(data.getTime())) return "Data indisponível";
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(data);
}
