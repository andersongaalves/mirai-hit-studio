export const newsletterState = {
    subscribers: [],
    campaigns: [],
    loading: false,
    error: "",
    tab: "campaigns",
    filter: { busca: "", status: "todos" },
};


export function resetNewsletterState() {
    newsletterState.subscribers = [];
    newsletterState.campaigns = [];
    newsletterState.loading = false;
    newsletterState.error = "";
    newsletterState.tab = "campaigns";
    newsletterState.filter = { busca: "", status: "todos" };
}
