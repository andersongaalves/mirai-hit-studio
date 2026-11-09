// Public areas with no published portfolio work are hidden from the menu, the home page,
// the portfolio intro and the portfolio filters; every area stays when the API fails.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const routes = { "/": "/index.html", "/portfolio": "/portfolio.html", "/creators": "/creators.html" };
const types = { ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml" };
const projects = [
    { id: 1, titulo: "Single", artista: "Artista", categoria: "Mixagem", link_audio: "https://example.com/a.mp3", link_capa: "https://example.com/a.webp", descricao: "Caso", destaque: true, vertical: "artists", segmentos_json: [], case_type: "client_case", creditos: [] },
    { id: 2, titulo: "Jogo", artista: "Estudio", categoria: "Trilha", link_audio: "https://example.com/b.mp3", link_capa: "https://example.com/b.webp", descricao: "Demo", destaque: false, vertical: "media_games", segmentos_json: [], case_type: "demo", creditos: [] },
];

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "rejected"));
        const page = await context.newPage();
        const errors = [];
        let answer = { verticais: ["artists", "media_games"] };
        let calls = 0;
        page.on("pageerror", error => errors.push(error.message));
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") {
                const file = path.resolve(root, `.${routes[url.pathname] || decodeURIComponent(url.pathname)}`);
                try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
                catch { return route.fulfill({ status: 404, body: "" }); }
            }
            if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 204, body: "" });
            if (url.pathname === "/projetos/public/verticais") {
                calls += 1;
                return answer ? route.fulfill({ json: answer }) : route.abort("failed");
            }
            if (url.pathname === "/projetos") return route.fulfill({ json: projects });
            return route.fulfill({ json: [] });
        });
        const navLink = name => page.locator(".site-nav__links a", { hasText: name });

        // Criadores has nothing published: gone from the menu and the home; numbering stays continuous.
        await page.goto("http://localhost:4173/");
        await page.waitForFunction(() => document.querySelector('.site-nav__links a[href="/creators"]')?.hidden === true);
        assert.equal(await navLink("Criadores").isVisible(), false);
        assert.equal(await navLink("Artistas").isVisible(), true);
        assert.equal(await navLink("Media & Games").isVisible(), true);
        assert.equal(await page.locator('a.vertical-card[href="/creators"]').isVisible(), false);
        assert.deepEqual(await page.locator("a.vertical-card:visible .home-service__number").allTextContents(), ["01", "02"]);
        assert.deepEqual(await page.locator("a.vertical-card:visible strong").allTextContents(), ["Artistas", "Media & Games"]);

        // The mobile menu hides it too.
        await page.setViewportSize({ width: 390, height: 800 });
        await page.locator("#site-nav-toggle").click();
        assert.equal(await navLink("Criadores").isVisible(), false);
        assert.equal(await navLink("Artistas").isVisible(), true);
        await page.setViewportSize({ width: 1280, height: 900 });

        // Portfolio: intro sentence and filter buttons follow the published areas.
        await page.goto("http://localhost:4173/portfolio");
        await page.waitForSelector("#filtros-portfolio .filter-btn");
        await page.waitForFunction(() => !document.querySelector("[data-vertical-intro]").textContent.includes("criadores"));
        assert.equal(await page.locator("[data-vertical-intro]").textContent(), "Produções, demos e estudos com contexto e crédito para artistas e mídia e games.");
        assert.deepEqual(await page.locator("[data-vertical-intro] a").evaluateAll(links => links.map(link => link.getAttribute("href"))), ["/artists", "/media-games"]);
        assert.deepEqual(await page.locator('#filtros-portfolio [data-filter-kind="vertical"]').allTextContents(), ["Todos", "Artistas", "Media & Games"]);

        // The last answer is applied right away on the next page, before the API answers.
        answer = null;
        await page.goto("http://localhost:4173/");
        await page.waitForSelector(".site-nav__links a");
        assert.equal(await navLink("Criadores").isVisible(), false);
        assert.ok(calls >= 3);

        // A new area with work appears once published.
        answer = { verticais: ["artists", "creators", "media_games"] };
        const published = page.waitForResponse(response => response.url().endsWith("/projetos/public/verticais"));
        await page.reload();
        await published;
        await page.waitForFunction(() => document.querySelector('a.vertical-card[href="/creators"]')?.hidden === false
            && document.querySelector('.site-nav__links a[href="/creators"]')?.hidden === false);
        assert.deepEqual(await page.locator("a.vertical-card:visible .home-service__number").allTextContents(), ["01", "02", "03"]);

        // No cache and no API: every area stays visible.
        await page.evaluate(() => localStorage.removeItem("mirai.public_verticals.v1"));
        answer = null;
        await page.reload();
        await page.waitForSelector(".site-nav__links a");
        await page.waitForTimeout(300);
        for (const name of ["Artistas", "Criadores", "Media & Games"]) assert.equal(await navLink(name).isVisible(), true, name);
        assert.equal(await page.locator("a.vertical-card:visible").count(), 3);

        // The area page itself still opens by its direct address.
        answer = { verticais: ["artists"] };
        const direct = await page.goto("http://localhost:4173/creators");
        assert.equal(direct.status(), 200);
        await page.waitForFunction(() => document.querySelector('.site-nav__links a[href="/creators"]')?.hidden === true);
        assert.equal(await page.locator("main h1").isVisible(), true);
        assert.deepEqual(errors, []);
        console.log("PASS: public areas without published work are hidden from menu, home, portfolio intro and filters; cache and API failure handled.");
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
