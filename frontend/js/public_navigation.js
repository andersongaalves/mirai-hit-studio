const BREAKPOINT = 900;
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
const LOCAL_ROUTE_FILES = {
    "/": "index.html",
    "/artists": "artists.html",
    "/creators": "creators.html",
    "/media-games": "media-games.html",
    "/portfolio": "portfolio.html",
    "/orcamento": "calculadora.html",
    "/acesso": "acesso.html",
    "/cadastro": "cadastro.html",
};


function adaptLinksForLocalStaticPreview() {
    const isLocalHtmlPreview = LOCAL_HOSTS.has(window.location.hostname)
        && window.location.pathname.toLowerCase().endsWith(".html");
    if (!isLocalHtmlPreview) return;

    document.querySelectorAll('a[href^="/"]').forEach(link => {
        const target = new URL(link.getAttribute("href"), window.location.origin);
        const route = target.pathname.replace(/\/$/, "") || "/";
        const filename = LOCAL_ROUTE_FILES[route];
        if (!filename) return;

        const localTarget = new URL(filename, window.location.href);
        localTarget.search = target.search;
        localTarget.hash = target.hash;
        link.href = localTarget.href;
    });
}


function normalizedPath() {
    const aliases = {
        "/index.html": "/",
        "/artists.html": "/artists",
        "/creators.html": "/creators",
        "/media-games.html": "/media-games",
        "/portfolio.html": "/portfolio",
        "/calculadora.html": "/orcamento",
        "/acesso.html": "/acesso",
        "/cadastro.html": "/cadastro",
    };
    const pathname = window.location.pathname.replace(/\/$/, "") || "/";
    const path = LOCAL_HOSTS.has(window.location.hostname) && pathname.toLowerCase().endsWith(".html")
        ? `/${pathname.split("/").pop()}`
        : pathname;
    return aliases[path] || path;
}


export function initPublicNavigation() {
    adaptLinksForLocalStaticPreview();
    const nav = document.querySelector(".site-nav");
    const header = nav?.closest(".site-header");
    const toggle = document.getElementById("site-nav-toggle");
    const links = document.getElementById("site-nav-links");
    if (!nav || !toggle || !links || nav.dataset.initialized === "true") return;
    nav.dataset.initialized = "true";
    const close = ({ restoreFocus = false } = {}) => {
        links.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        if (restoreFocus) toggle.focus();
    };

    toggle.addEventListener("click", () => {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        links.classList.toggle("is-open", open);
        toggle.setAttribute("aria-expanded", String(open));
        if (open) links.querySelector("a")?.focus();
    });
    links.addEventListener("click", event => {
        if (event.target.closest("a")) close();
    });
    document.addEventListener("keydown", event => {
        if (event.key !== "Escape" || toggle.getAttribute("aria-expanded") !== "true") return;
        event.preventDefault();
        close({ restoreFocus: true });
    });
    window.addEventListener("resize", () => {
        if (window.innerWidth > BREAKPOINT) close();
    });

    const updateHeaderAppearance = () => {
        header?.classList.toggle("is-scrolled", window.scrollY > 12);
    };
    window.addEventListener("scroll", updateHeaderAppearance, { passive: true });
    updateHeaderAppearance();

    const activePath = normalizedPath();
    nav.querySelectorAll("[data-public-path]").forEach(link => {
        if (link.dataset.publicPath === activePath) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}
