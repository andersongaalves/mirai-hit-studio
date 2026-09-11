import { $ } from "../../utils/dom.js";
import { getTituloProposta } from "./proposta_utils.js";

export function abrirModalProposta(orcamento) {
    const modal = $("modal-proposta");
    const title = $("proposta-title");

    if (title) {
        title.textContent = getTituloProposta(orcamento);
    }

    modal
        ?.classList
        .remove("hidden");
}

export function fecharModalProposta() {
    $("modal-proposta")
        ?.classList
        .add("hidden");
}
