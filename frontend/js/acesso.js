import { AUTH_CONTEXTS } from "./admin/auth.js";
import { API_URL } from "./config.js";

const form = document.getElementById("access-login-form");
const errorElement = document.getElementById("login-error");
const submitButton = form?.querySelector("button[type='submit']");

const destinations = Object.freeze({
    admin: "/admin",
    produtor: "/produtor",
    cliente: "/cliente",
});

function contextForUser(user) {
    return Object.values(AUTH_CONTEXTS).find(context => context.accepts(user));
}

function showError(message) {
    errorElement.textContent = message;
    errorElement.classList.remove("hidden");
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorElement.classList.add("hidden");
    submitButton.disabled = true;

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: form.elements.username.value.trim(),
                password: form.elements.password.value,
            }),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(
                typeof data?.detail === "string"
                    ? data.detail
                    : "Usuário ou senha incorretos.",
            );
        }

        const context = contextForUser(data?.user);
        if (!context || typeof data?.access_token !== "string" || !data.access_token) {
            throw new Error("Esta conta não possui uma área de acesso válida.");
        }

        localStorage.setItem(context.storageKey, data.access_token);
        form.elements.password.value = "";
        window.location.assign(destinations[context.name]);
    } catch (error) {
        showError(error instanceof Error ? error.message : "Não foi possível entrar.");
    } finally {
        submitButton.disabled = false;
    }
});
