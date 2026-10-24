import { fazerLogin, getCurrentUser, logout, restaurarSessao } from "../admin/auth.js";
import * as api from "./api.js";
import { initProductionRequest } from "./request.js";
import { messagesPanel } from "../modules/production_messages.js";
import { stagesPanel } from "../modules/production_stages.js";
import { syncUploadHints } from "../modules/file_quotas.js";
import { startPortalNotifications } from "../modules/portal_notifications.js";
import { enqueueUpload } from "../modules/upload_tasks.js";
import { beatPreview } from "../modules/beat_preview.js";
import {
    applySettings,
    renderDashboard,
    renderDetail,
    renderList,
    renderProposalDetail,
    renderProposalList,
    renderProposalSummary,
    renderWallet,
    setAlert,
    showView,
    updateProcessedPreviews,
} from "./ui.js";

let productions = [];
let proposals = [];
let proposalsEnabled = false;
let finances = new Map();
const objectUrls = new Set();
const filters = { status: "todos", order: "recente" };
let uploadFeedback = null;
let filtersInitialized = false;
let tagPollTimer = null;

function watchTaggedPreviews(production, files, failures = 0) {
    clearTimeout(tagPollTimer);
    if (!files.some(file => file.processamento_tag === "pendente") || failures >= 3) return;
    tagPollTimer = setTimeout(async () => {
        if (route().view !== "detail" || route().id !== production.id || !getCurrentUser()) return;
        try {
            const updated = await api.listarArquivos(production.id);
            if (route().view !== "detail" || route().id !== production.id || !getCurrentUser()) return;
            updateProcessedPreviews(updated, { onDownload: downloadFile, onPreview: playPreview });
            watchTaggedPreviews(production, updated);
        } catch {
            watchTaggedPreviews(production, files, failures + 1);
        }
    }, 5000);
}

function route() {
    if (/^\/cliente\/(?:explorar|beats)\/?$/.test(location.pathname)) return { view: "beats" };
    if (/^\/cliente\/creditos\/?$/.test(location.pathname)) return { view: "credits" };
    const proposal = location.pathname.match(/^\/cliente\/propostas\/(\d+)\/?$/);
    if (proposal) return { view: "proposal-detail", id: Number(proposal[1]) };
    if (/^\/cliente\/propostas\/?$/.test(location.pathname)) return { view: "proposals" };
    const match = location.pathname.match(/^\/cliente\/projetos\/(\d+)\/?$/);
    if (match) return { view: "detail", id: Number(match[1]) };
    if (/^\/cliente\/projetos\/?$/.test(location.pathname)) return { view: "projects" };
    return { view: "dashboard" };
}

async function openProposalDetail(id) {
    setAlert();
    try {
        const proposal = await api.obterProposta(id);
        renderProposalDetail(proposal, {
            onAccept: acceptProposal,
            onRefuse: refuseProposal,
            onDownload: downloadProposal,
        });
        showView("proposal-detail");
    } catch (error) {
        setAlert(error.message, true);
        history.replaceState({}, "", "/cliente/propostas");
        renderRoute();
    }
}

function releaseObjectUrls() {
    objectUrls.forEach(url => URL.revokeObjectURL(url));
    objectUrls.clear();
}

// Roadmap 5.06: contract stages replace the legacy checklist when the contract has them.
// Loaded after the detail, so a failure keeps the legacy view instead of blocking it.
async function loadStages(production) {
    let data = null;
    try {
        data = await api.listarEtapas(production.id);
    } catch {
        return;
    }
    if (route().view !== "detail" || route().id !== production.id) return;
    const panel = document.getElementById("production-stages-panel");
    if (!panel) return;
    if (data?.etapas_ocultas) {
        // 5.10: the contract shows only the overall progress to the client.
        const title = document.createElement("h2");
        title.textContent = "Etapas";
        const progress = document.createElement("p");
        progress.textContent = `Progresso do projeto: ${Number(data.progresso_percentual) || 0}%`;
        panel.replaceChildren(title, progress);
        return;
    }
    if (!data?.etapas?.length) return;
    panel.replaceChildren(stagesPanel({
        role: "cliente",
        data,
    }));
}

