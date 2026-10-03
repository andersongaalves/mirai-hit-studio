import { fazerLogin, getCurrentUser, logout, restaurarSessao } from "../admin/auth.js";
import * as api from "./api.js";
import { renderDashboard, renderDetail, renderList, renderPayouts, setAlert, showView } from "./ui.js";

let productions = [];
let payouts = [];
const filters = { status: "todos", order: "prazo" };

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

async function openDetail(id) {
    setAlert();
    try {
        const [production, files] = await Promise.all([
            api.obterProducao(id),
            api.listarArquivos(id),
        ]);
        renderDetail(production, files, {
            onStatus: updateStatus,
            onUpload: uploadFile,
            onDownload: downloadFile,
        });
        showView("detail");
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
        const files = await api.listarArquivos(id);
        renderDetail(updated, files, {
            onStatus: updateStatus,
            onUpload: uploadFile,
            onDownload: downloadFile,
        });
        setAlert("Andamento atualizado.");
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
    URL.revokeObjectURL(url);
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

async function uploadFile(production, file, type, replacesId, button) {
    button.disabled = true;
    setAlert();
    try {
        await api.enviarArquivo(production.id, file, type, replacesId);
        await openDetail(production.id);
        setAlert("Arquivo enviado como uma nova versão.");
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
    document.getElementById("producer-username").textContent = user.username;
    document.getElementById("producer-greeting").textContent = user.username;
    document.getElementById("producer-loading").classList.remove("hidden");
    document.querySelectorAll(".producer-view").forEach(item => item.classList.add("hidden"));
    try {
        [productions, payouts] = await Promise.all([
            api.listarProducoes(),
            api.listarRepasses(),
        ]);
        renderRoute();
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
    setAlert();
});

if (await restaurarSessao()) await enterPortal();
