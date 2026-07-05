import { $, clear } from "../../utils/dom.js";
import { DICIONARIO_PARAMETROS, getParametroLabel } from "./servicos_utils.js";

export function inicializarParametrosSelector() {
    const select = $("param_selector");

    if (!select) return;

    clear(select);

    Object.entries(DICIONARIO_PARAMETROS).forEach(([key, label]) => {
        const option = document.createElement("option");

        option.value = key;
        option.textContent = label;

        select.appendChild(option);
    });
}

export function renderizarParametros(
    parametros = [],
    { onMover = () => {}, onRemover = () => {} } = {},
) {
    const container = $("param_list_render");

    if (!container) return;

    clear(container);

    if (!parametros.length) {
        container.innerHTML = `
            <div class="admin-empty">
                Nenhum parâmetro adicionado.
            </div>
        `;
        return;
    }

    parametros.forEach((parametro, index) => {
        container.appendChild(
            createParametroItem(parametro, index, parametros.length, {
                onMover,
                onRemover,
            }),
        );
    });
}

function createParametroItem(parametro, index, total, handlers) {
    const item = document.createElement("div");
    const texto = document.createElement("span");
    const subir = document.createElement("button");
    const descer = document.createElement("button");
    const remover = document.createElement("button");

    item.className = "admin-param-item";

    texto.textContent = `${index + 1}. ${getParametroLabel(parametro)}`;

    subir.type = "button";
    subir.textContent = "⬆";
    subir.disabled = index === 0;
    subir.onclick = () => {
        handlers.onMover(index, -1);
    };

    descer.type = "button";
    descer.textContent = "⬇";
    descer.disabled = index === total - 1;
    descer.onclick = () => {
        handlers.onMover(index, 1);
    };

    remover.type = "button";
    remover.textContent = "Remover";
    remover.onclick = () => {
        handlers.onRemover(index);
    };

    item.append(texto, subir, descer, remover);

    return item;
}
