const shell = document.querySelector(".integrado-portal");
const toggle = shell?.querySelector(".integrado-portal__menu-toggle");
const sidebar = shell?.querySelector(".producer-sidebar");
const mobile = window.matchMedia("(max-width: 767px)");

function setMenuOpen(open, returnFocus = false) {
    if (!shell || !toggle) return;
    shell.classList.toggle("is-menu-open", open && mobile.matches);
    toggle.setAttribute("aria-expanded", String(open && mobile.matches));
    toggle.textContent = open && mobile.matches ? "Fechar" : "Menu";
    if (returnFocus) toggle.focus();
}

toggle?.addEventListener("click", () => {
    setMenuOpen(toggle.getAttribute("aria-expanded") !== "true");
});

sidebar?.addEventListener("click", event => {
    if (event.target.closest(".producer-nav a")) setMenuOpen(false);
});

document.addEventListener("keydown", event => {
    if (event.target.closest("dialog[open]")) return;
    if (!mobile.matches || toggle?.getAttribute("aria-expanded") !== "true") return;
    if (event.key === "Escape") {
        event.preventDefault();
        setMenuOpen(false, true);
        return;
    }
    if (event.key !== "Tab") return;
    const focusable = [toggle, ...sidebar.querySelectorAll(".producer-nav a:not(.hidden), .producer-account button")]
        .filter(element => element && !element.hidden && element.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
});

mobile.addEventListener("change", () => setMenuOpen(false));
