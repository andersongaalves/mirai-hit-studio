export const auditoriaState = {
    items: [],
    loading: false,
    error: "",
    total: 0,
    page: 1,
    pageSize: 25,
    pages: 0,
    filters: { action: "", entityType: "", entityId: "", actorUserId: "", dateFrom: "", dateTo: "" },
};


export function resetAuditoriaState() {
    auditoriaState.items = [];
    auditoriaState.loading = false;
    auditoriaState.error = "";
    auditoriaState.total = 0;
    auditoriaState.page = 1;
    auditoriaState.pages = 0;
    auditoriaState.filters = { action: "", entityType: "", entityId: "", actorUserId: "", dateFrom: "", dateTo: "" };
}
