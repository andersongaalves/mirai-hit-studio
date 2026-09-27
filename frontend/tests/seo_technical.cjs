const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const origin = "https://miraihitstudio.com.br";
const indexablePages = new Map([
    ["index.html", `${origin}/`],
    ["artists.html", `${origin}/artists`],
    ["creators.html", `${origin}/creators`],
    ["media-games.html", `${origin}/media-games`],
    ["portfolio.html", `${origin}/portfolio`],
]);


function attribute(html, tag, attributeName) {
    const match = html.match(new RegExp(`<${tag}[^>]*${attributeName}=["']([^"']+)["'][^>]*>`, "i"));
    return match?.[1] ?? null;
}

function metaContent(html, selector) {
    const name = selector === "description" || selector === "robots" || selector.startsWith("twitter:") ? "name" : "property";
    const match = html.match(new RegExp(`<meta[^>]*${name}=["']${selector}["'][^>]*content=["']([^"']+)["'][^>]*>`, "i"));
    return match?.[1] ?? null;
}

(async () => {
    for (const [file, canonical] of indexablePages) {
        const html = await fs.readFile(path.join(root, file), "utf8");
        assert.match(html, /<html lang="pt-BR">/i, `${file}: language`);
        assert.match(html, /<title>[^<]+<\/title>/i, `${file}: title`);
        assert.ok(metaContent(html, "description"), `${file}: description`);
        assert.equal(attribute(html, "link", "href"), canonical, `${file}: canonical`);
        assert.equal(metaContent(html, "og:url"), canonical, `${file}: og:url`);
        assert.equal(metaContent(html, "og:type"), "website", `${file}: og:type`);
        assert.equal(metaContent(html, "twitter:card"), "summary_large_image", `${file}: Twitter card`);
        assert.equal(metaContent(html, "robots"), "index,follow", `${file}: indexability`);
    }

    const home = await fs.readFile(path.join(root, "index.html"), "utf8");
    const jsonLd = home.match(/<script type="application\/ld\+json">\s*([\s\S]*?)\s*<\/script>/i)?.[1];
    const organization = JSON.parse(jsonLd);
    assert.equal(organization["@context"], "https://schema.org");
    assert.equal(organization["@type"], "Organization");
    assert.equal(organization.url, `${origin}/`);
    assert.ok(organization.name && organization.logo && organization.description);

    const robots = await fs.readFile(path.join(root, "robots.txt"), "utf8");
    assert.match(robots, /^Allow: \/$/m);
    assert.match(robots, new RegExp(`^Sitemap: ${origin.replace(/[./]/g, "\\$&")}\/sitemap\\.xml$`, "m"));

    const sitemap = await fs.readFile(path.join(root, "sitemap.xml"), "utf8");
    const sitemapUrls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1]);
    assert.deepEqual(sitemapUrls, [...indexablePages.values()]);
    assert.doesNotMatch(sitemap, /checkout|admin|\.html|<lastmod>|<changefreq>|<priority>/i);

    const checkout = await fs.readFile(path.join(root, "checkout.html"), "utf8");
    const admin = await fs.readFile(path.join(root, "admin.html"), "utf8");
    const notFound = await fs.readFile(path.join(root, "404.html"), "utf8");
    const headers = await fs.readFile(path.join(root, "_headers"), "utf8");
    assert.match(checkout, /name="robots" content="noindex,nofollow"/i);
    assert.match(admin, /name="robots" content="noindex,nofollow,noarchive"/i);
    assert.match(notFound, /name="robots" content="noindex,nofollow"/i);
    assert.match(headers, /\/admin\*\s+X-Robots-Tag: noindex, nofollow, noarchive/s);

    const manifest = JSON.parse(await fs.readFile(path.join(root, "site.webmanifest"), "utf8"));
    assert.equal(manifest.start_url, "/");
    assert.equal(manifest.icons[0].src, "/assets/favicon.png");
    await fs.access(path.join(root, "assets", "favicon.png"));

    const internalLinks = await Promise.all(["components/nav.html", "components/footer.html", "index.html", "artists.html", "creators.html", "media-games.html", "portfolio.html"].map(file => fs.readFile(path.join(root, file), "utf8")));
    assert.doesNotMatch(internalLinks.join("\n"), /href="\/(?:artists|creators|media-games|portfolio)\.html"|href="\/(?:artists|creators|media-games|portfolio)\/"/i);

    console.log("PASS: canonical URLs, sitemap, robots, noindex, JSON-LD, manifest and public links.");
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
