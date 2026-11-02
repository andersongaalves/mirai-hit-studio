// Where a visit came from, for the Marketing area: campaign tags (utm_*), the referring
// site (host only) and the landing page. First-party, no personal data, kept 30 days in
// this browser and sent only with a lead the person chooses to submit.
const KEY = "mirai.origem.v1";
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const UTM = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
const OWN_HOSTS = /(^|\.)miraihitstudio\.com\.br$|(^|\.)mirai-hit-studio\.pages\.dev$|^localhost$|^127\.0\.0\.1$/;

const clean = value => String(value || "").replace(/\s+/g, " ").trim().slice(0, 100) || null;

function read() {
    try {
        const saved = JSON.parse(localStorage.getItem(KEY) || "null");
        if (saved && Date.now() - new Date(saved.primeiro_acesso).getTime() < MAX_AGE_MS) return saved;
    } catch { /* storage unavailable or corrupt: start fresh */ }
    return null;
}

function write(value) {
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { /* private mode: lead goes without origin */ }
}

export function registrarOrigem(location = window.location, referrer = document.referrer) {
    const params = new URLSearchParams(location.search);
    const tags = Object.fromEntries(UTM.map(name => [name, clean(params.get(name))]).filter(([, value]) => value));
    let host = null;
    try { host = referrer ? new URL(referrer).hostname.toLowerCase() : null; } catch { host = null; }
    const external = host && !OWN_HOSTS.test(host) ? host.slice(0, 120) : null;
    const current = read();
    // A tagged link (new campaign) or an outside referrer starts a new attribution;
    // navigation inside the site keeps the first one.
    if (current && !Object.keys(tags).length && !external) return current;
    if (current && !Object.keys(tags).length && external && current.referrer === external) return current;
    const origem = {
        ...tags,
        referrer: external,
        landing: (location.pathname || "/").slice(0, 200),
        primeiro_acesso: new Date().toISOString(),
    };
    write(origem);
    return origem;
}

export function origemMarketing() {
    const saved = read();
    if (!saved) return null;
    const output = {};
    for (const key of [...UTM, "referrer", "landing", "primeiro_acesso"]) {
        if (saved[key]) output[key] = saved[key];
    }
    return Object.keys(output).length ? output : null;
}
