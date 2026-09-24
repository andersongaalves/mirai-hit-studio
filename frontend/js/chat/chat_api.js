import { API_URL } from "../config.js";

export async function chatRequest(path, { token, payload } = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 55000);
    try {
        const response = await fetch(`${API_URL}/ai/chat/${path}`, {
            method: payload === undefined ? "GET" : "POST",
            headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
            ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
            credentials: "omit", cache: "no-store", signal: controller.signal,
        });
        if (!response.ok) {
            const error = new Error("chat_request_failed");
            error.status = response.status;
            throw error;
        }
        return await response.json();
    } finally {
        clearTimeout(timeout);
    }
}
