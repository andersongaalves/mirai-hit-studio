const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const configValues = {
    desconto: 10,
    val_extra_duracao: 0.1,
    val_extra_pessoa: 20,
    val_extra_canal_voz: 5,
    val_extra_canal_inst: 5,
    val_extra_melodia: 10,
    val_inst_hibrido: 40,
    val_inst_gravado: 100,
    val_lease_desconto: 50,
    val_extra_revisao: 30,
    val_prazo_urgente: 40,
    val_prazo_express: 80,
};
let revision = 1;
let segments = [
    { id: "rock", label: "Rock", active: true, order: 1, usage_count: 1 },
    { id: "legacy_mix", label: "Legacy Mix", active: false, order: 2, usage_count: 1 },
    { id: "unused", label: "Unused", active: true, order: 3, usage_count: 0 },
];
const retired = new Set();
let projects = [{
    id: 7,
    titulo: "Projeto sintético",
    artista: "Mirai",
    categoria: "Mixagem",
    vertical: "artists",
    segmentos_json: ["rock", "legacy_mix"],
    case_type: "demo",
    link_audio: "https://example.invalid/audio.mp3",
    link_capa: "https://example.invalid/cover.webp",
    descricao: "Fixture",
    destaque: false,
    audio_before_url: null,
    audio_after_url: null,
    show_mix_comparison_on_landing: false,
    landing_order: null,
}];
const projectWrites = [];
const financialWrites = [];

function catalog() {
    return { segments, revision: String(revision).padStart(64, "0") };
}