// Roadmap 5.09: quota hints load after the detail; the server enforces them anyway.
async function loadQuotas(production) {
    let data = null;
    try {
        data = await api.listarCotas(production.id);
    } catch {
        return;
    }
    if (route().view !== "detail" || route().id !== production.id) return;
    syncUploadHints(document, data?.cotas || []);
}

// Roadmap 5.03: the thread loads after the detail so its failure never blocks the project.
async function loadMessages(production, files) {
    const slot = document.getElementById("production-messages-slot");
    if (!slot) return;
    let messages = [];
    let error = "";
    try {
        messages = await api.listarMensagens(production.id);
    } catch {
        error = "Não foi possível carregar as mensagens agora.";
    }
    if (route().view !== "detail" || route().id !== production.id) return;
    slot.replaceChildren(messagesPanel({
        role: "cliente",
        messages,
        files,
        error,
        onSend: async payload => {
            await api.enviarMensagem(production.id, payload);
            await loadMessages(production, files);
        },
    }));
}

function rememberProduction(production) {
    if (!production || typeof production.id !== "number") return;
    const index = productions.findIndex(item => item.id === production.id);
    if (index >= 0) productions = productions.map(item => item.id === production.id ? { ...item, ...production } : item);
}

function navigate(path) {
    clearTimeout(tagPollTimer);
    releaseObjectUrls();
    setAlert();
    uploadFeedback = null;
    history.pushState({}, "", path);
    renderRoute();
}

async function openDetail(id) {
    setAlert();
    try {
        // Finance is secondary: its failure must not hide the project and its files.
        const [production, files, financeResult] = await Promise.all([
            api.obterProducao(id),
            api.listarArquivos(id),
            api.obterFinanceiro(id).then(
                value => ({ ok: true, value }),
                () => ({ ok: false, value: finances.get(id) ?? { indisponivel: true } }),
            ),
        ]);
        const finance = financeResult.value;
        if (financeResult.ok) finances.set(id, finance);
        rememberProduction(production);
        renderDetail(production, files, finance, {
            onUpload: uploadFile,
            onRefreshFiles: refreshFiles,
            onDownload: downloadFile,
            onPreview: playPreview,
            uploadFeedback,
        });
        showView("detail");
        watchTaggedPreviews(production, files);
        loadMessages(production, files);
        loadStages(production);
        loadQuotas(production);
        if (!financeResult.ok) {
            setAlert("Não foi possível atualizar as informações de pagamento agora. Os demais dados estão disponíveis.", true);
        }
    } catch (error) {
        setAlert(error.message, true);
        history.replaceState({}, "", "/cliente/projetos");
        renderRoute();
    }
}

function renderRoute() {
    const current = route();
    if (current.view === "beats") {
        loadBeats();
        return;
    }
    if (current.view === "credits") {
        loadWallet();
        return;
    }
    if (current.view === "proposal-detail") {
        openProposalDetail(current.id);
        return;
    }
    if (current.view === "proposals") {
        renderProposalList(proposals, id => navigate(`/cliente/propostas/${id}`));
        showView("proposals");
        return;
    }
    if (current.view === "detail") {
        openDetail(current.id);
        return;
    }
    if (current.view === "projects") {
        renderList(productions, finances, filters, id => navigate(`/cliente/projetos/${id}`));
        showView("projects");
        return;
    }
    renderDashboard(productions, finances);
    renderProposalSummary(proposals, id => navigate(`/cliente/propostas/${id}`));
    showView("dashboard");
}

