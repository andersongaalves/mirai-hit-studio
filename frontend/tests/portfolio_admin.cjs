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
const legacyProject = {
    id: 8,
    titulo: "Projeto legado",
    artista: "Artista legado",
    categoria: "Produção",
    vertical: null,
    segmentos_json: [],
    case_type: null,
    link_audio: "",
    link_capa: "",
    descricao: "Antes da classificação A/B",
    destaque: true,
};
const segmentCatalog = {
    revision: "a".repeat(64),
    segments: [
        { id: "rock", label: "Rock", active: true, order: 1, usage_count: 1 },
        { id: "legacy_mix", label: "Legacy Mix", active: false, order: 2, usage_count: 0 },
    ],
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
    let projects = [project, legacyProject];
    page.on("pageerror", error => errors.push(error.message));

    await page.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") return staticResponse(route);
        if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 200, body: "" });
        if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "session", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
        if (url.pathname === "/projetos/admin") return route.fulfill({ json: projects });
        if (url.pathname === "/config/portfolio-segments") return route.fulfill({ json: segmentCatalog });
        if (/\/projetos\/(7|8)/.test(url.pathname) && request.method() === "PUT") {
            const payload = request.postDataJSON();
            writes.push({ path: url.pathname, method: request.method(), payload });
            if (payload.titulo === "x") {
                return route.fulfill({
                    status: 422,
                    json: { detail: [{ loc: ["body", "titulo"], msg: "String should have at least 3 characters", type: "string_too_short" }] },
                });
            }
            if (payload.titulo === "xx") {
                return route.fulfill({
                    status: 422,
                    json: { detail: [
                        { loc: ["body", "titulo"], msg: "String should have at least 3 characters", type: "string_too_short" },
                        { loc: ["body", "segmentos_json"], msg: "Value error, invalid_segment", type: "value_error" },
                    ] },
                });
            }
            const id = Number(url.pathname.split("/").pop());
            projects = projects.map(item => item.id === id ? { ...item, ...payload } : item);
            return route.fulfill({ json: projects.find(item => item.id === id) });
        }
        if (/\/projetos\/7\/audio\/(before|after)/.test(url.pathname)) {
            writes.push({ path: url.pathname, method: request.method() });
            return route.fulfill({ json: project });
        }
        if (url.pathname === "/projetos/7/imagem" && ["POST", "DELETE"].includes(request.method())) {
            writes.push({ path: url.pathname, method: request.method() });
            const link_capa = request.method() === "POST"
                ? "https://res.cloudinary.com/example/image/upload/portfolio/test-cover"
                : "";
            projects = projects.map(item => item.id === 7 ? { ...item, link_capa } : item);
            return route.fulfill({ json: projects.find(item => item.id === 7) });
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
        assert.deepEqual(Object.keys(writes[3].payload).sort(), ["landing_order", "show_mix_comparison_on_landing"]);
        assert.equal(await page.locator(".portfolio-mix-comparison").evaluate(element => element.scrollWidth <= element.clientWidth), true);

        await page.waitForTimeout(50);
        await page.evaluate(() => window.editarProjeto(7));
        await page.locator("#proj_capa_upload").setInputFiles({
            name: "client-visible-name.png",
            mimeType: "image/png",
            buffer: Buffer.from("\x89PNG\r\n\x1a\nsynthetic"),
        });
        assert.equal(await page.locator("#proj_capa_preview").isVisible(), true);
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        await page.waitForFunction(() => document.getElementById("modal-projeto").classList.contains("hidden"));
        assert.equal(writes.at(-1).method, "POST");
        assert.equal(writes.at(-1).path, "/projetos/7/imagem");

        await page.waitForTimeout(50);
        await page.evaluate(() => window.editarProjeto(7));
        assert.equal(await page.locator("#proj_capa_preview").getAttribute("src"), projects[0].link_capa);
        await page.locator("#proj_capa_remove").click();
        assert.equal(writes.at(-1).method, "DELETE");
        assert.equal(writes.at(-1).path, "/projetos/7/imagem");
        await page.locator("#proj_capa_preview").waitFor({ state: "hidden" });
        await page.evaluate(() => window.fecharModalProjeto());

        await page.waitForTimeout(50);
        const beforeLegacyEdit = writes.length;
        await page.evaluate(() => window.editarProjeto(8));
        await page.locator("#proj_titulo").fill("Projeto legado editado");
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        await page.waitForTimeout(100);
        assert.equal(
            await page.locator("#modal-projeto").evaluate(element => element.classList.contains("hidden")),
            true,
            `legacy save failed: ${await page.locator(".notification-message").allTextContents()}`,
        );
        assert.deepEqual(writes.slice(beforeLegacyEdit).map(item => item.payload), [
            { titulo: "Projeto legado editado" },
        ]);
        assert.equal(projects.find(item => item.id === 8).destaque, true);
        assert.equal(projects.find(item => item.id === 8).vertical, null);

        await page.waitForTimeout(50);
        await page.evaluate(() => window.editarProjeto(8));
        await page.locator("#proj_titulo").fill("x");
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        let message = page.locator(".notification.error .notification-message").last();
        await message.waitFor();
        assert.match(await message.textContent(), /Título: texto abaixo do tamanho mínimo/);
        assert.doesNotMatch(await message.textContent(), /\[object Object\]/);
        assert.equal(await page.locator("#proj_titulo").inputValue(), "x");
        assert.equal(await page.locator("#modal-projeto").evaluate(element => element.classList.contains("hidden")), false);

        await page.locator("#proj_titulo").fill("xx");
        await page.locator('#proj_segmentos_opcoes input[value="rock"]').check();
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        message = page.locator(".notification.error .notification-message").last();
        await page.waitForFunction(() => document.querySelectorAll(".notification.error").length >= 2);
        const multipleMessage = await message.textContent();
        assert.match(multipleMessage, /Título:/);
        assert.match(multipleMessage, /Segmentos:/);
        assert.doesNotMatch(multipleMessage, /\[object Object\]/);
        assert.equal(await page.locator("#proj_titulo").inputValue(), "xx");
        assert.equal(await page.locator('#proj_segmentos_opcoes input[value="rock"]').isChecked(), true);
        assert.deepEqual(errors, []);
        console.log("PASS: Portfolio Admin legacy edits, A/B preservation and readable validation errors.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
