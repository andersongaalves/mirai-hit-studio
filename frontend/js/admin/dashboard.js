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

import { $, $$$, show, hide } from "../utils/dom.js";
import { setActiveSection } from "./admin_shell.js";

const loaders = [
    carregarServicos,
    carregarPortfolio,
    initOrcamentos,
    carregarConfiguracoes,
    initProducoes,
    initClientes,
    initUsuarios,
    initNewsletterAdmin,
    initAuditoria,
];

function focusHeading(container) {
    const heading = container?.querySelector("h1, h2");
    if (!heading) return;
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
}

export async function inicializarDashboard() {
    mostrarDashboard({ carregar: false });
    inicializarParametros();

    await Promise.all([carregarDashboard().catch(() => null), ...loaders.map((loader) => loader())]);
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
}

export function voltarDashboard() {
    mostrarDashboard();
}

export function atualizarTudo() {
    Promise.all([carregarDashboard(), ...loaders.map((loader) => loader())]).catch((error) => {
        console.error(error);
    });
}

export function abrirModal(id) {
    show($(id));
}

export function fecharModal(id) {
    hide($(id));
}
