import { exigirSessao, getCurrentUser, logout } from "../admin/auth.js";
import * as api from "./api.js";
import { bindImageCrop } from "../modules/image_crop.js";
import { applyBeatUploadLimits, validateBeatUpload } from "../modules/beat_upload_validation.js";
import { messagesPanel } from "../modules/production_messages.js";
import { stagesPanel } from "../modules/production_stages.js";
import { syncUploadHints } from "../modules/file_quotas.js";
import { startPortalNotifications } from "../modules/portal_notifications.js";
import { startAccountPassword } from "../modules/account_password.js";
import { loadPortfolioSubmissions } from "../modules/portfolio_submissions.js";
import { loadAudioTag } from "../modules/audio_tags.js";
import { enqueueUpload } from "../modules/upload_tasks.js";
import { beatPreview } from "../modules/beat_preview.js";
import { applySettings, renderDashboard, renderDetail, renderList, renderPayouts, setAlert, setCurrentUserId, showView } from "./ui.js";

let productions = [];
let beatUploadConfig = null;
bindImageCrop(document.querySelector('#producer-beat-form [name="capa"]'), { ratio: 1, width: 1024 });
let payouts = [];
const filters = { status: "todos", order: "prazo" };
let filtersInitialized = false;

function route() {
    const match = location.pathname.match(/^\/produtor\/producoes\/(\d+)\/?$/);
    if (match) return { view: "detail", id: Number(match[1]) };
    if (/^\/produtor\/producoes\/?$/.test(location.pathname)) return { view: "productions" };
    if (/^\/produtor\/financeiro\/?$/.test(location.pathname)) return { view: "financeiro" };
    if (/^\/produtor\/portfolio\/?$/.test(location.pathname)) return { view: "portfolio" };
    if (/^\/produtor\/perfil\/?$/.test(location.pathname)) return { view: "perfil" };
    if (/^\/produtor\/catalogo\/?$/.test(location.pathname)) return { view: "catalog" };
    if (/^\/produtor\/beats\/?$/.test(location.pathname)) return { view: "beats" };
    return { view: "dashboard" };
}

function navigate(path) {
    setAlert();
    history.pushState({}, "", path);
    renderRoute();
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
    if (route().view !== "detail" || route().id !== production.id || !data?.etapas?.length) return;
    const panel = document.getElementById("production-stages-panel");
    if (!panel) return;
    panel.replaceChildren(stagesPanel({
        role: "produtor",
        data,
        onChange: async (stage, destino) => {
            await api.atualizarEtapa(production.id, stage.id, { status: destino, status_atual: stage.status });
            await loadStages(production);
        },
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

// Roadmap 5.03: the thread loads after the detail so its failure never blocks the production.
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
        role: "produtor",
        messages,
        files,
        error,
        onSend: async payload => {
            await api.enviarMensagem(production.id, payload);
            await loadMessages(production, files);
        },
    }));
}

async function openDetail(id) {
    setAlert();
    try {
        const [production, files] = await Promise.all([
            api.obterProducao(id),
            api.listarArquivos(id),
        ]);
        productions = productions.map(item => item.id === production.id ? { ...item, ...production } : item);
        renderDetail(production, files, {
            onStatus: updateStatus,
            onUpload: uploadFile,
            onDownload: downloadFile,
            onListen: listenFile,
            onEditNote: (file, observacao) => api.editarObservacao(file.id, observacao),
        });
        showView("detail");
        loadMessages(production, files);
        loadStages(production);
        loadQuotas(production);
    } catch (error) {
        setAlert(error.message, true);
        navigate("/produtor/producoes");
    }
}

function renderRoute() {
    const current = route();
    if (current.view === "beats") {
        loadBeats();
        return;
    }
    if (current.view === "catalog") {
        loadBeatCatalog();
        return;
    }
    if (current.view === "perfil") {
        showView("perfil");
        loadAudioTag(document.getElementById("producer-audio-tag"));
        return;
    }
    if (current.view === "portfolio") {
        showView("portfolio");
        loadPortfolioSubmissions(document.getElementById("producer-portfolio-content"), { productions });
        return;
    }
    if (current.view === "detail") {
        openDetail(current.id);
        return;
    }
    if (current.view === "productions") {
        renderList(productions, filters, id => navigate(`/produtor/producoes/${id}`));
        showView("productions");
        return;
    }
    if (current.view === "financeiro") {
        renderPayouts(payouts, downloadReceipt);
        showView("financeiro");
        return;
    }
    renderDashboard(productions, payouts);
    showView("dashboard");
}

