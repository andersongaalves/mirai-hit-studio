import * as Auth from "./auth.js";
import * as Dashboard from "./dashboard.js";
import * as Servicos from "./servicos/servicos.js";
import * as Projetos from "./projetos.js";
import * as Orcamentos from "./orcamentos/orcamentos.js";
import * as Propostas from "./propostas/propostas.js";
import * as Config from "./configuracoes.js";
import * as Clientes from "./clientes/clientes.js";
import * as Usuarios from "./usuarios/usuarios.js";
import * as Newsletter from "./newsletter/newsletter.js";

import { fecharModalProducao } from "./producoes/producoes_modal.js";
import { orcamentosState } from "./orcamentos/orcamentos_state.js";
import { producoesState } from "./producoes/producoes_state.js";
import { servicosState } from "./servicos/servicos_state.js";
import { resetClientesState } from "./clientes/clientes_state.js";
import { resetDashboardState } from "./dashboard/dashboard_state.js";
import { resetUsuariosState } from "./usuarios/usuarios_state.js";
import { resetNewsletterState } from "./newsletter/newsletter_state.js";
import { resetBuilder } from "./builder/builder.js";
import { initializeAdminShell, resetAdminShell } from "./admin_shell.js";
import { closeAllAdminModals } from "./admin_modal.js";

function expose(name, callback) {
    window[name] = callback;
}

let inicializacao = null;
let sessaoInicializada = null;
let loginEmAndamento = null;

async function initializeAdmin() {
    const token = Auth.getToken();
    if (!token) return;
    if (sessaoInicializada === token && inicializacao) return inicializacao;
    // Serialize loads, including a new login while old requests are finishing.
    if (inicializacao) await inicializacao;
    if (Auth.getToken() !== token) return;
    if (sessaoInicializada === token && inicializacao) return inicializacao;
    sessaoInicializada = token;
    inicializacao = Dashboard.inicializarDashboard().catch((error) => {
        sessaoInicializada = null;
        inicializacao = null;
        console.error("Erro ao iniciar admin:", error);
    });
    return inicializacao;
}

function fazerLogin() {
    if (!loginEmAndamento) {
        loginEmAndamento = (async () => {
            if (await Auth.fazerLogin()) await initializeAdmin();
        })().finally(() => { loginEmAndamento = null; });
    }
    return loginEmAndamento;
}

document.addEventListener("admin:logout", () => {
    sessaoInicializada = null;
    orcamentosState.lista = [];
    orcamentosState.produtores = [];
    producoesState.lista = [];
    servicosState.lista = [];
    servicosState.parametros = [];
    resetClientesState();
    resetDashboardState();
    resetUsuariosState();
    resetNewsletterState();
    orcamentosState.filtro = { busca: "", status: "todos" };
    producoesState.filtro = { busca: "", status: "todos", prazo: "todos" };
    resetBuilder();
    resetAdminShell();
    Orcamentos.fecharModalOrcamento();
    fecharModalProducao();
    Clientes.closeClienteModal();
    Usuarios.closeUsuarioModal();
    Newsletter.closeCampaignModal();
    closeAllAdminModals({ restoreFocus: false });
    document.querySelectorAll("#editor-servico").forEach(element => element.classList.add("hidden"));
    document.querySelectorAll(".admin-container input, .admin-container textarea").forEach(input => {
        input.value = "";
        if (input.type === "checkbox") input.checked = false;
    });
    for (const id of ["dashboard-content", "orcamentos-list", "producoes-list", "clientes-list", "cliente-historico", "usuarios-list", "newsletter-campaigns-list", "newsletter-subscribers-list", "lista-servicos", "portfolio-list", "builder-preview-render", "builder-sections", "builder-benefits", "param_list_render", "prod_etapas"]) {
        document.getElementById(id)?.replaceChildren();
    }
    document.querySelectorAll("#modal-orcamento span, #modal-producao span, #modal-orcamento h2, #modal-producao h2").forEach(el => { el.textContent = ""; });
    document.getElementById("orc_guia")?.removeAttribute("href");
    const proposalTitle = document.getElementById("proposta-title");
    if (proposalTitle) proposalTitle.textContent = "";
    document.querySelectorAll(".notification").forEach(el => el.remove());
});
expose("fazerLogin", fazerLogin);
expose("fazerLogout", Auth.logout);

expose("mostrarDashboard", Dashboard.mostrarDashboard);
expose("mostrarSecao", Dashboard.mostrarSecao);

expose("abrirEditorServico", Servicos.abrirEditorServico);
expose("fecharEditorServico", Servicos.fecharEditorServico);
expose("salvarServico", Servicos.salvarServico);
expose("deletarServico", Servicos.deletarServico);
expose("adicionarParametroBloco", Servicos.adicionarParametro);
expose("removerParametro", Servicos.removerParametro);
expose("moverParametro", Servicos.moverParametro);

expose("novoProjeto", Projetos.novoProjeto);
expose("editarProjeto", Projetos.editarProjeto);
expose("fecharModalProjeto", Projetos.fecharModal);
expose("salvarProjeto", Projetos.salvarProjeto);
expose("deletarProjeto", Projetos.deletarProjeto);

expose("visualizarOrcamento", Orcamentos.visualizarOrcamento);
expose("fecharModalOrcamento", Orcamentos.fecharModalOrcamento);
expose("deletarOrcamento", Orcamentos.deletarOrcamento);

expose("fecharEditorProposta", Propostas.fecharEditorProposta);

expose("fecharModalProducao", fecharModalProducao);
expose("novoCliente", Clientes.novoCliente);
expose("fecharModalCliente", Clientes.closeClienteModal);

expose("salvarConfiguracoesExtras", Config.salvarConfiguracoesExtras);

document.addEventListener("DOMContentLoaded", async () => {
    try {
        initializeAdminShell({
            onNavigate: (id) => id === "dashboard-menu"
                ? Dashboard.mostrarDashboard()
                : Dashboard.mostrarSecao(id),
        });
        if (await Auth.restaurarSessao()) {
            await initializeAdmin();
        }
    } catch (error) {
        console.error("Erro ao iniciar admin:", error);
    }
});
