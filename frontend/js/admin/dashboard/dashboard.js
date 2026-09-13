import { carregarDashboardApi } from "./dashboard_api.js";
import { dashboardState } from "./dashboard_state.js";
import { renderDashboard, renderDashboardError, renderDashboardLoading } from "./dashboard_ui.js";


let request = null;

export async function carregarDashboard() {
    if (request) return request;
    dashboardState.loading = true;
    dashboardState.error = "";
    renderDashboardLoading();
    request = carregarDashboardApi()
        .then((data) => {
            dashboardState.data = data;
            renderDashboard(data);
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
