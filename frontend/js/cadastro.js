import { API_URL } from "./config.js";
import { initPublicNavigation } from "./public_navigation.js";

initPublicNavigation();

const form = document.getElementById("signup-form");
const errorElement = document.getElementById("signup-error");
const sent = document.getElementById("signup-sent");
const resend = document.getElementById("signup-resend");
let submittedEmail = "";

function validationMessage(detail) {
    if (!Array.isArray(detail)) return null;
    const fields = {
        nome: "nome",
        email: "e-mail",
        telefone: "telefone",
        privacy_accepted: "aceite de privacidade",
    };
    const labels = detail.map(item => fields[item?.loc?.at(-1)]).filter(Boolean);
    return labels.length ? `Revise: ${[...new Set(labels)].join(", ")}.` : null;
}

async function request(path, body) {
    const response = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const message = response.status === 429
            ? "Muitas tentativas. Aguarde antes de tentar novamente."
            : validationMessage(data?.detail) || "Não foi possível concluir agora. Tente novamente.";
        const error = new Error(message);
        error.status = response.status;
        throw error;
    }
    return data;
}

function showError(message) {
    errorElement.textContent = message;
    errorElement.classList.remove("hidden");
}

form?.addEventListener("submit", async event => {
    event.preventDefault();
    errorElement.classList.add("hidden");
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    submittedEmail = form.elements.email.value.trim().toLowerCase();
    try {
        await request("/auth/client-signup", {
            nome: form.elements.nome.value.trim(),
            email: submittedEmail,
            telefone: form.elements.telefone.value.trim() || null,
            privacy_accepted: form.elements.privacy.checked,
        });
        form.classList.add("hidden");
        sent.classList.remove("hidden");
    } catch (error) {
        showError(error.message);
    } finally {
        button.disabled = false;
    }
});

resend?.addEventListener("click", async () => {
    if (!submittedEmail) return;
    resend.disabled = true;
    try {
        await request("/auth/client-signup/resend", { email: submittedEmail });
        resend.textContent = "Confirmação solicitada";
    } catch (error) {
        showError(error.message);
    } finally {
        resend.disabled = false;
    }
});
