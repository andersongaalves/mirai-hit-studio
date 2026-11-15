// Where the store talks to the API (catalog, account, purchases) and where the studio site is.
const PRODUCTION_HOSTS = new Set(["labs.miraihitstudio.com.br", "mirai-hit-labs.pages.dev"]);
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const host = window.location.hostname;
const local = LOCAL_HOSTS.has(host);

export const API_URL = local ? "http://localhost:8000"
    : PRODUCTION_HOSTS.has(host) ? "https://api.miraihitstudio.com.br"
        : "https://api.mirai-labs-preview.invalid";
export const STUDIO_URL = local ? "http://localhost:4173" : "https://miraihitstudio.com.br";

// International payment (Stripe, US dollars) on the English store. Off for now: both stores sell in
// reais through the Mirai checkout (Mercado Pago, Pix or card). To turn it on, set this to true and,
// on the API, LABS_STRIPE_ENABLED=true with the Stripe keys (docs/MIRAI_LABS_CONTAS.md).
export const INTERNATIONAL_PAYMENT = false;
