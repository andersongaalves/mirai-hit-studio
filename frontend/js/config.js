const LOCAL_API = "http://localhost:8000";
const PROD_API = "https://mirai-hit-studio.onrender.com";
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
