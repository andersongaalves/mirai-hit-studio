import * as UI from "../ui.js";
import { $ } from "../utils/dom.js";

export async function initHome() {
    if (!$("home-portfolio-track")) {
        return;
    }

    await UI.renderizarPortfolio();

    document.querySelectorAll("[data-carousel-direction]").forEach((button) => {
        button.addEventListener("click", () => {
            const direction = Number(button.dataset.carouselDirection) || 0;
            $("home-portfolio-track")?.scrollBy({
                left: direction * 320,
                behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                    ? "auto"
                    : "smooth",
            });
        });
    });
}