async function loadBeats() {
    showView("beats");
    const list = document.getElementById("client-beats-list"); list.textContent = "Carregando catálogo...";
    try {
        const [beats, acquired] = await Promise.all([api.listarBeats(), api.listarMultitracksAdquiridos()]);
        const acquiredList = document.getElementById("client-acquired-beats");
        acquiredList.replaceChildren(...acquired.map(item => {
            const card = document.createElement("article"); card.className = "producer-card";
            const title = document.createElement("h3"); title.textContent = item.titulo;
            const actions = document.createElement("div"); actions.className = "producer-card__footer";
            for (const kind of item.arquivos || []) {
                const button = document.createElement("button"); button.type = "button"; button.className = "btn-outline";
                button.textContent = `Baixar ${{ mp3: "MP3", wav: "WAV", multitrack: "multitrack" }[kind]}`;
                button.onclick = async () => {
                    button.disabled = true;
                    try {
                        const delivery = await api.baixarBeat(item.beat_id, kind);
                        if (delivery.type === "link") window.open(delivery.url, "_blank", "noopener,noreferrer");
                        else saveBlob(delivery);
                    } catch (error) { setAlert(error.message, true); }
                    finally { button.disabled = false; }
                };
                actions.append(button);
            }
            card.append(title, actions); return card;
        }));
        if (!acquired.length) acquiredList.textContent = "Nenhuma compra liberada ainda.";
        list.replaceChildren(...beats.map(beat => {
            const card = document.createElement("article"); card.className = "producer-card beat-card client-beat-card";
            const content = document.createElement("div"); content.className = "client-beat-card__content";
            const title = document.createElement("h3"); title.textContent = beat.titulo;
            let cover = null;
            if (beat.capa_url) { cover = document.createElement("img"); cover.className = "beat-cover"; cover.src = beat.capa_url; cover.alt = `Capa de ${beat.titulo}`; }
            const author = document.createElement("p"); author.textContent = `${beat.produtor}${beat.bpm ? ` · ${beat.bpm} BPM` : ""}${beat.tonalidade ? ` · ${beat.tonalidade}` : ""}`;
            const audio = beatPreview(() => api.ouvirBeat(beat.id));
            const actions = document.createElement("div"); actions.className = "producer-card__footer";
            for (const [kind, label, price] of [[beat.formato_novo ? "lease_mp3" : "lease", "MP3 lease", beat.preco_lease], ["lease_wav", "WAV lease", beat.preco_wav], ["multitrack", "Multitrack", beat.preco_multitrack], ["exclusivo", "Exclusivo", beat.preco_exclusivo]]) {
                if (!price) continue;
                const button = document.createElement("button"); button.className = "btn-outline"; button.type = "button";
                const idempotencyKey = crypto.randomUUID();
                button.textContent = `${label} · ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(price)}`;
                button.onclick = async () => {
                    button.disabled = true;
                    try {
                        const purchase = await api.solicitarBeat(beat.id, kind, idempotencyKey);
                        if (!/^\/checkout\?proposta=\d+$/.test(purchase.checkout_path || "")) throw new Error("Checkout indisponível para esta compra.");
                        window.location.assign(purchase.checkout_path);
                    }
                    catch (error) { setAlert(error.message, true); button.disabled = false; }
                };
                actions.append(button);
            }
            content.append(title, author, audio, actions);
            if (cover) card.append(cover);
            else { const placeholder = document.createElement("div"); placeholder.className = "beat-cover beat-cover--placeholder"; placeholder.setAttribute("aria-hidden", "true"); card.append(placeholder); }
            card.append(content);
            return card;
        }));
        if (!beats.length) list.textContent = "Nenhum beat disponível no momento.";
    } catch (error) { setAlert(error.message, true); list.textContent = ""; }
}

let walletRequest = 0;
async function loadWallet() {
    const request = ++walletRequest;
    const owner = getCurrentUser()?.id;
    setAlert();
    showView("credits");
    document.getElementById("client-credits-content").textContent = "Carregando créditos...";
    try {
        const data = await api.obterCreditos();
        if (request !== walletRequest || route().view !== "credits" || getCurrentUser()?.id !== owner) return;
        renderWallet(data);
    } catch (error) {
        if (request !== walletRequest || route().view !== "credits" || getCurrentUser()?.id !== owner) return;
        document.getElementById("client-credits-content").textContent = "";
        setAlert(error.message, true);
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn-outline";
        retry.textContent = "Tentar novamente";
        retry.onclick = loadWallet;
        document.getElementById("client-credits-content").append(retry);
    }
}

