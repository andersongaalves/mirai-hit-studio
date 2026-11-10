// Where the store reads the catalog and where purchases continue (the studio site,
// with the customer's account and the checkout).
const PRODUCTION_HOSTS = new Set(["labs.miraihitstudio.com.br", "mirai-hit-labs.pages.dev"]);
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const host = window.location.hostname;
const local = LOCAL_HOSTS.has(host);

export const API_URL = local ? "http://localhost:8000"
    : PRODUCTION_HOSTS.has(host) ? "https://api.miraihitstudio.com.br"
        : "https://api.mirai-labs-preview.invalid";
export const STUDIO_URL = local ? "http://localhost:4173" : "https://miraihitstudio.com.br";

export function purchaseUrl(slug) {
    return `${STUDIO_URL}/cliente/plugins/comprar/${encodeURIComponent(slug)}`;
}
