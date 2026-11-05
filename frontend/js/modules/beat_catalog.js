// Beat catalog: the card shown in the grid (cover, producer and preview) and the beat
// page it opens (details, licenses with prices and differences, and the tag notice).
// Shared by the client catalog (with purchase) and the producer catalog (view only).
import { beatPreview } from "./beat_preview.js";
import { splitList } from "./beat_filters.js";

const money = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function cover(beat, className) {
    if (beat.capa_url) {
        const image = el("img", `beat-cover ${className}`);
        image.src = beat.capa_url;
        image.alt = `Capa de ${beat.titulo}`;
        image.loading = "lazy";
        image.decoding = "async";
        return image;
    }
    const placeholder = el("div", `beat-cover beat-cover--placeholder ${className}`);
    placeholder.setAttribute("aria-hidden", "true");
    return placeholder;
}

/** "prod. Name", linking to the producer's public page when it has one. */
function producerLine(beat, className) {
    const line = el("p", className);
    const slug = typeof beat.produtor_perfil === "string" && /^[a-z0-9-]{1,60}$/.test(beat.produtor_perfil) ? beat.produtor_perfil : "";
    if (!slug) {
        line.textContent = `prod. ${beat.produtor}`;
        return line;
    }
    const link = el("a", "beat-producer-link", beat.produtor);
    link.href = `/produtores/${slug}`;
    link.title = `Ver o perfil de ${beat.produtor}`;
    line.append("prod. ", link);
    return line;
}

const opensHere = event => event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

/**
 * The catalog card: a large cover, the title, who produced it and the preview player.
 * The whole card opens the beat page (the title link covers it); the player keeps its
 * own controls above that link.
 */
export function beatCard(beat, { href, onOpen, loadPreview, lazy = false }) {
    const card = el("article", "producer-card beat-card beat-tile");
    card.dataset.beatId = String(beat.id);
    // Cover with the tempo and the key over it, like a record sleeve.
    const media = el("div", "beat-tile__media");
    media.append(cover(beat, "beat-tile__cover"));
    const specs = [
        beat.bpm ? ["beat-tile__spec", `${beat.bpm} BPM`, `${beat.bpm} batidas por minuto`] : null,
        beat.tonalidade?.trim() ? ["beat-tile__spec beat-tile__spec--key", beat.tonalidade.trim(), `Tom ${beat.tonalidade.trim()}`] : null,
    ].filter(Boolean);
    if (specs.length) {
        const list = el("ul", "beat-tile__specs");
        list.setAttribute("aria-label", "BPM e tom");
        specs.forEach(([className, text, label]) => {
            const item = el("li", className, text);
            item.setAttribute("aria-label", label);
            list.append(item);
        });
        media.append(list);
    }
    if (beat.vendido) media.append(el("span", "beat-card__sold beat-tile__sold", "Vendido"));

    const body = el("div", "beat-tile__body");
    const title = el("h3", "beat-tile__title");
    const link = el("a", "beat-tile__link", beat.titulo);
    link.href = href;
    link.addEventListener("click", event => {
        if (!opensHere(event)) return;
        event.preventDefault();
        onOpen();
    });
    title.append(link);
    body.append(title, producerLine(beat, "beat-tile__producer"));
    // Genres first, then moods (told apart by style); a long list ends in "+N".
    const tags = [
        ...splitList(beat.generos).map(text => ["genre", text]),
        ...splitList(beat.moods).map(text => ["mood", text]),
    ];
    if (tags.length) {
        const list = el("ul", "beat-card__tags beat-tile__tags");
        list.setAttribute("aria-label", "Gêneros e moods");
        const shown = tags.length > 4 ? tags.slice(0, 3) : tags;
        shown.forEach(([kind, text]) => list.append(el("li", `beat-tile__tag beat-tile__tag--${kind}`, text)));
        if (shown.length < tags.length) {
            const more = el("li", "beat-tile__tag beat-tile__tag--more", `+${tags.length - shown.length}`);
            more.title = tags.slice(shown.length).map(([, text]) => text).join(", ");
            list.append(more);
        }
        body.append(list);
    }
    if (beat.vendido) {
        // Sold with exclusivity: shown as sold, without preview.
        card.classList.add("beat-card--sold");
    } else {
        body.append(beatPreview(loadPreview, { lazy }));
    }
    card.append(media, body);
    return card;
}

