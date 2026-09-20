import { state } from "../state.js";
import * as API from "../api.js";
import * as PUI from "../portfolio_ui.js";

const filters = { vertical: "", categoria: "" };

function filteredProjects() {
    return state.todosProjetos.filter(project =>
        (!filters.vertical || project.vertical === filters.vertical) &&
        (!filters.categoria || project.categoria === filters.categoria),
    );
}

function updateFilter(kind, value) {
    filters[kind] = value;
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter);
    PUI.renderizarProjetos(filteredProjects());
}

export async function initPortfolioPage() {
    const projects = await API.getProjetos();
    state.todosProjetos = Array.isArray(projects)
        ? projects.filter(PUI.isPublicProject)
        : [];
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter);
    PUI.renderizarProjetos(state.todosProjetos);
}
