import { closeAdminModal, openAdminModal } from "../admin_modal.js";
import { formatarData } from "./clientes_utils.js";


let current = null;
let onSave = null;


function field(id) {
    return document.getElementById(id);
}


function renderHistory(items = []) {
    const container = field("cliente-historico");
    if (!container) return;
    container.replaceChildren();
    if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "admin-empty";
        empty.textContent = "Nenhuma interação comercial registrada.";
        container.appendChild(empty);
        return;
    }
    const list = document.createElement("ol");
    list.className = "cliente-history-list";
    items.forEach((item) => {
        const row = document.createElement("li");
        const title = document.createElement("strong");
        const date = document.createElement("time");
        title.textContent = item.titulo;
        date.textContent = formatarData(item.data, "Data não informada");
        if (item.data) date.dateTime = item.data;
        row.append(title, date);
        list.appendChild(row);
    });
    container.appendChild(list);
}


function payload() {
    return {
        nome: field("cliente-nome").value.trim(),
        email: field("cliente-email").value.trim() || null,
        telefone: field("cliente-telefone").value.trim() || null,
        observacoes: field("cliente-observacoes").value,
        ativo: field("cliente-ativo").checked,
    };
}


export function openClienteModal(cliente = null, handlers = {}) {
    current = cliente;
    onSave = handlers.onSave || null;
    field("cliente-modal-title").textContent = cliente ? "Cliente" : "Novo cliente";
    field("cliente-nome").value = cliente?.nome || "";
    field("cliente-email").value = cliente?.email || "";
    field("cliente-telefone").value = cliente?.telefone || "";
    field("cliente-observacoes").value = cliente?.observacoes || "";
    field("cliente-ativo").checked = cliente?.ativo ?? true;
    field("cliente-history-block").classList.toggle("hidden", !cliente);
    renderHistory(cliente?.historico || []);

    const save = field("cliente-save");
    save.onclick = async () => {
        if (save.disabled || !onSave) return;
        save.disabled = true;
        try {
            await onSave(current?.id || null, payload());
        } finally {
            save.disabled = false;
        }
    };
    openAdminModal("modal-cliente", {
        onRequestClose: closeClienteModal,
        initialFocus: "#cliente-nome",
    });
}


export function closeClienteModal() {
    current = null;
    onSave = null;
    closeAdminModal("modal-cliente");
}
