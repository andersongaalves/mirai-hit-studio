import { state } from "../state.js";
import * as API from "../api.js";
import * as PUI from "../portfolio_ui.js";

import { registerFiltrar } from "./globals.js";

function filtrar(categoria) {

    if (categoria === "Todos") {
        PUI.renderizarProjetos(
            state.todosProjetos

        );
        return;

    }

    PUI.renderizarProjetos(
        state.todosProjetos.filter(
            projeto =>
                projeto.categoria === categoria

        )
    );

}

export async function initPortfolioPage() {

    state.todosProjetos =
        await API.getProjetos();

    PUI.renderizarFiltros(
        state.todosProjetos,
        filtrar

    );

    PUI.renderizarProjetos(
        state.todosProjetos
    );

}

registerFiltrar(filtrar);