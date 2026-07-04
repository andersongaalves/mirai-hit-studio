function normalize(value = "") {
    return String(value ?? "")
        .trim()
        .toLowerCase();
}

function matchesBusca(item, busca) {
    if (!busca) return true;

    return (
        normalize(item.nome_cliente).includes(busca) ||
        normalize(item.servico).includes(busca)
    );
}

function matchesStatus(item, status) {
    return status === "todos" || item.status === status;
}

export function filtrarOrcamentos(orcamentos = [], filtro = {}) {
    const busca = normalize(filtro.busca);
    const status = filtro.status || "todos";

    return orcamentos.filter(
        item =>
            matchesBusca(item, busca) &&
            matchesStatus(item, status)
    );
}
