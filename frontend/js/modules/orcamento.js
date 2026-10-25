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

// AUD6-S03-001: the server recalculates the price from this selection; the
// total shown in the browser is only an estimate.
function obterSelecao() {
    const servico = state.servicoSelecionadoOBJ;
    const parametros = {};
    const nomes = new Set((servico.parametros || "").split(",").map((item) => item.trim()).filter(Boolean));
    if (nomes.has("inst_aberto")) nomes.add("canais_inst");
    for (const nome of nomes) {
        if (nome === "descricao" || nome === "guia") continue;
        const campo = $(nome);
        if (campo && campo.value !== "") parametros[nome] = String(campo.value).slice(0, 20);
    }
    return servico.tipo === "combo"
        ? { combo_id: Number(servico.combo?.id ?? String(servico.id).replace(/^c/, "")), parametros }
        : { servico_id: Number(servico.id), parametros };
}

export function initOrcamento() {
    const btnSolicitar = $("btn-solicitar");
    const form = $("orcamento-form");
    const status = $("quote-submit-status");

    if (!btnSolicitar || !form || btnSolicitar.dataset.initialized) return;
    btnSolicitar.dataset.initialized = "true";
    let enviando = false;
    let submission = null;

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

                selecao: obterSelecao(),
            };
            const trap = $("contato_site")?.value.trim();
            if (trap) payload.contato_site = trap;

            try {
                enviando = true;
                btnSolicitar.disabled = true;
                btnSolicitar.setAttribute("aria-busy", "true");
                setStatus("Enviando solicitação...");
                const fingerprint = JSON.stringify(payload);
                if (submission?.fingerprint !== fingerprint) {
                    submission = { fingerprint, key: crypto.randomUUID() };
                }
                await API.postOrcamento(payload, submission.key);
                if (!submission.confirmed) {
                    track("generate_lead", { service_id: state.servicoSelecionadoOBJ.id });
                    submission.confirmed = true;
                }
                setStatus("Solicitação recebida. A equipe analisará o briefing antes de preparar a proposta.", "success");
                Notify.success("Solicitação de orçamento enviada.");
            } catch (error) {
                if (error?.status === 422 && error?.message) {
                    setStatus(error.message, "error");
                    Notify.error(error.message);
                    return;
                }
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
