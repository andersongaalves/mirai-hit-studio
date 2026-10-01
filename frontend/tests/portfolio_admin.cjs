const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const project = {
    id: 7,
    titulo: "Mix synthetic",
    artista: "Synthetic Artist",
    categoria: "Mixagem",
    vertical: "artists",
    segmentos_json: ["rock"],
    case_type: "demo",
    link_audio: "https://example.invalid/release",
    link_capa: "https://example.invalid/cover.webp",
    descricao: "Fixture",
    destaque: false,
    audio_before_url: "https://media.invalid/before.mp3",
    audio_after_url: "https://media.invalid/after.mp3",
    show_mix_comparison_on_landing: true,
    landing_order: 2,
};

async function staticResponse(route) {
    const pathname = new URL(route.request().url()).pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { ".js": "text/javascript", ".css": "text/css", ".html": "text/html" }[path.extname(file)] || "application/octet-stream",
        });
    } catch {
        return route.fulfill({ status: 404, body: "" });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    const writes = [];
    page.on("pageerror", error => errors.push(error.message));

    await page.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") return staticResponse(route);
        if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 200, body: "" });
        if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "session", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
        if (url.pathname === "/projetos/admin") return route.fulfill({ json: [project] });
        if (url.pathname === "/projetos/7" && request.method() === "PUT") {
            writes.push({ path: url.pathname, method: request.method(), payload: request.postDataJSON() });
            return route.fulfill({ json: { ...project, ...request.postDataJSON() } });
        }
        if (/\/projetos\/7\/audio\/(before|after)/.test(url.pathname)) {
            writes.push({ path: url.pathname, method: request.method() });
            return route.fulfill({ json: project });
        }
        const empty = ["/config", "/servicos", "/orcamentos", "/producoes", "/clientes", "/usuarios", "/usuarios/produtores", "/newsletter/subscribers", "/newsletter/campaigns"];
        if (empty.includes(url.pathname)) return route.fulfill({ json: url.pathname === "/config" ? {} : [] });
        if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        return route.fulfill({ status: 404, json: { detail: "Not found" } });
    });

    try {
        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("password");
        await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
        await page.waitForFunction(() => typeof window.editarProjeto === "function");
        await page.evaluate(() => window.editarProjeto(7));

        assert.equal(await page.locator("#proj_audio_before_preview").getAttribute("src"), project.audio_before_url);
        assert.equal(await page.locator("#proj_audio_after_preview").getAttribute("src"), project.audio_after_url);
        assert.equal(await page.locator("#proj_mix_landing").isChecked(), true);
        assert.equal(await page.locator("#proj_mix_order").inputValue(), "2");

        const mp3 = { name: "private-client-name.mp3", mimeType: "audio/mpeg", buffer: Buffer.from("ID3synthetic") };
        await page.locator("#proj_audio_before").setInputFiles(mp3);
        await page.locator("#proj_audio_after").setInputFiles(mp3);
        await page.locator("#proj_mix_landing").check();
        await page.locator("#proj_mix_order").selectOption("1");
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        await page.waitForFunction(() => document.getElementById("modal-projeto").classList.contains("hidden"));

        assert.deepEqual(writes.map(item => `${item.method} ${item.path}`), [
            "PUT /projetos/7",
            "POST /projetos/7/audio/before",
            "POST /projetos/7/audio/after",
            "PUT /projetos/7",
        ]);
        assert.equal(writes[0].payload.show_mix_comparison_on_landing, false);
        assert.equal(writes[3].payload.show_mix_comparison_on_landing, true);
        assert.equal(writes[3].payload.landing_order, 1);
        assert.equal(await page.locator(".portfolio-mix-comparison").evaluate(element => element.scrollWidth <= element.clientWidth), true);
        assert.deepEqual(errors, []);
        console.log("PASS: Portfolio A/B Admin upload, previews, highlight ordering and mobile structure.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
