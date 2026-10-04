import { state } from "../state.js";
import * as API from "../api.js";
import * as PUI from "../portfolio_ui.js";

const filters = { vertical: "", categoria: "" };
let segmentLabels = {};

function filteredProjects() {
    return state.todosProjetos.filter(project =>
        (!filters.vertical || project.vertical === filters.vertical) &&
        (!filters.categoria || project.categoria === filters.categoria),
    );
}

function updateFilter(kind, value) {
    filters[kind] = value;
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter);
    PUI.renderizarProjetos(filteredProjects(), segmentLabels);
}

export async function initPortfolioPage() {
    const [projects, segments] = await Promise.all([
        API.getProjetos(),
        API.getPortfolioSegments().catch(() => []),
    ]);
    segmentLabels = Object.fromEntries(
        (Array.isArray(segments) ? segments : []).map(segment => [segment.id, segment.label]),
    );
    state.todosProjetos = Array.isArray(projects)
        ? projects.filter(PUI.isPublicProject)
        : [];
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter);
    PUI.renderizarProjetos(state.todosProjetos, segmentLabels);
}
