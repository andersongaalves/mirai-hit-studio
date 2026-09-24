export const inboxState = {
    page: 1,
    pageSize: 20,
    total: 0,
    pages: 0,
    items: [],
    selected: null,
    loading: false,
    loadingDetail: false,
    sending: false,
    pendingSend: null,
    suggesting: false,
    error: "",
    epoch: 0,
    filters: { search: "", status: "", mode: "", channel: "", handoff: false, assigned: "", updated_from: "", updated_to: "" },
};

export function resetInboxState() {
    inboxState.epoch += 1;
    Object.assign(inboxState, {
        page: 1, total: 0, pages: 0, items: [], selected: null,
        loading: false, loadingDetail: false, sending: false, suggesting: false, pendingSend: null, error: "",
        filters: { search: "", status: "", mode: "", channel: "", handoff: false, assigned: "", updated_from: "", updated_to: "" },
    });
}
