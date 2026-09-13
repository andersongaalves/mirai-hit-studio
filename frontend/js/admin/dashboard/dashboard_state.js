export const dashboardState = {
    data: null,
    loading: false,
    error: "",
};

export function resetDashboardState() {
    dashboardState.data = null;
    dashboardState.loading = false;
    dashboardState.error = "";
}
