import * as Auth from "./auth.js";
import * as Dashboard from "./dashboard.js";
import * as Servicos from "./servicos.js";
import * as Projetos from "./projetos.js";
import * as Orcamentos from "./orcamentos.js";
import * as Config from "./configuracoes.js";


// ==========================================
// LOGIN
// ==========================================

window.fazerLogin = Auth.fazerLogin;

window.fazerLogout = Auth.logout;

// ==========================================
// DASHBOARD
// ==========================================

window.mostrarDashboard =
    Dashboard.mostrarDashboard;

window.mostrarSecao =
    Dashboard.mostrarSecao;

// ==========================================
// SERVIÇOS
// ==========================================

window.abrirEditorServico =
    Servicos.abrirEditorServico;

window.salvarServico =
    Servicos.salvarServico;

window.deletarServico =
    Servicos.deletarServico;

window.adicionarParametroBloco =
    Servicos.adicionarParametro;

window.removerParametro =
    Servicos.removerParametro;

window.moverParametro =
    Servicos.moverParametro;

// ==========================================
// PROJETOS
// ==========================================

window.novoProjeto =
    Projetos.novoProjeto;

window.editarProjeto =
    Projetos.editarProjeto;

window.salvarProjeto =
    Projetos.salvarProjeto;

window.deletarProjeto =
    Projetos.deletarProjeto;

// ==========================================
// ORÇAMENTOS
// ==========================================

window.visualizarOrcamento =
    Orcamentos.visualizarOrcamento;

window.fecharModalOrcamento =
    Orcamentos.fecharModalOrcamento;

window.deletarOrcamento =
    Orcamentos.deletarOrcamento;

// ==========================================
// CONFIGURAÇÕES
// ==========================================

window.salvarConfiguracoesExtras = 
    Config.salvarConfiguracoesExtras;

// ==========================================
// STARTUP
// ==========================================

document.addEventListener(

    "DOMContentLoaded",

    async () => {
        if (
            Auth.restaurarSessao()
        ) {
            Dashboard.inicializarDashboard();
        }
    }
);