const CONSENT_KEY = "mirai.analytics_consent.v1";
const CONSENT_VALUES = new Set(["unknown", "accepted", "rejected"]);
const EVENT_PROPERTIES = {
    page_view: ["page_path"],
    view_service: ["service_id"],
    begin_briefing: ["service_id"],
    generate_lead: ["service_id"],
    listen_portfolio: ["project_id"],
    newsletter_subscribe: [],
};

let memoryConsent = "unknown";
let providerLoaded = false;
let pageViewSent = false;
let interactionBound = false;
const sentOnce = new Set();

function readConsent() {
    try {
        const value = localStorage.getItem(CONSENT_KEY);
        return CONSENT_VALUES.has(value) ? value : memoryConsent;
    } catch {
        return memoryConsent;
    }
}

function saveConsent(value) {
    memoryConsent = value;
    try {
        localStorage.setItem(CONSENT_KEY, value);
    } catch {
        // Consent still applies during this page when storage is unavailable.
    }
}

function getMeasurementId() {
    const id = document.querySelector('meta[name="mirai-ga-id"]')?.content?.trim();
    return /^G-[A-Z0-9]+$/i.test(id ?? "") ? id : null;
}

function activateProvider() {
    const measurementId = getMeasurementId();
    if (!measurementId || providerLoaded) return Boolean(measurementId);
    providerLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function (...args) { window.dataLayer.push(args); };
    window.gtag("js", new Date());
    window.gtag("consent", "default", { analytics_storage: "denied" });
    window.gtag("config", measurementId, { send_page_view: false });
    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    script.dataset.miraiAnalytics = "true";
    document.head.appendChild(script);
    return true;
}

function sanitizeProperties(eventName, properties = {}) {
    const allowed = EVENT_PROPERTIES[eventName] ?? [];
    const output = {};
    for (const property of allowed) {
        const value = properties[property];
        if ((property === "service_id" || property === "project_id") && Number.isInteger(Number(value)) && Number(value) > 0) {
            output[property] = Number(value);
        }
        if (property === "page_path") output[property] = location.pathname.slice(0, 500) || "/";
    }
    return output;
}

function closeDialog() {
    document.getElementById("analytics-consent-dialog")?.remove();
}

function showDialog() {
    if (document.getElementById("analytics-consent-dialog")) return;
    const dialog = document.createElement("section");
    dialog.id = "analytics-consent-dialog";
    dialog.className = "analytics-consent";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "false");
    dialog.setAttribute("aria-labelledby", "analytics-consent-title");

    const title = document.createElement("h2");
    title.id = "analytics-consent-title";
    title.textContent = "Preferencias de privacidade";
    const text = document.createElement("p");
    text.textContent = "Usamos metricas opcionais para entender quais paginas e servicos ajudam mais. Voce pode aceitar ou recusar sem afetar o uso do site.";
    const actions = document.createElement("div");
    actions.className = "analytics-consent-actions";
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "analytics-consent-button";
    reject.textContent = "Recusar metricas";
    reject.addEventListener("click", () => setAnalyticsConsent("rejected"));
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "analytics-consent-button";
    accept.textContent = "Aceitar metricas";
    accept.addEventListener("click", () => setAnalyticsConsent("accepted"));
    actions.append(reject, accept);
    dialog.append(title, text, actions);
    document.body.appendChild(dialog);
    accept.focus();
}

function ensurePreferencesButton() {
    if (document.getElementById("analytics-preferences")) return;
    const button = document.createElement("button");
    button.id = "analytics-preferences";
    button.type = "button";
    button.className = "analytics-preferences";
    button.textContent = "Privacidade";
    button.addEventListener("click", showDialog);
    document.body.appendChild(button);
}

function bindPortfolioListener() {
    if (interactionBound) return;
    interactionBound = true;
    document.addEventListener("click", event => {
        const link = event.target.closest("[data-analytics-listen]");
        if (link) track("listen_portfolio", { project_id: link.dataset.projectId });
    });
}

export function getAnalyticsConsent() {
    return readConsent();
}

export function setAnalyticsConsent(value) {
    if (!CONSENT_VALUES.has(value) || value === "unknown") return false;
    saveConsent(value);
    closeDialog();
    if (value === "accepted") {
        activateProvider();
        window.gtag?.("consent", "update", { analytics_storage: "granted" });
        if (!pageViewSent) {
            pageViewSent = true;
            track("page_view", { page_path: location.pathname });
        }
    }
    if (value === "rejected" && providerLoaded) {
        window.gtag?.("consent", "update", { analytics_storage: "denied" });
    }
    return true;
}

export function track(eventName, properties = {}) {
    if (!EVENT_PROPERTIES[eventName] || readConsent() !== "accepted" || !activateProvider()) return false;
    window.gtag("event", eventName, sanitizeProperties(eventName, properties));
    return true;
}

export function trackOnce(eventName, properties = {}) {
    if (sentOnce.has(eventName) || !track(eventName, properties)) return false;
    sentOnce.add(eventName);
    return true;
}

export function initAnalytics() {
    ensurePreferencesButton();
    bindPortfolioListener();
    if (readConsent() === "accepted") setAnalyticsConsent("accepted");
    if (readConsent() === "unknown") showDialog();
}
