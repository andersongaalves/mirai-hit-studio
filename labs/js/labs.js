// Shared helpers for the Mirai Hit Labs store: catalog requests and the plugin card.
import { API_URL, INTERNATIONAL_PAYMENT } from "./config.js";
import { LANG, LOCALE, href, initLanguage, localized, t } from "./i18n.js";

// false when the page is moving to the visitor's saved language (nothing else should start)
export const READY = initLanguage();

export function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "" && text !== null && text !== undefined) node.textContent = text;
    return node;
}

export async function getJSON(path) {
    let response;
    try {
        response = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" } });
    } catch {
        const error = new Error(t("offline"));
        error.status = 0;
        throw error;
    }
    if (!response.ok) {
        const error = new Error(response.status === 404 ? t("notFound") : t("unavailable"));
        error.status = response.status;
        throw error;
    }
    return response.json();
}

// Portuguese store: reais (Mirai checkout). English store: US dollars with Stripe when the international
// payment is on (same number: R$ 149,90 -> US$ 149.90); while it is off, reais too (Mercado Pago).
export const CURRENCY = LANG === "en" && INTERNATIONAL_PAYMENT ? "USD" : "BRL";
const FORMAT = new Intl.NumberFormat(LOCALE, { style: "currency", currency: CURRENCY });
export const money = value => FORMAT.format(Number(value || 0));

export function priceNode(plugin, className = "price") {
    const node = el("span", className);
    if (plugin.gratuito) {
        node.textContent = t("free");
        return node;
    }
    if (plugin.em_promocao) node.append(el("s", "", money(plugin.preco)));
    node.append(document.createTextNode(money(plugin.preco_vigente)));
    return node;
}

export function formatsNode(formats) {
    const list = el("ul", "formats");
    list.setAttribute("aria-label", t("formats"));
    (formats || []).forEach(format => list.append(el("li", "", format)));
    return list;
}

export function systemsText(plugin) {
    const names = (plugin.sistemas || []).map(item => item.nome);
    return names.length ? names.join(t("and")) : t("soon");
}

export function coverNode(plugin, className) {
    const box = el("div", className);
    if (plugin.capa_url) {
        const image = el("img");
        image.src = plugin.capa_url;
        image.alt = t("coverAlt", { name: plugin.nome });
        image.loading = "lazy";
        image.decoding = "async";
        image.width = 600;
        image.height = 600;
        box.append(image);
    } else {
        const placeholder = el("div", "plugin-card__placeholder");
        const mark = el("img");
        mark.src = "/img/icon-monograma.svg";
        mark.alt = "";
        placeholder.append(mark);
        box.append(placeholder);
    }
    return box;
}

export function pluginCard(plugin) {
    const card = el("article", "plugin-card");
    const cover = coverNode(plugin, "plugin-card__cover");
    if (plugin.gratuito) cover.append(el("span", "plugin-card__badge plugin-card__badge--dark", t("free")));
    else if (plugin.em_promocao) cover.append(el("span", "plugin-card__badge", t("sale")));
    else if (plugin.destaque) cover.append(el("span", "plugin-card__badge", t("featured")));
    const body = el("div", "plugin-card__body");
    const category = localized(plugin, "categoria");
    if (category) body.append(el("p", "plugin-card__meta", category));
    const title = el("h3", "plugin-card__title");
    const link = el("a", "plugin-card__link", plugin.nome);
    link.href = href(`/plugins/${encodeURIComponent(plugin.slug)}`);
    title.append(link);
    body.append(title);
    const tagline = localized(plugin, "tagline");
    if (tagline) body.append(el("p", "plugin-card__tagline", tagline));
    const foot = el("div", "plugin-card__foot");
    foot.append(priceNode(plugin), formatsNode(plugin.formatos));
    body.append(foot);
    card.append(cover, body);
    return card;
}

export function setYear() {
    document.querySelectorAll("[data-year]").forEach(node => { node.textContent = String(new Date().getFullYear()); });
}

setYear();

// Announcement banner set in the admin panel (Loja). Store paths get the page's language.
async function showBanner() {
    if (document.querySelector(".announcement")) return;
    let content;
    try { content = await getJSON("/labs/conteudo"); } catch { return; }
    const banner = content?.banner;
    const text = (LANG === "pt" ? banner?.texto : banner?.texto_en) || banner?.texto || banner?.texto_en;
    if (!text) return;
    const bar = el("aside", "announcement");
    bar.setAttribute("aria-label", t("announcement"));
    const inner = el(banner.link ? "a" : "p", "announcement__text", text);
    if (banner.link) inner.href = banner.link.startsWith("/") ? href(banner.link) : banner.link;
    bar.append(inner);
    document.body.prepend(bar);
}

if (READY) showBanner();
