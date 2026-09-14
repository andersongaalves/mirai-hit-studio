import * as Notify from "../../utils/notifications.js";
import * as Auth from "../auth.js";
import * as API from "./usuarios_api.js";
import { closeUsuarioModal, openUsuarioModal } from "./usuarios_modal.js";
import { usuariosState } from "./usuarios_state.js";
import * as UI from "./usuarios_ui.js";
import { filtrarUsuarios } from "./usuarios_utils.js";


function filtered() {
    const active = Boolean(usuariosState.filtro.busca.trim())
        || usuariosState.filtro.status !== "todos"
        || usuariosState.filtro.role !== "todos";
    return { active, items: filtrarUsuarios(usuariosState.lista, usuariosState.filtro) };
}


export function syncUsuarioAccess() {
    const admin = Auth.isAdmin();
    document.querySelectorAll("[data-admin-only]").forEach((element) => {
        element.classList.toggle("admin-access-hidden", !admin);
    });
    return admin;
}


export function refreshUsuarios() {
    if (usuariosState.loading) return UI.renderLoading();
    if (usuariosState.error) return UI.renderError();
    const { active, items } = filtered();
    document.getElementById("usuarios-clear-filters")?.classList.toggle("hidden", !active);
    UI.renderSummary(usuariosState.lista.length, items.length, active);
    UI.renderUsuarios(items, { onOpen: abrirUsuario, filtered: active });
}


function registerFilters() {
    const search = document.getElementById("usuarios-search");
    const status = document.getElementById("usuarios-status-filter");
    const role = document.getElementById("usuarios-role-filter");
    const clear = document.getElementById("usuarios-clear-filters");
    if (search) search.oninput = (event) => {
        usuariosState.filtro.busca = event.target.value;
        refreshUsuarios();
    };
    if (status) status.onchange = (event) => {
        usuariosState.filtro.status = event.target.value;
        refreshUsuarios();
    };
    if (role) role.onchange = (event) => {
        usuariosState.filtro.role = event.target.value;
        refreshUsuarios();
    };
    if (clear) clear.onclick = () => {
        usuariosState.filtro = { busca: "", status: "todos", role: "todos" };
        search.value = "";
        status.value = "todos";
        role.value = "todos";
        refreshUsuarios();
        search.focus();
    };
}


export async function carregarUsuarios() {
    if (!syncUsuarioAccess()) return;
    usuariosState.loading = true;
    usuariosState.error = "";
    refreshUsuarios();
    try {
        const data = await API.listarUsuarios();
        usuariosState.lista = Array.isArray(data) ? data : [];
    } catch (error) {
        console.error(error);
        usuariosState.error = error.message;
    } finally {
        usuariosState.loading = false;
        refreshUsuarios();
    }
}


export function novoUsuario() {
    openUsuarioModal(null, { onSave: salvarUsuario, onPasswordReset: resetPassword });
}


export async function abrirUsuario(id) {
    try {
        openUsuarioModal(await API.buscarUsuario(id), {
            onSave: salvarUsuario,
            onPasswordReset: resetPassword,
        });
    } catch (error) {
        console.error(error);
        Notify.error(error.message);
    }
}


async function salvarUsuario(original, payload) {
    if (original?.ativo && !payload.ativo && !confirm(`Desativar ${original.username}?`)) return false;
    if (original?.role === "admin" && payload.role !== "admin"
        && !confirm(`Remover permissao administrativa de ${original.username}?`)) return false;
    try {
        if (original) await API.atualizarUsuario(original.id, payload);
        else await API.criarUsuario(payload);
        await carregarUsuarios();
        closeUsuarioModal();
        Notify.success(original ? "Usuario atualizado." : "Usuario criado.");
        return true;
    } catch (error) {
        console.error(error);
        Notify.error(error.status === 409 ? error.message : "Nao foi possivel salvar o usuario.");
        return false;
    }
}


async function resetPassword(id, novaSenha) {
    try {
        await API.redefinirSenha(id, novaSenha);
        Notify.success("Senha redefinida.");
        return true;
    } catch (error) {
        console.error(error);
        Notify.error("Nao foi possivel redefinir a senha.");
        return false;
    }
}


export function initUsuarios() {
    if (!syncUsuarioAccess()) return Promise.resolve();
    const newButton = document.getElementById("usuario-new");
    if (newButton) newButton.onclick = novoUsuario;
    registerFilters();
    return carregarUsuarios();
}


export { closeUsuarioModal };
