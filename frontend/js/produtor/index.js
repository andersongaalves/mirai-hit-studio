import { fazerLogin, getCurrentUser, logout, restaurarSessao } from "../admin/auth.js";
import * as api from "./api.js";
import { messagesPanel } from "../modules/production_messages.js";
import { applySettings, renderDashboard, renderDetail, renderList, renderPayouts, setAlert, setCurrentUserId, showView } from "./ui.js";

let productions = [];
let payouts = [];
const filters = { status: "todos", order: "prazo" };
let filtersInitialized = false;

function route() {
    const match = location.pathname.match(/^\/produtor\/producoes\/(\d+)\/?$/);
    if (match) return { view: "detail", id: Number(match[1]) };
    if (/^\/produtor\/producoes\/?$/.test(location.pathname)) return { view: "productions" };
    if (/^\/produtor\/financeiro\/?$/.test(location.pathname)) return { view: "financeiro" };
    return { view: "dashboard" };
}

function navigate(path) {
    setAlert();
    history.pushState({}, "", path);
    renderRoute();
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
    } catch (error) {
        setAlert(error.message, true);
        navigate("/produtor/producoes");
    }
}

function renderRoute() {
    const current = route();
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

async function downloadReceipt(id, button) {
    button.disabled = true;
    try {
        saveBlob(await api.baixarComprovante(id));
    } catch (error) {
        setAlert(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function uploadFile(production, file, type, replacesId, button, note = "") {
    button.disabled = true;
    setAlert();
    try {
        await api.enviarArquivo(production.id, file, type, replacesId, note);
        await openDetail(production.id);
        setAlert(type === "previa" ? "Prévia enviada ao cliente com sucesso!" : "Arquivo enviado como uma nova versão.");
    } catch (error) {
        setAlert(error.message, true);
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
    document.getElementById("producer-username").textContent = user.username;
    document.getElementById("producer-greeting").textContent = user.username;
    document.getElementById("producer-loading").classList.remove("hidden");
    document.querySelectorAll(".producer-view").forEach(item => item.classList.add("hidden"));
    try {
        // Payouts are secondary: a failure there must not block production work.
        const [loadedProductions, payoutResult, loadedSettings] = await Promise.all([
            api.listarProducoes(),
            api.listarRepasses().then(value => ({ ok: true, value }), () => ({ ok: false, value: [] })),
            // Settings are secondary: built-in defaults apply when they cannot be loaded.
            api.obterConfiguracao().then(data => data?.config || null).catch(() => null),
        ]);
        productions = loadedProductions;
        payouts = payoutResult.value;
        applySettings(loadedSettings);
        if (loadedSettings?.filtros && !filtersInitialized) {
            filters.status = loadedSettings.filtros.status_padrao;
            filters.order = loadedSettings.filtros.ordenacao_padrao;
            document.getElementById("producer-status-filter").value = filters.status;
            document.getElementById("producer-order").value = filters.order;
        }
        filtersInitialized = true;
        renderRoute();
        if (!payoutResult.ok) {
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
