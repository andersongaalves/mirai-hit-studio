function normalizar(value = "") {
    return String(value ?? "").trim().toLocaleLowerCase("pt-BR");
}


export function filtrarClientes(clientes = [], filtro = {}) {
    const busca = normalizar(filtro.busca);
    const telefoneBusca = busca.replace(/\D/g, "");
    const status = filtro.status || "todos";
    return clientes.filter((cliente) => {
        const corresponde = !busca || [
            cliente.nome,
            cliente.email,
        ].some((value) => normalizar(value).includes(busca))
            || Boolean(
                telefoneBusca
                && String(cliente.telefone || "").replace(/\D/g, "").includes(telefoneBusca),
            );
        const statusCorreto = status === "todos"
            || (status === "ativo" ? cliente.ativo : !cliente.ativo);
        return corresponde && statusCorreto;
    });
}


export function formatarData(value, fallback = "Sem interação") {
    if (!value) return fallback;
    const data = new Date(value);
    if (Number.isNaN(data.getTime())) return fallback;
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(data);
}


export function formatarContato(cliente) {
    return [cliente.email, cliente.telefone].filter(Boolean).join(" · ")
        || "Contato não informado";
}
