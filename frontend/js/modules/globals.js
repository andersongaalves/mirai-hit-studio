import { $ } from "../utils/dom.js";
import { state } from "../state.js";
import { trackOnce } from "../analytics.js";

let calcular = () => {};
let filtrar = () => {};

export function registerCalcular(fn) {
    calcular = fn;
}

export function registerFiltrar(fn) {
    filtrar = fn;
}

window.filtrarProjetos = (...args) => filtrar(...args);

window.moverCarrossel = (dir) => {
    const track = $("home-portfolio-track");

    if (!track) return;

    track.scrollBy({
        left: dir * 320,
        behavior: "smooth",
    });
};

window.avancarPasso = function (passo) {
    document
        .querySelectorAll(".step-content")
        .forEach((el) => el.classList.add("hidden"));

    document
        .querySelectorAll(".step-indicator")
        .forEach((el) => el.classList.remove("active"));

    const target = document.getElementById(`step-${passo}`);
    target?.classList.remove("hidden");

    for (let i = 1; i <= passo; i++) {
        const indicador = $(`ind-${i}`);

        if (indicador) {
            indicador.classList.add("active");
            if (i === passo) indicador.setAttribute("aria-current", "step");
            else indicador.removeAttribute("aria-current");
        }
    }

    if (passo === 3) {
        calcular();
    }

    if (passo === 2 && state.servicoSelecionadoOBJ) {
        trackOnce("begin_briefing", { service_id: state.servicoSelecionadoOBJ.id });
    }

    target?.querySelector("h2")?.focus?.({ preventScroll: true });
    target?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
        block: "start",
    });
};

window.voltarPasso = function (passo) {
    window.avancarPasso(passo);
};
