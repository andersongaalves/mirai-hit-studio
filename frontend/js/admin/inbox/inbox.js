import * as Api from "./inbox_api.js";
import { inboxState, resetInboxState } from "./inbox_state.js";
import { renderDetail, renderError, renderList, renderPagination } from "./inbox_dom.js";
import { renderAdminState } from "../ui.js";
import * as Notify from "../../utils/notifications.js";
import { getCurrentUser } from "../auth.js";

let initialized = false;

function $(id) { return document.getElementById(id); }

function filtersActive() {
    return Object.values(inboxState.filters).some((value) => value !== "" && value !== false);
}

function syncFilters() {
    inboxState.filters = {
        search: $("inbox-search")?.value.trim() || "",
        status: $("inbox-status-filter")?.value || "",
        mode: $("inbox-mode-filter")?.value || "",
        channel: $("inbox-channel-filter")?.value || "",
        handoff: Boolean($("inbox-handoff-filter")?.checked),
        assigned: $("inbox-assigned-filter")?.value || "",
        updated_from: $("inbox-updated-from")?.value || "",
        updated_to: $("inbox-updated-to")?.value || "",
    };
    $("inbox-clear-filters")?.classList.toggle("hidden", !filtersActive());
}

function renderListState() {
    const container = $("inbox-list");
    if (!container) return;
    if (inboxState.loading) { renderAdminState(container, "loading", "Carregando conversas..."); return; }
    if (inboxState.error) { renderError(container, inboxState.error); return; }
    renderList(container, inboxState, {
        selectedId: inboxState.selected?.id,
        onOpen: abrirConversa,
    });
    renderPagination($("inbox-pagination"), inboxState, carregarPagina);
}

async function carregarPagina(page = 1) {
    syncFilters();
    const epoch = inboxState.epoch;
    inboxState.loading = true;
    inboxState.error = "";
    inboxState.page = page;
    renderListState();
    try {
        const { assigned, updated_from, updated_to, ...filters } = inboxState.filters;
        if (assigned === "mine" && getCurrentUser()?.id) filters.assigned_user_id = getCurrentUser().id;
        if (assigned === "unassigned") filters.unassigned = true;
        if (updated_from) filters.updated_from = `${updated_from}T00:00:00-03:00`;
        if (updated_to) filters.updated_to = `${updated_to}T23:59:59-03:00`;
        const data = await Api.listarConversas(filters, page, inboxState.pageSize);
        if (epoch !== inboxState.epoch) return;
        Object.assign(inboxState, { ...data, loading: false, error: "" });
    } catch (error) {
        if (epoch !== inboxState.epoch) return;
        inboxState.loading = false;
        inboxState.error = error.message || "Não foi possível carregar a Inbox.";
    }
    renderListState();
}

async function abrirConversa(id) {
    const epoch = inboxState.epoch;
    inboxState.loadingDetail = true;
    try { const detail = await Api.buscarConversa(id); if (epoch !== inboxState.epoch) return; inboxState.selected = detail; }
    catch (error) { Notify.error(error.message || "Não foi possível abrir a conversa."); return; }
    finally { inboxState.loadingDetail = false; }
    $("inbox-detail-panel")?.classList.remove("hidden");
    $("inbox-list-panel")?.classList.add("inbox-list-panel--mobile-hidden");
    renderDetail($("inbox-detail"), inboxState.selected, handlers());
    renderListState();
}

function voltarLista() {
    inboxState.selected = null;
    inboxState.pendingSend = null;
    $("inbox-detail-panel")?.classList.add("hidden");
    $("inbox-list-panel")?.classList.remove("inbox-list-panel--mobile-hidden");
    renderListState();
}

async function atualizarDetalhe(data) {
    inboxState.selected = data.conversation || data;
    renderDetail($("inbox-detail"), inboxState.selected, handlers());
    await carregarPagina(inboxState.page);
}

