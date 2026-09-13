import { state } from "../state.js";
import * as API from "../api.js";
import * as UI from "../ui.js";
import { CalculatorLogic } from "../calculator.js";
import { registerCalcular } from "./globals.js";
import { money } from "../utils/format.js";
import {$} from "../utils/dom.js";
import { track } from "../analytics.js";

export async function initCalculadora() {
    const [config, servicos] = await Promise.all([
        API.getAPI("config"),

        API.getAPI("servicos"),
    ]);

    state.configGlobal = {
        ...config,

        mult_desconto: (100 - config.desconto) / 100,
    };

    state.servicosDB = servicos;

    UI.renderizarBotoes(state.servicosDB);
}

export function calcular() {
    if (!state.servicoSelecionadoOBJ) return;

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

    if (state.servicoSelecionadoOBJ.aplica_desconto) {
        total *= state.configGlobal.mult_desconto;

        if (badge) {
            badge.style.display = "inline-block";

            badge.innerText = `DESCONTO DE ${state.configGlobal.desconto}% APLICADO`;
        }
    } else {
        if (badge) {
            badge.style.display = "none";
        }
    }

    state.valorTotalCalculado = total;

    const valor = $("valorTotal");

    if (valor) {
        valor.innerText = money(total);
    }
}

export async function initEventosCalculadora() {

    await initCalculadora();

    document.body.addEventListener(
        "input",

        (e) => {
            if (e.target.name === "servico") {
                state.servicoSelecionadoOBJ = state.servicosDB.find(
                    (s) => s.id == e.target.value,
                );

                if (state.servicoSelecionadoOBJ) {
                    track("view_service", { service_id: state.servicoSelecionadoOBJ.id });
                }

                const btnNext1 = $("btn-next-1");

                if (btnNext1) {
                    btnNext1.disabled = false;

                    btnNext1.classList.remove("disabled");
                }

                UI.renderizarFormularioParametros(
                    state.servicoSelecionadoOBJ.parametros,
                );
            }

            if (state.servicoSelecionadoOBJ) {
                calcular();
            }
        },
    );
}

registerCalcular(calcular);
