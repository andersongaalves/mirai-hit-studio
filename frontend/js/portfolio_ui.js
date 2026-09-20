import { safeURL } from "./utils/security.js";
import { $, clear } from "./utils/dom.js";

const VERTICAL_LABELS = {
    artists: "Artists",
    creators: "Creators",
    media_games: "Media & Games",
};

const CASE_TYPE_LABELS = {
    client_case: "Case de cliente",
    demo: "Demo",
    concept_project: "Concept Project",
    study: "Study",
};

export function isPublicProject(project) {
    return Boolean(
        project &&
        Number.isInteger(Number(project.id)) &&
        VERTICAL_LABELS[project.vertical] &&
        CASE_TYPE_LABELS[project.case_type] &&
        safeURL(project.link_audio),
    );
}

export function obterCapaInteligente(linkAudio, linkCapa) {
    if (safeURL(linkCapa)) return safeURL(linkCapa);
    const match = safeURL(linkAudio).match(
        /(?:youtube\.com\/(?:[^/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?/\s]{11})/i,
    );
    return match?.[1]
        ? `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`
        : "/img/logo-principal.webp";
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
}

function isDirectAudio(url) {
    try {
        return /\.(mp3|m4a|ogg|wav|flac)$/i.test(new URL(url).pathname);
    } catch {
        return false;
    }
}

function createProjectCard(project) {
    const card = element("article", "portfolio-card");
    const cover = element("img", "portfolio-card__cover");
    cover.src = obterCapaInteligente(project.link_audio, project.link_capa);
    cover.alt = project.titulo ? `Capa de ${project.titulo}` : "Capa do projeto";
    cover.width = 640;
    cover.height = 400;
    cover.loading = "lazy";
    cover.decoding = "async";

    const body = element("div", "portfolio-card__body");
    const badges = element("div", "portfolio-card__badges");
    badges.append(
        element("span", "portfolio-card__badge portfolio-card__badge--type", CASE_TYPE_LABELS[project.case_type]),
        element("span", "portfolio-card__badge", VERTICAL_LABELS[project.vertical]),
    );
    if (project.categoria) badges.append(element("span", "portfolio-card__badge", project.categoria));

    const title = element("h2", "", project.titulo || "Projeto sem título");
    const credit = element("p", "portfolio-card__credit", project.artista || "Mirai Hit Studio");
    const description = element("p", "portfolio-card__description", project.descricao || "Material publicado no portfólio Mirai.");
    const segments = element("div", "portfolio-card__segments");
    (Array.isArray(project.segmentos_json) ? project.segmentos_json : []).forEach(segment => {
        segments.append(element("span", "portfolio-card__segment", segment.replaceAll("_", " ")));
    });

    const audioURL = safeURL(project.link_audio);
    let media;
    if (isDirectAudio(audioURL)) {
        media = element("audio", "");
        media.controls = true;
        media.preload = "metadata";
        media.src = audioURL;
        media.dataset.analyticsListen = "";
        media.dataset.projectId = String(project.id);
        media.setAttribute("aria-label", `Ouvir ${project.titulo}`);
    } else {
        media = element("a", "portfolio-card__listen", "Ouvir projeto");
        media.href = audioURL;
        media.target = "_blank";
        media.rel = "noopener noreferrer";
        media.dataset.analyticsListen = "";
        media.dataset.projectId = String(project.id);
    }

    body.append(badges, title, credit, description);
    if (segments.childElementCount) body.append(segments);
    body.append(media);
    card.append(cover, body);
    return card;
}

export function renderizarProjetos(projects) {
    const container = $("render-portfolio");
    if (!container) return;
    const published = Array.isArray(projects) ? projects.filter(isPublicProject) : [];
    clear(container);

    if (!published.length) {
        container.append(element("p", "portfolio-empty", "Ainda não há materiais classificados e autorizados para esta seleção."));
        return;
    }

    published.forEach(project => container.append(createProjectCard(project)));
}

function createFilterGroup(label, kind, options, selected, onChange) {
    const group = element("div", "portfolio-filter-group");
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", label);
    group.append(element("span", "portfolio-filter-label", label));
    const all = [{ value: "", label: "Todos" }, ...options];
    all.forEach(option => {
        const button = element("button", "filter-btn", option.label);
        button.type = "button";
        button.dataset.filterKind = kind;
        button.dataset.filterValue = option.value;
        button.setAttribute("aria-pressed", String(selected === option.value));
        button.addEventListener("click", () => onChange(kind, option.value));
        group.append(button);
    });
    return group;
}

export function renderizarFiltros(projects, filters, onChange) {
    const container = $("filtros-portfolio");
    if (!container) return;
    const published = Array.isArray(projects) ? projects.filter(isPublicProject) : [];
    const verticals = [...new Set(published.map(project => project.vertical))];
    const categories = [...new Set(published.map(project => project.categoria).filter(Boolean))].sort();
    clear(container);

    if (verticals.length > 1) {
        container.append(createFilterGroup("Vertical", "vertical", verticals.map(value => ({ value, label: VERTICAL_LABELS[value] })), filters.vertical, onChange));
    }
    if (categories.length > 1) {
        container.append(createFilterGroup("Serviço", "categoria", categories.map(value => ({ value, label: value })), filters.categoria, onChange));
    }
    container.classList.toggle("hidden", !container.childElementCount);
}
