import { API_URL } from "./config.js";

const form = document.getElementById("activation-form");
const lead = document.getElementById("activation-lead");
const message = document.getElementById("activation-message");
const login = document.getElementById("activation-login");
const token = new URLSearchParams(window.location.search).get("token") || "";

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
                expirado: "Este convite expirou. Solicite um novo envio à Mirai Hit Studio.",
                revogado: "Este convite foi revogado.",
                utilizado: "Este convite já foi utilizado.",
            };
            lead.textContent = labels[result.estado] || "Este convite não está disponível.";
            if (result.estado === "utilizado") login.classList.remove("hidden");
            return;
        }
        lead.textContent = "Escolha suas credenciais para acessar seus projetos.";
        form.classList.remove("hidden");
    } catch (error) {
        lead.textContent = error.status === 429
            ? error.message
            : "Este convite é inválido ou não está mais disponível.";
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
        lead.textContent = "Seu acesso foi ativado com segurança.";
        showMessage("Conta criada. Entre pelo acesso unificado.", false);
        login.classList.remove("hidden");
        window.history.replaceState({}, document.title, "/ativar");
    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
    }
});

initialize();
