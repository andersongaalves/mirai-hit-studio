// Plugin page (/plugins/<endereço>): details, price and the purchase on the studio site.
import { purchaseUrl } from "./config.js";
import { coverNode, el, getJSON, money, setYear, systemsText } from "./labs.js";

const root = document.getElementById("product");
const DEFAULT_TITLE = document.title;

function slugFromPath() {
    const match = window.location.pathname.match(/^\/plugins\/([a-z0-9-]{1,60})\/?$/);
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
    const description = document.querySelector('meta[name="description"]');
    if (description && plugin.tagline) description.setAttribute("content", `${plugin.nome}: ${plugin.tagline}`);
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.href = `https://labs.miraihitstudio.com.br/plugins/${plugin.slug}`;
}

function fact(label, value) {
    const row = el("div");
    row.append(el("dt", "", label), el("dd", "", value));
    return row;
}

function buyBox(plugin) {
    const box = el("section", "buy");
    box.setAttribute("aria-label", "Comprar");
    const price = el("div", "buy__price");
    if (plugin.gratuito) {
        price.append(el("strong", "", "Grátis"));
    } else {
        if (plugin.em_promocao) price.append(el("s", "", money(plugin.preco)));
        price.append(el("strong", "", money(plugin.preco_vigente)));
        price.append(el("span", "", "pagamento único"));
    }
    const available = (plugin.sistemas || []).length > 0;
    const action = el("a", "btn", plugin.gratuito ? "Baixar grátis" : "Comprar");
    action.href = purchaseUrl(plugin.slug);
    if (!available) {
        action.setAttribute("aria-disabled", "true");
        action.textContent = "Em breve";
        action.removeAttribute("href");
    }
    const note = el("p", "buy__note", plugin.gratuito
        ? "Entre na sua conta da Mirai Hit Studio (ou crie uma, é grátis) e o plugin vai para Meus plugins, com a chave e os instaladores."
        : "Você entra na sua conta da Mirai Hit Studio (ou cria uma, é grátis) e paga por Pix ou cartão. A chave e os instaladores ficam em Meus plugins.");
    box.append(price, action, note);
    return box;
}

function render(plugin) {
    setMeta(plugin);
    const crumbs = el("ol", "crumbs");
    crumbs.setAttribute("aria-label", "Você está em");
    const home = el("li");
    const homeLink = el("a", "", "Plugins");
    homeLink.href = "/#plugins";
    home.append(homeLink);
    const current = el("li", "", plugin.nome);
    current.setAttribute("aria-current", "page");
    crumbs.append(home, current);

    const product = el("div", "product");
    const cover = coverNode(plugin, "product__cover");
    if (plugin.capa_url) cover.querySelector("img").loading = "eager";
    const info = el("div", "product__info");
    const head = el("div", "product__head");
    if (plugin.categoria) head.append(el("p", "eyebrow", plugin.categoria));
    head.append(el("h1", "product__title", plugin.nome));
    if (plugin.tagline) head.append(el("p", "product__tagline", plugin.tagline));
    info.append(head, buyBox(plugin));

    const facts = el("dl", "facts");
    facts.append(
        fact("Formatos", (plugin.formatos || []).join(" · ") || "—"),
        fact("Sistemas", systemsText(plugin)),
        fact("Versão", plugin.versao || "—"),
        fact("Licença", "Pessoal, com chave de ativação"),
    );
    info.append(facts);

    if (plugin.descricao) {
        const about = el("section", "prose");
        about.append(el("h2", "", "Sobre"), el("p", "", plugin.descricao));
        info.append(about);
    }
    if (plugin.recursos?.length) {
        const features = el("section", "prose");
        const list = el("ul", "features");
        plugin.recursos.forEach(item => list.append(el("li", "", item)));
        features.append(el("h2", "", "Recursos"), list);
        info.append(features);
    }
    const videoId = plugin.video_url ? youtubeId(plugin.video_url) : null;
    if (videoId) {
        const video = el("section", "prose");
        const frame = el("div", "video");
        const iframe = el("iframe");
        iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}`;
        iframe.title = `Vídeo do ${plugin.nome}`;
        iframe.loading = "lazy";
        iframe.allow = "accelerometer; encrypted-media; gyroscope; picture-in-picture";
        iframe.referrerPolicy = "strict-origin-when-cross-origin";
        iframe.allowFullscreen = true;
        frame.append(iframe);
        video.append(el("h2", "", "Em ação"), frame);
        info.append(video);
    } else if (plugin.video_url) {
        const link = el("a", "btn btn--ghost", "Ver vídeo");
        link.href = plugin.video_url;
        link.target = "_blank";
        link.rel = "noopener";
        info.append(link);
    }
    if (plugin.requisitos) {
        const requirements = el("section", "prose");
        requirements.append(el("h2", "", "Requisitos"), el("p", "", plugin.requisitos));
        info.append(requirements);
    }
    product.append(cover, info);
    root.replaceChildren(crumbs, product);
}

function missing(message) {
    document.title = `Plugin não encontrado | Mirai Hit Labs`;
    const box = el("div", "missing");
    const icon = el("img");
    icon.src = "/img/icon-sinal.svg";
    icon.alt = "";
    const back = el("a", "btn", "Ver todos os plugins");
    back.href = "/#plugins";
    box.append(icon, el("h1", "section-title", "Plugin não encontrado"), el("p", "lead", message), back);
    root.replaceChildren(box);
}

async function load() {
    const slug = slugFromPath();
    if (!slug) {
        missing("Este endereço não corresponde a nenhum plugin.");
        return;
    }
    root.setAttribute("aria-busy", "true");
    try {
        render(await getJSON(`/labs/plugins/${encodeURIComponent(slug)}`));
    } catch (error) {
        document.title = DEFAULT_TITLE;
        missing(error.status === 404 ? "Ele pode ter saído do catálogo ou o endereço mudou." : error.message);
    } finally {
        root.removeAttribute("aria-busy");
    }
}

setYear();
load();