// AUD6-S08-001: the tag lives in "Meu perfil"; the dashboard only points there when missing.
async function loadTagNotice() {
    const notice = document.getElementById("producer-tag-notice");
    if (!notice) return;
    let tag = null;
    try {
        tag = await api.obterTag();
    } catch {
        notice.classList.add("hidden");
        return;
    }
    if (tag?.tag_id) {
        notice.classList.add("hidden");
        return;
    }
    const text = document.createElement("p");
    text.textContent = tag?.padrao_disponivel
        ? "Você ainda não cadastrou sua tag. Suas prévias usam a tag padrão da Mirai."
        : "Você ainda não cadastrou sua tag. Sem ela, suas prévias não recebem tag.";
    const link = document.createElement("a");
    link.href = "/produtor/perfil";
    link.className = "btn-outline";
    link.textContent = "Cadastrar minha tag";
    link.addEventListener("click", event => {
        event.preventDefault();
        navigate("/produtor/perfil");
    });
    notice.replaceChildren(text, link);
    notice.classList.remove("hidden");
}

async function loadBeats() {
    showView("beats");
    const list = document.getElementById("producer-beats-list");
    list.textContent = "Carregando beats...";
    try {
        const [beats, config] = await Promise.all([api.listarBeats(), api.obterConfiguracaoBeats()]);
        beatUploadConfig = config;
        applyBeatUploadLimits(document.getElementById("producer-beat-form"), config.limits);
        const uploadStatus = document.getElementById("producer-beat-upload-status");
        if (uploadStatus) uploadStatus.textContent = config.ready ? "" : config.message;
        list.replaceChildren(...beats.map(beat => {
            const card = document.createElement("article");
            card.className = "producer-card beat-card producer-beat-card";
            const content = document.createElement("div");
            content.className = "producer-beat-card__content";
            const title = document.createElement("h3"); title.textContent = beat.titulo;
            let cover = null;
            if (beat.capa_url) { cover = document.createElement("img"); cover.className = "beat-cover"; cover.src = beat.capa_url; cover.alt = `Capa de ${beat.titulo}`; }
            const meta = document.createElement("p"); meta.textContent = `${beat.produtor} · ${beat.status} · ${beat.bpm ? `${beat.bpm} BPM · ` : ""}${beat.generos || "Sem gênero"}`;
            const prices = document.createElement("p"); prices.className = "beat-card__prices"; prices.textContent = [["MP3", beat.preco_lease], ["WAV", beat.preco_wav], ["Multitrack", beat.preco_multitrack], ["Exclusivo", beat.preco_exclusivo]].filter(([, value]) => value).map(([label, value]) => `${label}: R$ ${Number(value).toFixed(2)}`).join(" · ");
            const audio = beatPreview(() => api.ouvirBeat(beat.id));
            content.append(title, meta, prices, audio);
            if (beat.motivo_rejeicao) { const reason = document.createElement("p"); reason.textContent = beat.motivo_rejeicao; content.append(reason); }
            if (cover) card.append(cover);
            else { const placeholder = document.createElement("div"); placeholder.className = "beat-cover beat-cover--placeholder"; placeholder.setAttribute("aria-hidden", "true"); card.append(placeholder); }
            card.append(content);
            return card;
        }));
        if (!beats.length) list.textContent = "Nenhum beat enviado.";
    } catch (error) { setAlert(error.message, true); list.textContent = ""; }
}

