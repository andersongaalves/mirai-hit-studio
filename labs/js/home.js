// Home: the plugin catalog (featured first), with loading, empty and error states.
import { el, getJSON, pluginCard, setYear } from "./labs.js";

const root = document.getElementById("catalog");

function state(title, text, retry = false) {
    const box = el("div", "state");
    const icon = el("img");
    icon.src = "/img/icon-sinal.svg";
    icon.alt = "";
    box.append(icon, el("h3", "", title), el("p", "", text));
    if (retry) {
        const button = el("button", "btn btn--ghost", "Tentar de novo");
        button.type = "button";
        button.addEventListener("click", load);
        box.append(button);
    }
    return box;
}

async function load() {
    if (!root) return;
    root.setAttribute("aria-busy", "true");
    root.replaceChildren(...Array.from({ length: 3 }, () => el("div", "skeleton")));
    try {
        const plugins = await getJSON("/labs/plugins");
        root.replaceChildren(...(plugins.length
            ? plugins.map(pluginCard)
            : [state("Os primeiros plugins estão a caminho", "Estamos finalizando as primeiras ferramentas da Mirai Hit Labs. Siga @miraihitstudio para saber do lançamento.")]));
        const count = document.getElementById("catalog-count");
        if (count) count.textContent = plugins.length ? `${plugins.length} plugin${plugins.length === 1 ? "" : "s"}` : "";
    } catch (error) {
        root.replaceChildren(state("Catálogo indisponível", error.message, true));
    } finally {
        root.removeAttribute("aria-busy");
    }
}

setYear();
load();
