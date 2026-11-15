// /reset-password?token=...: the link from the password e-mail (same password on Labs and Studio).
import { api } from "./auth.js";
import { href, t } from "./i18n.js";
import { READY, el } from "./labs.js";

const root = document.getElementById("reset");

function takeToken() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
        params.delete("token");
        const rest = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : ""));
    }
    return token && token.length >= 32 && token.length <= 512 ? token : null;
}

function finished(text) {
    const box = el("div", "panel panel--wide");
    const go = el("a", "btn", t("signInTitle"));
    go.href = href("/account");
    box.append(el("p", "panel__lead", text), go);
    root.replaceChildren(box);
}

function input(name) {
    const node = el("input", "field__input");
    node.name = name;
    node.type = "password";
    node.required = true;
    node.minLength = 8;
    node.maxLength = 72;
    node.autocomplete = "new-password";
    return node;
}

function field(label, control) {
    const wrap = el("label", "field");
    wrap.append(el("span", "field__label", label), control);
    return wrap;
}

function start() {
    const token = takeToken();
    if (!token) {
        finished(t("noToken"));
        return;
    }
    const panel = el("section", "panel panel--wide");
    const form = el("form", "form");
    const password = input("password");
    const confirm = input("confirm");
    const status = el("p", "form-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const submit = el("button", "btn", t("resetButton"));
    submit.type = "submit";
    form.append(field(t("newPassword"), password), field(t("confirmPassword"), confirm), submit, status);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        confirm.setCustomValidity(confirm.value === password.value ? "" : t("passwordsDiffer"));
        if (!form.reportValidity()) return;
        submit.disabled = true;
        submit.textContent = t("saving");
        status.textContent = "";
        try {
            await api("/auth/password-recovery/reset", { method: "POST", body: { token, password: password.value } });
            finished(t("resetDone"));
        } catch (error) {
            status.textContent = error.status === 409 || error.status === 422 || error.status === 404 ? t("linkInvalid") : error.message;
            submit.disabled = false;
            submit.textContent = t("resetButton");
        }
    });
    confirm.addEventListener("input", () => confirm.setCustomValidity(""));
    panel.append(el("h1", "panel__title", t("resetTitle")), el("p", "panel__lead", t("resetLead")), form);
    root.replaceChildren(panel);
    password.focus();
}

if (READY && root) start();
