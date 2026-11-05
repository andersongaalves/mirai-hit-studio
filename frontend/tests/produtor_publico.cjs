// Public producer page: header, metrics, bio, tabs (Portfólio / Beats), canonical address,
// links from beat cards, and safe rendering of producer-written text.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml" };
const beat = { id: 71, produtor: "Ana <b>Beats</b>", produtor_perfil: "ana", titulo: "Horizonte", descricao: "", bpm: 140, tonalidade: "Am", generos: "Trap", moods: "Dark", preco_lease: "100.00", preco_wav: null, preco_multitrack: null, preco_exclusivo: "500.00", formato_novo: true, capa_url: null, vendido: false };
const perfil = {
    slug: "ana", nome: "Ana <b>Beats</b>", headline: "Trap e R&B <script>x</script>", bio: "Produtora de SP.\nMix e beats.",
    cidade: "São Paulo", foto_url: null, capa_url: null, cor: "#cb32e6", aba_inicial: "beats",
    links: { instagram: "https://www.instagram.com/ana", site: "javascript:alert(1)" },
    especialidades: ["beatmaker", "mixagem"],
    metricas: { total: 5, portfolio: 2, mirai: 3, beats: 1 },
    portfolio: [
        { id: 10, titulo: "Hit", artista: "Yonda", categoria: "Mixagem", descricao: "", vertical: "artists", case_type: "client_case", segmentos_json: [], link_audio: "https://example.com/a.mp3", link_capa: "https://example.com/a.webp", funcoes: ["Mixagem", "Direção vocal"] },
        { id: 11, titulo: "Outro", artista: "Fulano", categoria: "Produção", descricao: "", vertical: "artists", case_type: "demo", segmentos_json: [], link_audio: "https://example.com/b.mp3", link_capa: "https://example.com/b.webp", funcoes: ["Produção"] },
    ],
    beats: [beat],
};

async function staticResponse(route) {
    const url = new URL(route.request().url());
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === "/produtores" || pathname.startsWith("/produtores/")) pathname = "/produtores.html";
    if (pathname === "/beats" || pathname.startsWith("/beats/")) pathname = "/beats.html";
    const file = path.resolve(root, `.${pathname}`);
    assert.ok(file.startsWith(root + path.sep));
    try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
    catch { return route.fulfill({ status: 404, body: "" }); }
}

