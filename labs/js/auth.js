// Mirai Hit Labs account session: sign in with a Labs account or a Mirai Hit Studio
// customer account (same login). The token lives in this site's storage only.
import { API_URL } from "./config.js";
import { t } from "./i18n.js";

const TOKEN_KEY = "mirai.labs.access_token";
const USER_KEY = "mirai.labs.user";

function read(key) {
    try { return window.localStorage.getItem(key); } catch { return null; }
}

function write(key, value) {
    try {
        if (value === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, value);
    } catch { /* private mode: the session lasts only for this page */ }
}

export function getToken() {
    return read(TOKEN_KEY);
}

export function currentUser() {
    try { return JSON.parse(read(USER_KEY) || "null"); } catch { return null; }
}

export function isSignedIn() {
    return Boolean(getToken());
}

export function signOut() {
    write(TOKEN_KEY, null);
    write(USER_KEY, null);
}

function saveSession(data) {
    write(TOKEN_KEY, data.access_token);
    write(USER_KEY, JSON.stringify(data.user || null));
}

// Turns the API's messages (Portuguese, for operators) into what the buyer should read.
const MESSAGES = [
    [/^Usu[aá]rio ou senha incorretos/i, "wrongLogin"],
    [/^Nome de usuario indisponivel/i, "usernameTaken"],
    [/^Conta ou vinculo indisponivel/i, "usernameTaken"],
    [/convite ja foi utilizado|ja possui acesso/i, "linkUsed"],
    [/expirou/i, "linkExpired"],
    [/revogado/i, "linkRevoked"],
    [/Link invalido|indisponivel ou expirado/i, "linkInvalid"],
    [/Voc[eê] j[aá] tem este plugin/i, "alreadyOwned"],
    [/Complete seu cadastro/i, "completeProfile"],
];

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

function humanMessage(detail, status) {
    if (status === 429) return t("tooMany");
    if (status === 0) return t("offline");
    const match = MESSAGES.find(([pattern]) => pattern.test(detail || ""));
    if (match) return t(match[1]);
    if (status === 401) return t("sessionExpired");
    if (status >= 500) return t("unavailable");
    return t("genericError");
}

export async function api(path, { method = "GET", body, auth = false, headers = {} } = {}) {
    const init = { method, headers: { Accept: "application/json", ...headers } };
    if (body !== undefined) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
    }
    if (auth) {
        const token = getToken();
        if (!token) throw new ApiError(t("sessionExpired"), 401);
        init.headers.Authorization = `Bearer ${token}`;
    }
    let response;
    try {
        response = await fetch(`${API_URL}${path}`, init);
    } catch {
        throw new ApiError(humanMessage("", 0), 0);
    }
    let data = null;
    try { data = await response.json(); } catch { /* empty body */ }
    if (!response.ok) {
        if (auth && response.status === 401) signOut();
        const detail = typeof data?.detail === "string" ? data.detail : "";
        throw new ApiError(humanMessage(detail, response.status), response.status);
    }
    return data;
}

export async function signIn(username, password) {
    const data = await api("/auth/login", { method: "POST", body: { username, password } });
    if (data?.user?.role !== "cliente") {
        // Studio staff accounts don't buy on the store.
        throw new ApiError(t("customersOnly"), 403);
    }
    saveSession(data);
    return data.user;
}

// Confirms the session is still valid (password changed, account disabled...).
export async function refreshUser() {
    if (!isSignedIn()) return null;
    try {
        const user = await api("/auth/me", { auth: true });
        write(USER_KEY, JSON.stringify(user));
        return user;
    } catch (error) {
        if (error.status === 401 || error.status === 403) signOut();
        throw error;
    }
}
