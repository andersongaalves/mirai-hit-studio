import { closeAdminModal, openAdminModal } from "../admin_modal.js";
import { getCurrentUser } from "../auth.js";


let current = null;
let onSave = null;
let onPasswordReset = null;


function field(id) {
    return document.getElementById(id);
}


function valid(...ids) {
    return ids.every((id) => field(id)?.reportValidity());
}


function displayName() {
    return field("usuario-nome-exibicao").value.replace(/\s+/g, " ").trim() || null;
}


function payload() {
    if (!current) {
        return {
            username: field("usuario-username").value.trim(),
            nome_exibicao: displayName(),
            password: field("usuario-password").value,
            role: field("usuario-role").value,
            painel_beats: field("usuario-painel-beats").checked,
        };
    }
    const update = {
        username: field("usuario-username").value.trim(),
        nome_exibicao: displayName(),
        role: field("usuario-role").value,
        ativo: field("usuario-ativo").checked,
        painel_beats: field("usuario-painel-beats").checked,
    };
    // AUD6-S02-005: a client account keeps its role and client link; only name and access change here.
    if (current.role === "cliente") {
        delete update.role;
        delete update.painel_beats;
    }
    return update;
}


export function openUsuarioModal(usuario = null, handlers = {}) {
    current = usuario;
    onSave = handlers.onSave || null;
    onPasswordReset = handlers.onPasswordReset || null;
    const self = usuario?.id === getCurrentUser()?.id;
    const client = usuario?.role === "cliente";
    field("usuario-modal-title").textContent = usuario ? "Usuario" : "Novo usuario";
    field("usuario-username").value = usuario?.username || "";
    field("usuario-nome-exibicao").value = usuario?.nome_exibicao || "";
    field("usuario-role").value = usuario?.role || "produtor";
    field("usuario-ativo").checked = usuario?.ativo ?? true;
    field("usuario-painel-beats").checked = usuario?.painel_beats ?? false;
    field("usuario-password").value = "";
    field("usuario-new-password").value = "";
    field("usuario-username").disabled = self;
    field("usuario-role").disabled = self || client;
    field("usuario-role").querySelector('option[value="cliente"]').hidden = !client;
    field("usuario-client-help").classList.toggle("hidden", !client);
    field("usuario-open-client").onclick = client && usuario.cliente_id
        ? () => { closeUsuarioModal(); handlers.onOpenClient?.(usuario.cliente_id); }
        : null;
    field("usuario-open-client").classList.toggle("hidden", !(client && usuario.cliente_id && handlers.onOpenClient));
    field("usuario-ativo").disabled = self;
    field("usuario-active-field").classList.toggle("hidden", !usuario);
    field("usuario-create-password").classList.toggle("hidden", Boolean(usuario));
    field("usuario-reset-password").classList.toggle("hidden", !usuario);
    field("usuario-self-help").classList.toggle("hidden", !self);
    const syncBeatPermission = () => {
        const producer = field("usuario-role").value === "produtor";
        field("usuario-beats-field").classList.toggle("hidden", !producer);
        if (!producer) field("usuario-painel-beats").checked = false;
    };
    field("usuario-role").onchange = syncBeatPermission;
    syncBeatPermission();

    const save = field("usuario-save");
    save.onclick = async () => {
        const required = current
            ? ["usuario-username", "usuario-role"]
            : ["usuario-username", "usuario-role", "usuario-password"];
        if (save.disabled || !onSave || !valid(...required)) return;
        save.disabled = true;
        try {
            await onSave(current, payload());
        } finally {
            save.disabled = false;
        }
    };
    const reset = field("usuario-password-reset");
    reset.onclick = async () => {
        if (reset.disabled || !current || !onPasswordReset || !valid("usuario-new-password")) return;
        reset.disabled = true;
        try {
            if (await onPasswordReset(current.id, field("usuario-new-password").value)) {
                field("usuario-new-password").value = "";
            }
        } finally {
            reset.disabled = false;
        }
    };
    field("usuario-close").onclick = closeUsuarioModal;
    openAdminModal("modal-usuario", {
        onRequestClose: closeUsuarioModal,
        initialFocus: "#usuario-username:not([disabled]), #usuario-role",
    });
}


export function closeUsuarioModal() {
    current = null;
    onSave = null;
    onPasswordReset = null;
    closeAdminModal("modal-usuario");
}
