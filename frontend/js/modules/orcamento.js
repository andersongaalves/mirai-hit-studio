import { state } from "../state.js";
import * as API from "../api.js";
import * as Notify from "../utils/notifications.js";
import { $ } from "../utils/dom.js";
import { PARAM_TEMPLATES } from "../ui.js";
import { track } from "../analytics.js";

function obterDetalhes() {
    const partes = [];
    const descricao = $("descricao")?.value.trim();
    if (descricao) partes.push(`Descrição: ${descricao}`);
    const parametros = state.servicoSelecionadoOBJ.parametros || "";
    for (const param of new Set(parametros.split(",").map((item) => item.trim()))) {
        const campo = $(param);
        const formatar = PARAM_TEMPLATES[param]?.detalhe;
        if (campo && campo.value !== "" && formatar) {
            partes.push(formatar(campo.value, $("canais_inst")?.value));
        }
    }
    return partes.join("\n");
}

export function initOrcamento() {
    const btnSolicitar = $("btn-solicitar");

    if (!btnSolicitar || btnSolicitar.dataset.initialized) return;
    btnSolicitar.dataset.initialized = "true";
    let enviando = false;

    btnSolicitar.addEventListener(
        "click",

        async () => {
            if (enviando) return;
            if (!state.servicoSelecionadoOBJ) {
                Notify.error("Selecione um serviço.");

                return;
            }

            const payload = {
                nome_cliente: $("nome_cliente").value,

                email: $("email").value,

                whatsapp: $("whatsapp").value,

                servico: state.servicoSelecionadoOBJ.nome,

                valor_total: state.valorTotalCalculado,

                link_guia: $("guia")?.value || "",

                detalhes: obterDetalhes(),
            };

            try {
                enviando = true;
                btnSolicitar.disabled = true;
                await API.postOrcamento(payload);
                track("generate_lead", { service_id: state.servicoSelecionadoOBJ.id });
                Notify.success("Solicitação de orçamento enviada.");
            } catch (error) {
                console.error(error);
                Notify.error("Erro ao enviar solicitação de orçamento.");
            } finally {
                enviando = false;
                btnSolicitar.disabled = false;
            }
        },
    );
}
