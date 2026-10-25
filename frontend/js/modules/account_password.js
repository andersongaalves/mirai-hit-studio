import { authFetch, getCurrentUser, renovarSessao } from "../admin/auth.js";

// AUD6-S02-004: every account changes its own password with the current one.
// The backend ends every other session and returns a new token for this tab.

let stopCurrent = null;

export function stopAccountPassword() {
    stopCurrent?.();
    stopCurrent = null;
}

function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
}

function passwordField(id, label, autocomplete) {
    const wrapper = element("label", label, "account-password__field");
    wrapper.htmlFor = id;
    const input = element("input");
    input.id = id;
    input.type = "password";
    input.required = true;
    input.maxLength = 72;
    input.autocomplete = autocomplete;
    if (id !== "account-password-current") input.minLength = 8;
    wrapper.append(input);
    return { wrapper, input };
}

export function startAccountPassword(user) {
    stopAccountPassword();
    const admin = Boolean(user?.is_admin) && user.role === "admin";
    const account = document.querySelector(admin ? ".admin-topbar__actions" : ".producer-account");
    if (!account || !user?.id) return;

    const button = element("button", "Alterar senha", admin ? "btn-small account-password-button" : "btn-outline account-password-button");
    button.type = "button";
    button.setAttribute("aria-haspopup", "dialog");
    account.insertBefore(button, account.lastElementChild);

    const dialog = element("dialog", "", "portal-dialog account-password-dialog");
    dialog.setAttribute("aria-labelledby", "account-password-title");
    const header = element("header");
    const title = element("h2", "Alterar senha");
    title.id = "account-password-title";
    const close = element("button", "Fechar");
    close.type = "button";
    close.addEventListener("click", () => dialog.close());
    header.append(title, close);
    const form = element("form", "", "account-password__form");
    form.noValidate = false;
    const current = passwordField("account-password-current", "Senha atual", "current-password");
    const next = passwordField("account-password-new", "Nova senha (8 a 72 caracteres)", "new-password");
    const confirm = passwordField("account-password-confirm", "Repita a nova senha", "new-password");
    const help = element("p", "Ao salvar, os outros aparelhos conectados saem da conta. Esta aba continua conectada.", "account-password__help");
    const status = element("p", "", "account-password__status");
    status.setAttribute("role", "status");
    const submit = element("button", "Salvar nova senha", "btn-cta");
    submit.type = "submit";
    form.append(current.wrapper, next.wrapper, confirm.wrapper, help, status, submit);
    dialog.append(header, form);
    document.body.append(dialog);

    form.addEventListener("submit", async event => {
        event.preventDefault();
        status.textContent = "";
        if (next.input.value !== confirm.input.value) {
            status.textContent = "As duas novas senhas precisam ser iguais.";
            confirm.input.focus();
            return;
        }
        if (!form.reportValidity()) return;
        submit.disabled = true;
        status.textContent = "Salvando...";
        try {
            const response = await authFetch("/auth/senha", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ senha_atual: current.input.value, nova_senha: next.input.value }),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                status.textContent = response.status === 429
                    ? "Muitas tentativas. Aguarde alguns minutos e tente de novo."
                    : response.status === 400 ? "A senha atual não confere." : "Não foi possível alterar a senha agora.";
                return;
            }
            if (getCurrentUser()?.id !== user.id || !renovarSessao(data.access_token, data.user)) {
                status.textContent = "Senha alterada. Entre de novo para continuar.";
                return;
            }
            form.reset();
            status.textContent = "Senha alterada. Os outros aparelhos foram desconectados.";
        } catch {
            status.textContent = "Não foi possível alterar a senha agora.";
        } finally {
            submit.disabled = false;
        }
    });
    button.addEventListener("click", () => {
        form.reset();
        status.textContent = "";
        dialog.showModal();
        current.input.focus();
    });
    stopCurrent = () => {
        if (dialog.open) dialog.close();
        dialog.remove();
        button.remove();
    };
}

document.addEventListener("admin:logout", stopAccountPassword);