// Plain-language summary of each license; the limits come from the contract terms.
const RESUMOS = {
    lease_mp3: "O arquivo MP3 do beat, pronto para gravar e lançar a sua música.",
    lease_wav: "O arquivo WAV, sem compressão: a melhor qualidade para mixar e masterizar.",
    multitrack: "Cada instrumento em uma faixa separada (stems), para mixar a música do seu jeito. Inclui o MP3 e o WAV.",
    exclusivo: "O beat passa a ser só seu: sai do catálogo e não é licenciado a mais ninguém. Todos os formatos, sem limites de uso.",
};
const ROTULOS = { lease_mp3: "Lease MP3", lease_wav: "Lease WAV", multitrack: "Lease Multitrack (stems)", exclusivo: "Exclusiva" };
const FORMATOS = { lease_mp3: "MP3", lease_wav: "WAV", multitrack: "MP3, WAV e multitrack (stems)", exclusivo: "MP3, WAV e multitrack (stems)" };

/** The licenses this beat is offered with, in comparison order, with their prices. */
export function beatLicenses(beat, terms = []) {
    const byType = new Map((terms || []).map(item => [item.tipo, item]));
    return [
        // Older beats were published with a single MP3 lease ("lease"): same terms.
        [beat.formato_novo ? "lease_mp3" : "lease", "lease_mp3", beat.preco_lease],
        ["lease_wav", "lease_wav", beat.preco_wav],
        ["multitrack", "multitrack", beat.preco_multitrack],
        ["exclusivo", "exclusivo", beat.preco_exclusivo],
    ].filter(([, , price]) => price).map(([kind, key, price]) => {
        const term = byType.get(key) || {};
        return {
            kind,
            price,
            label: term.rotulo || ROTULOS[key],
            formats: term.formatos || FORMATOS[key],
            exclusive: key === "exclusivo",
            limits: term.limites || null,
            summary: RESUMOS[key],
        };
    });
}

function rows(license) {
    if (license.exclusive) {
        return [
            ["Arquivos", license.formats],
            ["Streams", "Sem limite"],
            ["Vendas e downloads", "Sem limite"],
            ["Videoclipes", "Sem limite, monetizados"],
            ["Rádio e TV", "Liberado"],
            ["Filmes, jogos e publicidade", "Liberado"],
            ["Shows ao vivo", "Sem limite"],
            ["O beat no catálogo", "Sai do catálogo: ninguém mais pode comprar"],
        ];
    }
    const limits = license.limits;
    return [
        ["Arquivos", license.formats],
        ...(limits ? [
            ["Streams", `Até ${limits.streams} reproduções`],
            ["Vendas e downloads", `Até ${limits.vendas} unidades`],
            ["Videoclipes", `${limits.videos} videoclipe, monetizado até ${limits.visualizacoes} visualizações`],
            ["Rádio e TV", limits.radio.charAt(0).toUpperCase() + limits.radio.slice(1)],
        ] : []),
        ["Filmes, jogos e publicidade", "Com autorização por escrito"],
        ["Shows ao vivo", "Sem limite"],
        ["O beat no catálogo", "Continua disponível para outras pessoas"],
    ];
}

function licenseCard(license, { onBuy, buyLink }) {
    const card = el("article", `beat-license${license.exclusive ? " beat-license--exclusive" : ""}`);
    const head = el("header", "beat-license__head");
    head.append(
        el("span", "beat-license__kind", license.exclusive ? "Exclusiva" : "Não exclusiva"),
        el("h3", "beat-license__name", license.label),
        el("p", "beat-license__price", money(license.price)),
    );
    const list = el("dl", "beat-license__terms");
    rows(license).forEach(([term, value]) => {
        const row = el("div");
        row.append(el("dt", "", term), el("dd", "", value));
        list.append(row);
    });
    card.append(head, el("p", "beat-license__summary", license.summary), list);
    card.dataset.license = license.kind;
    if (onBuy) {
        const button = el("button", "btn-cta beat-license__buy", `Comprar ${license.label}`);
        button.type = "button";
        button.addEventListener("click", () => onBuy(license.kind, button));
        card.append(button);
    } else if (buyLink) {
        const link = el("a", "btn-cta beat-license__buy", `Comprar ${license.label}`);
        link.href = buyLink(license.kind);
        card.append(link);
    }
    return card;
}

/**
 * The beat page. `onBuy(kind, button)` buys in place (the client portal); `buyLink(kind)`
 * links to where the purchase happens (the public page, through sign-in); with neither
 * the licenses are shown for reference. `selected` highlights a license on arrival.
 */
