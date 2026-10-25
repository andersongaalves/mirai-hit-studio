import { AUTH_CONTEXTS } from "./admin/auth.js";
import { API_URL } from "./config.js";
import { accessPath, safeClientNext } from "./auth_next.js";
import { initPublicNavigation } from "./public_navigation.js";

initPublicNavigation();

const form = document.getElementById("activation-form");
const lead = document.getElementById("activation-lead");
const message = document.getElementById("activation-message");
const login = document.getElementById("activation-login");
const token = new URLSearchParams(window.location.search).get("token") || "";
const next = safeClientNext(new URLSearchParams(window.location.search).get("next"));
login.href = accessPath(next);

function showMessage(text, error = true) {
    message.textContent = text;
    message.classList.remove("hidden");
    message.classList.toggle("producer-message--error", error);
}

async function api(path, body) {
    const response = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = data?.detail;
        const text = typeof detail === "string" ? detail : "Não foi possível concluir a ativação.";
        const error = new Error(text);
        error.status = response.status;
        throw error;
    }
    return data;
}

async function initialize() {
    if (!token) {
        lead.textContent = "O link de ativação está incompleto.";
        return;
    }
    try {
        const result = await api("/cliente-acessos/validar", { token });
        if (result.estado !== "valido") {
            const labels = {
                expirado: "Este link expirou. Peça ao estúdio um novo convite de acesso.",
                revogado: "Este link foi cancelado. Peça ao estúdio um novo convite de acesso.",
                utilizado: "Este link já foi utilizado.",
            };
            lead.textContent = labels[result.estado] || "Este link não está disponível.";
            if (result.estado === "utilizado") login.classList.remove("hidden");
            return;
        }
        lead.textContent = "Escolha suas credenciais para acessar o Portal do Cliente.";
        form.classList.remove("hidden");
    } catch (error) {
        lead.textContent = error.status === 429
            ? error.message
            : "Este link é inválido ou não está mais disponível.";
    }
}

async function signIn(username, password) {
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok || typeof data?.access_token !== "string" || !AUTH_CONTEXTS.cliente.accepts(data.user)) return false;
        localStorage.setItem(AUTH_CONTEXTS.cliente.storageKey, data.access_token);
        showMessage("Entrando no Portal do Cliente...", false);
        window.location.assign(next || "/cliente");
        return true;
    } catch {
        return false;
    }
}

form?.addEventListener("submit", async event => {
    event.preventDefault();
    message.classList.add("hidden");
    const button = form.querySelector("button[type='submit']");
    const username = form.elements.username.value.trim();
    const password = form.elements.password.value;
    if (password !== form.elements.confirm.value) {
        showMessage("As senhas não coincidem.");
        return;
    }
    button.disabled = true;
    try {
        await api("/cliente-acessos/ativar", { token, username, password });
        form.classList.add("hidden");
        lead.textContent = "Conta criada com sucesso.";
        const cleanPath = next ? `/ativar?next=${encodeURIComponent(next)}` : "/ativar";
        window.history.replaceState({}, document.title, cleanPath);
        // AUD6-S02-014: the new account goes straight to the portal instead of a second login.
        if (await signIn(username, password)) return;
        showMessage("Entre pelo acesso unificado para continuar.", false);
        login.classList.remove("hidden");
    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
    }
});

initialize();
