import { authFetch } from "../auth.js";


export async function carregarDashboardApi() {
    const response = await authFetch("/dashboard");
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(typeof data?.detail === "string"
            ? data.detail
            : "Não foi possível carregar o dashboard.");
    }
    if (!data || typeof data !== "object" || !data.metrics || !data.pipeline
        || !data.attention || !Array.isArray(data.recent_activity)) {
        throw new Error("Resposta inválida do dashboard.");
    }
    return data;
}