function saveBlob({ blob, filename }) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    // Revoking synchronously can cancel the download in some browsers.
    setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function downloadFile(id, button) {
    button.disabled = true;
    try {
        saveBlob(await api.baixarArquivo(id));
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function downloadProposal(proposal, button) {
    button.disabled = true;
    try {
        saveBlob(await api.baixarProposta(proposal.id));
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function refreshProposals(selectedId = null) {
    proposals = await api.listarPropostas();
    if (selectedId) await openProposalDetail(selectedId);
    else renderRoute();
}

async function acceptProposal(proposal, button) {
    if (!confirm(`Aceitar a proposta ${proposal.numero}, versão ${proposal.versao}?`)) return;
    button.disabled = true;
    setAlert();
    try {
        await api.aceitarProposta(proposal.id, proposal.versao);
        await refreshProposals(proposal.id);
        setAlert("Proposta aceita. O projeto será liberado após a confirmação do pagamento.");
    } catch (error) {
        setAlert(error.message, true);
        button.disabled = false;
    }
}

async function refuseProposal(proposal, button) {
    if (!confirm(`Recusar a proposta ${proposal.numero}, versão ${proposal.versao}?`)) return;
    button.disabled = true;
    setAlert();
    try {
        await api.recusarProposta(proposal.id, proposal.versao);
        await refreshProposals(proposal.id);
        setAlert("Proposta recusada.");
    } catch (error) {
        setAlert(error.message, true);
        button.disabled = false;
    }
}

async function playPreview(file, player, button) {
    button.disabled = true;
    try {
        const { blob } = await api.baixarArquivo(file.id);
        const url = URL.createObjectURL(blob);
        objectUrls.add(url);
        const media = document.createElement(file.mime_type.startsWith("video/") ? "video" : "audio");
        media.className = "client-player";
        media.controls = true;
        media.preload = "metadata";
        media.playsInline = true;
        media.src = url;
        player.replaceChildren(media);
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

function uploadError(error) {
    if (error.status === 403) return "Você não tem permissão para enviar arquivos a este projeto.";
    // Contract quota (5.09): the server message says exactly which limit was reached.
    if ([409, 422].includes(error.status) && /contrat/i.test(error.message || "")) return error.message;
    if (error.status === 409) return "O projeto ou a versão mudou. Atualize a lista antes de tentar novamente.";
    if (error.status === 413) return "O arquivo excede o tamanho permitido.";
    if (error.status === 422 || error.status === 415) return "Arquivo não permitido. Confira o formato e o tamanho.";
    if (!error.status) return "Falha de conexão. O envio não foi confirmado; confira a lista antes de tentar novamente.";
    return "Não foi possível enviar o arquivo. Tente novamente.";
}

async function refreshFiles(production, setFeedback) {
    if (route().view !== "detail" || route().id !== production.id) return;
    try {
        const files = await api.listarArquivos(production.id);
        if (route().view !== "detail" || route().id !== production.id) return;
        uploadFeedback = { kind: "success", message: uploadFeedback?.successMessage || "Lista atualizada." };
        renderDetail(production, files, finances.get(production.id), {
            onUpload: uploadFile,
            onRefreshFiles: refreshFiles,
            onDownload: downloadFile,
            onPreview: playPreview,
            uploadFeedback,
        });
        watchTaggedPreviews(production, files);
        loadMessages(production, files);
        loadStages(production);
        loadQuotas(production);
    } catch (error) {
        uploadFeedback = {
            kind: "error",
            message: "Arquivo enviado, mas a lista não pôde ser atualizada. Não reenvie; tente atualizar a lista.",
            retry: true,
            successMessage: uploadFeedback?.successMessage,
        };
        setFeedback("error", uploadFeedback.message, true);
    }
}

async function uploadFile(production, file, type, replacesId, form, setFeedback, note = "") {
    if (form.dataset.busy === "true") return;
    form.dataset.busy = "true";
    setFeedback("loading", "Adicionando à fila de envios...");
    try {
        const body = new FormData();
        body.append("arquivo", file);
        body.append("tipo", type);
        if (replacesId) body.append("substitui_arquivo_id", String(replacesId));
        if (note.trim()) body.append("observacao", note.trim());
        await enqueueUpload(`/portal/cliente/producoes/${production.id}/arquivos`, body, {
            label: `${file.name} · ${production.titulo}`,
            meta: { kind: "client-production", productionId: production.id },
        });
        uploadFeedback = { kind: "success", message: "Envio iniciado. Você pode continuar usando o portal e acompanhar em Envios." };
        setFeedback("success", uploadFeedback.message);
        form.reset();
    } catch (error) {
        uploadFeedback = { kind: "error", message: uploadError(error) };
        setFeedback("error", uploadFeedback.message);
    } finally {
        form.dataset.busy = "false";
    }
}

document.addEventListener("mirai:upload-task", event => {
    const task = event.detail;
    if (task.status !== "completed" || task.meta?.kind !== "client-production") return;
    if (route().view === "detail" && route().id === task.meta.productionId) openDetail(task.meta.productionId);
});


function denyWrongRole() {
    logout();
    const error = document.getElementById("login-error");
    error.textContent = "Esta área é exclusiva para contas de cliente.";
    error.classList.remove("hidden");
}

async function loadFinances(items) {
    const results = await Promise.allSettled(items.map(item => api.obterFinanceiro(item.id)));
    return new Map(results.flatMap((result, index) => result.status === "fulfilled"
        ? [[items[index].id, result.value]]
        : []));
}

async function enterPortal() {
    const user = getCurrentUser();
    if (!user || user.role !== "cliente" || user.is_admin === true || !user.cliente_id) {
        denyWrongRole();
        return;
    }
    document.getElementById("client-username").textContent = user.username;
    startPortalNotifications(user);
    document.getElementById("client-greeting").textContent = user.username;
    document.getElementById("client-loading").classList.remove("hidden");
    document.querySelectorAll(".producer-view").forEach(item => item.classList.add("hidden"));
    try {
        const [loadedProductions, loadedProposals, loadedSettings] = await Promise.all([
            api.listarProducoes(),
            api.listarPropostas().then(items => ({ enabled: true, items })).catch(error => {
                if (error.status === 404) return { enabled: false, items: [] };
                throw error;
            }),
            // Settings are secondary: built-in defaults apply when they cannot be loaded.
            api.obterConfiguracao().then(data => data?.config || null).catch(() => null),
        ]);
        productions = loadedProductions;
        applySettings(loadedSettings);
        if (loadedSettings?.filtros && !filtersInitialized) {
            filters.status = loadedSettings.filtros.situacao_padrao;
            filters.order = loadedSettings.filtros.ordenacao_padrao;
            document.getElementById("client-status-filter").value = filters.status;
            document.getElementById("client-order").value = filters.order;
        }
        filtersInitialized = true;
        const proposalsAllowed = loadedSettings?.areas?.propostas !== false;
        proposals = proposalsAllowed ? loadedProposals.items : [];
        proposalsEnabled = loadedProposals.enabled && proposalsAllowed;
        document.getElementById("client-proposals-link").classList.toggle("hidden", !proposalsEnabled);
        finances = await loadFinances(productions);
        if (!proposalsEnabled && route().view.startsWith("proposal")) {
            history.replaceState({}, "", "/cliente");
        }
        renderRoute();
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        document.getElementById("client-loading").classList.add("hidden");
    }
}

document.getElementById("client-login-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (await fazerLogin()) await enterPortal();
});
document.getElementById("client-logout").addEventListener("click", logout);
document.getElementById("client-detail-back").addEventListener("click", () => navigate("/cliente/projetos"));
document.getElementById("client-proposal-back").addEventListener("click", () => navigate("/cliente/propostas"));
document.getElementById("client-status-filter").addEventListener("change", event => {
    filters.status = event.target.value;
    renderRoute();
});
document.getElementById("client-order").addEventListener("change", event => {
    filters.order = event.target.value;
    renderRoute();
});
document.querySelectorAll("a[data-route]").forEach(link => link.addEventListener("click", event => {
    event.preventDefault();
    navigate(link.getAttribute("href"));
}));
window.addEventListener("client:open", event => navigate(`/cliente/projetos/${event.detail}`));
window.addEventListener("popstate", () => {
    releaseObjectUrls();
    uploadFeedback = null;
    renderRoute();
});
document.addEventListener("admin:logout", () => {
    clearTimeout(tagPollTimer);
    releaseObjectUrls();
    uploadFeedback = null;
    productions = [];
    proposals = [];
    proposalsEnabled = false;
    finances = new Map();
    filtersInitialized = false;
    applySettings(null);
    setAlert();
});

let summaryRefresh = null;
async function refreshSummary() {
    if (summaryRefresh || !getCurrentUser()) return;
    const view = route().view;
    if (view !== "dashboard" && view !== "projects") return;
    summaryRefresh = (async () => {
        try {
            productions = await api.listarProducoes();
            finances = await loadFinances(productions);
            const current = route().view;
            if (current === "dashboard" || current === "projects") renderRoute();
        } catch {
            // Keep the last known list; the next visit retries.
        } finally {
            summaryRefresh = null;
        }
    })();
}
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshSummary();
});

initProductionRequest(setAlert);
if (await restaurarSessao()) await enterPortal();
