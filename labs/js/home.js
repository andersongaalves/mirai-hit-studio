// Home: the plugin catalog (featured first), with loading, empty and error states.
import { t } from "./i18n.js";
import { READY, el, getJSON, pluginCard } from "./labs.js";

const root = document.getElementById("catalog");

function state(title, text, retry = false) {
    const box = el("div", "state");
    const icon = el("img");
    icon.src = "/img/icon-sinal.svg";
    icon.alt = "";
    box.append(icon, el("h3", "", title), el("p", "", text));
    if (retry) {
        const button = el("button", "btn btn--ghost", t("retry"));
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
            : [state(t("emptyTitle"), t("emptyText"))]));
        const count = document.getElementById("catalog-count");
        if (count) count.textContent = plugins.length ? t(plugins.length === 1 ? "count" : "countMany", { n: plugins.length }) : "";
    } catch (error) {
        root.replaceChildren(state(t("catalogDown"), error.message, true));
    } finally {
        root.removeAttribute("aria-busy");
    }
}

if (READY) load();
