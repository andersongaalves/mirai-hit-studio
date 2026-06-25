import { $, $$, $$$ } from "../utils/dom.js";

let calcular = () => {};
let filtrar = () => {};

export function registerCalcular(fn) {
    calcular = fn;
}

export function registerFiltrar(fn) {
    filtrar = fn;
}

window.filtrarProjetos = (...args) =>
    filtrar(...args);

window.moverCarrossel = (dir) => {
    const track = $(
        "home-portfolio-track"
    );

    if (!track) return;

    track.scrollBy({
        left: dir * 320,
        behavior: "smooth"
    });
};

window.avancarPasso = function (passo) {

    document
        .querySelectorAll(".step-content")
        .forEach(el =>
            el.classList.add("hidden")
        );

    document
        .querySelectorAll(".step-indicator")
        .forEach(el =>
            el.classList.remove("active")
        );

    document
        .getElementById(`step-${passo}`)
        ?.classList.remove("hidden");

    for (let i = 1; i <= passo; i++) {

        const indicador =
            $(
                `ind-${i}`
            );

        if (indicador) {

            indicador.classList.add(
                "active"
            );
        }
    }

    if (passo === 3) {
        calcular();

    }
};

window.voltarPasso = function (passo) {
    window.avancarPasso(passo);

};