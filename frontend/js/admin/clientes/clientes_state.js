export const clientesState = {
    lista: [],
    loading: false,
    error: "",
    filtro: {
        busca: "",
        status: "todos",
    },
};

export function resetClientesState() {
    clientesState.lista = [];
    clientesState.loading = false;
    clientesState.error = "";
    clientesState.filtro = { busca: "", status: "todos" };
}
