import {
    carregarServicos,
    inicializarParametros,
} from "./servicos/servicos.js";

import { carregarPortfolio } from "./projetos.js";

import { initOrcamentos } from "./orcamentos/orcamentos.js";

import { carregarConfiguracoes } from "./configuracoes.js";

import { initProducoes } from "./producoes/producoes.js";
import { initClientes } from "./clientes/clientes.js";
import { carregarDashboard } from "./dashboard/dashboard.js";
import { initUsuarios } from "./usuarios/usuarios.js";
import { initNewsletterAdmin } from "./newsletter/newsletter.js";
import { initAuditoria } from "./auditoria/auditoria.js";
import { initFinanceiro } from "./financeiro/financeiro.js";
import { initInbox } from "./inbox/inbox.js";
import { initBeats } from "./beats.js";

import { $, $$$, show, hide } from "../utils/dom.js";
import { setActiveSection } from "./admin_shell.js";

// AUD6-S09-004: each section loads its data the first time it is opened, so
// signing in only asks the API for the dashboard. Inbox and Beats refresh on
// every visit, as before.
const firstVisitLoaders = {
    "section-servicos": carregarServicos,
    "section-portfolio": carregarPortfolio,
    "section-orcamentos": initOrcamentos,
    "section-custos": carregarConfiguracoes,
    "section-producoes": initProducoes,
    "section-clientes": initClientes,
    "section-usuarios": initUsuarios,
    "section-newsletter": initNewsletterAdmin,
    "section-auditoria": initAuditoria,
    "section-financeiro": initFinanceiro,
};

const sectionLoaders = {
    "section-inbox": initInbox,
    "section-beats": initBeats,
};

const loadedSections = new Set();
document.addEventListener("admin:logout", () => loadedSections.clear());

function loadSection(id) {
    const loader = sectionLoaders[id] || (!loadedSections.has(id) && firstVisitLoaders[id]);
    if (!loader) return Promise.resolve();
    if (firstVisitLoaders[id]) loadedSections.add(id);
    return Promise.resolve().then(loader).catch((error) => {
        // A failed first load can be retried by opening the section again.
        loadedSections.delete(id);
        throw error;
    });
}

function focusHeading(container) {
    const heading = container?.querySelector("h1, h2");
    if (!heading) return;
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
}

export async function inicializarDashboard() {
    mostrarDashboard({ carregar: false });
    inicializarParametros();

    await carregarDashboard().catch(() => null);
}

export function mostrarDashboard({ carregar = true } = {}) {
    $$$(".admin-section").forEach((section) => hide(section));

    const dashboard = $("dashboard-menu");
    show(dashboard);
    setActiveSection("dashboard-menu");
    focusHeading(dashboard);
    if (carregar) carregarDashboard().catch(() => {});
}

export function mostrarSecao(id) {
    hide($("dashboard-menu"));

    $$$(".admin-section").forEach((section) => hide(section));

    show($(id));
    setActiveSection(id);

    focusHeading($(id));
    loadSection(id).catch(() => {});
}

export function voltarDashboard() {
    mostrarDashboard();
}

export function atualizarTudo() {
    const loaded = [...loadedSections].map((id) => firstVisitLoaders[id]());
    Promise.all([carregarDashboard(), ...loaded]).catch((error) => {
        console.error(error);
    });
}

export function abrirModal(id) {
    show($(id));
}

export function fecharModal(id) {
    hide($(id));
}
