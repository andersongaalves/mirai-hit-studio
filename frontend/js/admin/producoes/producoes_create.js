import { authFetch } from "../auth.js";
import { openAdminModal, closeAdminModal } from "../admin_modal.js";
import * as Notify from "../../utils/notifications.js";

async function request(path, options) {
    const response = await authFetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível concluir a operação.");
    return data;
}

function options(select, items, label) {
    select.length = 1;
    items.forEach((item) => select.add(new Option(label(item), item.id)));
}

export function initCriarProducao(onCreated) {
    const opener = document.getElementById("nova-producao");
    const form = document.getElementById("nova-producao-form");
    if (!opener || !form) return;
    const error = document.getElementById("nova-producao-erro");
    let requestId;
    let submitting = false;
    const close = () => { if (!submitting) closeAdminModal("modal-nova-producao"); };
    document.getElementById("nova-producao-cancelar").onclick = close;
    opener.onclick = async () => {
        opener.disabled = true;
        try {
            const [clients, services, producers] = await Promise.all([
                request("/clientes?ativo=true&ambiente=todos"),
                request("/servicos"), request("/usuarios/produtores"),
            ]);
            form.reset();
            options(form.elements.cliente_id, clients, (item) => `${item.nome}${item.email ? ` · ${item.email}` : ""}${item.is_test ? " (teste)" : ""}`);
            options(form.elements.servico_id, services, (item) => item.nome);
            options(form.elements.produtor_id, producers, (item) => item.username);
            error.textContent = "";
            requestId = crypto.randomUUID();
            openAdminModal("modal-nova-producao", { opener, onRequestClose: close });
        } catch (err) {
            Notify.error(err.message);
        } finally {
            opener.disabled = false;
        }
    };
    form.onsubmit = async (event) => {
        event.preventDefault();
        if (submitting || !form.reportValidity()) return;
        const data = Object.fromEntries(new FormData(form));
        data.cliente_id = Number(data.cliente_id);
        data.servico_id = Number(data.servico_id);
        data.produtor_id = data.produtor_id ? Number(data.produtor_id) : null;
        data.prazo_entrega = data.prazo_entrega ? new Date(data.prazo_entrega).toISOString() : null;
        data.request_id = requestId;
        submitting = true;
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true;
        error.textContent = "";
        try {
            const production = await request("/producoes/direta", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
            });
            submitting = false;
            close();
            Notify.success("Produção criada com sucesso!");
            await onCreated(production);
        } catch (err) {
            error.textContent = err.message;
        } finally {
            submitting = false;
            submit.disabled = false;
        }
    };
}
