// /account: sign in (Labs or Mirai Hit Studio customer account), create a Labs account
// and ask for a new password. After signing in, goes back to ?next= (e.g. the plugin).
import { api, currentUser, isSignedIn, signIn, signOut } from "./auth.js";
import { LANG, href, safeNext, t } from "./i18n.js";
import { READY, el } from "./labs.js";

const root = document.getElementById("account");
const PRIVACY_URL = "https://miraihitstudio.com.br/privacidade";
const params = new URLSearchParams(window.location.search);
const next = safeNext(params.get("next"));

function field(label, input) {
    const wrap = el("label", "field");
    wrap.append(el("span", "field__label", label), input);
    return wrap;
}

function input(name, type, attrs = {}) {
    const node = el("input", "field__input");
    node.name = name;
    node.type = type;
    Object.entries(attrs).forEach(([key, value]) => { node[key] = value; });
    return node;
}

function status() {
    const node = el("p", "form-status");
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    return node;
}

function setBusy(button, busy, label) {
    button.disabled = busy;
    if (label) button.textContent = label;
}

function goAfterSignIn() {
    window.location.assign(next || href("/my-plugins"));
}

function signInPanel() {
    const panel = el("section", "panel");
    panel.setAttribute("aria-labelledby", "signin-title");
    const title = el("h2", "panel__title", t("signInTitle"));
    title.id = "signin-title";
    const form = el("form", "form");
    form.noValidate = false;
    const username = input("username", "text", { required: true, maxLength: 50, autocomplete: "username", autocapitalize: "none", spellcheck: false });
    const password = input("password", "password", { required: true, maxLength: 72, autocomplete: "current-password" });
    const message = status();
    const submit = el("button", "btn", t("signInButton"));
    submit.type = "submit";
    const forgot = el("button", "link-button", t("forgot"));
    forgot.type = "button";
    form.append(field(t("username"), username), field(t("password"), password), submit, forgot, message);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        setBusy(submit, true, t("signingIn"));
        message.textContent = "";
        try {
            await signIn(username.value.trim(), password.value);
            goAfterSignIn();
        } catch (error) {
            message.textContent = error.message;
            setBusy(submit, false, t("signInButton"));
            password.select();
        }
    });
    const forgotBox = forgotPanel(() => { forgotBox.hidden = true; form.hidden = false; username.focus(); });
    forgotBox.hidden = true;
    forgot.addEventListener("click", () => { form.hidden = true; forgotBox.hidden = false; forgotBox.querySelector("input").focus(); });
    panel.append(title, el("p", "panel__lead", t("signInLead")), form, forgotBox);
    return panel;
}

function forgotPanel(onBack) {
    const box = el("div", "subpanel");
    const form = el("form", "form");
    const email = input("email", "email", { required: true, maxLength: 150, autocomplete: "email" });
    const message = status();
    const submit = el("button", "btn", t("sendLink"));
    submit.type = "submit";
    const back = el("button", "link-button", t("backToSignIn"));
    back.type = "button";
    back.addEventListener("click", onBack);
    form.append(field(t("email"), email), submit, back, message);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        setBusy(submit, true, t("sending"));
        message.textContent = "";
        try {
            await api("/auth/password-recovery", { method: "POST", body: { email: email.value.trim(), canal: "labs", idioma: LANG } });
            message.textContent = t("forgotSent");
        } catch (error) {
            message.textContent = error.message;
        } finally {
            setBusy(submit, false, t("sendLink"));
        }
    });
    box.append(el("h3", "subpanel__title", t("forgotTitle")), el("p", "panel__lead", t("forgotLead")), form);
    return box;
}

function signUpPanel() {
    const panel = el("section", "panel");
    panel.setAttribute("aria-labelledby", "signup-title");
    const title = el("h2", "panel__title", t("signUpTitle"));
    title.id = "signup-title";
    const form = el("form", "form");
    const name = input("nome", "text", { required: true, maxLength: 120, autocomplete: "name" });
    const email = input("email", "email", { required: true, maxLength: 150, autocomplete: "email" });
    const consent = el("label", "check");
    const box = input("privacy", "checkbox", { required: true });
    const text = el("span");
    const [before, after] = t("privacy").split(t("privacyLink"));
    const link = el("a", "", t("privacyLink"));
    link.href = PRIVACY_URL;
    link.target = "_blank";
    link.rel = "noopener";
    text.append(document.createTextNode(before || ""), link, document.createTextNode(after || ""));
    consent.append(box, text);
    const message = status();
    const submit = el("button", "btn btn--ghost", t("createButton"));
    submit.type = "submit";
    form.append(field(t("name"), name), field(t("email"), email), consent, submit, message);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        setBusy(submit, true, t("creating"));
        message.textContent = "";
        const address = email.value.trim();
        try {
            await api("/auth/client-signup", { method: "POST", body: {
                nome: name.value.trim(), email: address, privacy_accepted: true, canal: "labs", idioma: LANG,
            } });
            form.replaceChildren(sentNotice(address));
        } catch (error) {
            message.textContent = error.message;
            setBusy(submit, false, t("createButton"));
        }
    });
    panel.append(title, el("p", "panel__lead", t("signUpLead")), form);
    return panel;
}

function sentNotice(address) {
    const box = el("div", "notice");
    box.setAttribute("role", "status");
    const message = status();
    const resend = el("button", "btn btn--ghost", t("resend"));
    resend.type = "button";
    resend.addEventListener("click", async () => {
        setBusy(resend, true, t("sending"));
        try {
            await api("/auth/client-signup/resend", { method: "POST", body: { email: address } });
            message.textContent = t("resent");
        } catch (error) {
            message.textContent = error.message;
        } finally {
            setBusy(resend, false, t("resend"));
        }
    });
    box.append(el("p", "", t("signUpSent", { email: address })), resend, message);
    return box;
}

function signedInPanel() {
    const user = currentUser();
    const panel = el("section", "panel panel--wide");
    const name = user?.nome_exibicao || user?.username || "";
    const go = el("a", "btn", t("goMyPlugins"));
    go.href = next || href("/my-plugins");
    const out = el("button", "btn btn--ghost", t("signOut"));
    out.type = "button";
    out.addEventListener("click", () => { signOut(); render(); });
    const actions = el("div", "panel__actions");
    actions.append(go, out);
    panel.append(el("h2", "panel__title", t("signedInAs", { name })), actions);
    return panel;
}

function render() {
    root.replaceChildren(...(isSignedIn() ? [signedInPanel()] : [signInPanel(), signUpPanel()]));
}

if (READY && root) render();
