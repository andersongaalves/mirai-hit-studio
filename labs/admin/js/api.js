// Admin session and API calls. The admin token lives only in this site's storage, apart
// from the store's customer session (mirai.labs.access_token).
import { API_URL, UPLOAD_URL } from "/js/config.js";

const TOKEN_KEY = "mirai.labs.admin.access_token";
const USER_KEY = "mirai.labs.admin.user";

function read(key) {
    try { return window.localStorage.getItem(key); } catch { return null; }
}

function write(key, value) {
    try {
        if (value === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, value);
    } catch { /* private mode: the session lasts only for this page */ }
}

let memoryToken = null;

export const getToken = () => memoryToken || read(TOKEN_KEY);
export const savedUser = () => { try { return JSON.parse(read(USER_KEY) || "null"); } catch { return null; } };

export function clearSession() {
    memoryToken = null;
    write(TOKEN_KEY, null);
    write(USER_KEY, null);
}

export const isAdmin = user => user?.ativo !== false && user?.role === "admin" && user?.is_admin === true;

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

function message(data, status) {
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        const first = detail[0];
        const where = Array.isArray(first?.loc) ? first.loc.filter(part => part !== "body").join(".") : "";
        const why = String(first?.msg || "").replace(/^Value error, /, "");
        return `Revise o campo ${where || "destacado"}${why ? `: ${why}` : ""}.`;
    }
    if (status === 0) return "Sem conexão com a API.";
    if (status === 401) return "Sessão encerrada; entre de novo.";
    if (status === 403) return "Esta conta não é de administrador.";
    if (status === 429) return "Muitas tentativas; aguarde alguns minutos.";
    if (status >= 500) return "A API está indisponível agora.";
    return "Não foi possível concluir.";
}

function expired() {
    clearSession();
    document.dispatchEvent(new CustomEvent("labs-admin:expired"));
}

export async function api(path, { method = "GET", body, auth = true } = {}) {
    const init = { method, headers: { Accept: "application/json" } };
    if (body !== undefined) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
    }
    if (auth) {
        const token = getToken();
        if (!token) { expired(); throw new ApiError(message(null, 401), 401); }
        init.headers.Authorization = `Bearer ${token}`;
    }
    let response;
    try {
        response = await fetch(`${API_URL}${path}`, init);
    } catch {
        throw new ApiError(message(null, 0), 0);
    }
    let data = null;
    try { data = await response.json(); } catch { /* empty body */ }
    if (!response.ok) {
        if (auth && response.status === 401) expired();
        throw new ApiError(message(data, response.status), response.status);
    }
    return data;
}

// Multipart upload with progress (installers can be large): goes straight to the upload host.
export function upload(path, formData, onProgress = () => {}) {
    return new Promise((resolve, reject) => {
        const token = getToken();
        if (!token) { expired(); reject(new ApiError(message(null, 401), 401)); return; }
        const request = new XMLHttpRequest();
        request.open("POST", `${UPLOAD_URL}${path}`);
        request.setRequestHeader("Authorization", `Bearer ${token}`);
        request.setRequestHeader("Accept", "application/json");
        request.upload.addEventListener("progress", event => {
            if (event.lengthComputable) onProgress(event.loaded / event.total);
        });
        request.addEventListener("load", () => {
            let data = null;
            try { data = JSON.parse(request.responseText); } catch { /* empty */ }
            if (request.status >= 200 && request.status < 300) resolve(data);
            else {
                if (request.status === 401) expired();
                reject(new ApiError(message(data, request.status), request.status));
            }
        });
        request.addEventListener("error", () => reject(new ApiError(message(null, 0), 0)));
        request.send(formData);
    });
}

export async function signIn(username, password) {
    const data = await api("/auth/login", { method: "POST", body: { username, password }, auth: false });
    if (!isAdmin(data?.user)) throw new ApiError("Esta conta não é de administrador.", 403);
    memoryToken = data.access_token;
    write(TOKEN_KEY, data.access_token);
    write(USER_KEY, JSON.stringify(data.user));
    return data.user;
}

export async function currentAdmin() {
    if (!getToken()) return null;
    const user = await api("/auth/me");
    if (!isAdmin(user)) { clearSession(); return null; }
    write(USER_KEY, JSON.stringify(user));
    return user;
}
