// Public beat catalog (/beats): browse and listen without an account; buying goes
// through the client sign-in and continues on the same beat in the client portal.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml", ".ttf": "font/ttf" };
const beats = [
    { id: 71, produtor: "<Producer>", titulo: "<Horizonte>", descricao: "Trap escuro.", bpm: 140, tonalidade: "Am", generos: "Trap", moods: "Dark", preco_lease: "100.00", preco_wav: "180.00", preco_multitrack: null, preco_exclusivo: "500.00", formato_novo: true, capa_url: null, vendido: false },
    { id: 74, produtor: "Lia", titulo: "Céu de agosto", descricao: "", bpm: 95, tonalidade: "C#m", generos: "R&B, Pop", moods: "Romântico", preco_lease: null, preco_wav: null, preco_multitrack: null, preco_exclusivo: "900.00", formato_novo: true, capa_url: null, vendido: false },
    { id: 73, produtor: "<Producer>", titulo: "<Vendido>", descricao: "", bpm: 90, tonalidade: null, generos: "Boom bap", moods: "", preco_lease: null, preco_wav: null, preco_multitrack: null, preco_exclusivo: null, formato_novo: true, capa_url: null, vendido: true },
];
const terms = [
    { tipo: "lease_mp3", rotulo: "Lease MP3", formatos: "MP3", exclusivo: false, limites: { streams: "200.000", vendas: "5.000", videos: "1", visualizacoes: "200.000", radio: "permitida em até 2 emissoras" } },
    { tipo: "lease_wav", rotulo: "Lease WAV", formatos: "WAV", exclusivo: false, limites: { streams: "500.000", vendas: "5.000", videos: "1", visualizacoes: "500.000", radio: "permitida em até 2 emissoras" } },
    { tipo: "multitrack", rotulo: "Lease Multitrack (stems)", formatos: "MP3, WAV e multitrack (stems)", exclusivo: false, limites: { streams: "500.000", vendas: "5.000", videos: "1", visualizacoes: "500.000", radio: "permitida em até 2 emissoras" } },
    { tipo: "exclusivo", rotulo: "Exclusiva", formatos: "MP3, WAV e multitrack (stems)", exclusivo: true, limites: null },
];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === "/beats" || pathname.startsWith("/beats/")) pathname = "/beats.html";
    if (pathname === "/acesso") pathname = "/acesso.html";
    const file = path.resolve(root, `.${pathname}`);
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
        await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "rejected"));
        const page = await context.newPage();
        const errors = [];
        const api = [];
        page.on("pageerror", error => errors.push(error.message));
        await context.route("**/*", async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "https://www.googletagmanager.com") return route.fulfill({ contentType: "text/javascript", body: "" });
            if (url.origin === "http://localhost:8000") {
                api.push({ path: url.pathname, auth: request.headers().authorization || null });
                if (url.pathname === "/beats/publico") return route.fulfill({ json: beats });
                if (url.pathname === "/beats/licencas") return route.fulfill({ json: terms });
                if (url.pathname === "/beats/publico/71/previa") return route.fulfill({ body: "ID3synthetic-preview", contentType: "audio/mpeg" });
                return route.fulfill({ status: 404, json: { detail: "not found" } });
            }
            return route.fulfill({ status: 404, body: "" });
        });

        await page.setViewportSize({ width: 1280, height: 900 });
        await page.goto("http://localhost:4173/beats");
        await page.waitForSelector(".site-nav[data-initialized='true']");
        await page.waitForSelector("#beats-public-list .beat-card");
        assert.equal(await page.locator(".site-nav").getByRole("link", { name: "Beats" }).getAttribute("aria-current"), "page");
        assert.equal(await page.locator("#beats-public-list .beat-card").count(), 3);
        assert.doesNotMatch(await page.locator("#beats-public-list").textContent(), /R\$/, "prices live on the beat page");
        assert.equal(await page.locator("#beats-public-list script, #beats-public-list img").count(), 0, "titles are text, never markup");
        assert.match(await page.locator("#beats-public-list").textContent(), /<Horizonte>.*prod\. <Producer>/s);
        // Previews download only when played, without any account.
        assert.equal(api.filter(item => item.path.includes("/previa")).length, 0);
        await page.locator("#beats-public-list .beat-card").first().locator(".beat-preview__play").click();
        await page.waitForFunction(() => document.querySelector("#beats-public-list .beat-preview__play").classList.contains("is-playing") || document.querySelector("#beats-public-list .beat-preview audio").src.startsWith("blob:"));
        assert.ok(api.some(item => item.path === "/beats/publico/71/previa"));
        assert.ok(api.every(item => item.auth === null), "the public catalog never sends credentials");
        assert.equal(new URL(page.url()).pathname, "/beats", "the player does not open the page");
        // Filters work here as in the portal.
        await page.getByRole("search", { name: "Filtrar beats" }).getByLabel("Gênero").selectOption("Pop");
        assert.deepEqual(await page.locator("#beats-public-list .beat-card:not([hidden]) h3").allTextContents(), ["Céu de agosto"]);
        await page.getByRole("search", { name: "Filtrar beats" }).getByLabel("Gênero").selectOption("");

        // The card opens the beat page with licenses, limits and the tag notice.
        const cover = await page.locator("#beats-public-list .beat-tile__cover").first().boundingBox();
        await page.mouse.click(cover.x + cover.width / 2, cover.y + cover.height / 2);
        await page.waitForURL("**/beats/71");
        const beatPage = page.locator("#beats-public-beat");
        await beatPage.locator(".beat-license").first().waitFor();
        assert.equal(await page.locator("#beats-public-catalog").isVisible(), false);
        assert.match(await page.title(), /<Horizonte> · prod\. <Producer>/);
        assert.equal(await page.locator(".site-nav").getByRole("link", { name: "Beats" }).getAttribute("aria-current"), "page");
        assert.match(await beatPage.getByRole("note").textContent(), /A tag sai depois da compra/);
        assert.deepEqual(await beatPage.locator(".beat-license__name").allTextContents(), ["Lease MP3", "Lease WAV", "Exclusiva"]);
        assert.match(await beatPage.locator(".beat-license").nth(1).textContent(), /R\$\s*180,00.*WAV.*Até 500\.000 reproduções/s);
        assert.match(await beatPage.locator(".beat-page__purchase-note").textContent(), /crie uma conta grátis/);
        // Without an account, buying goes to the client sign-in and back to this beat.
        const buy = beatPage.getByRole("link", { name: "Comprar Lease WAV" });
        const target = new URL(await buy.getAttribute("href"), "http://localhost:4173");
        assert.equal(target.pathname, "/acesso");
        assert.equal(target.searchParams.get("next"), "/cliente/beats/71?licenca=lease_wav");
        assert.equal(target.searchParams.get("motivo"), "comprar_beat");
        await buy.click();
        await page.waitForURL("**/acesso?**");
        await page.waitForFunction(() => !document.getElementById("access-notice")?.classList.contains("hidden"));
        assert.match(await page.locator("main").textContent(), /Para comprar o beat, entre na sua conta de cliente/);
        assert.equal(await page.getByRole("link", { name: "Criar conta" }).count() > 0, true);
        await page.goBack();
        await page.waitForURL("**/beats/71");
        await beatPage.locator(".beat-license").first().waitFor();
        await beatPage.getByRole("button", { name: "Voltar ao catálogo" }).click();
        await page.waitForURL(url => url.pathname === "/beats");

        // A signed-in client goes straight to the portal beat page.
        await page.evaluate(() => localStorage.setItem("mirai.auth.cliente.access_token", "synthetic"));
        await page.goto("http://localhost:4173/beats/74");
        await beatPage.locator(".beat-license").first().waitFor();
        assert.equal(await beatPage.getByRole("link", { name: "Comprar Exclusiva" }).getAttribute("href"), "/cliente/beats/74?licenca=exclusivo");
        await page.evaluate(() => localStorage.removeItem("mirai.auth.cliente.access_token"));
        // Sold and missing beats.
        await page.goto("http://localhost:4173/beats/73");
        await beatPage.locator(".beat-page__sold-note").waitFor();
        assert.equal(await beatPage.locator(".beat-license__buy").count(), 0);
        await page.goto("http://localhost:4173/beats/999");
        await page.getByText("Este beat não está mais disponível no catálogo.").waitFor();

        for (const [width, url] of [[320, "/beats"], [390, "/beats/71"], [768, "/beats"], [1440, "/beats/71"]]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(`http://localhost:4173${url}`);
            await page.waitForSelector(url === "/beats" ? "#beats-public-list .beat-card" : "#beats-public-beat .beat-license");
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `beats overflow at ${width}px on ${url}: ${overflow}px`);
        }
        assert.deepEqual(errors, []);
        console.log("PASS: public beats catalog, lazy previews, beat page, licenses and sign-in to buy.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
