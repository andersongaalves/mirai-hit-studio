const BREAKPOINT = 900;


function normalizedPath() {
    const aliases = {
        "/index.html": "/",
        "/artists.html": "/artists",
        "/creators.html": "/creators",
        "/media-games.html": "/media-games",
        "/portfolio.html": "/portfolio",
        "/calculadora.html": "/orcamento",
    };
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    return aliases[path] || path;
}


export function initPublicNavigation() {
    const nav = document.querySelector(".site-nav");
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

    const activePath = normalizedPath();
    nav.querySelectorAll("[data-public-path]").forEach(link => {
        if (link.dataset.publicPath === activePath) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });
}
