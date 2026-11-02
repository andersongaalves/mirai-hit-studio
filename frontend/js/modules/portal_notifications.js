import { authFetch, getCurrentUser, getToken } from "../admin/auth.js";
import { activityItem, ativo, icon as activityIcon, iconFor, when } from "./activity_item.js";
import { uploadActivities } from "./upload_tasks.js";

const ICONE_TIPO = {
    nova_previa: "audio", nova_entrega: "audio", entrega_liberada: "audio", admin_falha_tag: "audio",
    beat_aprovado: "audio", beat_rejeitado: "audio", admin_beat_revisao: "audio",
    pagamento_confirmado: "arquivo", proposta_enviada: "pdf", nova_mensagem: "sino",
};

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
    // AUD6-S11-001: the Admin panel uses the same inbox with its own endpoint and sections.
    const admin = Boolean(user.is_admin) && user.role === "admin";
    const account = document.querySelector(admin ? ".admin-topbar__actions" : ".producer-account");
    const workspace = document.querySelector(admin ? ".admin-shell__workspace" : ".producer-workspace");
    if (!account || !workspace || !(admin || ["cliente", "produtor"].includes(user.role))) return;
    const endpoint = admin ? "/admin/notificacoes" : "/portal/notificacoes";
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
    list.className = "notifications-history";
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = "Mais antigas";
    more.hidden = true;
    // "Em andamento": uploads of this session and server work (previews being generated, queues).
    const activity = document.createElement("section");
    activity.className = "notifications-activity";
    activity.setAttribute("aria-labelledby", "notifications-activity-title");
    activity.hidden = true;
    const activityTitle = document.createElement("h3");
    activityTitle.id = "notifications-activity-title";
    activityTitle.className = "notifications-section-title";
    activityTitle.textContent = "Em andamento";
    const activityList = document.createElement("ul");
    activityList.className = "activity-list";
    activity.append(activityTitle, activityList);
    const historyTitle = document.createElement("h3");
    historyTitle.className = "notifications-section-title";
    historyTitle.textContent = "Notificações";
    dialog.append(header, activity, historyTitle, status, list, more);
    document.body.append(dialog);
    let cursor = null;
    let loading = false;
    let refreshing = false;
    let banner = null;

    async function request(path, options = {}) {
        const response = await authFetch(`${endpoint}${path}`, { ...options, signal: controller.signal });
        if (!response.ok) throw new Error("notifications_unavailable");
        const data = await response.json();
        if (!current()) throw new Error("session_changed");
        return data;
    }

    function link(item) {
        const anchor = document.createElement("a");
        anchor.textContent = item.texto;
        if (admin) {
            const section = /^\/admin\.html#((?:section-[a-z-]+)|dashboard-menu)$/.exec(item.url)?.[1] || "dashboard-menu";
            anchor.href = `/admin.html#${section}`;
            anchor.addEventListener("click", event => {
                event.preventDefault();
                if (dialog.open) dialog.close();
                if (section === "dashboard-menu") window.mostrarDashboard?.();
                else window.mostrarSecao?.(section);
            });
            return anchor;
        }
        const allowed = user.role === "cliente"
            ? /^\/cliente\/(projetos|propostas)\/[1-9]\d*$/
            : /^\/produtor\/(producoes\/[1-9]\d*|beats)$/;
        anchor.href = allowed.test(item.url) ? item.url : `/${user.role}`;
        return anchor;
    }

    function historyRow(item) {
        const row = document.createElement("li");
        row.className = `notification-row${item.vista_em ? "" : " is-new"}`;
        const thumb = document.createElement("span");
        thumb.className = "activity-thumb";
        thumb.append(activityIcon(ICONE_TIPO[item.tipo] || iconFor("", item.tipo) || "sino"));
        if (item.miniatura) {
            const img = document.createElement("img");
            img.alt = "";
            img.loading = "lazy";
            img.referrerPolicy = "no-referrer";
            img.addEventListener("load", () => thumb.classList.add("is-loaded"));
            img.addEventListener("error", () => img.remove());
            img.src = item.miniatura;
            thumb.append(img);
        }
        const body = document.createElement("span");
        body.className = "notification-row__body";
        body.append(link(item));
        if (item.contexto) {
            const context = document.createElement("span");
            context.className = "notification-row__context";
            context.textContent = item.contexto;
            body.append(context);
        }
        const date = document.createElement("time");
        date.dateTime = item.created_at;
        date.textContent = new Date(item.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
        date.title = when(item.created_at);
        body.append(date);
        row.append(thumb, body);
        return row;
    }

    // ---------- Em andamento ----------
    let serverActivities = [];
    let activityTimer = null;
    let activityBusy = false;

    function openActivity(event, item) {
        if (!admin || !item.url?.startsWith("/admin.html#")) return;
        event.preventDefault();
        if (dialog.open) dialog.close();
        const section = item.url.split("#")[1];
        if (section === "dashboard-menu") window.mostrarDashboard?.();
        else window.mostrarSecao?.(section);
    }

    function renderActivity() {
        const items = [...uploadActivities(), ...serverActivities];
        activityList.replaceChildren(...items.map(item => activityItem({ ...item, icone: item.icone || iconFor("", item.tipo) }, {
            onOpen: openActivity,
        })));
        activity.hidden = items.length === 0;
        const running = items.filter(ativo).length;
        button.classList.toggle("is-busy", running > 0);
        const unread = badge.hidden ? 0 : Number(badge.textContent) || 0;
        button.setAttribute("aria-label", ["Notificações", unread ? `${unread} novas` : "", running ? `${running} em andamento` : ""]
            .filter(Boolean).join(", "));
        return running;
    }

    async function loadActivity() {
        if (activityBusy || !current() || document.hidden) return;
        activityBusy = true;
        try {
            const data = await request("/atividades");
            serverActivities = data.itens.map(item => ({ ...item, prefixo: item.estado === "concluido" ? "Concluído" : undefined }));
        } catch {
            // Secondary: the list simply stays as it was.
        } finally { activityBusy = false; }
        scheduleActivity(renderActivity());
    }

    // Fast while something is running or the panel is open, slow otherwise.
    function scheduleActivity(running) {
        clearTimeout(activityTimer);
        if (!current()) return;
        activityTimer = setTimeout(loadActivity, running || dialog.open ? 4000 : 45000);
    }

    const onLocalActivity = () => renderActivity();
    const onRefreshActivity = () => loadActivity();
    document.addEventListener("mirai:activities", onLocalActivity);
    document.addEventListener("mirai:activities-refresh", onRefreshActivity);

    async function history(append = false) {
        if (loading) return;
        loading = true;
        more.disabled = true;
        status.textContent = "Carregando...";
        if (!append) { list.replaceChildren(); cursor = null; }
        try {
            const data = await request(cursor ? `?antes_id=${cursor}` : "");
            for (const item of data.itens) list.append(historyRow(item));
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
            renderActivity();
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
            renderActivity();
            if (dialog.open) await history();
        } catch {
            // Secondary feature: the production/payment UI remains usable while offline.
        } finally { refreshing = false; }
    }

    button.addEventListener("click", () => { dialog.showModal(); history(); loadActivity(); });
    more.addEventListener("click", () => history(true));
    const timer = setInterval(refresh, 45000);
    document.addEventListener("visibilitychange", refresh);
    stopCurrent = () => {
        controller.abort();
        clearInterval(timer);
        clearTimeout(activityTimer);
        document.removeEventListener("mirai:activities", onLocalActivity);
        document.removeEventListener("mirai:activities-refresh", onRefreshActivity);
        document.removeEventListener("visibilitychange", refresh);
        dialog.close();
        dialog.remove();
        button.remove();
        banner?.remove();
    };
    refresh();
    loadActivity();
}

document.addEventListener("admin:logout", stopPortalNotifications);
