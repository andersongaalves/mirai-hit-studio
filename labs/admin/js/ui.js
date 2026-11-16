// Small DOM helpers for the admin panel (no framework; everything built with textContent).

export function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
        if (value === undefined || value === null || value === false) continue;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else if (key === "dataset") Object.assign(node.dataset, value);
        else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
        else if (key in node && typeof value !== "string") node[key] = value;
        else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
}

// ---------------------------------------------------------------- formatting

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const USD = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
const DATE = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
const DATETIME = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });

export const money = (value, currency = "brl") => (currency === "usd" ? USD : BRL).format(Number(value || 0));
export const date = value => (value ? DATE.format(new Date(value)) : "—");
export const datetime = value => (value ? DATETIME.format(new Date(value)) : "—");
export const size = bytes => (bytes ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB` : "");
export const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;

export function slugify(text) {
    return String(text || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
        .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
}

// ISO value for <input type="datetime-local"> and back.
export function toLocalInput(iso) {
    if (!iso) return "";
    const value = new Date(iso);
    const pad = number => String(number).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}
export const fromLocalInput = value => (value ? new Date(value).toISOString() : null);

// ---------------------------------------------------------------- pieces

export function chip(text, tone = "") {
    return el("span", { class: `chip${tone ? ` chip--${tone}` : ""}`, text });
}

export const LICENCA = {
    ativa: ["Ativa", "ok"], reservada: ["Aguardando pagamento", "warn"],
    revogada: ["Revogada", "bad"], cancelada: ["Cancelada", ""],
};
export const ORIGEM = { compra: "Compra (BRL)", stripe: "Compra (USD)", gratuito: "Grátis", cortesia: "Cortesia" };

export function licenseChip(row) {
    if (row.status === "reservada" && row.motivo === "pagamento_revertido") return chip("Suspensa", "bad");
    if (row.motivo === "checkout_expirado") return chip("Checkout expirado");
    const [label, tone] = LICENCA[row.status] || [row.status, ""];
    return chip(label, tone);
}

export const PEDIDO = {
    pago: ["Pago", "ok"], aguardando: ["Aguardando", "warn"], expirado: ["Expirado", ""],
    cancelado: ["Cancelado", ""], revogado: ["Revogado", "bad"], reembolsado: ["Reembolsado", "bad"],
    contestado: ["Contestado", "bad"], revertido: ["Revertido", "bad"],
};
export const PLUGIN_STATUS = { rascunho: ["Rascunho", ""], publicado: ["Publicado", "ok"], arquivado: ["Arquivado", "bad"] };

export function field(label, input, { help = "", full = false } = {}) {
    return el("label", { class: `field${full ? " field--full" : ""}` },
        el("span", { class: "field__label", text: label }), input,
        help ? el("span", { class: "field__help", text: help }) : null);
}

export function input(name, value = "", attrs = {}) {
    const node = el("input", { class: "field__input", name, ...attrs });
    node.value = value ?? "";
    return node;
}

export function textarea(name, value = "", attrs = {}) {
    const node = el("textarea", { class: "field__input", name, rows: 4, ...attrs });
    node.value = value ?? "";
    return node;
}

export function select(name, options, value = "", attrs = {}) {
    const node = el("select", { class: "field__input", name, ...attrs },
        ...Object.entries(options).map(([key, label]) => el("option", { value: key, text: label })));
    node.value = value ?? "";
    return node;
}

export function checkbox(name, checked, label) {
    const box = el("input", { type: "checkbox", name });
    box.checked = Boolean(checked);
    return el("label", { class: "check" }, box, el("span", { text: label }));
}

export function table(headers, rows, empty = "Nada por aqui ainda.") {
    if (!rows.length) return el("div", { class: "empty", text: empty });
    const head = el("tr", {}, ...headers.map(item => {
        const [label, className] = Array.isArray(item) ? item : [item, ""];
        return el("th", { class: className, scope: "col", text: label });
    }));
    return el("div", { class: "table-wrap" }, el("table", { class: "table" }, el("thead", {}, head), el("tbody", {}, ...rows)));
}

export function cell(content, className = "") {
    return el("td", { class: className }, content);
}

export function pageHead(title, { lead = "", crumb = null, actions = [] } = {}) {
    return el("div", { class: "page-head" },
        el("div", {}, crumb, el("h1", { class: "page-title", text: title }), lead ? el("p", { class: "page-lead", text: lead }) : null),
        actions.length ? el("div", { class: "actions" }, ...actions) : null);
}

export const loading = (text = "Carregando...") => el("p", { class: "loading", text });
export const errorBox = error => el("p", { class: "error-box", role: "alert", text: error?.message || String(error) });

export function cover(url, label = "") {
    const box = el("div", { class: "cover" });
    if (url) box.append(el("img", { src: url, alt: label, loading: "lazy", decoding: "async" }));
    else box.append(el("span", { text: "Sem capa" }));
    return box;
}

// ---------------------------------------------------------------- feedback

export function toast(text, tone = "") {
    const root = document.getElementById("toasts");
    const node = el("div", { class: `toast${tone ? ` toast--${tone}` : ""}`, text });
    root.append(node);
    while (root.children.length > 3) root.firstElementChild.remove();
    setTimeout(() => node.remove(), tone === "error" ? 7000 : 4000);
}

// A modal dialog; `build(close)` returns its body. Resolves with what close() receives.
export function dialog(title, build, { wide = false } = {}) {
    return new Promise(resolve => {
        const box = el("dialog", { class: `dialog${wide ? " dialog--wide" : ""}`, "aria-labelledby": "dialog-title" });
        const close = value => { box.close(); box.remove(); resolve(value); };
        box.addEventListener("cancel", event => { event.preventDefault(); close(null); });
        const body = el("div", { class: "dialog__body" }, el("h2", { class: "dialog__title", id: "dialog-title", text: title }));
        body.append(build(close));
        box.append(body);
        document.body.append(box);
        box.showModal();
    });
}

// Confirmation with consequences and, optionally, a required reason.
export function confirm({ title, lines = [], button = "Confirmar", danger = false, reason = null }) {
    return dialog(title, close => {
        const form = el("form", { class: "dialog__form" });
        lines.forEach(line => form.append(el("p", { class: "muted flush", text: line })));
        let reasonInput = null;
        if (reason) {
            reasonInput = input("motivo", "", { required: true, minLength: 3, maxLength: reason.max || 40 });
            form.append(field(reason.label, reasonInput));
        }
        const cancel = el("button", { class: "btn btn--ghost btn--small", type: "button", text: "Cancelar", onclick: () => close(null) });
        const ok = el("button", { class: `btn btn--small${danger ? " btn--danger" : ""}`, type: "submit", text: button });
        form.append(el("div", { class: "dialog__foot" }, cancel, ok));
        form.addEventListener("submit", event => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            close(reasonInput ? { motivo: reasonInput.value.trim() } : true);
        });
        setTimeout(() => (reasonInput || ok).focus(), 0);
        return form;
    });
}

// Runs an async action from a button: disables it and reports the error inline or as a toast.
export async function busy(button, action, status = null) {
    if (button) button.disabled = true;
    if (status) { status.textContent = ""; status.classList.remove("form-status--error"); }
    try {
        return await action();
    } catch (error) {
        if (status) { status.textContent = error.message; status.classList.add("form-status--error"); }
        else toast(error.message, "error");
        return undefined;
    } finally {
        if (button) button.disabled = false;
    }
}

export async function copy(text) {
    try {
        await navigator.clipboard.writeText(text);
        toast("Copiado.");
    } catch {
        toast("Não foi possível copiar.", "error");
    }
}