(async () => {
    const redirects = await fs.readFile(path.join(root, "_redirects"), "utf8");
    assert.match(redirects, /^\/produtores\/\* \/produtores 200$/m);
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "rejected"));
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("dialog", dialog => { errors.push(`dialog: ${dialog.message()}`); dialog.dismiss(); });
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "http://localhost:8000") {
                if (url.pathname === "/produtores/ana" || url.pathname === "/produtores/ana-beats-2") return route.fulfill({ json: perfil });
                if (url.pathname === "/produtores/nada-9") return route.fulfill({ status: 404, json: { detail: "Produtor não encontrado." } });
                if (url.pathname === "/beats/publico") return route.fulfill({ json: [beat] });
                if (url.pathname === "/beats/licencas") return route.fulfill({ json: [] });
                return route.fulfill({ status: 404, json: {} });
            }
            return route.fulfill({ status: 204, body: "" });
        });

        // The original address works and shows the one the producer chose.
        await page.goto("http://localhost:4173/produtores/ana-beats-2");
        await page.locator(".producer-page__name").waitFor();
        assert.equal(new URL(page.url()).pathname, "/produtores/ana");
        assert.equal(await page.locator(".producer-page__name").textContent(), "Ana <b>Beats</b>");
        assert.equal(await page.locator(".producer-page__headline").textContent(), "Trap e R&B <script>x</script>");
        assert.match(await page.title(), /^Ana <b>Beats<\/b> \| Produtor na Mirai Hit Studio$/);
        assert.equal(await page.locator(".producer-page__avatar").textContent(), "A<");
        assert.deepEqual(await page.locator(".producer-page__meta li").allTextContents(), ["São Paulo", "Beatmaker", "Mixagem"]);
        // Only safe links are rendered.
        assert.deepEqual(await page.locator(".producer-page__links a").allTextContents(), ["Instagram"]);
        assert.equal(await page.locator(".producer-page__links a").getAttribute("rel"), "noopener noreferrer me");
        assert.deepEqual(await page.locator(".producer-page__metric dd").allTextContents(), ["5", "2", "3", "1"]);
        assert.equal(await page.locator(".producer-page__bio p").textContent(), "Produtora de SP.\nMix e beats.");
        assert.equal(await page.locator("#produtor-publico").evaluate(node => node.style.getPropertyValue("--perfil-cor")), "#cb32e6");
        // The producer's first tab is Beats; switching keeps it in the address.
        assert.equal(await page.getByRole("tab", { name: "Beats (1)" }).getAttribute("aria-selected"), "true");
        assert.equal(await page.locator("#producer-panel-portfolio").isHidden(), true);
        await page.getByRole("tab", { name: "Portfólio (2)" }).click();
        assert.equal(new URL(page.url()).searchParams.get("aba"), "portfolio");
        assert.deepEqual(await page.locator("#producer-panel-portfolio .portfolio-card h2").allTextContents(), ["Hit", "Outro"]);
        assert.equal(await page.locator("#producer-panel-portfolio .producer-page__role").first().textContent(), "Função: Mixagem · Direção vocal");
        await page.keyboard.press("ArrowRight");
        assert.equal(await page.getByRole("tab", { name: "Beats (1)" }).getAttribute("aria-selected"), "true");
        assert.equal(await page.locator("#producer-panel-beats .beat-card h3").textContent(), "Horizonte");
        // No Beats tab without beats.
        perfil.beats = [];
        await page.reload();
        await page.locator(".producer-page__name").waitFor();
        assert.equal(await page.getByRole("tab").count(), 1);
        assert.equal(await page.getByRole("tab", { name: "Portfólio (2)" }).getAttribute("aria-selected"), "true");
        perfil.beats = [beat];
        // Unknown producer.
        await page.goto("http://localhost:4173/produtores/nada-9");
        await page.getByText("Este perfil não existe ou não está disponível.").waitFor();

        // From the public catalog, the producer's name opens the page (the card itself opens the beat).
        await page.goto("http://localhost:4173/beats");
        await page.locator("#beats-public-list .beat-card").waitFor();
        const producerLink = page.locator("#beats-public-list .beat-producer-link");
        assert.equal(await producerLink.getAttribute("href"), "/produtores/ana");
        assert.equal(await producerLink.textContent(), "Ana <b>Beats</b>");
        await producerLink.click();
        await page.waitForURL("**/produtores/ana");
        await page.locator(".producer-page__name").waitFor();

        for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            await page.reload();
            await page.locator(".producer-page__name").waitFor();
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `producer page overflow at ${width}px: ${overflow}px`);
        }
        if (process.env.SHOTS) {
            perfil.capa_url = "http://localhost:4173/img/mirai-studio-hero.webp";
            perfil.foto_url = "http://localhost:4173/img/mirai-creators-hero.webp";
            perfil.links.site = "https://ana.example.com";
            for (const [width, name] of [[1280, "d"], [390, "m"]]) {
                await page.setViewportSize({ width, height: 900 });
                await page.goto("http://localhost:4173/produtores/ana?aba=portfolio");
                await page.locator(".producer-page__name").waitFor();
                await page.waitForTimeout(600);
                await page.screenshot({ path: path.join(process.env.SHOTS, `perfil-${name}.png`), fullPage: true });
            }
        }
        assert.deepEqual(errors, []);
        console.log("PASS: producer page, metrics, tabs, canonical address and links from beats.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
