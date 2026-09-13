import { authFetch } from "../auth.js";


export async function carregarDashboardApi() {
    const response = await authFetch("/dashboard");
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(typeof data?.detail === "string"
            ? data.detail
            : "Nao foi possivel carregar o dashboard.");
    }
    if (!data || typeof data !== "object" || !data.metrics || !data.pipeline
        || !data.attention || !Array.isArray(data.recent_activity)) {
        throw new Error("Resposta invalida do dashboard.");
    }
    return data;
}
