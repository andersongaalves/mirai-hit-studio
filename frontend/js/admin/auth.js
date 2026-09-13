import { API_URL } from "../config.js";

import { $ } from "../utils/dom.js";
let sessionVersion = 0;
let verifiedToken = null;
let expiryTimer = null;

function watchExpiry(token) {
    clearTimeout(expiryTimer);
    expiryTimer = null;
    try {
        const { exp } = JSON.parse(atob(token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/")));
        if (Number.isFinite(exp)) expiryTimer = setTimeout(() => {
            if (getToken() === token) logout();
        }, Math.max(0, Math.min(exp * 1000 - Date.now(), 2147483647)));
    } catch { /* Only the backend authenticates; this timer merely clears expired UI. */ }
}

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
    const version = sessionVersion;
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
        if (version !== sessionVersion) return false;

        if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "Usuário ou senha incorretos.");
        }
        if (typeof data.access_token !== "string" || !data.access_token) throw new Error("Sessão inválida.");

        localStorage.setItem(
            "access_token",

            data.access_token,
        );

        mostrarAdmin();
        verifiedToken = data.access_token;
        watchExpiry(verifiedToken);
        if ($("password")) $("password").value = "";

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
    const version = sessionVersion;
    const ensureSession = () => {
        if (version !== sessionVersion || token !== getToken()) throw new Error("Sessão encerrada.");
    };
    if (!token) throw new Error("Sessão encerrada.");

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

    ensureSession();
    if (response.status === 401) {
        logout();

        throw new Error("Sessão expirada.");
    }

    // Guard delayed response bodies too, not only the arrival of HTTP headers.
    for (const method of ["json", "text", "blob", "arrayBuffer"]) {
        const read = response[method].bind(response);
        response[method] = async (...args) => {
            const data = await read(...args);
            ensureSession();
            return data;
        };
    }

    return response;
}

// ===========================
// SESSÃO
// ===========================

export async function restaurarSessao() {
    const version = sessionVersion;
    if (!isAuthenticated()) {
        return false;
    }
    if (verifiedToken === getToken()) {
        mostrarAdmin();
        return true;
    }

    try {
        const response = await authFetch("/auth/me");
        const user = await response.json();
        if (!response.ok || !user?.id) throw new Error("Sessão inválida.");
        verifiedToken = getToken();
        watchExpiry(verifiedToken);
        mostrarAdmin();
        return true;
    } catch {
        if (version === sessionVersion && getToken()) logout();
        return false;
    }
}

// ===========================
// LOGOUT
// ===========================

export function logout() {
    sessionVersion++;
    verifiedToken = null;
    clearTimeout(expiryTimer);
    expiryTimer = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    document.dispatchEvent(new Event("admin:logout"));

    mostrarLogin();

    if ($("username")) {
        $("username").value = "";
    }

    if ($("password")) {
        $("password").value = "";
    }
}

window.addEventListener("storage", event => {
    if (event.key !== "access_token") return;
    if (event.newValue === null) logout();
    else {
        sessionVersion++;
        document.dispatchEvent(new Event("admin:logout"));
        mostrarLogin();
        location.reload();
    }
});