export function beatPage(beat, { terms, termsError = false, loadPreview, onBuy = null, buyLink = null, onBack,
    viewOnlyNote = "", purchaseNote = null, selected = null, lazy = false }) {
    const page = el("article", "beat-page");
    page.setAttribute("aria-labelledby", "beat-page-title");
    const back = el("button", "btn-outline beat-page__back", "Voltar ao catálogo");
    back.type = "button";
    back.addEventListener("click", onBack);

    const hero = el("div", "beat-page__hero");
    const info = el("div", "beat-page__info");
    const heading = el("h1", "beat-page__title", beat.titulo);
    heading.id = "beat-page-title";
    info.append(el("p", "beat-page__eyebrow", "Beat"), heading, producerLine(beat, "beat-page__producer"));
    const facts = el("dl", "beat-page__facts");
    [["BPM", beat.bpm], ["Tom", beat.tonalidade]].filter(([, value]) => value).forEach(([term, value]) => {
        const row = el("div");
        row.append(el("dt", "", term), el("dd", "", String(value)));
        facts.append(row);
    });
    if (facts.childElementCount) info.append(facts);
    const tags = [
        ...splitList(beat.generos).map(text => ["genre", text]),
        ...splitList(beat.moods).map(text => ["mood", text]),
    ];
    if (tags.length) {
        const list = el("ul", "beat-card__tags");
        list.setAttribute("aria-label", "Gêneros e moods");
        tags.forEach(([kind, text]) => list.append(el("li", `beat-tile__tag beat-tile__tag--${kind}`, text)));
        info.append(list);
    }
    if (beat.descricao?.trim()) info.append(el("p", "beat-page__description", beat.descricao.trim()));
    if (beat.vendido) info.append(el("span", "beat-card__sold", "Vendido"));
    else info.append(beatPreview(loadPreview, { lazy }));
    hero.append(cover(beat, "beat-page__cover"), info);
    page.append(back, hero);

    if (beat.vendido) {
        page.append(el("p", "beat-page__sold-note", "Este beat foi vendido com licença exclusiva e não está mais disponível para compra."));
        return page;
    }

    const notice = el("aside", "beat-page__notice");
    notice.setAttribute("role", "note");
    notice.append(
        el("strong", "", "A tag sai depois da compra"),
        el("p", "", "A prévia toca com a tag de voz da Mirai para proteger o beat. Os arquivos liberados depois da compra vêm limpos, sem a tag."),
    );

    const section = el("section", "beat-page__licenses");
    section.setAttribute("aria-labelledby", "beat-licenses-title");
    const title = el("h2", "", "Licenças");
    title.id = "beat-licenses-title";
    section.append(title, el("p", "beat-page__lead", "Escolha como você vai usar o beat. A diferença entre as licenças está nos arquivos que você recebe e nos limites de uso da música."));
    const licenses = beatLicenses(beat, terms);
    if (termsError) section.append(el("p", "beat-page__warning", "Os limites de uso não puderam ser carregados agora; eles constam no contrato de cada licença."));
    if (!licenses.length) {
        section.append(el("p", "beat-page__lead", "Nenhuma licença está disponível para este beat no momento."));
    } else {
        const grid = el("div", "beat-licenses");
        licenses.forEach(license => {
            const card = licenseCard(license, { onBuy, buyLink });
            if (license.kind === selected) card.classList.add("is-selected");
            grid.append(card);
        });
        if (purchaseNote) section.append(purchaseNote);
        section.append(grid);
    }
    const common = el("ul", "beat-page__common");
    common.setAttribute("aria-label", "Valem para todas as licenças");
    [
        "O contrato da licença, em PDF, é liberado junto com os arquivos depois do pagamento.",
        "Licenças não exclusivas valem para uma música; cada nova música pede uma nova licença.",
        `O crédito "prod. ${beat.produtor}" deve aparecer nas publicações da música.`,
        "O produtor continua sendo o autor do beat; a licença não transfere os direitos autorais.",
    ].forEach(text => common.append(el("li", "", text)));
    section.append(el("h3", "beat-page__common-title", "Para todas as licenças"), common);
    if (!onBuy && !buyLink && viewOnlyNote) section.append(el("p", "beat-page__lead", viewOnlyNote));
    page.append(notice, section);
    return page;
}
