const FOCUSABLE_SELECTOR = [
    "a[href]",
    "button:not([disabled])",
    "input:not([type='hidden']):not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
].join(",");

const modalStates = new WeakMap();
const modalStack = [];
let initialized = false;

function resolveModal(modal) {
    if (typeof modal === "string") return document.getElementById(modal);
    return modal instanceof HTMLElement ? modal : null;
}

function focusableElements(modal) {
    return [...modal.querySelectorAll(FOCUSABLE_SELECTOR)].filter((element) => (
        !element.closest("[hidden], .hidden")
        && element.getAttribute("aria-hidden") !== "true"
    ));
}

function topModal() {
    return modalStack.at(-1) || null;
}

function handleTab(event, modal) {
    const focusable = focusableElements(modal);
    if (!focusable.length) {
        event.preventDefault();
        modal.focus();
        return;
    }

    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    } else if (document.activeElement === modal || !modal.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
    }
}

function handleKeydown(event) {
    const modal = topModal();
    if (!modal) return;

    if (event.key === "Escape") {
        event.preventDefault();
        const requestClose = modalStates.get(modal)?.onRequestClose;
        if (requestClose) requestClose();
        else closeAdminModal(modal);
        return;
    }

    if (event.key === "Tab") handleTab(event, modal);
}

function initialize() {
    if (initialized) return;
    initialized = true;
    document.addEventListener("keydown", handleKeydown);
}

export function openAdminModal(modalOrId, options = {}) {
    const modal = resolveModal(modalOrId);
    if (!modal) return false;
    initialize();

    const existing = modalStates.get(modal);
    const configuredOpener = typeof options.opener === "string"
        ? document.querySelector(options.opener)
        : options.opener;
    const opener = configuredOpener
        || (existing?.opener?.isConnected ? existing.opener : null)
        || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    modalStates.set(modal, {
        opener,
        onRequestClose: options.onRequestClose || existing?.onRequestClose || null,
    });

    const previousIndex = modalStack.indexOf(modal);
    if (previousIndex !== -1) modalStack.splice(previousIndex, 1);
    modalStack.push(modal);

    modal.classList.add("modal");
    modal.classList.remove("hidden");
    if (!modal.hasAttribute("role")) modal.setAttribute("role", "dialog");
    if (!modal.hasAttribute("aria-modal")) modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-hidden", "false");
    if (!modal.hasAttribute("tabindex")) modal.tabIndex = -1;
    document.body.classList.add("admin-modal-open");

    queueMicrotask(() => {
        if (topModal() !== modal) return;
        const initial = typeof options.initialFocus === "string"
            ? modal.querySelector(options.initialFocus)
            : options.initialFocus;
        const target = initial || focusableElements(modal)[0] || modal;
        target?.focus();
    });
    return true;
}

export function closeAdminModal(modalOrId, { restoreFocus = true } = {}) {
    const modal = resolveModal(modalOrId);
    if (!modal) return false;

    const state = modalStates.get(modal);
    const index = modalStack.indexOf(modal);
    if (index !== -1) modalStack.splice(index, 1);

    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    modalStates.delete(modal);
    if (!modalStack.length) document.body.classList.remove("admin-modal-open");

    if (restoreFocus && state?.opener?.isConnected) {
        queueMicrotask(() => state.opener.focus());
    }
    return true;
}

export function closeAllAdminModals({ restoreFocus = false } = {}) {
    [...modalStack].reverse().forEach((modal) => {
        closeAdminModal(modal, { restoreFocus });
    });

    document.querySelectorAll(".modal:not(.hidden)").forEach((modal) => {
        closeAdminModal(modal, { restoreFocus: false });
    });
}
