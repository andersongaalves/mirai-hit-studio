import * as Auth from "./auth.js";
import * as Dashboard from "./dashboard.js";
import * as Servicos from "./servicos/servicos.js";
import * as Projetos from "./projetos.js";
import * as Orcamentos from "./orcamentos/orcamentos.js";
import * as Propostas from "./propostas/propostas.js";
import * as Config from "./configuracoes.js";

import { fecharModalProducao } from "./producoes/producoes_modal.js";

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

document.addEventListener("admin:logout", () => { sessaoInicializada = null; });
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

expose("salvarConfiguracoesExtras", Config.salvarConfiguracoesExtras);

document.addEventListener("DOMContentLoaded", async () => {
    try {
        if (Auth.restaurarSessao()) {
            await initializeAdmin();
        }
    } catch (error) {
        console.error("Erro ao iniciar admin:", error);
    }
});
