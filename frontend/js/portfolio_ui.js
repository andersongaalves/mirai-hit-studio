import { safeURL } from "./utils/security.js";
import { $, clear } from "./utils/dom.js";
import { creditsList } from "./modules/portfolio_credits.js";

const VERTICAL_LABELS = {
    artists: "Artistas",
    creators: "Criadores",
    media_games: "Media & Games",
};

const CASE_TYPE_LABELS = {
    client_case: "Case de cliente",
    demo: "Demo",
    concept_project: "Concept Project",
    study: "Estudo",
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
        : new URL("../img/logo-principal.webp", import.meta.url).href;
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

function createProjectCard(project, segmentLabels = {}) {
    const card = element("article", "portfolio-card");
    const coverFrame = element("div", "portfolio-card__cover-frame");
    const cover = element("img", "portfolio-card__cover");
    cover.src = obterCapaInteligente(project.link_audio, project.link_capa);
    cover.alt = project.titulo ? `Capa de ${project.titulo}` : "Capa do projeto";
    cover.width = 640;
    cover.height = 360;
    cover.loading = "lazy";
    cover.decoding = "async";
    coverFrame.append(cover);

    const body = element("div", "portfolio-card__body");
    const badges = element("div", "portfolio-card__badges");
    badges.append(
        element("span", "portfolio-card__badge portfolio-card__badge--type", CASE_TYPE_LABELS[project.case_type]),
        element("span", "portfolio-card__badge", VERTICAL_LABELS[project.vertical]),
    );
    const title = element("h2", "", project.titulo || "Projeto sem título");
    const credit = element("p", "portfolio-card__credit", project.artista || "Mirai Hit Studio");
    const description = element("p", "portfolio-card__description", project.descricao || "Material publicado no portfólio Mirai.");
    const service = element("div", "portfolio-card__service");
    if (project.categoria) {
        service.append(
            element("span", "portfolio-card__service-label", "Serviço"),
            element("span", "portfolio-card__service-name", project.categoria),
        );
    }
    const segments = element("div", "portfolio-card__segments");
    (Array.isArray(project.segmentos_json) ? project.segmentos_json : []).forEach(segment => {
        segments.append(element(
            "span",
            "portfolio-card__segment",
            segmentLabels[segment] || segment.replaceAll("_", " "),
        ));
    });

    const audioURL = safeURL(project.link_audio);
    let media;
    if (isDirectAudio(audioURL)) {
        media = element("audio", "");
        media.controls = true;
        media.preload = "none";
        media.src = audioURL;
        media.dataset.analyticsListen = "";
        media.dataset.projectId = String(project.id);
        media.setAttribute("aria-label", `Ouvir ${project.titulo}`);
    }

    const listen = element("a", "portfolio-card__listen", "Ouvir projeto");
    listen.href = audioURL;
    listen.target = "_blank";
    listen.rel = "noopener noreferrer";
    listen.dataset.analyticsListen = "";
    listen.dataset.projectId = String(project.id);
    listen.setAttribute("aria-label", `Ouvir ${project.titulo || "projeto"}`);
    listen.append(element("span", "portfolio-card__listen-arrow", "↗"));

    body.append(badges, title, credit);
    // 5.19: who worked on the project (name and role only).
    const credits = creditsList(project.creditos);
    if (credits) body.append(credits);
    if (service.childElementCount) body.append(service);
    if (segments.childElementCount) body.append(segments);
    body.append(description);
    if (media) body.append(media);
    body.append(listen);
    card.append(coverFrame, body);
    return card;
}

export function renderizarProjetos(projects, segmentLabels = {}) {
    const container = $("render-portfolio");
    if (!container) return;
    const published = Array.isArray(projects) ? projects.filter(isPublicProject) : [];
    clear(container);

    if (!published.length) {
        container.append(element("p", "portfolio-empty", "Nenhum trabalho encontrado para esta seleção."));
        return;
    }

    published.forEach(project => container.append(createProjectCard(project, segmentLabels)));
}

export function renderizarErro(message) {
    const container = $("render-portfolio");
    if (!container) return;
    const notice = element("p", "portfolio-empty", message);
    notice.setAttribute("role", "alert");
    container.replaceChildren(notice);
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

function createSelectFilter(label, kind, options, selected, onChange) {
    const wrapper = element("label", "portfolio-filter-select");
    const caption = element("span", "", label);
    const select = element("select", "");
    select.dataset.filterKind = kind;
    options.forEach(option => {
        const item = element("option", "", option.label);
        item.value = option.value;
        item.selected = selected === option.value;
        select.append(item);
    });
    select.addEventListener("change", () => onChange(kind, select.value));
    wrapper.append(caption, select);
    return wrapper;
}

export function renderizarFiltros(projects, filters, onChange, segmentLabels = {}) {
    const container = $("filtros-portfolio");
    if (!container) return;
    const published = Array.isArray(projects) ? projects.filter(isPublicProject) : [];
    const segments = [...new Set(published.flatMap(project => Array.isArray(project.segmentos_json) ? project.segmentos_json : []))].sort();
    clear(container);

    container.append(createFilterGroup("Vertical", "vertical", Object.entries(VERTICAL_LABELS).map(([value, label]) => ({ value, label })), filters.vertical, onChange));
    container.append(createSelectFilter("Segmento", "segment", [
        { value: "", label: "Todos os segmentos" },
        ...segments.map(value => ({ value, label: segmentLabels[value] || value.replaceAll("_", " ") })),
    ], filters.segment, onChange));
    container.append(createSelectFilter("Classificação", "case_type", [
        { value: "", label: "Todos · Demo · Concept Project · Estudo" },
        ...Object.entries(CASE_TYPE_LABELS).map(([value, label]) => ({ value, label })),
    ], filters.case_type, onChange));
}
