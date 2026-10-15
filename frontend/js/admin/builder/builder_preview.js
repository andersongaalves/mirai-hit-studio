// Preview of the public card, with the same renderer the site uses (everything escaped).
import { builderState } from "./builder_state.js";
import { renderizarEstrutura } from "../../modules/service_renderer.js";

export function renderPreview() {
    const preview = document.getElementById("builder-preview-render");
    if (!preview) return;
    preview.innerHTML = renderizarEstrutura({
        versao: 2,
        intro: builderState.intro,
        destaques: builderState.destaques,
        limites: builderState.limites,
    });
}
