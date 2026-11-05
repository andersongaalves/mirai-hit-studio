// Public producer page (/produtores/<endereço>): cover, photo, name, short line, city,
// specialties, links, metrics (portfolio and Mirai projects, beats), bio, and the tabs
// "Portfólio" (projects they were credited on) and "Beats" (only when there are beats).
import { API_URL } from "../config.js";
import { createProjectCard } from "../portfolio_ui.js";
import { safeURL } from "../utils/security.js";
import { beatCard } from "./beat_catalog.js";
import { pausePreviews } from "./beat_preview.js";

const REDES = {
    instagram: "Instagram", youtube: "YouTube", spotify: "Spotify", soundcloud: "SoundCloud",
    tiktok: "TikTok", beatstars: "BeatStars", site: "Site",
};
const ESPECIALIDADES = { beatmaker: "Beatmaker", mixagem: "Mixagem", masterizacao: "Masterização" };
const COR = /^#[0-9a-f]{6}$/i;

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

async function listen(id) {
    const response = await fetch(`${API_URL}/beats/publico/${id}/previa`);
    if (response.status === 429) throw new Error("Muitas prévias em pouco tempo. Aguarde alguns minutos.");
    if (!response.ok) throw new Error("Não foi possível carregar a prévia.");
    return response.blob();
}

function initials(name) {
    return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "M";
}

function header(perfil) {
    const head = el("header", "producer-page__header");
    const cover = el("div", "producer-page__cover");
    const capa = safeURL(perfil.capa_url);
    if (capa) {
        const image = el("img");
        image.src = capa;
        image.alt = "";
        image.decoding = "async";
        cover.append(image);
    }
    const identity = el("div", "producer-page__identity");
    const avatar = el("div", "producer-page__avatar");
    const foto = safeURL(perfil.foto_url);
    if (foto) {
        const image = el("img");
        image.src = foto;
        image.alt = `Foto de ${perfil.nome}`;
        avatar.append(image);
    } else {
        avatar.textContent = initials(perfil.nome);
        avatar.setAttribute("aria-hidden", "true");
    }
    const text = el("div", "producer-page__intro");
    text.append(el("p", "beat-page__eyebrow", "Produtor Mirai"));
    const title = el("h1", "producer-page__name", perfil.nome);
    title.id = "producer-page-name";
    text.append(title);
    if (perfil.headline) text.append(el("p", "producer-page__headline", perfil.headline));
    const meta = el("ul", "producer-page__meta");
    if (perfil.cidade) meta.append(el("li", "producer-page__city", perfil.cidade));
    perfil.especialidades.forEach(item => meta.append(el("li", "producer-page__skill", ESPECIALIDADES[item] || item)));
    if (meta.childElementCount) text.append(meta);
    const links = el("ul", "producer-page__links");
    links.setAttribute("aria-label", "Redes e links");
    Object.entries(perfil.links || {}).forEach(([key, value]) => {
        const url = safeURL(value);
        if (!url || !REDES[key]) return;
        const item = el("li");
        const link = el("a", "", REDES[key]);
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer me";
        item.append(link);
        links.append(item);
    });
    if (links.childElementCount) text.append(links);
    identity.append(avatar, text);
    head.append(cover, identity);
    return head;
}

function metrics(perfil) {
    const list = el("dl", "producer-page__metrics");
    [
        ["Projetos", perfil.metricas.total, "no portfólio e na Mirai"],
        ["Portfólio", perfil.metricas.portfolio, "trabalhos publicados"],
        ["Na Mirai", perfil.metricas.mirai, "projetos entregues"],
        ["Beats", perfil.metricas.beats, "no catálogo"],
    ].forEach(([label, value, hint]) => {
        const item = el("div", "producer-page__metric");
        item.append(el("dt", "", label), el("dd", "", new Intl.NumberFormat("pt-BR").format(value || 0)), el("span", "", hint));
        list.append(item);
    });
    return list;
}

function portfolioPanel(perfil) {
    if (!perfil.portfolio.length) return el("p", "producer-page__empty", "Ainda não há trabalhos publicados no portfólio.");
    const grid = el("div", "portfolio-grid producer-page__portfolio");
    perfil.portfolio.forEach(project => {
        const card = createProjectCard(project);
        if (project.funcoes?.length) {
            const role = el("p", "producer-page__role", `Função: ${project.funcoes.join(" · ")}`);
            card.querySelector(".portfolio-card__credit")?.after(role);
        }
        grid.append(card);
    });
    return grid;
}

