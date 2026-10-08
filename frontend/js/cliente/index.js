import { fazerLogin, getCurrentUser, logout, restaurarSessao } from "../admin/auth.js";
import * as api from "./api.js";
import {
    renderDashboard,
    renderDetail,
    renderList,
    renderProposalDetail,
    renderProposalList,
    renderProposalSummary,
    setAlert,
    showView,
} from "./ui.js";

let productions = [];
let proposals = [];
let proposalsEnabled = false;
let finances = new Map();
const objectUrls = new Set();
const filters = { status: "todos", order: "recente" };

function route() {
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

function navigate(path) {
    releaseObjectUrls();
    setAlert();
    history.pushState({}, "", path);
    renderRoute();
}

async function openDetail(id) {
    setAlert();
    try {
        const [production, files, finance] = await Promise.all([
            api.obterProducao(id),
            api.listarArquivos(id),
            api.obterFinanceiro(id),
        ]);
        finances.set(id, finance);
        renderDetail(production, files, finance, {
            onUpload: uploadFile,
            onDownload: downloadFile,
            onPreview: playPreview,
        });
        showView("detail");
    } catch (error) {
        setAlert(error.message, true);
        history.replaceState({}, "", "/cliente/projetos");
        renderRoute();
    }
}

function renderRoute() {
    const current = route();
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

async function uploadFile(production, file, type, replacesId, button) {
    button.disabled = true;
    setAlert();
    try {
        await api.enviarArquivo(production.id, file, type, replacesId);
        await openDetail(production.id);
        setAlert(replacesId ? "Nova versão enviada." : "Arquivo enviado.");
    } catch (error) {
        setAlert(error.message, true);
        button.disabled = false;
    }
}

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
    document.getElementById("client-greeting").textContent = user.username;
    document.getElementById("client-loading").classList.remove("hidden");
    document.querySelectorAll(".producer-view").forEach(item => item.classList.add("hidden"));
    try {
        const [loadedProductions, loadedProposals] = await Promise.all([
            api.listarProducoes(),
            api.listarPropostas().then(items => ({ enabled: true, items })).catch(error => {
                if (error.status === 404) return { enabled: false, items: [] };
                throw error;
            }),
        ]);
        productions = loadedProductions;
        proposals = loadedProposals.items;
        proposalsEnabled = loadedProposals.enabled;
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
    renderRoute();
});
document.addEventListener("admin:logout", () => {
    releaseObjectUrls();
    productions = [];
    proposals = [];
    proposalsEnabled = false;
    finances = new Map();
    setAlert();
});

if (await restaurarSessao()) await enterPortal();
