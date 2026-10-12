import { state } from "../state.js";
import * as API from "../api.js";
import * as PUI from "../portfolio_ui.js";
import { safeURL } from "../utils/security.js";

const filters = { vertical: "", segment: "", case_type: "" };
let segmentLabels = {};

function filteredProjects() {
    return state.todosProjetos.filter(project =>
        (!filters.vertical || project.vertical === filters.vertical) &&
        (!filters.segment || (Array.isArray(project.segmentos_json) && project.segmentos_json.includes(filters.segment))) &&
        (!filters.case_type || project.case_type === filters.case_type),
    );
}

function updateFilter(kind, value) {
    filters[kind] = value;
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter, segmentLabels);
    PUI.renderizarProjetos(filteredProjects(), segmentLabels);
}

export async function initPortfolioPage() {
    let projects;
    let segments;
    try {
        [projects, segments] = await Promise.all([
            API.getProjetos(),
            API.getPortfolioSegments().catch(() => []),
        ]);
    } catch {
        PUI.renderizarFiltros([], filters, updateFilter);
        PUI.renderizarErro("Não foi possível carregar o portfólio agora. Tente novamente mais tarde.");
        return;
    }
    segmentLabels = Object.fromEntries(
        (Array.isArray(segments) ? segments : []).map(segment => [segment.id, segment.label]),
    );
    state.todosProjetos = Array.isArray(projects)
        ? projects.filter(PUI.isPublicProject)
        : [];
    PUI.renderizarFiltros(state.todosProjetos, filters, updateFilter, segmentLabels);
    PUI.renderizarProjetos(state.todosProjetos, segmentLabels);

    // The A/B player on the home page owns synchronized playback. Link to it
    // only when the public endpoint actually returns an authorized pair.
    try {
        const comparisons = await API.getMixComparisons();
        if (Array.isArray(comparisons) && comparisons.some(project =>
            safeURL(project.audio_before_url) && safeURL(project.audio_after_url)
        )) {
            const status = document.getElementById("portfolio-comparison-status");
            if (status) {
                const link = document.createElement("a");
                link.href = "/#mix-comparison";
                link.textContent = "Ouvir comparação";
                status.replaceChildren(link);
            }
        }
    } catch {
        // The honest unavailable state remains visible if the endpoint fails.
    }
}