async function loadBeatCatalog() {
    showView("catalog");
    const list = document.getElementById("producer-catalog-list");
    list.textContent = "Carregando catálogo...";
    try {
        const beats = await api.listarCatalogoBeats();
        list.replaceChildren(...beats.map(beat => {
            const card = document.createElement("article");
            card.className = "producer-card beat-card producer-beat-card";
            const content = document.createElement("div");
            content.className = "producer-beat-card__content";
            const title = document.createElement("h3"); title.textContent = beat.titulo;
            const producer = document.createElement("p"); producer.textContent = beat.produtor;
            const meta = document.createElement("p"); meta.textContent = `${beat.bpm ? `${beat.bpm} BPM · ` : ""}${beat.tonalidade ? `${beat.tonalidade} · ` : ""}${beat.generos || "Sem gênero"}`;
            const prices = document.createElement("p"); prices.className = "beat-card__prices"; prices.textContent = [["MP3", beat.preco_lease], ["WAV", beat.preco_wav], ["Multitrack", beat.preco_multitrack], ["Exclusivo", beat.preco_exclusivo]].filter(([, value]) => value).map(([label, value]) => `${label}: R$ ${Number(value).toFixed(2)}`).join(" · ");
            if (beat.vendido) {
                card.classList.add("beat-card--sold");
                const sold = document.createElement("span"); sold.className = "beat-card__sold"; sold.textContent = "Vendido";
                content.append(title, producer, meta, sold);
            } else content.append(title, producer, meta, prices, beatPreview(() => api.ouvirBeat(beat.id)));
            if (beat.capa_url) {
                const cover = document.createElement("img"); cover.className = "beat-cover"; cover.src = beat.capa_url; cover.alt = `Capa de ${beat.titulo}`; card.append(cover);
            } else {
                const placeholder = document.createElement("div"); placeholder.className = "beat-cover beat-cover--placeholder"; placeholder.setAttribute("aria-hidden", "true"); card.append(placeholder);
            }
            card.append(content);
            return card;
        }));
        if (!beats.length) list.textContent = "Nenhum beat disponível no momento.";
    } catch (error) { setAlert(error.message, true); list.textContent = ""; }
}

