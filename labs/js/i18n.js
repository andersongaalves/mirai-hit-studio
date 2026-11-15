// Languages of the Mirai Hit Labs store: English at /, Portuguese at /pt/.
// Each page declares its language in <html lang>; the texts built by the scripts live here.

export const LANG = (document.documentElement.lang || "en").toLowerCase().startsWith("pt") ? "pt" : "en";
export const LOCALE = LANG === "pt" ? "pt-BR" : "en-US";
export const SITE_URL = "https://labs.miraihitstudio.com.br";
const PREFIX = LANG === "pt" ? "/pt" : "";
const STORAGE_KEY = "labs-lang";

const STRINGS = {
    en: {
        offline: "We couldn't reach the store right now. Check your connection and try again.",
        notFound: "Plugin not found.",
        unavailable: "The store is unavailable at the moment. Try again in a few minutes.",
        free: "Free",
        sale: "Sale",
        featured: "Featured",
        formats: "Formats",
        systems: "Systems",
        and: " and ",
        soon: "Coming soon",
        coverAlt: "{name} plugin cover",
        retry: "Try again",
        emptyTitle: "The first plugins are on the way",
        emptyText: "We're finishing the first Mirai Hit Labs tools. Follow @miraihitstudio to hear about the launch.",
        catalogDown: "Catalog unavailable",
        count: "{n} plugin",
        countMany: "{n} plugins",
        buy: "Buy",
        buyLabel: "Buy",
        getFree: "Get it free",
        oneTime: "one-time payment",
        buyNoteFree: "Sign in to your Mirai Hit Studio account (or create one, it's free) and the plugin goes to My plugins, with the key and the installers.",
        buyNotePaid: "Sign in to your Mirai Hit Studio account (or create one, it's free) and pay by Pix or card. The key and the installers stay in My plugins.",
        youAreHere: "You are here",
        plugins: "Plugins",
        version: "Version",
        license: "License",
        licenseValue: "Personal, with activation key",
        about: "About",
        features: "Features",
        inAction: "In action",
        videoTitle: "{name} video",
        watchVideo: "Watch video",
        requirements: "Requirements",
        missingTitle: "Plugin not found",
        missingPage: "Plugin not found | Mirai Hit Labs",
        missingAddress: "This address doesn't match any plugin.",
        missingGone: "It may have left the catalog or the address changed.",
        allPlugins: "See all plugins",
    },
    pt: {
        offline: "Não foi possível falar com a loja agora. Verifique sua conexão e tente de novo.",
        notFound: "Plugin não encontrado.",
        unavailable: "A loja está indisponível no momento. Tente de novo em alguns minutos.",
        free: "Grátis",
        sale: "Promoção",
        featured: "Destaque",
        formats: "Formatos",
        systems: "Sistemas",
        and: " e ",
        soon: "Em breve",
        coverAlt: "Capa do plugin {name}",
        retry: "Tentar de novo",
        emptyTitle: "Os primeiros plugins estão a caminho",
        emptyText: "Estamos finalizando as primeiras ferramentas da Mirai Hit Labs. Siga @miraihitstudio para saber do lançamento.",
        catalogDown: "Catálogo indisponível",
        count: "{n} plugin",
        countMany: "{n} plugins",
        buy: "Comprar",
        buyLabel: "Comprar",
        getFree: "Baixar grátis",
        oneTime: "pagamento único",
        buyNoteFree: "Entre na sua conta da Mirai Hit Studio (ou crie uma, é grátis) e o plugin vai para Meus plugins, com a chave e os instaladores.",
        buyNotePaid: "Você entra na sua conta da Mirai Hit Studio (ou cria uma, é grátis) e paga por Pix ou cartão. A chave e os instaladores ficam em Meus plugins.",
        youAreHere: "Você está em",
        plugins: "Plugins",
        version: "Versão",
        license: "Licença",
        licenseValue: "Pessoal, com chave de ativação",
        about: "Sobre",
        features: "Recursos",
        inAction: "Em ação",
        videoTitle: "Vídeo do {name}",
        watchVideo: "Ver vídeo",
        requirements: "Requisitos",
        missingTitle: "Plugin não encontrado",
        missingPage: "Plugin não encontrado | Mirai Hit Labs",
        missingAddress: "Este endereço não corresponde a nenhum plugin.",
        missingGone: "Ele pode ter saído do catálogo ou o endereço mudou.",
        allPlugins: "Ver todos os plugins",
    },
};

export function t(key, vars = {}) {
    let text = STRINGS[LANG][key] ?? STRINGS.en[key] ?? key;
    for (const [name, value] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, String(value));
    return text;
}

// A path inside the store, in the page's language ("/plugins/x" -> "/pt/plugins/x").
export function href(path) {
    return `${PREFIX}${path}`;
}

// A plugin text in the page's language; empty English texts fall back to Portuguese.
export function localized(plugin, field) {
    if (LANG === "en") {
        const value = plugin.en?.[field];
        if (Array.isArray(value) ? value.length : value) return value;
    }
    return plugin[field];
}

// The same page in the other language.
export function counterpart(pathname) {
    if (LANG === "pt") return pathname.replace(/^\/pt(?=\/|$)/, "") || "/";
    return pathname === "/" ? "/pt/" : `/pt${pathname}`;
}

function savedLanguage() {
    try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

function saveLanguage(lang) {
    try { window.localStorage.setItem(STORAGE_KEY, lang); } catch { /* private mode: the choice just isn't remembered */ }
}

// Points the EN | PT switch at this page in the other language and remembers the choice.
// Someone who chose Portuguese before and lands on the English store goes to /pt.
export function initLanguage() {
    if (LANG === "en" && savedLanguage() === "pt") {
        window.location.replace(counterpart(window.location.pathname) + window.location.search + window.location.hash);
        return false;
    }
    document.querySelectorAll("[data-lang-switch]").forEach(link => {
        link.href = counterpart(window.location.pathname) + window.location.search + window.location.hash;
        link.addEventListener("click", () => saveLanguage(link.dataset.langSwitch));
    });
    return true;
}
