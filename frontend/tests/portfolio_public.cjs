const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".webp": "image/webp", ".ttf": "font/ttf" };
let projects = [
    { id: 1, titulo: "Faixa <script>alert(1)</script>", artista: "Artista teste", categoria: "Mixagem", link_audio: "https://example.com/audio.mp3", link_capa: "javascript:alert(1)", descricao: "Descrição <img src=x onerror=alert(1)>", destaque: true, vertical: "artists", segmentos_json: ["rap"], case_type: "client_case" },
    { id: 2, titulo: "Estudo de interface", artista: "Mirai Hit Studio", categoria: "Sound design", link_audio: "https://www.youtube.com/watch?v=abcdefghijk", link_capa: "https://example.com/cover.webp", descricao: "Material conceitual", destaque: false, vertical: "media_games", segmentos_json: ["games"], case_type: "study" },
    { id: 3, titulo: "Nao classificado", artista: "Interno", categoria: "Outro", link_audio: "https://example.com/private.mp3", link_capa: "https://example.com/private.webp", descricao: "Nao publicar", destaque: false, vertical: null, segmentos_json: [], case_type: null },
];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = url.pathname === "/portfolio" ? "/portfolio.html" : url.pathname;
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
            if (url.origin === "http://localhost:8000" && url.pathname === "/projetos") return route.fulfill({ json: projects });
            if (url.origin === "https://www.googletagmanager.com") return route.fulfill({ contentType: "text/javascript", body: "" });
            if (url.origin === "https://example.com" || url.origin === "https://img.youtube.com") return route.fulfill({ status: 200, body: "" });
            return route.fulfill({ status: 404, body: "" });
        });

        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto("http://localhost:4173/portfolio");
        await page.waitForSelector(".portfolio-card");
        assert.equal(await page.locator(".portfolio-card").count(), 2);
        assert.equal(await page.getByText("Nao classificado", { exact: true }).count(), 0);
        assert.equal(await page.locator(".portfolio-filter-group").count(), 2);
        assert.equal(await page.locator("script").filter({ hasText: "alert(1)" }).count(), 0);
        assert.match(await page.locator(".portfolio-card").first().textContent(), /<script>alert\(1\)<\/script>/);
        assert.equal(await page.locator("audio").getAttribute("autoplay"), null);
        assert.equal(await page.locator("audio").getAttribute("preload"), "metadata");
        assert.ok((await page.locator(".portfolio-card__cover").first().getAttribute("src")).includes("logo-principal.webp"));

        await page.locator("audio").evaluate(audio => audio.dispatchEvent(new Event("play")));
        await page.waitForFunction(() => window.dataLayer?.some(item => item[0] === "event" && item[1] === "listen_portfolio"));
        const listen = await page.evaluate(() => window.dataLayer.find(item => item[0] === "event" && item[1] === "listen_portfolio"));
        assert.deepEqual(listen[2], { project_id: 1 });

        const artistsButton = page.locator('[data-filter-kind="vertical"][data-filter-value="artists"]');
        await artistsButton.click();
        assert.equal(await page.locator(".portfolio-card").count(), 1);
        assert.match(await page.locator(".portfolio-card").textContent(), /Artista teste/);

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `portfolio overflow at ${width}px: ${overflow}px`);
        }

        projects = [];
        await page.reload();
        await page.waitForFunction(() => document.querySelector(".portfolio-empty")?.textContent.includes("Ainda não há materiais"));
        assert.match(await page.locator(".portfolio-empty").textContent(), /Ainda não há materiais/);
        assert.equal(await page.locator("#filtros-portfolio").isVisible(), false);
        assert.deepEqual(errors, []);
        console.log("PASS: classified portfolio, honest labels, filters, accessible audio, analytics, XSS and empty state.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
