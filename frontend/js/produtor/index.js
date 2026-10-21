import { fazerLogin, getCurrentUser, logout, restaurarSessao } from "../admin/auth.js";
import * as api from "./api.js";
import { bindImageCrop } from "../modules/image_crop.js";
import { uploadBusy } from "../modules/upload_feedback.js";
import { messagesPanel } from "../modules/production_messages.js";
import { stagesPanel } from "../modules/production_stages.js";
import { syncUploadHints } from "../modules/file_quotas.js";
import { startPortalNotifications } from "../modules/portal_notifications.js";
import { loadPortfolioSubmissions } from "../modules/portfolio_submissions.js";
import { loadAudioTag } from "../modules/audio_tags.js";
import { applySettings, renderDashboard, renderDetail, renderList, renderPayouts, setAlert, setCurrentUserId, showView } from "./ui.js";

let productions = [];
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

async function loadBeats() {
    showView("beats");
    const list = document.getElementById("producer-beats-list");
    list.textContent = "Carregando beats...";
    try {
        const beats = await api.listarBeats();
        list.replaceChildren(...beats.map(beat => {
            const card = document.createElement("article");
            card.className = "producer-card";
            const title = document.createElement("h3"); title.textContent = beat.titulo;
            if (beat.capa_url) { const cover = document.createElement("img"); cover.className = "beat-cover"; cover.src = beat.capa_url; cover.alt = `Capa de ${beat.titulo}`; cover.loading = "lazy"; card.append(cover); }
            const meta = document.createElement("p"); meta.textContent = `${beat.status} · ${beat.bpm ? `${beat.bpm} BPM · ` : ""}${beat.generos || "Sem gênero"}`;
            const prices = document.createElement("p"); prices.textContent = [["MP3 lease", beat.preco_lease], ["WAV lease", beat.preco_wav], ["Multitrack", beat.preco_multitrack], ["Exclusivo", beat.preco_exclusivo]].filter(([, value]) => value).map(([label, value]) => `${label}: R$ ${Number(value).toFixed(2)}`).join(" · ");
            const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none";
            audio.addEventListener("play", async () => {
                if (audio.src) return;
                const result = await api.ouvirBeat(beat.id); audio.src = URL.createObjectURL(result.blob); await audio.play();
            }, { once: true });
            card.append(title, meta, prices, audio);
            if (beat.motivo_rejeicao) { const reason = document.createElement("p"); reason.textContent = beat.motivo_rejeicao; card.append(reason); }
            return card;
        }));
        if (!beats.length) list.textContent = "Nenhum beat enviado.";
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
    const finish = uploadBusy(button);
    setAlert();
    try {
        const sent = await api.enviarArquivo(production.id, file, type, replacesId, note);
        await openDetail(production.id);
        // 5.10: the contract may hold previews until the studio approves them.
        const previewMessage = sent?.visivel_cliente === false
            ? "Prévia enviada. O cliente verá depois da aprovação do estúdio."
            : "Prévia enviada ao cliente com sucesso!";
        setAlert(sent?.processamento_tag === "pendente"
            ? "Prévia enviada. Processando a versão com tag para o cliente."
            : type === "previa" ? previewMessage : "Arquivo enviado como uma nova versão.");
    } catch (error) {
        setAlert(error.message, true);
        button.disabled = false;
    } finally {
        finish();
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
    document.getElementById("producer-beats-link").classList.toggle("hidden", !user.painel_beats);
    if (!user.painel_beats && route().view === "beats") history.replaceState({}, "", "/produtor");
    document.getElementById("producer-username").textContent = user.username;
    startPortalNotifications(user);
    document.getElementById("producer-greeting").textContent = user.username;
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
        if (!payoutResult.ok || !stageResult.ok) {
            setAlert("Não foi possível carregar os repasses agora. As produções continuam disponíveis.", true);
        }
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        document.getElementById("producer-loading").classList.add("hidden");
    }
}

document.getElementById("producer-login-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (await fazerLogin()) await enterPortal();
});

document.getElementById("producer-logout").addEventListener("click", logout);
document.getElementById("producer-beat-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    if (button.disabled) return;
    const finish = uploadBusy(button);
    try {
        const body = new FormData(form);
        for (const name of ["wav", "multitrack"]) {
            if (!body.get(name)?.size) body.delete(name);
        }
        await api.enviarBeat(body);
        form.reset();
        setAlert("Beat enviado para revisão.");
        await loadBeats();
    }
    catch (error) { setAlert(error.message, true); }
    finally { finish(); }
});
document.getElementById("producer-detail-back").addEventListener("click", () => navigate("/produtor/producoes"));
document.getElementById("producer-status-filter").addEventListener("change", event => {
    filters.status = event.target.value;
    renderRoute();
});
document.getElementById("producer-order").addEventListener("change", event => {
    filters.order = event.target.value;
    renderRoute();
});

document.querySelectorAll("a[data-route]").forEach(link => link.addEventListener("click", event => {
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

if (await restaurarSessao()) await enterPortal();
