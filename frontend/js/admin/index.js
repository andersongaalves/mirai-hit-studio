import * as Auth from "./auth.js";
import * as Dashboard from "./dashboard.js";
import * as Servicos from "./servicos/servicos.js";
import * as Projetos from "./projetos.js";
import * as Orcamentos from "./orcamentos/orcamentos.js";
import * as Config from "./configuracoes.js";

import { fecharModalProducao } from "./producoes/producoes_modal.js";

function expose(name, callback) {
    window[name] = callback;
}

expose("fazerLogin", Auth.fazerLogin);
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

expose("fecharModalProducao", fecharModalProducao);

expose("salvarConfiguracoesExtras", Config.salvarConfiguracoesExtras);

document.addEventListener("DOMContentLoaded", async () => {
    try {
        if (Auth.restaurarSessao()) {
            await Dashboard.inicializarDashboard();
        }
    } catch (error) {
        console.error("Erro ao iniciar admin:", error);
    }
});
