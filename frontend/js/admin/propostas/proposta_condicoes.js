import { $ } from "../../utils/dom.js";
import { atualizarCampoProposta } from "./proposta_state.js";
import { escapeHtml } from "./proposta_utils.js";

export function renderizarCondicoes(
    proposta,
    onChange = () => {}
) {
    const container = $("proposta-content");

    if (!container || !proposta) return;

    container.innerHTML = `
        <div class="admin-info">
            <div class="form-group">
                <label>Condições comerciais</label>
                <textarea id="proposta_condicoes" rows="14">${escapeHtml(proposta.condicoes)}</textarea>
            </div>
        </div>
    `;

    const condicoes = $("proposta_condicoes");

    if (condicoes) {
        condicoes.oninput = e => {
            atualizarCampoProposta(
                "condicoes",
                e.target.value
            );
            onChange();
        };
    }
}
