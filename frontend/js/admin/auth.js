import { API_URL } from "../config.js";
import { $ } from "../utils/dom.js";

const LEGACY_ACCESS_TOKEN_KEY = "access_token";
const LEGACY_REFRESH_TOKEN_KEY = "refresh_token";

export const AUTH_CONTEXTS = Object.freeze({
    admin: Object.freeze({
        name: "admin",
        storageKey: "mirai.auth.admin.access_token",
        deniedMessage: "Esta área é exclusiva para contas administrativas.",
        accepts: user => user?.ativo !== false && user?.role === "admin" && user?.is_admin === true,
    }),
    produtor: Object.freeze({
        name: "produtor",
        storageKey: "mirai.auth.produtor.access_token",
        deniedMessage: "Esta área é exclusiva para contas de produtor.",
        accepts: user => user?.ativo !== false && user?.role === "produtor" && user?.is_admin !== true,
    }),
    cliente: Object.freeze({
        name: "cliente",
        storageKey: "mirai.auth.cliente.access_token",
        deniedMessage: "Esta área é exclusiva para contas de cliente.",
        accepts: user => user?.ativo !== false
            && user?.role === "cliente"
            && user?.is_admin !== true
            && Number.isInteger(user?.cliente_id),
    }),
});

function contextForPath(pathname = window.location.pathname) {
    if (/^\/(?:portal-)?produtor(?:\.html|\/|$)/.test(pathname)) return AUTH_CONTEXTS.produtor;
    if (/^\/(?:portal-)?cliente(?:\.html|\/|$)/.test(pathname)) return AUTH_CONTEXTS.cliente;
    return AUTH_CONTEXTS.admin;
}

