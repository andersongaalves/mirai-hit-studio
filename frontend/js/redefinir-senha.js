import { AUTH_CONTEXTS } from "./admin/auth.js";
import { API_URL } from "./config.js";

const form = document.getElementById("reset-form");
const message = document.getElementById("reset-message");
const lead = document.getElementById("reset-lead");
const login = document.getElementById("reset-login");
const token = new URLSearchParams(window.location.search).get("token") || "";

function showMessage(text, error = false) {
    message.textContent = text;
    message.classList.remove("hidden", "producer-message--error");
    if (error) message.classList.add("producer-message--error");
}

if (token.length < 32) {
    form.classList.add("hidden");
    showMessage("Este link é inválido ou não está mais disponível.", true);
}

form?.addEventListener("submit", async event => {
    event.preventDefault();
    message.classList.add("hidden");
    const button = form.querySelector("button[type='submit']");
    const password = form.elements.password.value;
    if (password !== form.elements.confirm.value) {
        showMessage("As senhas não coincidem.", true);
        return;
    }
    button.disabled = true;
    button.textContent = "Redefinindo...";
    try {
        const response = await fetch(`${API_URL}/auth/password-recovery/reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token, password }),
        });
        const data = await response.json().catch(() => null);
        if (response.status === 429) {
            throw new Error("Muitas tentativas. Aguarde antes de tentar novamente.");
        }
        if (!response.ok) {
            throw new Error(typeof data?.detail === "string" ? data.detail : "Este link é inválido ou não está mais disponível.");
        }
        localStorage.removeItem(AUTH_CONTEXTS.cliente.storageKey);
        form.reset();
        form.classList.add("hidden");
        lead.textContent = "Senha redefinida com sucesso";
        showMessage("Entre novamente usando sua nova senha.");
        login.classList.remove("hidden");
        window.history.replaceState({}, document.title, "/redefinir-senha");
    } catch (error) {
        showMessage(error instanceof Error ? error.message : "Erro temporário. Tente novamente.", true);
    } finally {
        button.disabled = false;
        button.textContent = "Redefinir senha";
    }
});
