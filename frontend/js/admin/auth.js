import { API_URL } from "../config.js";

import { $ } from "../utils/dom.js";

// ===========================
// UI
// ===========================

function mostrarAdmin() {
    $("login-panel")?.classList.add("hidden");

    $("admin-area")?.classList.remove("hidden");
}

function mostrarLogin() {
    $("admin-area")?.classList.add("hidden");

    $("login-panel")?.classList.remove("hidden");
}

// ===========================
// LOGIN
// ===========================

export async function fazerLogin() {
    const username = $("username").value.trim();

    const password = $("password").value;

    const errorEl = $("login-error");

    errorEl?.classList.add("hidden");

    try {
        const response = await fetch(
            `${API_URL}/auth/login`,

            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                },

                body: JSON.stringify({
                    username,

                    password,
                }),
            },
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Usuário ou senha incorretos.");
        }

        localStorage.setItem(
            "access_token",

            data.access_token,
        );

        mostrarAdmin();

        return true;
    } catch (error) {
        console.error(error);

        if (errorEl) {
            errorEl.innerText = error.message;

            errorEl.classList.remove("hidden");
        }

        return false;
    }
}

// ===========================
// TOKEN
// ===========================

export function getToken() {
    return localStorage.getItem("access_token");
}

export function isAuthenticated() {
    return !!getToken();
}

// ===========================
// AUTH FETCH
// ===========================

export async function authFetch(
    endpoint,

    options = {},
) {
    const token = getToken();

    const headers = {
        ...(options.headers || {}),

        Authorization: `Bearer ${token}`,
    };

    if (options.body && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(
        `${API_URL}${endpoint}`,

        {
            ...options,

            headers,
        },
    );

    if (response.status === 401) {
        logout();

        throw new Error("Sessão expirada.");
    }

    return response;
}

// ===========================
// SESSÃO
// ===========================

export function restaurarSessao() {
    if (!isAuthenticated()) {
        return false;
    }

    mostrarAdmin();

    return true;
}

// ===========================
// LOGOUT
// ===========================

export function logout() {
    localStorage.removeItem("access_token");

    mostrarLogin();

    if ($("username")) {
        $("username").value = "";
    }

    if ($("password")) {
        $("password").value = "";
    }
}
