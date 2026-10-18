const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");

const root = path.resolve(__dirname, "..");
const items = [];
const posts = [];
const errors = [];
const screenDir = path.join(os.tmpdir(), "mirai-portfolio-submissions");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        await fs.mkdir(screenDir, { recursive: true });
        async function setup(role, width) {
            const context = await browser.newContext({ viewport: { width, height: 900 } });
            await context.route("**/*", async route => {
                const req = route.request();
                const url = new URL(req.url());
                if (url.origin === "http://localhost:4173") {
                    const pathname = url.pathname.startsWith("/produtor") ? "/portal-produtor.html" : url.pathname;
                    const file = path.resolve(root, "." + decodeURIComponent(pathname));
                    assert.ok(file.startsWith(root + path.sep));
                    const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".ttf": "font/ttf" };
                    try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
                    catch { return route.fulfill({ status: 404, body: "" }); }
                }
                if (url.origin !== "http://localhost:8000") return route.abort();
                const user = { id: role === "admin" ? 1 : 2, username: role, role, ativo: true, is_admin: role === "admin" };
                if (url.pathname === "/auth/login") {
                    // Reproduce a login completing after the click has returned to the test.
                    if (role === "admin") await new Promise(resolve => setTimeout(resolve, 150));
                    return route.fulfill({ json: { access_token: "synthetic-session", user } });
                }
                if (url.pathname === "/auth/me") return route.fulfill({ json: user });
                if (url.pathname === "/portal/produtor/portfolio" && req.method() === "POST") {
                    const data = req.postDataJSON();
                    posts.push(data);
                    const item = { id: items.length + 1, produtor_id: 2, dados: data, status: "pendente", versao: 1 };
                    items.push(item);
                    return route.fulfill({ status: 201, json: item });
                }
                if (["/portal/produtor/portfolio", "/projetos/envios/admin"].includes(url.pathname)) return route.fulfill({ json: items });
                if (/^\/projetos\/envios\/\d+\/revisao$/.test(url.pathname)) {
                    const data = req.postDataJSON();
                    posts.push(data);
                    items[0].status = data.decisao === "aprovar" ? "aprovado" : "recusado";
                    return route.fulfill({ json: items[0] });
                }
                if (url.pathname === "/config/portfolio-segments") return route.fulfill({ json: { segments: [] } });
                if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
                if (url.pathname === "/config") return route.fulfill({ json: {} });
                if (url.pathname === "/portal/produtor/configuracao") return route.fulfill({ status: 503, json: {} });
                if (url.pathname === "/portal/notificacoes") return route.fulfill({ json: { itens: [], nao_vistas: 0 } });
                return route.fulfill({ json: [] });
            });
            const page = await context.newPage();
            page.on("pageerror", error => errors.push(error.message));
            await page.goto(`http://localhost:4173/${role === "admin" ? "admin.html" : "produtor/portfolio"}`);
            await page.locator("#username").fill(role);
            await page.locator("#password").fill("synthetic-only");
            if (role === "admin") await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
            else await page.locator("#producer-login-form button[type=submit]").click();
            return { page, context };
        }
        const { page, context } = await setup("produtor", 1280);
        await page.locator("#portfolio-submit-titulo").waitFor({ state: "visible" });
        const form = page.locator(".portfolio-submission-form");
        await page.locator("#portfolio-submit-titulo").fill("<img src=x> Faixa sintética");
        await page.locator("#portfolio-submit-artista").fill("Artista sintético");
        await page.locator("#portfolio-submit-categoria").fill("Mixagem");
        await page.locator("#portfolio-submit-link_audio").fill("https://example.test/audio");
        await page.locator("#portfolio-submit-link_capa").fill("https://example.test/cover.png");
        await form.locator("button[type=submit]").click();
        assert.equal(posts.length, 0, "Consent is mandatory before submission");
        await page.locator("#portfolio-submit-autorizacao_artista").check();
        await form.locator("button[type=submit]").click();
        await page.getByText("Aguardando revisão", { exact: true }).waitFor();
        assert.equal(posts.length, 1);
        assert.equal(posts[0].autorizacao_artista, true);
        assert.match(posts[0].request_id, /^[a-f\d-]{36}$/);
        assert.equal(await page.locator(".portfolio-submission img").count(), 0, "Untrusted title is text, not HTML");
        await page.screenshot({ path: path.join(screenDir, "producer-desktop.png"), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.screenshot({ path: path.join(screenDir, "producer-mobile.png"), fullPage: true });
        await context.close();
        const admin = await setup("admin", 1280);
        await admin.page.locator('[data-admin-target="dashboard-menu"][aria-current="page"]').waitFor();
        await admin.page.locator('[data-admin-target="section-portfolio"]').click();
        const review = admin.page.locator(".portfolio-submission-review");
        await review.getByRole("button", { name: "Recusar", exact: true }).click();
        assert.equal(posts.length, 1, "Refusal needs a reason");
        await review.getByRole("button", { name: "Aprovar e publicar" }).click();
        await admin.page.getByText("Publicado", { exact: true }).waitFor();
        assert.equal(posts.length, 2);
        assert.deepEqual(posts[1], { versao: 1, decisao: "aprovar", motivo: null });
        await admin.page.screenshot({ path: path.join(screenDir, "admin-desktop.png"), fullPage: true });
        assert.deepEqual(errors, []);
        console.log("portfolio_submissions=passed; screenshots=" + screenDir);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
