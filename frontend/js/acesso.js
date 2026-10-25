import { AUTH_CONTEXTS } from "./admin/auth.js";
import { roleForNext, safeNextFor } from "./auth_next.js";
import { API_URL } from "./config.js";
import { initPublicNavigation } from "./public_navigation.js";

initPublicNavigation();

const form = document.getElementById("access-login-form");
const errorElement = document.getElementById("login-error");
const notice = document.getElementById("access-notice");
const sessionPanel = document.getElementById("access-session");
const sessionName = document.getElementById("access-session-name");
const continueButton = document.getElementById("access-continue");
const submitButton = form?.querySelector("button[type='submit']");
const params = new URLSearchParams(window.location.search);
const requestedNext = params.get("next");

const destinations = Object.freeze({
    admin: "/admin",
    produtor: "/produtor",
    cliente: "/cliente",
});
const REASONS = Object.freeze({
    sessao_expirada: "Sua sessão terminou. Entre novamente para continuar de onde parou.",
});

function contextForUser(user) {
    return Object.values(AUTH_CONTEXTS).find(context => context.accepts(user));
}

// AUD6-S02-003: return to the requested panel only when it belongs to this account.
function destinationFor(context) {
    return safeNextFor(context.name, requestedNext) || destinations[context.name];
}

function showError(message) {
    errorElement.textContent = message;
    errorElement.classList.remove("hidden");
}

function displayName(user) {
    return user?.nome_exibicao || user?.username || "sua conta";
}

if (notice && REASONS[params.get("motivo")]) {
    notice.textContent = REASONS[params.get("motivo")];
    notice.classList.remove("hidden");
}

// AUD6-S02-013: a visitor who is already signed in can continue without typing the
// password again. The form stays available to enter with another account.
async function existingSession() {
    const preferred = roleForNext(requestedNext);
    const contexts = Object.values(AUTH_CONTEXTS)
        .sort((a, b) => Number(b.name === preferred) - Number(a.name === preferred));
    for (const context of contexts) {
        const token = localStorage.getItem(context.storageKey);
        if (!token) continue;
        try {
            const response = await fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
            const user = response.ok ? await response.json().catch(() => null) : null;
            if (context.accepts(user) && localStorage.getItem(context.storageKey) === token) return { context, user };
        } catch {
            // Network failures leave the form available.
        }
    }
    return null;
}

if (sessionPanel) {
    existingSession().then(found => {
        if (!found) return;
        sessionName.textContent = displayName(found.user);
        sessionPanel.classList.remove("hidden");
        continueButton.onclick = () => window.location.assign(destinationFor(found.context));
    });
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
        window.location.assign(destinationFor(context));
    } catch (error) {
        showError(error instanceof Error ? error.message : "Não foi possível entrar.");
    } finally {
        submitButton.disabled = false;
    }
});
