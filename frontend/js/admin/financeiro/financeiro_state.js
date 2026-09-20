export const financeiroState = {
    summary: null,
    items: [],
    loading: false,
    error: "",
    total: 0,
    page: 1,
    pageSize: 25,
    pages: 0,
    selected: null,
    reconcilingPaymentId: null,
    filters: { search: "", status: "", reconciliationStatus: "", dateFrom: "", dateTo: "" },
};


export function resetFinanceiroState() {
    financeiroState.summary = null;
    financeiroState.items = [];
    financeiroState.loading = false;
    financeiroState.error = "";
    financeiroState.total = 0;
    financeiroState.page = 1;
    financeiroState.pages = 0;
    financeiroState.selected = null;
    financeiroState.reconcilingPaymentId = null;
    financeiroState.filters = { search: "", status: "", reconciliationStatus: "", dateFrom: "", dateTo: "" };
}
