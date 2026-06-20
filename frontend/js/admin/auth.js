import { API_URL } from "../config.js";

export async function fazerLogin() {

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const errorEl = document.getElementById("login-error");

    errorEl.classList.add("hidden");

    try {
        const response = await fetch(
            `${API_URL}/auth/login`,

            {
                method: "POST",
                headers: {

                    "Content-Type": "application/json"

                },
                body: JSON.stringify({
                    username,
                    password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Usuário ou senha incorretos."
            );

        }

        localStorage.setItem(
            "access_token",
            data.access_token

        );

        localStorage.setItem(
            "admin_logged",
            "true"

        );

        document
            .getElementById("login-panel")
            .classList.add("hidden");

        document
            .getElementById("admin-area")
            .classList.remove("hidden");

        return true;

    }

    catch (error) {

        console.error(error);

        errorEl.innerText = error.message;

        errorEl.classList.remove("hidden");

        return false;

    }
    console.log("TOKEN SALVO:", data.access_token);

}

export function logout() {

    localStorage.removeItem("access_token");

    localStorage.removeItem("admin_logged");

    document

        .getElementById("admin-area")

        .classList.add("hidden");

    document

        .getElementById("login-panel")

        .classList.remove("hidden");

    document.getElementById("username").value = "";

    document.getElementById("password").value = "";

}

export function getToken() {

    return localStorage.getItem(

        "access_token"

    );

}

export function isAuthenticated() {

    return !!localStorage.getItem(

        "access_token"

    );

}

export async function authFetch(

    endpoint,

    options = {}

) {

    const token = getToken();

    console.log("TOKEN ENVIADO:", token);

    const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {})
    };

    const response = await fetch(

        `${API_URL}${endpoint}`,

        {

            ...options,

            headers

        }

    );

    if (response.status === 401) {
        logout();
        throw new Error("Sessão expirada.");

    }

    return response;

}

export function restaurarSessao() {

    if (!isAuthenticated()) {
        return false;

    }

    document
        .getElementById("login-panel")
        .classList.add("hidden");

    document
        .getElementById("admin-area")
        .classList.remove("hidden");

    return true;

}