export function createAuthContext(config) {
    let sessionVersion = 0;
    let verifiedToken = null;
    let expiryTimer = null;
    let currentUser = null;

    function getToken() {
        return localStorage.getItem(config.storageKey);
    }

    function isAuthenticated() {
        return !!getToken();
    }

    function getCurrentUser() {
        return currentUser;
    }

    function isAdmin() {
        return currentUser?.is_admin === true && currentUser?.role === "admin";
    }

    function setCurrentUser(user) {
        currentUser = user && Number.isInteger(user.id) ? user : null;
        document.querySelectorAll("[data-admin-only]").forEach((element) => {
            element.classList.toggle("admin-access-hidden", !isAdmin());
        });
    }

    function mostrarAdmin() {
        $("login-panel")?.classList.add("hidden");
        $("admin-area")?.classList.remove("hidden");
    }

    function mostrarLogin() {
        $("admin-area")?.classList.add("hidden");
        $("login-panel")?.classList.remove("hidden");
    }

    function emitLogout() {
        document.dispatchEvent(new CustomEvent("admin:logout", {
            detail: { context: config.name },
        }));
    }

    function clearRuntimeSession({ emit = true } = {}) {
        sessionVersion++;
        verifiedToken = null;
        setCurrentUser(null);
        clearTimeout(expiryTimer);
        expiryTimer = null;
        if (emit) emitLogout();
        mostrarLogin();
    }

    function logout() {
        const hadSession = Boolean(getToken() || verifiedToken || currentUser);
        localStorage.removeItem(config.storageKey);
        clearRuntimeSession({ emit: hadSession });
        if ($("username")) $("username").value = "";
        if ($("password")) $("password").value = "";
    }

    function watchExpiry(token) {
        clearTimeout(expiryTimer);
        expiryTimer = null;
        try {
            const payload = token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/");
            const { exp } = JSON.parse(atob(payload));
            if (Number.isFinite(exp)) {
                expiryTimer = setTimeout(() => {
                    if (getToken() === token) logout();
                }, Math.max(0, Math.min(exp * 1000 - Date.now(), 2147483647)));
            }
        } catch {
            // The backend remains authoritative; this timer only clears expired UI state.
        }
    }

    function commitSession(token, user, { removeLegacy = false } = {}) {
        sessionVersion++;
        localStorage.setItem(config.storageKey, token);
        if (removeLegacy && localStorage.getItem(LEGACY_ACCESS_TOKEN_KEY) === token) {
            localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
            localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
        }
        verifiedToken = token;
        setCurrentUser(user);
        watchExpiry(token);
        mostrarAdmin();
    }

    async function fazerLogin() {
        const version = sessionVersion;
        const username = $("username")?.value.trim() || "";
        const password = $("password")?.value || "";
        const errorEl = $("login-error");
        errorEl?.classList.add("hidden");

        try {
            const response = await fetch(`${API_URL}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });
            const data = await response.json();
            if (version !== sessionVersion) return false;
            if (!response.ok) {
                throw new Error(typeof data.detail === "string" ? data.detail : "Usuário ou senha incorretos.");
            }
            if (typeof data.access_token !== "string" || !data.access_token) {
                throw new Error("Sessão inválida.");
            }
            if (!config.accepts(data.user)) throw new Error(config.deniedMessage);

            commitSession(data.access_token, data.user);
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

    async function authFetch(endpoint, options = {}) {
        const token = getToken();
        const version = sessionVersion;
        const ensureSession = () => {
            if (version !== sessionVersion || token !== getToken()) {
                throw new Error("Sessão encerrada.");
            }
        };
        if (!token) throw new Error("Sessão encerrada.");

        const headers = {
            ...(options.headers || {}),
            Authorization: `Bearer ${token}`,
        };
        if (options.body && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }

        const response = await fetch(`${API_URL}${endpoint}`, { ...options, headers });
        ensureSession();
        if (response.status === 401) {
            logout();
            throw new Error("Sessão expirada.");
        }

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

    async function restaurarSessao() {
        const version = sessionVersion;
        let token = getToken();
        const legacy = !token;
        if (legacy) token = localStorage.getItem(LEGACY_ACCESS_TOKEN_KEY);
        if (!token) return false;

        if (!legacy && verifiedToken === token && config.accepts(currentUser)) {
            mostrarAdmin();
            return true;
        }

        const sessionIsCurrent = () => version === sessionVersion && (
            legacy
                ? !getToken() && localStorage.getItem(LEGACY_ACCESS_TOKEN_KEY) === token
                : getToken() === token
        );

        try {
            const response = await fetch(`${API_URL}/auth/me`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!sessionIsCurrent()) return false;
            const user = await response.json().catch(() => null);
            if (!sessionIsCurrent()) return false;
            if (!response.ok || !user?.id) {
                if (legacy && response.status === 401) {
                    localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
                    localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY);
                } else if (!legacy) {
                    logout();
                }
                return false;
            }
            if (!config.accepts(user)) {
                if (!legacy) logout();
                return false;
            }

            commitSession(token, user, { removeLegacy: legacy });
            return true;
        } catch {
            if (sessionIsCurrent() && !legacy) logout();
            return false;
        }
    }

    function handleStorage(event) {
        if (event.key !== config.storageKey) return;
        clearRuntimeSession();
        if (event.newValue !== null) location.reload();
    }

    window.addEventListener("storage", handleStorage);

    return Object.freeze({
        authFetch,
        fazerLogin,
        getContextName: () => config.name,
        getCurrentUser,
        getStorageKey: () => config.storageKey,
        getToken,
        isAdmin,
        isAuthenticated,
        logout,
        restaurarSessao,
    });
}

const auth = createAuthContext(contextForPath());

export const authFetch = auth.authFetch;
export const fazerLogin = auth.fazerLogin;
export const getContextName = auth.getContextName;
export const getCurrentUser = auth.getCurrentUser;
export const getStorageKey = auth.getStorageKey;
export const getToken = auth.getToken;
export const isAdmin = auth.isAdmin;
export const isAuthenticated = auth.isAuthenticated;
export const logout = auth.logout;
export const restaurarSessao = auth.restaurarSessao;
