const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const routes = { "/artists": "/artists.html", "/creators": "/creators.html", "/media-games": "/media-games.html" };


async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = routes[url.pathname] || url.pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(file), contentType: { ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".png": "image/png", ".webp": "image/webp" }[path.extname(file)] || "application/octet-stream" });
    } catch { return route.fulfill({ status: 404, body: "" }); }
}


(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 800 } });
        await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "accepted"));
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "https://www.googletagmanager.com") return route.fulfill({ contentType: "text/javascript", body: "" });
            return route.fulfill({ status: 404, body: "" });
        });

        await page.goto("http://localhost:4173/artists");
        await page.waitForSelector(".site-nav[data-initialized='true']");
        assert.equal(await page.locator('[data-public-path="/artists"]').getAttribute("aria-current"), "page");
        assert.deepEqual(await page.locator(".site-nav__links a").evaluateAll(links => links.map(link => link.getAttribute("href"))), ["/", "/artists", "/creators", "/media-games", "/portfolio", "/orcamento"]);
        assert.equal(await page.locator(".site-nav__links").isVisible(), false);
        await page.locator("#site-nav-toggle").click();
        assert.equal(await page.locator("#site-nav-toggle").getAttribute("aria-expanded"), "true");
        assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Início");
        await page.keyboard.press("Escape");
        assert.equal(await page.locator("#site-nav-toggle").getAttribute("aria-expanded"), "false");
        assert.equal(await page.evaluate(() => document.activeElement?.id), "site-nav-toggle");
        await page.waitForFunction(() => window.dataLayer?.some(item => item[0] === "event" && item[1] === "view_vertical"));
        const event = await page.evaluate(() => window.dataLayer.find(item => item[0] === "event" && item[1] === "view_vertical"));
        assert.deepEqual(event[2], { vertical: "artists" });

        await page.setViewportSize({ width: 1024, height: 800 });
        assert.equal(await page.locator(".site-nav__links").isVisible(), true);
        for (const target of ["/creators", "/media-games"]) {
            await page.goto(`http://localhost:4173${target}`);
            await page.waitForSelector(".site-nav[data-initialized='true']");
            assert.equal(await page.locator(`[data-public-path="${target}"]`).getAttribute("aria-current"), "page");
        }
        assert.deepEqual(errors, []);
        console.log("PASS: public routes, semantic navigation, mobile keyboard flow, active state and vertical analytics.");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
