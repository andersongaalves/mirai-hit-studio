import { authFetch } from "../admin/auth.js";

export function initProductionRequest(setAlert) {
    const dialog = document.getElementById("client-request-dialog");
    const form = document.getElementById("client-request-form");
    if (!dialog || !form) return;
    const error = document.getElementById("client-request-error");
    let requestId;
    let busy = false;
    const close = () => { if (!busy) dialog.close(); };
    document.getElementById("client-request-close").onclick = close;
    dialog.addEventListener("cancel", (event) => { if (busy) event.preventDefault(); });
    document.addEventListener("admin:logout", () => dialog.close());
    document.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-new-production]");
        if (!button || button.disabled || busy) return;
        button.disabled = true;
        try {
            const response = await authFetch("/servicos");
            if (!response.ok) throw new Error("Não foi possível carregar os serviços.");
            const services = await response.json();
            form.reset();
            const select = form.elements.servico_id;
            select.length = 1;
            services.forEach((service) => select.add(new Option(service.nome, service.id)));
            requestId = crypto.randomUUID();
            error.textContent = "";
            dialog.showModal();
        } catch (err) {
            setAlert(err.message, true);
        } finally {
            button.disabled = false;
        }
    });
    form.onsubmit = async (event) => {
        event.preventDefault();
        if (busy || !form.reportValidity()) return;
        const payload = Object.fromEntries(new FormData(form));
        payload.servico_id = Number(payload.servico_id);
        payload.request_id = requestId;
        const submit = form.querySelector('[type="submit"]');
        busy = true;
        submit.disabled = true;
        error.textContent = "";
        try {
            const response = await authFetch("/portal/cliente/solicitacoes", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
            });
            const result = await response.json().catch(() => null);
            if (!response.ok) throw new Error(typeof result?.detail === "string" ? result.detail : "Não foi possível enviar a solicitação.");
            dialog.close();
            setAlert(`Solicitação #${result.id} enviada! A Mirai analisará seu projeto e preparará as condições.`);
        } catch (err) {
            error.textContent = err.message;
        } finally {
            busy = false;
            submit.disabled = false;
        }
    };
}
