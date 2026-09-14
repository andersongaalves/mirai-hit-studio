export const usuariosState = {
    lista: [],
    loading: false,
    error: "",
    filtro: { busca: "", status: "todos", role: "todos" },
};


export function resetUsuariosState() {
    usuariosState.lista = [];
    usuariosState.loading = false;
    usuariosState.error = "";
    usuariosState.filtro = { busca: "", status: "todos", role: "todos" };
}
