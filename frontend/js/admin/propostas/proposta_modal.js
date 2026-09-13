import { $ } from "../../utils/dom.js";
import { getTituloProposta } from "./proposta_utils.js";
import { closeAdminModal, openAdminModal } from "../admin_modal.js";

export function abrirModalProposta(orcamento, { onRequestClose } = {}) {
    const modal = $("modal-proposta");
    const title = $("proposta-title");

    if (title) {
        title.textContent = getTituloProposta(orcamento);
    }

    openAdminModal(modal, {
        onRequestClose,
    });
}

export function fecharModalProposta() {
    closeAdminModal("modal-proposta");
}
