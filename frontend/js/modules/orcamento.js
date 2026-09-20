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
    const form = $("orcamento-form");
    const status = $("quote-submit-status");

    if (!btnSolicitar || !form || btnSolicitar.dataset.initialized) return;
    btnSolicitar.dataset.initialized = "true";
    let enviando = false;

    const setStatus = (message, stateName = "") => {
        if (!status) return;
        status.textContent = message;
        status.dataset.state = stateName;
        status.classList.toggle("hidden", !message);
    };

    form.addEventListener(
        "submit",

        async (event) => {
            event.preventDefault();
            if (enviando) return;
            if (!state.servicoSelecionadoOBJ) {
                setStatus("Selecione um serviço antes de enviar.", "error");
                Notify.error("Selecione um serviço.");

                return;
            }
            if (!form.reportValidity()) {
                setStatus("Revise os campos obrigatórios para continuar.", "error");
                return;
            }

            const payload = {
                nome_cliente: $("nome_cliente").value.trim(),

                email: $("email").value.trim(),

                whatsapp: $("whatsapp").value.trim() || null,

                servico: state.servicoSelecionadoOBJ.nome,

                valor_total: state.valorTotalCalculado,

                link_guia: $("guia")?.value.trim() || null,

                detalhes: obterDetalhes(),
            };

            try {
                enviando = true;
                btnSolicitar.disabled = true;
                btnSolicitar.setAttribute("aria-busy", "true");
                setStatus("Enviando solicitação...");
                await API.postOrcamento(payload);
                track("generate_lead", { service_id: state.servicoSelecionadoOBJ.id });
                setStatus("Solicitação recebida. A equipe analisará o briefing antes de preparar a proposta.", "success");
                Notify.success("Solicitação de orçamento enviada.");
            } catch {
                setStatus("Não foi possível enviar agora. Seus dados continuam no formulário para uma nova tentativa.", "error");
                Notify.error("Erro ao enviar solicitação de orçamento.");
            } finally {
                enviando = false;
                btnSolicitar.disabled = false;
                btnSolicitar.removeAttribute("aria-busy");
            }
        },
    );
}
