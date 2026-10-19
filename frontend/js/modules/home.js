import * as UI from "../ui.js";
import { $ } from "../utils/dom.js";
import { initMixComparison } from "./mix_comparison.js";

export async function initHome() {
    if (!$("home-portfolio-track")) {
        return;
    }

    try {
        await UI.renderizarPortfolio();
        await initMixComparison();
    } catch {
        document.querySelectorAll("[data-carousel-direction]").forEach(button => { button.hidden = true; });
        const notice = document.createElement("p");
        notice.className = "public-empty";
        notice.setAttribute("role", "alert");
        notice.textContent = "Não foi possível carregar os trabalhos agora. Tente novamente mais tarde.";
        $("home-portfolio-track").replaceChildren(notice);
    }

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
