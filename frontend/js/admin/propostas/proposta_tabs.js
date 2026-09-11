import { $ } from "../../utils/dom.js";
import { PROPOSTA_ABAS } from "./proposta_utils.js";
import { createButtonElement } from "./proposta_dom.js";

export function renderizarTabs({
    abaAtiva = "cliente",
    onChange = () => {}
} = {}) {
    const container = $("proposta-tabs");

    if (!container) return;

    container.innerHTML = "";

    PROPOSTA_ABAS.forEach(aba => {
        const button = createButtonElement({
            text: aba.label,
            className: aba.id === abaAtiva
                ? "btn-small active"
                : "btn-small"
        });

        button.onclick = () => {
            onChange(aba.id);
        };

        container.appendChild(button);
    });
}
