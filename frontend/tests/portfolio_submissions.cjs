const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const { expectAccessPage, openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, "..");
const items = [];
const posts = [];
const imagePosts = [];
const errors = [];
const screenDir = path.join(os.tmpdir(), "mirai-portfolio-submissions");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        await fs.mkdir(screenDir, { recursive: true });
        async function setup(role, width) {
            const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: "block" });
            await context.addInitScript(() => {
                const listeners = new Set();
                const emit = task => listeners.forEach(listener => listener({ data: { type: "mirai-upload-task", task } }));
                const registration = { active: { postMessage: message => {
                    if (message.type === "mirai-upload-list") return;
                    const task = { id: message.id, label: message.label, owner: message.owner, meta: message.meta,
                        status: "uploading", message: "Aguardando envio.", createdAt: Date.now(), updatedAt: Date.now() };
                    emit(task);
                    setTimeout(async () => {
                        const body = new FormData();
                        message.entries.forEach(([name, value]) => body.append(name, value));
                        const response = await fetch(message.url, {
                            method: message.method,
                            headers: { Authorization: `Bearer ${message.token}` },
                            body,
                        });
                        task.status = response.ok ? "completed" : "failed";
                        task.message = response.ok ? "Envio concluído." : "O servidor não concluiu o envio. Tente novamente.";
                        task.updatedAt = Date.now();
                        emit(task);
                    }, 0);
                } } };
                Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: {
                    register: async () => registration,
                    ready: Promise.resolve(registration),
                    addEventListener: (type, listener) => { if (type === "message") listeners.add(listener); },
                } });
            });
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
                if (url.pathname === "/portal/produtor/portfolio/com-capa" && req.method() === "POST") {
                    assert.match(req.headers()["content-type"], /^multipart\/form-data; boundary=/);
                    assert.equal(req.headers().authorization, "Bearer synthetic-session");
                    const multipart = await new Response(req.postDataBuffer(), {
                        headers: { "content-type": req.headers()["content-type"] },
                    }).formData();
                    const data = JSON.parse(multipart.get("dados"));
                    const file = multipart.get("imagem");
                    imagePosts.push({ data, name: file.name, type: file.type, contents: Buffer.from(await file.arrayBuffer()) });
                    if (imagePosts.length === 1) return route.fulfill({ status: 503, json: { detail: "Falha temporária sintética." } });
                    const item = { id: items.length + 1, produtor_id: 2,
                        dados: { ...data, link_capa: "https://example.test/uploaded.png" }, status: "pendente", versao: 1 };
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
            await signIn(page, { next: role === "admin" ? "/admin.html" : "/produtor/portfolio", username: role, password: "synthetic-only" });
            return { page, context };
        }
        const { page, context } = await setup("produtor", 1280);
        await page.locator("#portfolio-submit-titulo").waitFor({ state: "visible" });
        const form = page.locator(".portfolio-submission-form");
        await page.locator("#portfolio-submit-titulo").fill("<img src=x> Faixa sintética");
        await page.locator("#portfolio-submit-artista").fill("Artista sintético");
        await page.locator("#portfolio-submit-categoria").fill("Mixagem");
        await page.locator("#portfolio-submit-link_audio").fill("https://example.test/audio");
        await page.locator("#portfolio-submit-capa_origem").selectOption("link");
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
        await openAdminSection(admin.page, 'section-portfolio');
        await admin.page.getByRole('tab', { name: 'Envios de produtores' }).click();
        const review = admin.page.locator(".portfolio-submission-review");
        await review.getByRole("button", { name: "Recusar", exact: true }).click();
        assert.equal(posts.length, 1, "Refusal needs a reason");
        await review.getByRole("button", { name: "Aprovar e publicar" }).click();
        await admin.page.getByText("Publicado", { exact: true }).waitFor();
        assert.equal(posts.length, 2);
        assert.deepEqual(posts[1], { versao: 1, decisao: "aprovar", motivo: null });
        await admin.page.screenshot({ path: path.join(screenDir, "admin-desktop.png"), fullPage: true });
        const upload = await setup("produtor", 1280);
        const imageForm = upload.page.locator(".portfolio-submission-form");
        await upload.page.locator("#portfolio-submit-titulo").fill("Nova faixa com capa");
        await upload.page.locator("#portfolio-submit-artista").fill("Artista sintético");
        await upload.page.locator("#portfolio-submit-categoria").fill("Mixagem");
        await upload.page.locator("#portfolio-submit-link_audio").fill("https://example.test/audio");
        await upload.page.locator("#portfolio-submit-autorizacao_artista").check();
        const picker = upload.page.locator("#portfolio-submit-imagem");
        await picker.setInputFiles({ name: "not-a-cover.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg/>") });
        await imageForm.locator("button[type=submit]").click();
        assert.equal(imagePosts.length, 0, "Invalid file type must not be uploaded");
        assert.ok(await picker.evaluate(el => el.validationMessage.length > 0));
        const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64");
        await picker.setInputFiles({ name: "cover.png", mimeType: "image/png", buffer: png });
        await upload.page.getByRole("dialog", { name: "Ajustar imagem" }).getByRole("button", { name: "Usar corte" }).click();
        const preview = upload.page.locator(".portfolio-cover-preview");
        await preview.waitFor({ state: "visible" });
        await upload.page.waitForFunction(() => document.querySelector(".portfolio-cover-preview")?.naturalWidth > 0);
        await upload.page.locator("#portfolio-submit-capa_origem").selectOption("link");
        assert.equal(await picker.isDisabled(), true);
        assert.equal(await preview.isVisible(), false);
        await upload.page.locator("#portfolio-submit-capa_origem").selectOption("arquivo");
        assert.equal(await preview.isVisible(), true);
        await upload.page.evaluate(() => scrollTo(0, 0));
        await upload.page.screenshot({ path: path.join(screenDir, "producer-image-desktop.png"), fullPage: true });
        await upload.page.setViewportSize({ width: 390, height: 844 });
        assert.ok(await upload.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await upload.page.screenshot({ path: path.join(screenDir, "producer-image-mobile.png"), fullPage: true });
        await imageForm.locator("button[type=submit]").click();
        await upload.page.waitForFunction(() => [...document.querySelectorAll(".upload-tasks-dialog li span")]
            .some(item => item.textContent === "O servidor não concluiu o envio. Tente novamente."));
        assert.equal(imagePosts.length, 1);
        await imageForm.locator("button[type=submit]").click();
        await upload.page.waitForFunction(() => [...document.querySelectorAll(".upload-tasks-dialog li span")]
            .some(item => item.textContent === "Concluído"));
        assert.equal(imagePosts.length, 2);
        assert.deepEqual(imagePosts[0], imagePosts[1], "Retry keeps the UUID, metadata and exact image bytes");
        assert.equal(imagePosts[1].contents.readUInt32BE(16), 1600);
        assert.equal(imagePosts[1].contents.readUInt32BE(20), 900);
        assert.equal(imagePosts[1].type, "image/png");
        assert.equal(imagePosts[1].name, "cover.png");
        assert.equal(imagePosts[1].data.autorizacao_artista, true);
        for (const field of ["link_capa", "capa_origem", "imagem"]) assert.equal(field in imagePosts[1].data, false);
        assert.equal(items.length, 2);
        await upload.context.close();
        assert.deepEqual(errors, []);
        console.log("portfolio_submissions=passed; screenshots=" + screenDir);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
