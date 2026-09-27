const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const frontend = path.resolve(__dirname, "..");
const pages = [
    { file: "index.html", title: "Produção musical e áudio | Mirai Hit Studio", h1: "Produção musical e áudio com identidade para artistas, criadores e projetos digitais", terms: ["artistas", "criadores", "projetos digitais"] },
    { file: "artists.html", title: "Produção musical, mixagem e masterização para artistas | Mirai Hit Studio", h1: "Produção musical para artistas", terms: ["instrumental", "mixagem", "masterização"] },
    { file: "creators.html", title: "Identidade sonora e música para criadores | Mirai Hit Studio", h1: "Música e identidade sonora para criadores", terms: ["trilhas", "intros", "stingers"] },
    { file: "media-games.html", title: "Trilha sonora e sound design para games | Mirai Hit Studio", h1: "Trilha sonora e design sonoro para mídia e games", terms: ["trilha sonora", "sound design", "games"] },
    { file: "portfolio.html", title: "Portfólio de produção musical e áudio | Mirai Hit Studio", h1: "Portfólio de produção musical e áudio", terms: ["Demo", "Concept Project", "Study"] },
];

const pageHtml = new Map(pages.map((page) => [page.file, fs.readFileSync(path.join(frontend, page.file), "utf8")]));
const descriptions = new Set();

for (const page of pages) {
    const html = pageHtml.get(page.file);
    const title = html.match(/<title>([^<]+)<\/title>/i)?.[1];
    const description = html.match(/<meta name="description" content="([^"]+)"/i)?.[1];
    const h1s = [...html.matchAll(/<h1(?:\s[^>]*)?>([^<]+)<\/h1>/gi)].map((match) => match[1].trim());

    assert.equal(title, page.title, `${page.file} must have its canonical content title`);
    assert.ok(description && description.length >= 70, `${page.file} must have a useful description`);
    assert.equal(h1s.length, 1, `${page.file} must have exactly one H1`);
    assert.equal(h1s[0], page.h1, `${page.file} must have its intended H1`);
    assert.ok(!descriptions.has(description), `${page.file} must not reuse another page description`);
    descriptions.add(description);

    for (const term of page.terms) {
        assert.match(html, new RegExp(term, "i"), `${page.file} must retain the term ${term}`);
    }

    for (const href of html.matchAll(/href="([^"]+)"/gi)) {
        assert.ok(!href[1].includes(".html"), `${page.file} must not expose .html internal URLs`);
    }
}

const portfolio = pageHtml.get("portfolio.html");
for (const route of ["/artists", "/creators", "/media-games"]) {
    assert.match(portfolio, new RegExp(`href="${route}"`), `Portfolio must contextualize ${route}`);
}

console.log("PASS: H.2 content metadata, intent, transparent portfolio labels and contextual links are present.");
