import * as Auth from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import * as API from "./newsletter_api.js";
import { closeCampaignModal, openCampaignModal } from "./newsletter_modal.js";
import { newsletterState } from "./newsletter_state.js";
import * as UI from "./newsletter_ui.js";
import { filtrarSubscribers } from "./newsletter_utils.js";


function syncAccess() {
    const admin = Auth.isAdmin();
    document.querySelectorAll("[data-admin-only]").forEach(element => element.classList.toggle("admin-access-hidden", !admin));
    return admin;
}


function refresh() {
    if (newsletterState.loading) return UI.renderLoading();
    if (newsletterState.error) return UI.renderError(newsletterState.error);
    const filterActive = Boolean(newsletterState.filter.busca.trim()) || newsletterState.filter.status !== "todos";
    const subscribers = filtrarSubscribers(newsletterState.subscribers, newsletterState.filter);
    document.getElementById("newsletter-subscribers-clear")?.classList.toggle("hidden", !filterActive);
    document.getElementById("newsletter-subscribers-summary").textContent = filterActive
        ? `${subscribers.length} de ${newsletterState.subscribers.length} inscritos`
        : `${newsletterState.subscribers.length} inscritos`;
    document.getElementById("newsletter-campaigns-summary").textContent = `${newsletterState.campaigns.length} campanha${newsletterState.campaigns.length === 1 ? "" : "s"}`;
    UI.renderSubscribers(subscribers, { onCancel: cancelarSubscriber, filtered: filterActive });
    UI.renderCampaigns(newsletterState.campaigns, { onOpen: abrirCampanha, onSend: solicitarEnvio });
}


export async function carregarNewsletter() {
    if (!syncAccess()) return;
    newsletterState.loading = true;
    newsletterState.error = "";
    refresh();
    try {
        const [subscribers, campaigns] = await Promise.all([API.listarSubscribers(), API.listarCampanhas()]);
        newsletterState.subscribers = Array.isArray(subscribers) ? subscribers : [];
        newsletterState.campaigns = Array.isArray(campaigns) ? campaigns : [];
    } catch (error) {
        console.error(error);
        newsletterState.error = "Não foi possível carregar a newsletter.";
    } finally {
        newsletterState.loading = false;
        refresh();
    }
}


function selectTab(tab) {
    newsletterState.tab = tab;
    const campaigns = tab === "campaigns";
    document.getElementById("newsletter-campaigns-panel")?.classList.toggle("hidden", !campaigns);
    document.getElementById("newsletter-subscribers-panel")?.classList.toggle("hidden", campaigns);
    document.getElementById("newsletter-tab-campaigns")?.setAttribute("aria-selected", String(campaigns));
    document.getElementById("newsletter-tab-subscribers")?.setAttribute("aria-selected", String(!campaigns));
}


export function novaCampanha() {
    openCampaignModal(null, { onSave: salvarCampanha });
}


export async function abrirCampanha(id) {
    try { openCampaignModal(await API.buscarCampanha(id), { onSave: salvarCampanha, onSend: enviarCampanha }); }
    catch (error) { Notify.error("Não foi possível abrir a campanha."); }
}


async function salvarCampanha(campaign, payload) {
    try {
        if (campaign) await API.atualizarCampanha(campaign.id, payload);
        else await API.criarCampanha(payload);
        await carregarNewsletter();
        closeCampaignModal();
        Notify.success(campaign ? "Rascunho atualizado." : "Campanha criada.");
    } catch (error) { Notify.error(error.message); }
}


async function enviarCampanha(campaign) {
    if (!confirm(`Enviar para ${campaign.eligible_subscribers || 0} inscritos ativos?`)) return;
    try {
        const result = await API.enviarCampanha(campaign.id);
        await carregarNewsletter();
        closeCampaignModal();
        Notify.success(`${result.total_sent || 0} envios concluídos.`);
    } catch (error) { Notify.error(error.message); }
}


async function solicitarEnvio(id) {
    try { await abrirCampanha(id); }
    catch { Notify.error("Não foi possível abrir a campanha."); }
}


async function cancelarSubscriber(subscriber) {
    if (!confirm(`Cancelar a inscrição de ${subscriber.email}?`)) return;
    try {
        await API.cancelarSubscriber(subscriber.id);
        await carregarNewsletter();
        Notify.success("Inscrição cancelada.");
    } catch (error) { Notify.error(error.message); }
}


export function initNewsletterAdmin() {
    if (!syncAccess()) return Promise.resolve();
    document.getElementById("newsletter-new-campaign").onclick = novaCampanha;
    document.getElementById("newsletter-tab-campaigns").onclick = () => selectTab("campaigns");
    document.getElementById("newsletter-tab-subscribers").onclick = () => selectTab("subscribers");
    const search = document.getElementById("newsletter-subscribers-search");
    const status = document.getElementById("newsletter-subscribers-status");
    search.oninput = event => { newsletterState.filter.busca = event.target.value; refresh(); };
    status.onchange = event => { newsletterState.filter.status = event.target.value; refresh(); };
    document.getElementById("newsletter-subscribers-clear").onclick = () => {
        newsletterState.filter = { busca: "", status: "todos" };
        search.value = "";
        status.value = "todos";
        refresh();
        search.focus();
    };
    selectTab(newsletterState.tab);
    return carregarNewsletter();
}


export { closeCampaignModal };
