import { authFetch, getCurrentUser, getToken } from "../admin/auth.js";

let stopCurrent = null;
let owner = null;

export function stopPortalNotifications() {
    stopCurrent?.();
    stopCurrent = null;
    owner = null;
}

export function startPortalNotifications(user) {
    const token = getToken();
    const key = `${user.id}:${user.role}:${token}`;
    if (owner === key) return;
    stopPortalNotifications();
    const account = document.querySelector(".producer-account");
    const workspace = document.querySelector(".producer-workspace");
    if (!account || !workspace || !["cliente", "produtor"].includes(user.role)) return;
    owner = key;
    const controller = new AbortController();
    const current = () => !controller.signal.aborted && getToken() === token && getCurrentUser()?.id === user.id;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "portal-notifications-button";
    button.title = "Notificações";
    button.setAttribute("aria-label", "Notificações");
    button.setAttribute("aria-haspopup", "dialog");
    const icon = document.createElement("span");
    icon.className = "portal-notifications-icon";
    icon.setAttribute("aria-hidden", "true");
    const badge = document.createElement("span");
    badge.className = "portal-notifications-count";
    badge.hidden = true;
    button.append(icon, badge);
    account.insertBefore(button, account.lastElementChild);

    const dialog = document.createElement("dialog");
    dialog.className = "portal-notifications-dialog";
    dialog.setAttribute("aria-labelledby", "portal-notifications-title");
    const header = document.createElement("header");
    const title = document.createElement("h2");
    title.id = "portal-notifications-title";
    title.textContent = "Notificações";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fechar";
    close.addEventListener("click", () => dialog.close());
    header.append(title, close);
    const list = document.createElement("ul");
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = "Mais antigas";
    more.hidden = true;
    dialog.append(header, status, list, more);
    document.body.append(dialog);
    let cursor = null;
    let loading = false;
    let refreshing = false;
    let banner = null;

    async function request(path, options = {}) {
        const response = await authFetch(`/portal/notificacoes${path}`, { ...options, signal: controller.signal });
        if (!response.ok) throw new Error("notifications_unavailable");
        const data = await response.json();
        if (!current()) throw new Error("session_changed");
        return data;
    }

    function link(item) {
        const anchor = document.createElement("a");
        const allowed = user.role === "cliente" ? /^\/cliente\/(projetos|propostas)\/[1-9]\d*$/ : /^\/produtor\/producoes\/[1-9]\d*$/;
        anchor.href = allowed.test(item.url) ? item.url : `/${user.role}`;
        anchor.textContent = item.texto;
        return anchor;
    }

    async function history(append = false) {
        if (loading) return;
        loading = true;
        more.disabled = true;
        status.textContent = "Carregando...";
        if (!append) { list.replaceChildren(); cursor = null; }
        try {
            const data = await request(cursor ? `?antes_id=${cursor}` : "");
            for (const item of data.itens) {
                const row = document.createElement("li");
                const date = document.createElement("time");
                date.dateTime = item.created_at;
                date.textContent = new Date(item.created_at).toLocaleString("pt-BR");
                row.append(link(item), date);
                list.append(row);
            }
            cursor = data.itens.at(-1)?.id ?? cursor;
            more.hidden = !data.tem_mais;
            status.textContent = list.children.length ? "" : "Nenhuma notificação por enquanto.";
        } catch {
            if (current()) status.textContent = "Notificações indisponíveis no momento.";
        } finally { loading = false; more.disabled = false; }
    }

    async function refresh() {
        if (refreshing || !current() || document.hidden) return;
        refreshing = true;
        try {
            const data = await request("?somente_nao_vistas=true&limite=50");
            badge.textContent = String(data.nao_vistas);
            badge.hidden = !data.nao_vistas;
            button.setAttribute("aria-label", `Notificações, ${data.nao_vistas} novas`);
            if (!data.itens.length) return;
            // The backend atomically claims events; another tab cannot announce them again.
            const claimed = await request("/vistas", { method: "POST", body: JSON.stringify({ ids: data.itens.map(item => item.id) }) });
            if (!claimed.length) return;
            if (!banner) {
                banner = document.createElement("section");
                banner.className = "portal-notifications-new";
                banner.setAttribute("aria-label", "Novas notificações");
                const heading = document.createElement("p");
                heading.textContent = "Novas notificações";
                heading.setAttribute("role", "status");
                const dismiss = document.createElement("button");
                dismiss.type = "button";
                dismiss.textContent = "Fechar";
                dismiss.addEventListener("click", () => { banner.remove(); banner = null; });
                banner.append(heading, dismiss, document.createElement("ul"));
                workspace.prepend(banner);
            }
            for (const item of claimed) {
                const row = document.createElement("li");
                row.append(link(item));
                banner.querySelector("ul").append(row);
            }
            badge.hidden = data.nao_vistas <= claimed.length;
            badge.textContent = String(Math.max(0, data.nao_vistas - claimed.length));
            button.setAttribute("aria-label", `Notificações, ${badge.textContent} novas`);
            if (dialog.open) await history();
        } catch {
            // Secondary feature: the production/payment UI remains usable while offline.
        } finally { refreshing = false; }
    }

    button.addEventListener("click", () => { dialog.showModal(); history(); });
    more.addEventListener("click", () => history(true));
    const timer = setInterval(refresh, 45000);
    document.addEventListener("visibilitychange", refresh);
    stopCurrent = () => {
        controller.abort();
        clearInterval(timer);
        document.removeEventListener("visibilitychange", refresh);
        dialog.close();
        dialog.remove();
        button.remove();
        banner?.remove();
    };
    refresh();
}

document.addEventListener("admin:logout", stopPortalNotifications);
