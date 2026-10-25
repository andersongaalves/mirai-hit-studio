import { carregarDashboardApi } from "./dashboard_api.js";
import { dashboardState } from "./dashboard_state.js";
import { renderFalhasTag } from "./dashboard_tag_failures.js";
import { renderDashboard, renderDashboardError, renderDashboardLoading } from "./dashboard_ui.js";


let request = null;
document.addEventListener("classificacao:atualizada", () => { carregarDashboard().catch(() => {}); });

export async function carregarDashboard() {
    if (request) return request;
    dashboardState.loading = true;
    dashboardState.error = "";
    renderDashboardLoading();
    request = carregarDashboardApi()
        .then((data) => {
            dashboardState.data = data;
            renderDashboard(data);
            renderFalhasTag(data);
            return data;
        })
        .catch((error) => {
            dashboardState.error = error.message;
            renderDashboardError(carregarDashboard);
            throw error;
        })
        .finally(() => {
            dashboardState.loading = false;
            request = null;
        });
    return request;
}
