import { state } from "../state.js";
import * as API from "../api.js";
import * as UI from "../ui.js";
import { CalculatorLogic } from "../calculator.js";
import { registerCalcular } from "./globals.js";
import { money } from "../utils/format.js";
import {$} from "../utils/dom.js";
import { track } from "../analytics.js";
import { catalogDiscount } from "./catalog_pricing.js";

function setCalculatorStatus(message, stateName = "") {
    const status = $("calculator-status");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = stateName;
    status.classList.toggle("hidden", !message);
}

// A combo is chosen like a service: same price, discount and calculator parameters.
function comboComoServico(combo) {
    return {
        id: `c${combo.id}`,
        tipo: "combo",
        nome: combo.nome,
        subtitulo: combo.subtitulo || "",
        valor_base: Number(combo.preco_base) || 0,
        aplica_desconto: Boolean(combo.aplica_desconto),
        parametros: combo.parametros || "",
        prazo_estimado_dias: combo.prazo_estimado_dias ?? null,
        preco_catalogo: combo.preco_catalogo ?? null,
        combo,
    };
}

// For projects that fit no listed service: described in the briefing, priced in the proposal.
export const PERSONALIZADO = Object.freeze({
    id: "personalizado",
    tipo: "personalizado",
    nome: "Personalizado",
    subtitulo: "Não encontrou o que precisa? Descreva o projeto e montamos uma proposta sob medida.",
    valor_base: 0,
    aplica_desconto: false,
    parametros: "descricao,guia",
    prazo_estimado_dias: null,
});

export const isPersonalizado = servico => servico?.tipo === "personalizado";

/** While the studio pauses new requests, the page shows a notice instead of the form. */
export function mostrarPausa(mensagem) {
    const aviso = $("orcamentos-pausados");
    if (!aviso) return;
    $("quote-paused-message").textContent = mensagem || "Pausamos novos pedidos por alguns dias. Volte em breve!";
    aviso.hidden = false;
    document.querySelectorAll(".quote-stepper-band, .quote-layout").forEach(node => { node.hidden = true; });
    document.querySelector(".quote-header > p:not(.public-eyebrow)")?.setAttribute("hidden", "");
    aviso.querySelector("h2")?.focus?.();
}

export async function verificarDisponibilidade() {
    try {
        const estado = await API.getAPI("orcamentos/disponibilidade");
        if (estado?.pausado) {
            mostrarPausa(estado.mensagem);
            return false;
        }
    } catch {
        // If the check fails, the form stays available; the API still decides on submit.
    }
    return true;
}

export async function initCalculadora() {
    setCalculatorStatus("Carregando serviços...");
    if (!(await verificarDisponibilidade())) {
        setCalculatorStatus("");
        return;
    }
    try {
        const [config, servicos, combos] = await Promise.all([
            API.getAPI("config"),
            API.getAPI("servicos"),
            // Catalog rework: a failure loading combos never hides the single services.
            API.getAPI("catalogo/combos").catch(() => []),
        ]);
        state.configGlobal = {
            ...config,
            mult_desconto: (100 - Number(config.desconto || 0)) / 100,
        };
        state.servicosDB = [
            ...(Array.isArray(servicos) ? servicos : []),
            ...(Array.isArray(combos) ? combos : []).map(comboComoServico),
            PERSONALIZADO,
        ];
        UI.renderizarBotoes(state.servicosDB);
        setCalculatorStatus(
            state.servicosDB.length
                ? ""
                : "Nenhum serviço está disponível no momento. Tente novamente mais tarde.",
            state.servicosDB.length ? "" : "error",
        );
    } catch {
        state.servicosDB = [];
        UI.renderizarBotoes([]);
        setCalculatorStatus("Não foi possível carregar os serviços. Tente novamente mais tarde.", "error");
    }
}

export function calcular() {
    if (!state.servicoSelecionadoOBJ) return;
    if (isPersonalizado(state.servicoSelecionadoOBJ)) {
        // No catalog price: the value comes in the proposal.
        state.valorTotalCalculado = null;
        const badge = $("badge-desconto");
        if (badge) badge.hidden = true;
        if ($("valorTotal")) $("valorTotal").innerText = "Sob consulta";
        if ($("quote-context-estimate")) $("quote-context-estimate").textContent = "Sob consulta";
        return;
    }

    let total = state.servicoSelecionadoOBJ.valor_base;

    (state.servicoSelecionadoOBJ.parametros || "")

        .split(",")
        .map((param) => param.trim())

        .forEach((param) => {
            const el = $(param.trim());

            if (!el) return;

            if (CalculatorLogic[param]) {
                total += CalculatorLogic[param](
                    el.value,

                    $("canais_inst")?.value,
                );
            }
        });

    const badge = $("badge-desconto");

    const desconto = catalogDiscount(state.servicoSelecionadoOBJ, state.configGlobal);
    if (desconto > 0) {
        total *= 1 - desconto / 100;

        if (badge) {
            badge.hidden = false;
            badge.innerText = `DESCONTO DE ${desconto}% APLICADO`;
        }
    } else {
        if (badge) {
            badge.hidden = true;
        }
    }

    state.valorTotalCalculado = total;

    const valor = $("valorTotal");

    if (valor) {
        valor.innerText = money(total);
    }
    const contextualEstimate = $("quote-context-estimate");
    if (contextualEstimate) contextualEstimate.textContent = money(total);
}

export async function initEventosCalculadora() {
    await initCalculadora();

    const form = $("orcamento-form");
    if (!form || form.dataset.calculatorInitialized === "true") return;
    form.dataset.calculatorInitialized = "true";

    form.querySelectorAll("[data-step-target]").forEach((button) => {
        button.addEventListener("click", () => {
            window.avancarPasso(Number(button.dataset.stepTarget));
        });
    });

    document.body.addEventListener(
        "input",

        (e) => {
            if (e.target.name === "servico") {
                state.servicoSelecionadoOBJ = state.servicosDB.find(
                    (s) => s.id == e.target.value,
                );

                if (state.servicoSelecionadoOBJ) {
                    track("view_service", { service_id: state.servicoSelecionadoOBJ.id });
                    setCalculatorStatus("");
                }

                const btnNext1 = $("btn-next-1");

                if (btnNext1) {
                    btnNext1.disabled = false;

                    btnNext1.classList.remove("disabled");
                }

                UI.renderizarFormularioParametros(
                    state.servicoSelecionadoOBJ.parametros,
                );
                // A custom project needs a description to become a proposal.
                const descricao = $("descricao");
                if (descricao && isPersonalizado(state.servicoSelecionadoOBJ)) {
                    descricao.required = true;
                    descricao.minLength = 20;
                    descricao.placeholder = "O que você precisa, referências, prazo desejado e o resultado esperado";
                    const label = document.querySelector('label[for="descricao"]');
                    if (label) label.textContent = "Descreva o projeto";
                }
            }

            if (state.servicoSelecionadoOBJ) {
                calcular();
            }
        },
    );
}

registerCalcular(calcular);
