import { state } from "../state.js";
import * as API from "../api.js";
import * as Notify from "../utils/notifications.js";
import * as Validation from "../utils/validation.js";
import { $, $$, $$$ } from "../utils/dom.js";

export function initOrcamento() {

    const btnSolicitar =
        $(
            "btn-solicitar"
        );

    if (!btnSolicitar) return;

    btnSolicitar.addEventListener(

        "click",

        async () => {

            if (!state.servicoSelecionadoOBJ) {

                Notify.error(
                    "Selecione um serviço."
                );

                return;

            }

            const payload = {

                nome_cliente:
                    $(
                        "nome_cliente"
                    ).value,

                email:
                    $(
                        "email"
                    ).value,

                whatsapp:
                    $(
                        "whatsapp"
                    ).value,

                servico:
                    state
                        .servicoSelecionadoOBJ
                        .nome,

                valor_total:
                    state
                        .valorTotalCalculado,

                link_guia:
                    $(
                        "guia"
                    )?.value || "",

                detalhes: ""

            };

            try {
                await API.postOrcamento(
                    payload
                );
                Notify.success(
                    "Proposta enviada com sucesso!"
                );
            }

            catch (error) {
                console.error(
                    error
                );
                Notify.error(
                    "Erro ao enviar proposta."
                );
            }
        }
    );
}