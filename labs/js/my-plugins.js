// /my-plugins: the signed-in customer's licenses, keys, installers and pending payments.
import { API_URL } from "./config.js";
import { api, currentUser, getToken, isSignedIn, refreshUser, signOut } from "./auth.js";
import { href, t } from "./i18n.js";
import { READY, coverNode, el } from "./labs.js";

const root = document.getElementById("library");

function signInPrompt() {
    const box = el("div", "panel panel--wide");
    const go = el("a", "btn", t("signInTitle"));
    go.href = `${href("/account")}?next=${encodeURIComponent(window.location.pathname)}`;
    box.append(el("p", "panel__lead", t("signInToSee")), go);
    root.replaceChildren(box);
}

async function download(license, system, button) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = t("preparing");
    try {
        const response = await fetch(`${API_URL}/labs/conta/plugins/${license.id}/download/${encodeURIComponent(system.sistema)}`, {
            headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (response.status === 401) { signOut(); signInPrompt(); return; }
        if (!response.ok) throw new Error(t("genericError"));
        if ((response.headers.get("Content-Type") || "").includes("application/json")) {
            const data = await response.json();
            // signed storage link or the installer page set by the studio (always https)
            if (typeof data.url === "string" && data.url.startsWith("https://")) window.location.assign(data.url);
            else throw new Error(t("genericError"));
        } else {
            const blob = await response.blob();
            const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
            const link = el("a");
            link.href = URL.createObjectURL(blob);
            link.download = match ? match[1] : `${license.slug}-${system.sistema}.zip`;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 30000);
        }
    } catch (error) {
        button.closest(".license")?.querySelector(".form-status")?.replaceChildren(document.createTextNode(error.message));
    } finally {
        button.disabled = false;
        button.textContent = label;
    }
}

function keyRow(key) {
    const row = el("div", "license__key");
    const code = el("code", "", key);
    const copy = el("button", "btn btn--ghost btn--small", t("copy"));
    copy.type = "button";
    copy.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(key);
            copy.textContent = t("copied");
            setTimeout(() => { copy.textContent = t("copy"); }, 2000);
        } catch {
            window.getSelection()?.selectAllChildren(code);
        }
    });
    row.append(el("span", "license__label", t("licenseKey")), code, copy);
    return row;
}

function licenseCard(license) {
    const card = el("article", "license");
    const cover = coverNode({ capa_url: license.capa_url, nome: license.plugin }, "license__cover");
    const body = el("div", "license__body");
    const title = el("h2", "license__title");
    const link = el("a", "", license.plugin);
    link.href = href(`/plugins/${encodeURIComponent(license.slug)}`);
    title.append(link);
    body.append(title);
    if (license.status === "ativa") {
        if (license.versao) body.append(el("p", "license__meta", `v${license.versao} · ${(license.formatos || []).join(" · ")}`));
        if (license.chave) body.append(keyRow(license.chave));
        const downloads = el("div", "license__downloads");
        (license.sistemas || []).forEach(system => {
            const button = el("button", "btn btn--small", t("download", { system: system.nome }));
            button.type = "button";
            button.addEventListener("click", () => download(license, system, button));
            downloads.append(button);
        });
        if (!(license.sistemas || []).length) downloads.append(el("p", "license__meta", t("soon")));
        body.append(downloads);
    } else if (license.status === "aguardando_pagamento") {
        body.append(el("p", "license__badge", t("waitingPayment")));
        if (license.checkout_url) {
            const pay = el("a", "btn btn--small", t("payNow"));
            pay.href = license.checkout_url;
            body.append(pay);
        }
    } else {
        body.append(el("p", "license__meta", t("suspended")));
    }
    const status = el("p", "form-status");
    status.setAttribute("role", "status");
    body.append(status);
    card.append(cover, body);
    return card;
}

function header() {
    const user = currentUser();
    const head = el("div", "library__head");
    const who = el("p", "eyebrow", t("signedInAs", { name: user?.nome_exibicao || user?.username || "" }));
    const out = el("button", "link-button", t("signOut"));
    out.type = "button";
    out.addEventListener("click", () => { signOut(); window.location.assign(href("/")); });
    head.append(who, out);
    return head;
}

// Back from Stripe: ask the API to check the payment now (the webhook may still be on its way).
async function confirmReturn() {
    const params = new URLSearchParams(window.location.search);
    const session = params.get("session_id");
    if (params.get("checkout") !== "success" || !/^cs_[A-Za-z0-9_]{4,250}$/.test(session || "")) return null;
    window.history.replaceState(null, "", window.location.pathname);
    try {
        const result = await api(`/labs/stripe/sessoes/${encodeURIComponent(session)}/confirmar`, { method: "POST", auth: true });
        return result?.pago ? t("paymentReceived") : t("paymentConfirming");
    } catch {
        return t("paymentConfirming");
    }
}

async function load() {
    if (!isSignedIn()) {
        signInPrompt();
        return;
    }
    root.setAttribute("aria-busy", "true");
    root.replaceChildren(el("p", "eyebrow", t("loadingPlugins")));
    try {
        await refreshUser();
        const notice = await confirmReturn();
        const licenses = await api("/labs/conta/plugins", { auth: true });
        const list = el("div", "library__list");
        if (licenses.length) licenses.forEach(item => list.append(licenseCard(item)));
        else {
            const empty = el("div", "state");
            const browse = el("a", "btn", t("browse"));
            browse.href = href("/#plugins");
            empty.append(el("p", "", t("noPlugins")), browse);
            list.append(empty);
        }
        const parts = [header()];
        if (notice) {
            const box = el("p", "notice library__notice", notice);
            box.setAttribute("role", "status");
            parts.push(box);
        }
        root.replaceChildren(...parts, list);
    } catch (error) {
        if (error.status === 401 || error.status === 403) signInPrompt();
        else root.replaceChildren(el("p", "lead", error.message));
    } finally {
        root.removeAttribute("aria-busy");
    }
}

if (READY && root) load();
