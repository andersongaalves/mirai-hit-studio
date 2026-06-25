import * as UI from "../ui.js";
import { $, $$, $$$ } from "../utils/dom.js";

export async function initHome() {
    if (
        !$(
            "home-portfolio-track"
        )
    ) {
        return;
    }

    await UI.renderizarPortfolio();
    UI.initHeroParallax();

}