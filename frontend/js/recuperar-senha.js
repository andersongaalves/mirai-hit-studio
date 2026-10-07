import { API_URL } from "./config.js";

const form = document.getElementById("recovery-form");
const message = document.getElementById("recovery-message");
const button = form?.querySelector("button[type='submit']");

function showMessage(text, error = false) {
    message.textContent = text;
    message.classList.remove("hidden", "producer-message--error");
    if (error) message.classList.add("producer-message--error");
}

form?.addEventListener("submit", async event => {
    event.preventDefault();
    message.classList.add("hidden");
    button.disabled = true;
    button.textContent = "Enviando...";
    try {
        const response = await fetch(`${API_URL}/auth/password-recovery`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: form.elements.email.value.trim() }),
        });
        const data = await response.json().catch(() => null);
        if (response.status === 429) {
            throw new Error("Muitas tentativas. Aguarde antes de solicitar novamente.");
        }
        if (!response.ok) {
            throw new Error("Não foi possível enviar agora. Tente novamente em instantes.");
        }
        showMessage(data?.message || "Se existir uma conta elegível para este e-mail, enviaremos instruções para redefinir a senha.");
        form.elements.email.value = "";
    } catch (error) {
        showMessage(error instanceof Error ? error.message : "Erro temporário. Tente novamente.", true);
    } finally {
        button.disabled = false;
        button.textContent = "Enviar instruções";
    }
});
