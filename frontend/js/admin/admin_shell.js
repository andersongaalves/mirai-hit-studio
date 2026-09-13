const MOBILE_BREAKPOINT = 900;

let initialized = false;
let navigate = null;

function elements() {
    return {
        shell: document.getElementById("admin-area"),
        navigation: document.getElementById("admin-navigation"),
        toggle: document.getElementById("admin-nav-toggle"),
    };
}

function setMobileNavigation(open) {
    const { navigation, toggle } = elements();
    if (!navigation || !toggle) return;

    navigation.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (open) {
        queueMicrotask(() => navigation.querySelector(".admin-nav__item")?.focus());
    }
}

export function closeMobileNavigation({ restoreFocus = false } = {}) {
    const { toggle } = elements();
    const wasOpen = toggle?.getAttribute("aria-expanded") === "true";
    setMobileNavigation(false);
    if (wasOpen && restoreFocus) toggle?.focus();
}

export function setActiveSection(sectionId) {
    document.querySelectorAll("[data-admin-target]").forEach((control) => {
        const active = control.dataset.adminTarget === sectionId;
        control.classList.toggle("is-active", active);
        if (control.matches(".admin-nav__item")) {
            if (active) control.setAttribute("aria-current", "page");
            else control.removeAttribute("aria-current");
        }
    });

    closeMobileNavigation();
}

function handleClick(event) {
    const control = event.target.closest("[data-admin-target]");
    if (!control || !elements().shell?.contains(control)) return;

    const target = control.dataset.adminTarget;
    if (!target) return;
    navigate?.(target);
}

function handleKeydown(event) {
    if (event.key !== "Escape") return;
    const { toggle } = elements();
    if (toggle?.getAttribute("aria-expanded") !== "true") return;

    event.preventDefault();
    closeMobileNavigation({ restoreFocus: true });
}

function handleResize() {
    if (window.innerWidth <= MOBILE_BREAKPOINT) return;
    const { navigation } = elements();
    closeMobileNavigation({
        restoreFocus: Boolean(navigation?.contains(document.activeElement)),
    });
}

export function initializeAdminShell({ onNavigate } = {}) {
    if (typeof onNavigate === "function") navigate = onNavigate;
    if (initialized) return;

    const { shell, toggle } = elements();
    if (!shell || !toggle) return;

    initialized = true;
    shell.addEventListener("click", handleClick);
    toggle.addEventListener("click", () => {
        setMobileNavigation(toggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", handleKeydown);
    window.addEventListener("resize", handleResize);
}

export function resetAdminShell() {
    closeMobileNavigation();
    setActiveSection("dashboard-menu");
}
