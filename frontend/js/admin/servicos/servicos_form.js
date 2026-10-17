import { $, show, hide } from "../../utils/dom.js";

import * as Builder from "../builder/builder.js";
import * as BuilderUI from "../builder/builder_ui.js";
import { carregarEtapasServico } from "./servicos_etapas.js";
import { carregarCotasServico } from "./servicos_cotas.js";
import { carregarPoliticasServico } from "./servicos_politicas.js";
import { promotionForm } from "../../modules/promotion_form.js";

let promotion = null;
function carregarPromocao(value = null) {
    const slot = $("servico-promocao-editor");
    promotion = slot ? promotionForm(value, "servico-promocao") : null;
    slot?.replaceChildren(...(promotion ? [promotion.element] : []));
}

const formFields = [
    "srv_id",
    "srv_nome",
    "srv_subtitulo",
    "srv_valor",
    "srv_aplica_desconto",
];

function setValue(id, value = "") {
    const element = $(id);

    if (element) {
        element.value = value ?? "";
    }
}

function getValue(id) {
    return $(id)?.value ?? "";
}

function setEditorTitle(text) {
    const title = $("editor-title");

    if (title) {
        title.textContent = text;
    }
}

export function abrirFormularioServico(servico = null) {
    show($("editor-servico"));

    if (!servico) {
        setEditorTitle("Criar Serviço");
        limparFormularioServico();
        carregarEtapasServico(null);
        carregarCotasServico(null);
        carregarPoliticasServico(null);
        return;
    }

    setEditorTitle("Editar Serviço");
    setValue("srv_id", servico.id);
    setValue("srv_nome", servico.nome);
    setValue("srv_subtitulo", servico.subtitulo);
    setValue("srv_valor", servico.valor_base);
    setValue("srv_aplica_desconto", String(!!servico.aplica_desconto));
    carregarPromocao(servico.promocao);

    Builder.carregarBuilder(servico.estrutura_servico);

    BuilderUI.initBuilder();
    carregarEtapasServico(servico.id);
    carregarCotasServico(servico.id);
    carregarPoliticasServico(servico.id);
}

export function fecharFormularioServico() {
    hide($("editor-servico"));
}

export function limparFormularioServico() {
    formFields.forEach((id) => {
        setValue(id, "");
    });

    setValue("srv_valor", 0);
    setValue("srv_aplica_desconto", "false");
    carregarPromocao();

    Builder.resetBuilder();
    BuilderUI.initBuilder();
}

export function getServicoFormPayload(parametros = []) {
    return {
        id: getValue("srv_id"),
        payload: {
            nome: getValue("srv_nome").trim(),
            subtitulo: getValue("srv_subtitulo").trim(),
            valor_base: Number(getValue("srv_valor") || 0),
            aplica_desconto: getValue("srv_aplica_desconto") === "true",
            parametros: parametros.join(","),
            estrutura_servico: Builder.gerarJSON(),
            ...(promotion ? { promocao: promotion.read() } : {}),
        },
    };
}
