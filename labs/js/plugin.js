// Plugin page (/plugins/<address>, /pt/plugins/<address>): details, price and the purchase on the studio site.
import { purchaseUrl } from "./config.js";
import { LANG, SITE_URL, href, localized, t } from "./i18n.js";
import { READY, coverNode, el, getJSON, money, systemsText } from "./labs.js";

const root = document.getElementById("product");
const DEFAULT_TITLE = document.title;

function slugFromPath() {
    const match = window.location.pathname.match(/^(?:\/pt)?\/plugins\/([a-z0-9-]{1,60})\/?$/);
    if (match) return match[1];
    return new URLSearchParams(window.location.search).get("plugin");
}

function youtubeId(url) {
    try {
        const parsed = new URL(url);
        if (parsed.hostname === "youtu.be") return parsed.pathname.slice(1, 12);
        if (/(^|\.)youtube\.com$/.test(parsed.hostname)) {
            if (parsed.pathname === "/watch") return parsed.searchParams.get("v");
            const match = parsed.pathname.match(/^\/(?:embed|shorts)\/([\w-]{11})/);
            return match?.[1] || null;
        }
    } catch { /* not a URL */ }
    return null;
}

function setMeta(plugin) {
    document.title = `${plugin.nome} | Mirai Hit Labs`;
    const tagline = localized(plugin, "tagline");
    const description = document.querySelector('meta[name="description"]');
    if (description && tagline) description.setAttribute("content", `${plugin.nome}: ${tagline}`);
    const path = `/plugins/${plugin.slug}`;
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.href = `${SITE_URL}${LANG === "pt" ? "/pt" : ""}${path}`;
    const alternates = { en: `${SITE_URL}${path}`, "pt-BR": `${SITE_URL}/pt${path}`, "x-default": `${SITE_URL}${path}` };
    document.querySelectorAll('link[rel="alternate"][hreflang]').forEach(link => {
        const url = alternates[link.getAttribute("hreflang")];
        if (url) link.href = url;
    });
}

function fact(label, value) {
    const row = el("div");
    row.append(el("dt", "", label), el("dd", "", value));
    return row;
}

function buyBox(plugin) {
    const box = el("section", "buy");
    box.setAttribute("aria-label", t("buyLabel"));
    const price = el("div", "buy__price");
    if (plugin.gratuito) {
        price.append(el("strong", "", t("free")));
    } else {
        if (plugin.em_promocao) price.append(el("s", "", money(plugin.preco)));
        price.append(el("strong", "", money(plugin.preco_vigente)));
        price.append(el("span", "", t("oneTime")));
    }
    const available = (plugin.sistemas || []).length > 0;
    const action = el("a", "btn", plugin.gratuito ? t("getFree") : t("buy"));
    action.href = purchaseUrl(plugin.slug);
    if (!available) {
        action.setAttribute("aria-disabled", "true");
        action.textContent = t("soon");
        action.removeAttribute("href");
    }
    const note = el("p", "buy__note", plugin.gratuito ? t("buyNoteFree") : t("buyNotePaid"));
    box.append(price, action, note);
    return box;
}

function render(plugin) {
    setMeta(plugin);
    const crumbs = el("ol", "crumbs");
    crumbs.setAttribute("aria-label", t("youAreHere"));
    const home = el("li");
    const homeLink = el("a", "", t("plugins"));
    homeLink.href = href("/#plugins");
    home.append(homeLink);
    const current = el("li", "", plugin.nome);
    current.setAttribute("aria-current", "page");
    crumbs.append(home, current);

    const product = el("div", "product");
    const cover = coverNode(plugin, "product__cover");
    if (plugin.capa_url) cover.querySelector("img").loading = "eager";
    const info = el("div", "product__info");
    const head = el("div", "product__head");
    const category = localized(plugin, "categoria");
    if (category) head.append(el("p", "eyebrow", category));
    head.append(el("h1", "product__title", plugin.nome));
    const tagline = localized(plugin, "tagline");
    if (tagline) head.append(el("p", "product__tagline", tagline));
    info.append(head, buyBox(plugin));

    const facts = el("dl", "facts");
    facts.append(
        fact(t("formats"), (plugin.formatos || []).join(" · ") || "—"),
        fact(t("systems"), systemsText(plugin)),
        fact(t("version"), plugin.versao || "—"),
        fact(t("license"), t("licenseValue")),
    );
    info.append(facts);

    const description = localized(plugin, "descricao");
    if (description) {
        const about = el("section", "prose");
        about.append(el("h2", "", t("about")), el("p", "", description));
        info.append(about);
    }
    const features = localized(plugin, "recursos") || [];
    if (features.length) {
        const section = el("section", "prose");
        const list = el("ul", "features");
        features.forEach(item => list.append(el("li", "", item)));
        section.append(el("h2", "", t("features")), list);
        info.append(section);
    }
    const videoId = plugin.video_url ? youtubeId(plugin.video_url) : null;
    if (videoId) {
        const video = el("section", "prose");
        const frame = el("div", "video");
        const iframe = el("iframe");
        iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
        iframe.title = t("videoTitle", { name: plugin.nome });
        iframe.loading = "lazy";
        iframe.allow = "accelerometer; encrypted-media; gyroscope; picture-in-picture";
        iframe.referrerPolicy = "strict-origin-when-cross-origin";
        iframe.allowFullscreen = true;
        frame.append(iframe);
        video.append(el("h2", "", t("inAction")), frame);
        info.append(video);
    } else if (plugin.video_url) {
        const link = el("a", "btn btn--ghost", t("watchVideo"));
        link.href = plugin.video_url;
        link.target = "_blank";
        link.rel = "noopener";
        info.append(link);
    }
    const requirements = localized(plugin, "requisitos");
    if (requirements) {
        const section = el("section", "prose");
        section.append(el("h2", "", t("requirements")), el("p", "", requirements));
        info.append(section);
    }
    product.append(cover, info);
    root.replaceChildren(crumbs, product);
}

function missing(message) {
    document.title = t("missingPage");
    const box = el("div", "missing");
    const icon = el("img");
    icon.src = "/img/icon-sinal.svg";
    icon.alt = "";
    const back = el("a", "btn", t("allPlugins"));
    back.href = href("/#plugins");
    box.append(icon, el("h1", "section-title", t("missingTitle")), el("p", "lead", message), back);
    root.replaceChildren(box);
}

async function load() {
    const slug = slugFromPath();
    if (!slug) {
        missing(t("missingAddress"));
        return;
    }
    root.setAttribute("aria-busy", "true");
    try {
        render(await getJSON(`/labs/plugins/${encodeURIComponent(slug)}`));
    } catch (error) {
        document.title = DEFAULT_TITLE;
        missing(error.status === 404 ? t("missingGone") : error.message);
    } finally {
        root.removeAttribute("aria-busy");
    }
}

if (READY) load();
