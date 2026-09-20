const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const aliases = { "/": "/index.html", "/artists": "/artists.html" };
const types = {
    ".css": "text/css",
    ".html": "text/html",
    ".js": "text/javascript",
    ".png": "image/png",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
};

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = aliases[url.pathname] || url.pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: types[path.extname(file)] || "application/octet-stream",
        });
    } catch {
        return route.fulfill({ status: 404, body: "" });
    }
}

(async () => {
    const browser = await chromium.launch({
        headless: true,
        channel: process.env.BROWSER_CHANNEL || "msedge",
    });
    try {
        const context = await browser.newContext();
        await context.addInitScript(() => {
            localStorage.setItem("mirai.analytics_consent.v1", "rejected");
        });
        const page = await context.newPage();
        const errors = [];
        const loadedHeroes = new Set();
        page.on("pageerror", error => errors.push(error.message));
        page.on("response", response => {
            if (response.url().includes("mirai-") && response.url().endsWith("-hero.webp")) {
                assert.equal(response.status(), 200);
                loadedHeroes.add(new URL(response.url()).pathname);
            }
        });
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "http://localhost:8000" && url.pathname === "/projetos") {
                return route.fulfill({ json: [] });
            }
            return route.fulfill({ status: 404, body: "" });
        });

        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto("http://localhost:4173/");
        await page.waitForSelector(".site-nav[data-initialized='true']");
        await page.waitForSelector("#home-portfolio-track .public-empty");
        assert.match(await page.locator("h1").textContent(), /Produção musical e áudio/);
        assert.equal(await page.locator(".vertical-card").count(), 3);
        assert.equal(await page.locator(".process-list > li").count(), 6);
        assert.equal(await page.getByText("estúdio de rap geek", { exact: false }).count(), 0);
        assert.equal(await page.locator("#particles-container").count(), 0);
        assert.ok((await page.locator("#home-portfolio-track").textContent()).includes("identificados e autorizados"));

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => ({
                page: document.documentElement.scrollWidth - window.innerWidth,
                elements: [...document.querySelectorAll("body *")]
                    .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
                    .slice(0, 5)
                    .map(element => `${element.tagName.toLowerCase()}.${element.className}`),
            }));
            assert.ok(overflow.page <= 1, `home overflow at ${width}px: ${JSON.stringify(overflow)}`);
        }
        if (process.env.VISUAL_OUTPUT) {
            await page.setViewportSize({ width: 1440, height: 900 });
            await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, "home-g2.png") });
        }

        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto("http://localhost:4173/artists");
        await page.waitForSelector(".site-nav[data-initialized='true']");
        assert.match(await page.locator("h1").textContent(), /identidade e acabamento/);
        assert.equal(await page.locator(".service-capabilities article").count(), 5);
        assert.match(await page.locator(".artists-intro").textContent(), /rap, trap, drill, funk, geek music/i);
        assert.equal(await page.locator("[data-public-path='/artists']").getAttribute("aria-current"), "page");
        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => ({
                page: document.documentElement.scrollWidth - window.innerWidth,
                elements: [...document.querySelectorAll("body *")]
                    .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
                    .slice(0, 5)
                    .map(element => `${element.tagName.toLowerCase()}.${element.className}`),
            }));
            assert.ok(overflow.page <= 1, `artists overflow at ${width}px: ${JSON.stringify(overflow)}`);
        }
        if (process.env.VISUAL_OUTPUT) {
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, "artists-g2-mobile.png") });
        }

        assert.deepEqual([...loadedHeroes].sort(), [
            "/img/mirai-artists-hero.webp",
            "/img/mirai-studio-hero.webp",
        ]);
        assert.deepEqual(errors, []);
        console.log("PASS: Home and Artists content, honest portfolio state, hero assets and responsive structure.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
