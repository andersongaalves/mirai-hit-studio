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


function payload() {
    if (!current) {
        return {
            username: field("usuario-username").value.trim(),
            password: field("usuario-password").value,
            role: field("usuario-role").value,
        };
    }
    return {
        username: field("usuario-username").value.trim(),
        role: field("usuario-role").value,
        ativo: field("usuario-ativo").checked,
    };
}


export function openUsuarioModal(usuario = null, handlers = {}) {
    current = usuario;
    onSave = handlers.onSave || null;
    onPasswordReset = handlers.onPasswordReset || null;
    const self = usuario?.id === getCurrentUser()?.id;
    field("usuario-modal-title").textContent = usuario ? "Usuario" : "Novo usuario";
    field("usuario-username").value = usuario?.username || "";
    field("usuario-role").value = usuario?.role || "produtor";
    field("usuario-ativo").checked = usuario?.ativo ?? true;
    field("usuario-password").value = "";
    field("usuario-new-password").value = "";
    field("usuario-username").disabled = self;
    field("usuario-role").disabled = self;
    field("usuario-ativo").disabled = self;
    field("usuario-active-field").classList.toggle("hidden", !usuario);
    field("usuario-create-password").classList.toggle("hidden", Boolean(usuario));
    field("usuario-reset-password").classList.toggle("hidden", !usuario);
    field("usuario-self-help").classList.toggle("hidden", !self);

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
