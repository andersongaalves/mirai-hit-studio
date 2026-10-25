import { API_URL } from "../config.js";
import { accessPath } from "../auth_next.js";
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

const EXPIRY_WARNING_MS = 5 * 60 * 1000;

export function createAuthContext(config) {
    let sessionVersion = 0;
    let verifiedToken = null;
    let expiryTimer = null;
    let warningTimer = null;
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

    // AUD6-S02-003: panels have no login form; without a session they send the
    // visitor to /acesso and come back to the same address after signing in.
    function mostrarLogin(reason = null) {
        $("admin-area")?.classList.add("hidden");
        $("login-panel")?.classList.remove("hidden");
        const here = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        window.location.assign(accessPath(here, reason));
    }

    function emitLogout() {
        document.dispatchEvent(new CustomEvent("admin:logout", {
            detail: { context: config.name },
        }));
    }

    function clearRuntimeSession({ emit = true, reason = null } = {}) {
        sessionVersion++;
        verifiedToken = null;
        setCurrentUser(null);
        clearTimeout(expiryTimer);
        expiryTimer = null;
        clearTimeout(warningTimer);
        warningTimer = null;
        hideExpiryWarning();
        if (emit) emitLogout();
        mostrarLogin(reason);
    }

    function logout(reason = null) {
        const hadSession = Boolean(getToken() || verifiedToken || currentUser);
        localStorage.removeItem(config.storageKey);
        clearRuntimeSession({ emit: hadSession, reason: typeof reason === "string" ? reason : null });
    }

    // AUD6-S02-011 (decision: 60 min with a warning): a few minutes before the session
    // ends, the visitor is told to save and sign in again; nothing renews silently.
    function hideExpiryWarning() {
        document.getElementById("session-expiry-warning")?.remove();
    }

    function showExpiryWarning(token, exp) {
        if (getToken() !== token || document.getElementById("session-expiry-warning")) return;
        const box = document.createElement("div");
        box.id = "session-expiry-warning";
        box.className = "session-expiry-warning";
        box.setAttribute("role", "alert");
        const minutes = Math.max(1, Math.round((exp * 1000 - Date.now()) / 60000));
        const text = document.createElement("p");
        text.textContent = `Sua sessão termina em cerca de ${minutes} min. Salve o que estiver fazendo; depois, entre de novo.`;
        const again = document.createElement("button");
        again.type = "button";
        again.textContent = "Entrar de novo agora";
        again.addEventListener("click", () => logout("sessao_expirada"));
        const dismiss = document.createElement("button");
        dismiss.type = "button";
        dismiss.textContent = "Ok";
        dismiss.addEventListener("click", hideExpiryWarning);
        box.append(text, again, dismiss);
        document.body.append(box);
    }

    function watchExpiry(token) {
        clearTimeout(expiryTimer);
        expiryTimer = null;
        clearTimeout(warningTimer);
        warningTimer = null;
        hideExpiryWarning();
        try {
            const payload = token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/");
            const { exp } = JSON.parse(atob(payload));
            if (Number.isFinite(exp)) {
                expiryTimer = setTimeout(() => {
                    if (getToken() === token) logout("sessao_expirada");
                }, Math.max(0, Math.min(exp * 1000 - Date.now(), 2147483647)));
                const warnAt = exp * 1000 - EXPIRY_WARNING_MS - Date.now();
                if (exp * 1000 - Date.now() > EXPIRY_WARNING_MS / 2) {
                    warningTimer = setTimeout(() => showExpiryWarning(token, exp), Math.max(0, Math.min(warnAt, 2147483647)));
                }
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
            logout("sessao_expirada");
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

    // Restores the stored session or sends the visitor to /acesso.
    async function exigirSessao() {
        if (await restaurarSessao()) return true;
        if (!getToken()) mostrarLogin();
        return false;
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
        if (event.newValue !== null) {
            sessionVersion++;
            location.reload();
            return;
        }
        clearRuntimeSession();
    }

    window.addEventListener("storage", handleStorage);

    return Object.freeze({
        authFetch,
        exigirSessao,
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
export const exigirSessao = auth.exigirSessao;
export const getContextName = auth.getContextName;
export const getCurrentUser = auth.getCurrentUser;
export const getStorageKey = auth.getStorageKey;
export const getToken = auth.getToken;
export const isAdmin = auth.isAdmin;
export const isAuthenticated = auth.isAuthenticated;
export const logout = auth.logout;
export const restaurarSessao = auth.restaurarSessao;
