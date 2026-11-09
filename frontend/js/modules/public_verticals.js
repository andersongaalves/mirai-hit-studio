// Public areas (Artistas, Criadores, Media & Games) with no published portfolio work are
// hidden from the menu, the home page and the portfolio intro. The last answer is kept in
// the browser so the hidden areas do not flash on the next page; when the API cannot be
// reached the site keeps every area visible.
import * as API from "../api.js";

const STORAGE_KEY = "mirai.public_verticals.v1";
export const VERTICAL_PATHS = { artists: "/artists", creators: "/creators", media_games: "/media-games" };
const TEXT_LABELS = { artists: "artistas", creators: "criadores", media_games: "mídia e games" };
const ALL = Object.keys(VERTICAL_PATHS);

function routeOf(link) {
    try {
        const path = new URL(link.getAttribute("href"), window.location.href).pathname.replace(/\/$/, "");
        return path.split("/").pop().replace(/\.html$/i, "");
    } catch {
        return "";
    }
}

function verticalOf(link) {
    const route = routeOf(link);
    return ALL.find(vertical => VERTICAL_PATHS[vertical] === `/${route}`) || null;
}

function readCache() {
    try {
        const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
        return Array.isArray(value) ? value.filter(item => ALL.includes(item)) : null;
    } catch {
        return null;
    }
}

function writeCache(verticais) {
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(verticais));
    } catch {
        // Storage may be blocked; the next page asks the API again.
    }
}

function renderIntro(paragraph, visible) {
    const parts = visible.map(vertical => {
        const link = document.createElement("a");
        link.href = VERTICAL_PATHS[vertical];
        link.textContent = TEXT_LABELS[vertical];
        return link;
    });
    const nodes = [document.createTextNode(paragraph.dataset.introPrefix || "")];
    parts.forEach((link, index) => {
        if (index > 0) nodes.push(document.createTextNode(index === parts.length - 1 ? " e " : ", "));
        nodes.push(link);
    });
    nodes.push(document.createTextNode("."));
    paragraph.replaceChildren(...nodes);
}

export function applyPublicVerticals(verticais) {
    const visible = ALL.filter(vertical => verticais.includes(vertical));
    // Menu, footer and home cards.
    document.querySelectorAll(".site-nav__links a, .site-footer a, a.vertical-card").forEach(link => {
        const vertical = verticalOf(link);
        if (vertical) link.hidden = !visible.includes(vertical);
    });
    // Home cards keep a continuous numbering (01, 02...).
    let number = 0;
    document.querySelectorAll("a.vertical-card").forEach(card => {
        if (card.hidden) return;
        number += 1;
        const label = card.querySelector(".home-service__number");
        if (label) label.textContent = String(number).padStart(2, "0");
    });
    document.querySelectorAll("[data-vertical-intro]").forEach(paragraph => {
        if (visible.length) {
            paragraph.hidden = false;
            renderIntro(paragraph, visible);
        }
    });
}

export async function initPublicVerticals() {
    const cached = readCache();
    if (cached) applyPublicVerticals(cached);
    try {
        const data = await API.getAPI("projetos/public/verticais");
        if (!Array.isArray(data?.verticais)) return;
        const verticais = data.verticais.filter(item => ALL.includes(item));
        writeCache(verticais);
        applyPublicVerticals(verticais);
    } catch {
        // Without an answer, a cached choice stays; otherwise every area stays visible.
    }
}