function handlers() {
    const id = inboxState.selected?.id;
    const canAct = inboxState.selected?.assigned_user_id === getCurrentUser()?.id;
    return {
        canAct,
        sending: inboxState.sending,
        suggesting: inboxState.suggesting,
        onBack: voltarLista,
        onAssign: async () => {
            try { await atualizarDetalhe(await Api.assumirConversa(id)); Notify.success("Conversa assumida."); }
            catch (error) { Notify.error(error.message || "Não foi possível assumir a conversa."); }
        },
        onMode: async (mode) => {
            try { await atualizarDetalhe(await Api.alterarModo(id, mode)); }
            catch (error) { Notify.error(error.message || "Não foi possível alterar o modo."); renderDetail($("inbox-detail"), inboxState.selected, handlers()); }
        },
        onSuggest: async () => {
            if (inboxState.suggesting) return;
            inboxState.suggesting = true;
            try {
                const data = await Api.gerarSugestao(id);
                const detail = await Api.buscarConversa(id);
                inboxState.suggesting = false;
                inboxState.selected = detail;
                renderDetail($("inbox-detail"), detail, handlers());
                Notify.success(data?.suggestion ? "Sugestão pronta para revisão." : "Sugestão gerada.");
            } catch (error) { Notify.error(error.message || "Não foi possível gerar a sugestão."); }
            finally { inboxState.suggesting = false; }
        },
        onIgnore: async (suggestionId) => {
            try { await atualizarDetalhe(await Api.ignorarSugestao(id, suggestionId)); }
            catch (error) { Notify.error(error.message || "Não foi possível ignorar a sugestão."); }
        },
        onRetry: async (messageId) => {
            if (inboxState.sending) return;
            inboxState.sending = true;
            try {
                await Api.reenviarMensagem(id, messageId);
                inboxState.selected = await Api.buscarConversa(id);
                renderDetail($("inbox-detail"), inboxState.selected, handlers());
                Notify.success("Mensagem enviada.");
            } catch { Notify.error("Falha ao enviar. Tente novamente."); }
            finally { inboxState.sending = false; }
        },
        onOlder: async (before) => {
            try {
                const earlier = await Api.buscarConversa(id, before);
                if (inboxState.selected?.id !== id) return;
                inboxState.selected = {
                    ...inboxState.selected,
                    messages: [...earlier.messages, ...inboxState.selected.messages],
                    has_more_messages: earlier.has_more_messages,
                    next_before: earlier.next_before,
                };
                renderDetail($("inbox-detail"), inboxState.selected, handlers());
            } catch (error) { Notify.error(error.message || "Não foi possível carregar mensagens anteriores."); }
        },
        onSend: async (value, suggestionId) => {
            const text = value.trim();
            if (!text || inboxState.sending) return;
            const pending = inboxState.pendingSend;
            const key = pending?.text === text && pending?.suggestionId === suggestionId
                ? pending.key : crypto.randomUUID();
            inboxState.pendingSend = { text, suggestionId, key };
            inboxState.sending = true;
            const submit = $("inbox-detail")?.querySelector(".inbox-composer button[type='submit']");
            if (submit) { submit.disabled = true; submit.textContent = "Enviando..."; }
            try {
                await Api.enviarMensagem(id, {
                    text, suggestion_id: suggestionId,
                    idempotency_key: key,
                });
                inboxState.pendingSend = null;
                inboxState.selected = await Api.buscarConversa(id);
                renderDetail($("inbox-detail"), inboxState.selected, handlers());
                await carregarPagina(inboxState.page);
            } catch (error) {
                Notify.error(error.status === 409 ? "A conversa mudou. Revise a resposta antes de enviar." : "Falha ao enviar. Tente novamente.");
            } finally {
                inboxState.sending = false;
                if (submit?.isConnected) { submit.disabled = false; submit.textContent = "Enviar resposta"; }
            }
        },
        onClose: async () => {
            if (!window.confirm("Encerrar esta conversa?")) return;
            try { await atualizarDetalhe(await Api.encerrarConversa(id)); Notify.success("Conversa encerrada."); }
            catch (error) { Notify.error(error.message || "Não foi possível encerrar a conversa."); }
        },
    };
}

function bind() {
    ["inbox-search", "inbox-status-filter", "inbox-mode-filter", "inbox-channel-filter", "inbox-handoff-filter", "inbox-assigned-filter", "inbox-updated-from", "inbox-updated-to"].forEach((id) => {
        $(id)?.addEventListener(id === "inbox-search" ? "input" : "change", () => {
            window.clearTimeout($(id).dataset.timer);
            $(id).dataset.timer = window.setTimeout(() => carregarPagina(1), id === "inbox-search" ? 250 : 0);
        });
    });
    $("inbox-clear-filters")?.addEventListener("click", () => {
        ["inbox-search", "inbox-status-filter", "inbox-mode-filter", "inbox-channel-filter", "inbox-assigned-filter", "inbox-updated-from", "inbox-updated-to"].forEach((id) => { if ($(id)) $(id).value = ""; });
        if ($("inbox-handoff-filter")) $("inbox-handoff-filter").checked = false;
        carregarPagina(1);
    });
}

export async function initInbox() {
    if (!$("section-inbox")) return;
    if (!initialized) { initialized = true; bind(); }
    await carregarPagina(inboxState.page);
}

export function resetInbox() {
    resetInboxState();
    ["inbox-search", "inbox-status-filter", "inbox-mode-filter", "inbox-channel-filter", "inbox-assigned-filter", "inbox-updated-from", "inbox-updated-to"].forEach((id) => {
        window.clearTimeout($(id)?.dataset.timer);
        if ($(id)) $(id).value = "";
    });
    if ($("inbox-handoff-filter")) $("inbox-handoff-filter").checked = false;
    $("inbox-detail-panel")?.classList.add("hidden");
    $("inbox-list-panel")?.classList.remove("inbox-list-panel--mobile-hidden");
}
