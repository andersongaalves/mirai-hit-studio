const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".webp": "image/webp", ".ttf": "font/ttf" };

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = url.pathname === "/media-games" ? "/media-games.html" : url.pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" });
    } catch {
        return route.fulfill({ status: 404, body: "" });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext();
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

        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto("http://localhost:4173/media-games");
        await page.waitForSelector(".site-nav[data-initialized='true']");
        await page.waitForFunction(() => window.dataLayer?.some(item => item[0] === "event" && item[1] === "view_vertical"));
        assert.match(await page.locator("h1").textContent(), /constrói mundos/i);
        assert.equal(await page.locator(".media-capabilities article").count(), 7);
        assert.match(await page.locator("main").textContent(), /Demo, Concept Project e Study/);
        assert.equal(await page.getByText(/grandes estúdios|clientes como|trabalhamos com/i).count(), 0);
        const event = await page.evaluate(() => window.dataLayer.find(item => item[0] === "event" && item[1] === "view_vertical"));
        assert.deepEqual(event[2], { vertical: "media_games" });

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `media-games overflow at ${width}px: ${overflow}px`);
        }
        assert.deepEqual(errors, []);
        console.log("PASS: Media & Games capabilities, transparent proof labels, analytics and responsive structure.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
