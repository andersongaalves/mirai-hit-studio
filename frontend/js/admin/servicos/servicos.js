import * as Notify from "../../utils/notifications.js";
import { $ } from "../../utils/dom.js";

import * as ServicosAPI from "./servicos_api.js";
import * as ServicosUI from "./servicos_ui.js";
import * as ServicosForm from "./servicos_form.js";
import * as ServicosParametros from "./servicos_parametros.js";

import { servicosState } from "./servicos_state.js";

function getUiHandlers() {
    return {
        onEditar: abrirEditorServico,
        onDeletar: deletarServico,
    };
}

function getParametroHandlers() {
    return {
        onMover: moverParametro,
        onRemover: removerParametro,
    };
}

function renderizarServicos() {
    ServicosUI.renderizarServicos(servicosState.lista, getUiHandlers());
}

function renderizarParametros() {
    ServicosParametros.renderizarParametros(
        servicosState.parametros,
        getParametroHandlers(),
    );
}

function setParametrosFromServico(servico) {
    servicosState.parametros = servico?.parametros
        ? servico.parametros.split(",").filter(Boolean)
        : [];
}

export async function carregarServicos() {
    try {
        const servicos = await ServicosAPI.buscarServicos();

        servicosState.lista = Array.isArray(servicos) ? servicos : [];

        renderizarServicos();
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao carregar serviços.");
    }
}

export function abrirEditorServico(id = null) {
    const servico = id
        ? servicosState.lista.find((item) => item.id === id)
        : null;

    if (id && !servico) {
        Notify.error("Serviço não encontrado.");
        return;
    }

    setParametrosFromServico(servico);
    ServicosForm.abrirFormularioServico(servico);
    renderizarParametros();
}

export function fecharEditorServico() {
    ServicosForm.fecharFormularioServico();
}

export function adicionarParametro() {
    const valor = $("param_selector")?.value;

    if (!valor) return;

    if (servicosState.parametros.includes(valor)) {
        Notify.warning("Parâmetro já existe.");
        return;
    }

    servicosState.parametros.push(valor);
    renderizarParametros();
}

export function removerParametro(index) {
    servicosState.parametros.splice(index, 1);
    renderizarParametros();
}

export function moverParametro(index, direcao) {
    const destino = index + direcao;

    if (destino < 0 || destino >= servicosState.parametros.length) {
        return;
    }

    [servicosState.parametros[index], servicosState.parametros[destino]] = [
        servicosState.parametros[destino],
        servicosState.parametros[index],
    ];

    renderizarParametros();
}

export async function salvarServico() {
    const { id, payload } = ServicosForm.getServicoFormPayload(
        servicosState.parametros,
    );

    if (!payload.nome) {
        Notify.warning("Informe o nome do serviço.");
        return;
    }

    try {
        await ServicosAPI.salvarServicoRequest(id, payload);

        Notify.success("Serviço salvo.");

        fecharEditorServico();
        carregarServicos();
    } catch (error) {
        console.error(error);

        Notify.error(error.message);
    }
}

export async function deletarServico(id) {
    if (!confirm("Deseja realmente excluir este serviço?")) {
        return;
    }

    try {
        await ServicosAPI.excluirServico(id);

        servicosState.lista = servicosState.lista.filter(
            (item) => item.id !== id,
        );

        renderizarServicos();

        Notify.success("Serviço removido.");
    } catch (error) {
        console.error(error);

        Notify.error("Erro ao excluir serviço.");
    }
}

export function inicializarParametros() {
    ServicosParametros.inicializarParametrosSelector();
    renderizarParametros();
}
