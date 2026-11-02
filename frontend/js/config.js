const LOCAL_API = "http://localhost:8000";
// Everything goes through Cloudflare (WAF, rate limiting) on the API subdomain.
const PROD_API = "https://api.miraihitstudio.com.br";
// Cloudflare's free plan refuses request bodies above 100 MB, so file uploads (beats,
// final deliveries) go straight to Render; that address accepts only uploads.
const PROD_UPLOAD_API = "https://mirai-hit-studio.onrender.com";
// Reserved TLD (RFC 2606): never resolves, so non-production hosts cannot reach real data.
const NO_API = "https://api-indisponivel-fora-de-producao.invalid";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
// Only the official domains talk to the production API (AUD-S12-004). Previews
// (Netlify, Cloudflare branch deployments) must not create real records.
const PRODUCTION_HOSTS = new Set([
    "miraihitstudio.com.br",
    "www.miraihitstudio.com.br",
    "mirai-hit-studio.pages.dev",
]);

const hostname = window.location.hostname;

export const API_URL = LOCAL_HOSTS.has(hostname)
    ? LOCAL_API
    : PRODUCTION_HOSTS.has(hostname)
        ? PROD_API
        : NO_API;

export const UPLOAD_API = LOCAL_HOSTS.has(hostname)
    ? LOCAL_API
    : PRODUCTION_HOSTS.has(hostname)
        ? PROD_UPLOAD_API
        : NO_API;

// Base address for a request: multipart file uploads use the direct upload address.
export const apiPara = body => (typeof FormData !== "undefined" && body instanceof FormData ? UPLOAD_API : API_URL);
