const ROLE_LABELS = { admin: "Administrador", produtor: "Produtor" };


export function roleLabel(role) {
    return ROLE_LABELS[role] || "Papel desconhecido";
}


export function filtrarUsuarios(usuarios, filtro) {
    const busca = filtro.busca.trim().toLocaleLowerCase("pt-BR");
    return usuarios.filter((usuario) => {
        const texto = `${usuario.username} ${roleLabel(usuario.role)}`.toLocaleLowerCase("pt-BR");
        const statusOk = filtro.status === "todos"
            || (filtro.status === "ativo" ? usuario.ativo : !usuario.ativo);
        const roleOk = filtro.role === "todos" || usuario.role === filtro.role;
        return (!busca || texto.includes(busca)) && statusOk && roleOk;
    });
}