async function updateStatus(id, status, button) {
    button.disabled = true;
    setAlert();
    try {
        const updated = await api.atualizarStatus(id, status);
        productions = productions.map(item => item.id === updated.id ? updated : item);
        // The status is already saved; a file-list failure must not report it as an error.
        const files = await api.listarArquivos(id).catch(() => null);
        if (files) {
            renderDetail(updated, files, {
                onStatus: updateStatus,
                onUpload: uploadFile,
                onDownload: downloadFile,
                onListen: listenFile,
                onEditNote: (file, observacao) => api.editarObservacao(file.id, observacao),
            });
            loadMessages(updated, files);
            loadStages(updated);
            setAlert("Andamento atualizado.");
        } else {
            button.disabled = false;
            setAlert("Andamento atualizado, mas a lista de arquivos não pôde ser recarregada.", true);
        }
    } catch (error) {
        setAlert(error.message, true);
        button.disabled = false;
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

// Listen in the page: the tagged preview or the original upload.
async function listenFile(file, versao) {
    const { blob } = await api.baixarArquivo(file.id, { versao, ouvir: true });
    return blob;
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

async function downloadReceipt(id, button, byStage = false) {
    button.disabled = true;
    try {
        saveBlob(await (byStage ? api.baixarComprovanteEtapa(id) : api.baixarComprovante(id)));
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function uploadFile(production, file, type, replacesId, button, note = "") {
    if (button.disabled) return;
    button.disabled = true;
    setAlert();
    try {
        const form = new FormData();
        form.append("arquivo", file);
        form.append("tipo", type);
        if (replacesId) form.append("substitui_arquivo_id", String(replacesId));
        if (note.trim()) form.append("observacao", note.trim());
        await enqueueUpload(`/portal/produtor/producoes/${production.id}/arquivos`, form, {
            label: `${file.name} · ${production.titulo}`,
            meta: { kind: "producer-production", productionId: production.id },
        });
        setAlert("Envio iniciado. Você pode continuar usando o portal e acompanhar em Envios.");
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

function denyWrongRole() {
    logout();
    const error = document.getElementById("login-error");
    error.textContent = "Esta área é exclusiva para contas de produtor.";
    error.classList.remove("hidden");
}

async function enterPortal() {
    const user = getCurrentUser();
    if (!user || user.role !== "produtor" || user.is_admin === true) {
        denyWrongRole();
        return;
    }
    setCurrentUserId(user.id);
    // AUD6-S08-001: one "Beats" entry; producers with the beats panel land on their own beats.
    document.getElementById("producer-beats-link").setAttribute("href", user.painel_beats ? "/produtor/beats" : "/produtor/catalogo");
    document.querySelectorAll("[data-beats-panel]").forEach(tab => tab.classList.toggle("hidden", !user.painel_beats));
    if (!user.painel_beats && route().view === "beats") history.replaceState({}, "", "/produtor/catalogo");
    // AUD6-S02-011: people are greeted by their display name, not their login.
    const shownName = user.nome_exibicao?.trim() || user.username;
    document.getElementById("producer-username").textContent = shownName;
    startPortalNotifications(user);
    startAccountPassword(user);
    document.getElementById("producer-greeting").textContent = shownName;
    document.getElementById("producer-loading").classList.remove("hidden");
    document.querySelectorAll(".producer-view").forEach(item => item.classList.add("hidden"));
    try {
        // Payouts are secondary: a failure there must not block production work.
        const [loadedProductions, payoutResult, loadedSettings, stageResult] = await Promise.all([
            api.listarProducoes(),
            api.listarRepasses().then(value => ({ ok: true, value }), () => ({ ok: false, value: [] })),
            // Settings are secondary: built-in defaults apply when they cannot be loaded.
            api.obterConfiguracao().then(data => data?.config || null).catch(() => null),
            api.listarRepassesEtapas().then(value => ({ ok: true, value }), () => ({ ok: false, value: [] })),
        ]);
        productions = loadedProductions;
        payouts = [...payoutResult.value, ...stageResult.value.filter(row => row.bruto_centavos > 0).map(row => ({
            ...row, valor_combinado: row.produtor_centavos / 100, status: row.estado, por_etapa: true,
        }))];
        applySettings(loadedSettings);
        if (loadedSettings?.filtros && !filtersInitialized) {
            filters.status = loadedSettings.filtros.status_padrao;
            filters.order = loadedSettings.filtros.ordenacao_padrao;
            document.getElementById("producer-status-filter").value = filters.status;
            document.getElementById("producer-order").value = filters.order;
        }
        filtersInitialized = true;
        renderRoute();
        loadTagNotice();
        if (!payoutResult.ok || !stageResult.ok) {
            setAlert("Não foi possível carregar os repasses agora. As produções continuam disponíveis.", true);
        }
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        document.getElementById("producer-loading").classList.add("hidden");
    }
}


document.getElementById("producer-logout").addEventListener("click", logout);
document.getElementById("producer-beat-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    if (button.disabled) return;
    const status = document.getElementById("producer-beat-upload-status");
    const validation = validateBeatUpload(form, beatUploadConfig);
    if (!validation.valid) {
        if (status) textStatus(status, validation.message, true);
        return;
    }
    button.disabled = true;
    if (status) textStatus(status, "Adicionando à fila de envios...", false);
    try {
        const body = new FormData(form);
        if (beatUploadConfig.limits.multitrack_mode === "link") {
            body.set("preco_multitrack", body.get("preco_multitrack_link") || "");
            body.delete("preco_multitrack_link");
            body.delete("multitrack");
        } else {
            body.delete("multitrack_url");
            body.delete("preco_multitrack_link");
        }
        for (const name of ["wav", "multitrack"]) {
            if (!body.get(name)?.size) body.delete(name);
        }
        await enqueueUpload("/portal/produtor/beats", body, {
            label: `Beat · ${body.get("titulo")}`,
            meta: { kind: "producer-beat" },
        });
        form.reset();
        applyBeatUploadLimits(form, beatUploadConfig.limits);
        setAlert("Beat adicionado aos envios. Você pode sair desta tela.");
        if (status) textStatus(status, "Envio iniciado. Acompanhe em Envios.", false);
    }
    catch (error) { setAlert(error.message, true); if (status) textStatus(status, error.message, true); }
    finally { button.disabled = false; }
});

document.addEventListener("mirai:upload-task", event => {
    const task = event.detail;
    if (task.status !== "completed") return;
    if (task.meta?.kind === "producer-beat") loadBeats();
    if (task.meta?.kind === "producer-production" && route().view === "detail" && route().id === task.meta.productionId) {
        openDetail(task.meta.productionId);
    }
});


function textStatus(node, message, error) {
    node.textContent = message;
    node.dataset.state = error ? "error" : "info";
}
document.getElementById("producer-detail-back").addEventListener("click", () => navigate("/produtor/producoes"));
document.getElementById("producer-status-filter").addEventListener("change", event => {
    filters.status = event.target.value;
    renderRoute();
});
document.getElementById("producer-order").addEventListener("change", event => {
    filters.order = event.target.value;
    renderRoute();
});

document.querySelectorAll("a[data-route], a[data-route-tab]").forEach(link => link.addEventListener("click", event => {
    event.preventDefault();
    navigate(link.getAttribute("href"));
}));

window.addEventListener("producer:open", event => navigate(`/produtor/producoes/${event.detail}`));
window.addEventListener("popstate", renderRoute);
document.addEventListener("admin:logout", () => {
    productions = [];
    payouts = [];
    filtersInitialized = false;
    applySettings(null);
    setAlert();
});

if (await exigirSessao()) await enterPortal();
