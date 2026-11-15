// /activate?token=...: the link from the confirmation e-mail. Checks the link, lets the
// customer choose username and password, signs in and opens My plugins.
import { api, signIn } from "./auth.js";
import { href, t } from "./i18n.js";
import { READY, el } from "./labs.js";

const root = document.getElementById("activate");

// The token leaves the address bar right away (history, screenshots, shared links).
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

function message(text) {
    const box = el("div", "panel panel--wide");
    const back = el("a", "btn btn--ghost", t("signInTitle"));
    back.href = href("/account");
    box.append(el("p", "panel__lead", text), back);
    root.replaceChildren(box);
}

function input(name, type, attrs = {}) {
    const node = el("input", "field__input");
    node.name = name;
    node.type = type;
    Object.entries(attrs).forEach(([key, value]) => { node[key] = value; });
    return node;
}

function field(label, control) {
    const wrap = el("label", "field");
    wrap.append(el("span", "field__label", label), control);
    return wrap;
}

function form(token) {
    const panel = el("section", "panel panel--wide");
    const formNode = el("form", "form");
    const username = input("username", "text", { required: true, maxLength: 50, autocomplete: "username", autocapitalize: "none", spellcheck: false });
    const password = input("password", "password", { required: true, minLength: 8, maxLength: 72, autocomplete: "new-password" });
    const confirm = input("confirm", "password", { required: true, minLength: 8, maxLength: 72, autocomplete: "new-password" });
    const status = el("p", "form-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const submit = el("button", "btn", t("activateButton"));
    submit.type = "submit";
    formNode.append(field(t("username"), username), field(t("newPassword"), password), field(t("confirmPassword"), confirm), submit, status);
    formNode.addEventListener("submit", async event => {
        event.preventDefault();
        confirm.setCustomValidity(confirm.value === password.value ? "" : t("passwordsDiffer"));
        password.setCustomValidity(password.value.length >= 8 ? "" : t("passwordShort"));
        if (!formNode.reportValidity()) return;
        submit.disabled = true;
        submit.textContent = t("activating");
        status.textContent = "";
        const login = username.value.trim();
        try {
            await api("/cliente-acessos/ativar", { method: "POST", body: { token, username: login, password: password.value } });
            status.textContent = t("activated");
            await signIn(login, password.value);
            window.location.assign(href("/my-plugins"));
        } catch (error) {
            status.textContent = error.message;
            submit.disabled = false;
            submit.textContent = t("activateButton");
        }
    });
    [password, confirm].forEach(node => node.addEventListener("input", () => node.setCustomValidity("")));
    panel.append(el("h1", "panel__title", t("activateTitle")), el("p", "panel__lead", t("activateLead")), formNode);
    root.replaceChildren(panel);
    username.focus();
}

async function start() {
    const token = takeToken();
    if (!token) {
        message(t("noToken"));
        return;
    }
    root.replaceChildren(el("p", "eyebrow", t("checkingLink")));
    try {
        const result = await api("/cliente-acessos/validar", { method: "POST", body: { token } });
        const state = result?.estado;
        if (state === "valido") form(token);
        else message(t(state === "utilizado" ? "linkUsed" : state === "revogado" ? "linkRevoked" : "linkExpired"));
    } catch (error) {
        message(error.status === 404 || error.status === 422 ? t("linkInvalid") : error.message);
    }
}

if (READY && root) start();
