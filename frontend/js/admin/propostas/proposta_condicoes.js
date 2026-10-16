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
                <label for="proposta_condicoes">Condições específicas desta proposta (opcional)</label>
                <p class="admin-help">As condições padrão (pagamento, revisões, reembolso, direitos, comunicação, prazo, validade de 10 dias e aceite pelo Portal do Cliente) já fazem parte do documento. Use este campo só para o que for particular deste projeto.</p>
                <textarea id="proposta_condicoes" rows="8">${escapeHtml(proposta.condicoes)}</textarea>
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
