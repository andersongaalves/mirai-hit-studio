import * as Notify from "../../utils/notifications.js";
import * as API from "./clientes_api.js";
import { closeClienteModal, openClienteModal } from "./clientes_modal.js";
import { clientesState } from "./clientes_state.js";
import * as UI from "./clientes_ui.js";
import { filtrarClientes } from "./clientes_utils.js";

document.addEventListener("proposta:comercial-atualizada", carregarClientes);


function filtered() {
    const filtro = clientesState.filtro;
    const active = Boolean(filtro.busca.trim()) || filtro.status !== "todos";
    return { active, items: filtrarClientes(clientesState.lista, filtro) };
}


export function refreshClientes() {
    if (clientesState.loading) {
        UI.renderSummary();
        UI.renderLoading();
        return;
    }
    if (clientesState.error) {
        UI.renderSummary();
        UI.renderError(clientesState.error);
        return;
    }
    const { active, items } = filtered();
    document.getElementById("clientes-clear-filters")?.classList.toggle("hidden", !active);
    UI.renderSummary(clientesState.lista.length, items.length, active);
    UI.renderClientes(items, { onOpen: abrirCliente, filtered: active });
}


function registerFilters() {
    const search = document.getElementById("clientes-search");
    const status = document.getElementById("clientes-status-filter");
    const clear = document.getElementById("clientes-clear-filters");
    if (search) search.oninput = (event) => {
        clientesState.filtro.busca = event.target.value;
        refreshClientes();
    };
    if (status) status.onchange = (event) => {
        clientesState.filtro.status = event.target.value;
        refreshClientes();
    };
    if (clear) clear.onclick = () => {
        clientesState.filtro = { busca: "", status: "todos" };
        if (search) search.value = "";
        if (status) status.value = "todos";
        refreshClientes();
        search?.focus();
    };
}


export async function carregarClientes() {
    clientesState.loading = true;
    clientesState.error = "";
    refreshClientes();
    try {
        const data = await API.listarClientes();
        clientesState.lista = Array.isArray(data) ? data : [];
    } catch (error) {
        console.error(error);
        clientesState.error = "Não foi possível carregar os clientes.";
    } finally {
        clientesState.loading = false;
        refreshClientes();
    }
}


export function novoCliente() {
    openClienteModal(null, { onSave: salvarCliente });
}


export async function abrirCliente(id) {
    try {
        openClienteModal(await API.buscarCliente(id), { onSave: salvarCliente });
    } catch (error) {
        console.error(error);
        Notify.error("Não foi possível abrir o cliente.");
    }
}


async function salvarCliente(id, payload) {
    try {
        if (id) await API.atualizarCliente(id, payload);
        else await API.criarCliente(payload);
        await carregarClientes();
        closeClienteModal();
        Notify.success(id ? "Cliente atualizado." : "Cliente criado.");
    } catch (error) {
        console.error(error);
        Notify.error(error.status === 409
            ? "Já existe um cliente com este e-mail ou telefone."
            : error.message);
        return false;
    }
}


export function initClientes() {
    registerFilters();
    return carregarClientes();
}


export { closeClienteModal };
