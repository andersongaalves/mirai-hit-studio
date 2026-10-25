import { authFetch } from "./auth.js";

// AUD6-S09-006: one search box for the Admin. Results come grouped by kind;
// choosing one opens its section with that section's own search filled in.
const SECTION_SEARCH = Object.freeze({
    "section-clientes": "clientes-search",
    "section-orcamentos": "orcamentos-search",
    "section-producoes": "producoes-search",
    "section-usuarios": "usuarios-search",
});
const MIN_LENGTH = 2;
const DELAY_MS = 300;

let stopCurrent = null;

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

export function stopBuscaGlobal() {
    stopCurrent?.();
    stopCurrent = null;
}

async function openResult(group, item) {
    const open = window.mostrarSecao;
    if (typeof open !== "function") return;
    await open(group.secao);
    const field = document.getElementById(SECTION_SEARCH[group.secao] || "");
    if (!field || !item.filtro) return;
    field.value = item.filtro;
    field.dispatchEvent(new Event("input", { bubbles: true }));
}

export function startBuscaGlobal() {
    stopBuscaGlobal();
    const topbar = document.querySelector(".admin-topbar");
    const actions = topbar?.querySelector(".admin-topbar__actions");
    if (!topbar || !actions) return;

    const form = element("form", "admin-search");
    form.setAttribute("role", "search");
    const label = element("label", "admin-visually-hidden", "Buscar no painel");
    label.htmlFor = "admin-search-input";
    const input = element("input", "admin-search__input");
    input.id = "admin-search-input";
    input.type = "search";
    input.autocomplete = "off";
    input.maxLength = 80;
    input.placeholder = "Buscar cliente, orçamento, proposta…";
    input.setAttribute("aria-controls", "admin-search-results");
    input.setAttribute("aria-expanded", "false");
    const panel = element("div", "admin-search__results hidden");
    panel.id = "admin-search-results";
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Resultados da busca");
    panel.setAttribute("aria-live", "polite");
    form.append(label, input, panel);
    topbar.insertBefore(form, actions);

    let timer = null;
    let controller = null;
    let sequence = 0;

    const close = () => {
        panel.classList.add("hidden");
        input.setAttribute("aria-expanded", "false");
    };
    const show = (...children) => {
        panel.replaceChildren(...children);
        panel.classList.remove("hidden");
        input.setAttribute("aria-expanded", "true");
    };

    function render(data) {
        const groups = Array.isArray(data?.grupos) ? data.grupos : [];
        if (!groups.length) {
            show(element("p", "admin-search__empty", `Nada encontrado para “${data?.termo ?? input.value.trim()}”.`));
            return;
        }
        show(...groups.map(group => {
            const section = element("section", "admin-search__group");
            const title = element("h2", "admin-search__group-title", group.rotulo);
            const list = element("ul", "admin-search__list");
            for (const item of group.itens || []) {
                const entry = element("li");
                const button = element("button", "admin-search__item");
                button.type = "button";
                button.append(element("strong", "", item.titulo), element("span", "", item.detalhe || ""));
                button.addEventListener("click", () => {
                    close();
                    openResult(group, item).catch(() => {});
                });
                entry.append(button);
                list.append(entry);
            }
            section.append(title, list);
            return section;
        }));
    }

    async function search() {
        clearTimeout(timer);
        const term = input.value.trim();
        controller?.abort();
        if (term.length < MIN_LENGTH) {
            close();
            return;
        }
        const mine = ++sequence;
        controller = new AbortController();
        show(element("p", "admin-search__empty", "Buscando…"));
        try {
            const response = await authFetch(`/admin/busca?q=${encodeURIComponent(term)}`, { signal: controller.signal });
            const data = await response.json().catch(() => null);
            if (mine !== sequence) return;
            if (!response.ok) throw new Error("busca_indisponivel");
            render(data);
        } catch (error) {
            if (mine !== sequence || error?.name === "AbortError") return;
            show(element("p", "admin-search__empty", "Não foi possível buscar agora."));
        }
    }

    input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(search, DELAY_MS);
    });
    form.addEventListener("submit", event => {
        event.preventDefault();
        search();
    });
    const onKey = event => {
        if (event.key === "Escape" && !panel.classList.contains("hidden")) {
            // Keep the typed text; the first Escape only closes the results.
            event.preventDefault();
            close();
            input.focus();
        }
    };
    const onPointer = event => {
        if (!form.contains(event.target)) close();
    };
    form.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);

    stopCurrent = () => {
        clearTimeout(timer);
        controller?.abort();
        document.removeEventListener("pointerdown", onPointer);
        form.remove();
    };
}

document.addEventListener("admin:logout", stopBuscaGlobal);