function nextRevision() {
    revision += 1;
    segments = segments.map((segment, index) => ({ ...segment, order: index + 1 }));
}

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
    const launchOptions = { headless: true };
    if (process.env.BROWSER_CHANNEL) launchOptions.channel = process.env.BROWSER_CHANNEL;
    else if (process.platform === "win32") launchOptions.channel = "msedge";
    const browser = await chromium.launch(launchOptions);
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));

    await page.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") return staticResponse(route);
        if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 200, body: "" });
        if (url.pathname === "/auth/login") {
            return route.fulfill({ json: { access_token: "admin-token", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
        }
        if (url.pathname === "/auth/me") {
            return route.fulfill({ json: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } });
        }
        if (url.pathname === "/config" && request.method() === "GET") return route.fulfill({ json: configValues });
        if (url.pathname === "/config" && request.method() === "PUT") {
            financialWrites.push(request.postDataJSON());
            return route.fulfill({ json: configValues });
        }
        if (url.pathname === "/config/portfolio-segments" && request.method() === "GET") {
            return route.fulfill({ json: catalog() });
        }
        if (url.pathname === "/config/portfolio-segments" && request.method() === "POST") {
            const body = request.postDataJSON();
            const id = body.label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
            if (segments.some(item => item.id === id) || retired.has(id)) {
                return route.fulfill({ status: 409, json: { detail: "Este identificador já existe ou foi aposentado." } });
            }
            segments.push({ id, label: body.label.trim(), active: true, order: segments.length + 1, usage_count: 0 });
            nextRevision();
            return route.fulfill({ json: catalog() });
        }
        if (url.pathname === "/config/portfolio-segments/order" && request.method() === "PUT") {
            const body = request.postDataJSON();
            segments = body.segment_ids.map(id => segments.find(segment => segment.id === id));
            nextRevision();
            return route.fulfill({ json: catalog() });
        }
        const segmentMatch = url.pathname.match(/^\/config\/portfolio-segments\/([a-z0-9_]+)$/);
        if (segmentMatch && request.method() === "PATCH") {
            const body = request.postDataJSON();
            segments = segments.map(segment => segment.id === segmentMatch[1]
                ? { ...segment, ...(body.label == null ? {} : { label: body.label.trim() }), ...(body.active == null ? {} : { active: body.active }) }
                : segment);
            nextRevision();
            return route.fulfill({ json: catalog() });
        }
        if (segmentMatch && request.method() === "DELETE") {
            const current = segments.find(segment => segment.id === segmentMatch[1]);
            if (current.usage_count) return route.fulfill({ status: 409, json: { detail: "Segmento em uso." } });
            retired.add(current.id);
            segments = segments.filter(segment => segment.id !== current.id);
            nextRevision();
            return route.fulfill({ json: catalog() });
        }
        if (url.pathname === "/projetos/admin") return route.fulfill({ json: projects });
        if (url.pathname === "/projetos/7" && request.method() === "PUT") {
            const payload = request.postDataJSON();
            projectWrites.push(payload);
            projects = projects.map(project => project.id === 7 ? { ...project, ...payload } : project);
            return route.fulfill({ json: projects[0] });
        }
        const empty = ["/servicos", "/orcamentos", "/producoes", "/clientes", "/usuarios", "/usuarios/produtores", "/newsletter/subscribers", "/newsletter/campaigns"];
        if (empty.includes(url.pathname)) return route.fulfill({ json: [] });
        if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        return route.fulfill({ status: 404, json: { detail: "Not found" } });
    });

    try {
        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("password");
        await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
        await page.evaluate(() => window.mostrarSecao("section-custos"));
        await page.locator('[data-segment-id="rock"]').waitFor();

        await page.locator("#portfolio-segment-label").fill("Brazilian Phonk");
        await page.locator("#portfolio-segment-add").getByRole("button", { name: "Adicionar" }).click();
        const phonk = page.locator('[data-segment-id="brazilian_phonk"]');
        await phonk.waitFor();
        await phonk.locator('input[type="text"]').fill("Brazilian Phonk / Games");
        await phonk.getByRole("button", { name: /Salvar nome/ }).click();
        assert.equal(await phonk.locator('input[type="text"]').inputValue(), "Brazilian Phonk / Games");

        await phonk.locator('input[type="checkbox"]').uncheck();
        await phonk.locator('input[type="checkbox"]').check();
        await phonk.getByRole("button", { name: /Mover .* para cima/ }).click();
        assert.ok(segments.findIndex(item => item.id === "brazilian_phonk") < segments.length - 1);

        await page.locator('[data-segment-id="unused"]').getByRole("button", { name: /Remover/ }).click();
        await page.waitForFunction(() => !document.querySelector('[data-segment-id="unused"]'));
        assert.equal(retired.has("unused"), true);

        await page.locator("#portfolio-segment-label").fill("Rock");
        await page.locator("#portfolio-segment-add").getByRole("button", { name: "Adicionar" }).click();
        const duplicateMessage = page.locator(".notification.error .notification-message").last();
        await duplicateMessage.waitFor();
        assert.match(await duplicateMessage.textContent(), /já existe|aposentado/i);

        await page.evaluate(() => window.mostrarSecao("section-portfolio"));
        await page.evaluate(() => window.editarProjeto(7));
        const legacy = page.locator('#proj_segmentos_opcoes input[value="legacy_mix"]');
        assert.equal(await legacy.isChecked(), true);
        assert.equal(await legacy.isDisabled(), false);
        await page.locator("#proj_segmentos_busca").fill("Brazilian");
        await page.locator("#proj_segmentos_busca").press("ArrowDown");
        assert.equal(await page.evaluate(() => document.activeElement?.value), "brazilian_phonk");
        await page.locator('#proj_segmentos_opcoes input[value="brazilian_phonk"]').check();
        await page.getByRole("button", { name: "Salvar Projeto" }).click();
        await page.waitForFunction(() => document.getElementById("modal-projeto").classList.contains("hidden"));
        assert.deepEqual(projectWrites.at(-1).segmentos_json, ["rock", "legacy_mix", "brazilian_phonk"]);

        await page.evaluate(() => window.mostrarSecao("section-custos"));
        await page.getByRole("button", { name: "SALVAR TABELA" }).click();
        assert.deepEqual(financialWrites, [configValues]);

        for (const width of [320, 390, 768, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const layout = await page.evaluate(() => ({
                overflow: document.documentElement.scrollWidth - window.innerWidth,
                offenders: [...document.querySelectorAll("body *")]
                    .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
                    .slice(0, 4)
                    .map(element => `${element.tagName.toLowerCase()}#${element.id}.${element.className}`),
            }));
            assert.ok(layout.overflow <= 1, `segment admin overflow at ${width}px: ${layout.overflow}px ${layout.offenders.join(", ")}`);
        }

        await page.reload();
        await page.waitForFunction(() => window.fazerLogin instanceof Function);
        await page.locator('[data-segment-id="brazilian_phonk"]').waitFor({ state: "attached" });
        assert.deepEqual(errors, []);
        console.log("PASS: segment catalog CRUD, stable IDs, ordering, multi-select, keyboard, legacy values, finance isolation and mobile layout.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