function beatsPanel(perfil) {
    const grid = el("div", "producer-list client-beats-list producer-page__beats");
    perfil.beats.forEach(beat => grid.append(beatCard(beat, {
        href: `/beats/${beat.id}`,
        onOpen: () => window.location.assign(`/beats/${beat.id}`),
        loadPreview: () => listen(beat.id),
        lazy: true,
    })));
    return grid;
}

function tabs(perfil) {
    const wrap = el("section", "producer-page__work");
    wrap.setAttribute("aria-label", "Trabalhos");
    const available = [["portfolio", `Portfólio (${perfil.portfolio.length})`, portfolioPanel]];
    if (perfil.beats.length) available.push(["beats", `Beats (${perfil.beats.length})`, beatsPanel]);
    const list = el("div", "producer-page__tabs");
    list.setAttribute("role", "tablist");
    const panels = [];
    const requested = new URLSearchParams(location.search).get("aba");
    const initial = available.some(([key]) => key === requested) ? requested
        : available.some(([key]) => key === perfil.aba_inicial) ? perfil.aba_inicial : "portfolio";
    available.forEach(([key, label, render]) => {
        const tab = el("button", "producer-page__tab", label);
        tab.type = "button";
        tab.id = `producer-tab-${key}`;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-controls", `producer-panel-${key}`);
        const panel = el("div", "producer-page__panel");
        panel.id = `producer-panel-${key}`;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", tab.id);
        panel.append(render(perfil));
        panels.push([key, tab, panel]);
        tab.addEventListener("click", () => select(key, true));
        list.append(tab);
    });
    list.addEventListener("keydown", event => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        const index = panels.findIndex(([, tab]) => tab === document.activeElement);
        if (index < 0) return;
        const next = panels[(index + (event.key === "ArrowRight" ? 1 : panels.length - 1)) % panels.length];
        select(next[0], true);
        next[1].focus();
    });
    function select(key, remember) {
        pausePreviews();
        panels.forEach(([name, tab, panel]) => {
            const active = name === key;
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
            panel.hidden = !active;
        });
        if (remember) {
            const url = new URL(location.href);
            url.searchParams.set("aba", key);
            history.replaceState(history.state, "", url);
        }
    }
    wrap.append(list, ...panels.map(([, , panel]) => panel));
    select(initial, false);
    return wrap;
}

function render(host, perfil) {
    if (COR.test(perfil.cor || "")) host.style.setProperty("--perfil-cor", perfil.cor);
    const page = el("article", "producer-page__content");
    page.setAttribute("aria-labelledby", "producer-page-name");
    page.append(header(perfil), metrics(perfil));
    if (perfil.bio) {
        const about = el("section", "producer-page__bio");
        about.setAttribute("aria-label", "Sobre");
        about.append(el("h2", "", "Sobre"), el("p", "", perfil.bio));
        page.append(about);
    }
    page.append(tabs(perfil));
    host.replaceChildren(page);
    document.title = `${perfil.nome} | Produtor na Mirai Hit Studio`;
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = perfil.headline || `Trabalhos, projetos e beats de ${perfil.nome} na Mirai Hit Studio.`;
}

function failure(host, message) {
    const box = el("div", "producer-page__missing");
    box.append(el("h1", "", "Produtor não encontrado"), el("p", "", message));
    const link = el("a", "btn-outline", "Ver os beats");
    link.href = "/beats";
    box.append(link);
    host.replaceChildren(box);
}

export async function initProducerPage() {
    const host = document.getElementById("produtor-publico");
    const slug = location.pathname.match(/^\/produtores\/([a-z0-9-]{1,60})\/?$/i)?.[1]?.toLowerCase();
    if (!slug) {
        failure(host, "Abra o perfil pelo nome do produtor em um beat ou no portfólio.");
        return;
    }
    try {
        const response = await fetch(`${API_URL}/produtores/${encodeURIComponent(slug)}`);
        if (response.status === 404) {
            failure(host, "Este perfil não existe ou não está disponível.");
            return;
        }
        if (!response.ok) throw new Error();
        const perfil = await response.json();
        // The original address keeps working; the page shows the one the producer chose.
        if (perfil.slug && perfil.slug !== slug) {
            history.replaceState(history.state, "", `/produtores/${perfil.slug}${location.search}`);
        }
        render(host, perfil);
    } catch {
        failure(host, "Não foi possível carregar o perfil agora. Tente de novo em instantes.");
    }
}
