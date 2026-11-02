// Work in progress everywhere: the tag manager regenerates every preview in a queue (double
// confirmation, live progress ring), the notification bell turns while something runs and
// its panel lists "Em andamento" (uploads with thumbnail, size, time and progress; server
// work such as previews being generated) above the history (thumbnail, context, date/time).
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { openAdminSection, signIn } = require("./support/access.cjs");

const root = path.resolve(__dirname, "..");
const PIXEL = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: "block" });
    // Upload worker stand-in: reports progress like the real one, then completes.
    await context.addInitScript(() => {
        const listeners = new Set();
        const emit = task => listeners.forEach(listener => listener({ data: { type: "mirai-upload-task", task: { ...task } } }));
        window.__finishUpload = null;
        const registration = { active: { postMessage: message => {
            if (message.type === "mirai-upload-list") return;
            const task = { id: message.id, label: message.label, owner: message.owner, meta: message.meta, size: message.size,
                status: "uploading", progress: 0.4, message: "", createdAt: Date.now(), updatedAt: Date.now() };
            emit(task);
            window.__finishUpload = () => { task.status = "completed"; task.progress = 1; task.updatedAt = Date.now(); emit(task); };
        } } };
        Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: {
            register: async () => registration,
            ready: Promise.resolve(registration),
            addEventListener: (type, listener) => { if (type === "message") listeners.add(listener); },
        } });
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    let lote = null;
    const posts = [];
    const now = new Date().toISOString();
    await context.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") {
            const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            const types = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png" };
            try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
            catch { return route.fulfill({ status: 404, body: "" }); }
        }
        if (url.hostname === "res.cloudinary.com") return route.fulfill({ body: PIXEL, contentType: "image/png" });
        if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 200, body: "" });
        const admin = { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true };
        if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "synthetic-admin", user: admin } });
        if (url.pathname === "/auth/me") return route.fulfill({ json: admin });
        if (url.pathname === "/admin/audio-tag") return route.fulfill({ json: { versao: 3, nome: "mirai.wav", tag_id: 4, intervalo_segundos: 10,
            volume_percentual: 40, nivelamento_automatico: true, alvo_relativo_db: -3, ganho_min_db: -40, ganho_max_db: 30,
            silencio_lufs: -60, limiter_dbfs: -0.9, padrao_disponivel: true } });
        if (url.pathname === "/admin/audio-tag/preview/opcoes") return route.fulfill({ json: { tags: [], fontes: [] } });
        if (url.pathname === "/admin/audio-tag/previas/lote") {
            if (request.method() === "POST") {
                posts.push("lote");
                lote = { id: 7, total: 8, concluidos: 2, erros: 0, pendentes: 6, sem_tag: 1, progresso: 0.25, em_andamento: true,
                    created_at: now, concluido_em: null };
                return route.fulfill({ status: 202, json: { lote } });
            }
            return route.fulfill({ json: { lote } });
        }
        if (url.pathname === "/admin/notificacoes/atividades") return route.fulfill({ json: { ativas: 2, itens: [
            { id: "lote:7", tipo: "lote_previas", titulo: "Gerando todas as prévias de novo", detalhe: "2 de 8 prontas", estado: "processando",
                progresso: 0.25, criado_em: now, concluido_em: null, url: "/admin.html#section-custos", miniatura: null },
            { id: "previa:41", tipo: "previa", titulo: "Gerando prévia com tag", detalhe: "rough.wav · #12 Faixa <b>A</b>", estado: "processando",
                progresso: null, criado_em: now, concluido_em: null, url: "/admin.html#section-producoes", miniatura: null },
            { id: "previa:40", tipo: "previa", titulo: "Prévia com tag pronta", detalhe: "intro.wav · #12 Faixa A", estado: "concluido",
                progresso: null, criado_em: now, concluido_em: now, url: "/admin.html#section-producoes", miniatura: null },
        ] } });
        if (url.pathname === "/admin/notificacoes" && request.method() === "GET") return route.fulfill({ json: {
            nao_vistas: 0, tem_mais: false, itens: [
                { id: 90, tipo: "admin_beat_revisao", texto: "Um beat foi enviado para revisão.", url: "/admin.html#section-beats",
                    created_at: now, vista_em: now, contexto: "Noite <img src=x>", miniatura: "https://res.cloudinary.com/demo/capa.png" },
                { id: 89, tipo: "admin_falha_tag", texto: "Uma prévia ficou sem tag de áudio.", url: "/admin.html#dashboard-menu",
                    created_at: now, vista_em: now, contexto: "#12 Faixa A · rough.wav", miniatura: null },
            ] } });
        if (url.pathname === "/upload-alvo") return route.fulfill({ status: 201, json: { ok: true } });
        if (url.pathname === "/config") return route.fulfill({ json: {} });
        if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        return route.fulfill({ json: [] });
    });

    try {
        await signIn(page, { next: "/admin.html", username: "admin" });
        await page.waitForFunction(() => !document.getElementById("admin-area").classList.contains("hidden"));
        const bell = page.locator(".portal-notifications-button");
        await bell.waitFor();
        await page.waitForFunction(() => document.querySelector(".portal-notifications-button")?.classList.contains("is-busy"));
        assert.match(await bell.getAttribute("aria-label"), /2 em andamento/);

        // Tag manager: one button regenerates every preview, behind a double confirmation.
        await openAdminSection(page, "section-custos");
        const batch = page.locator(".audio-tag-batch");
        await batch.waitFor();
        const start = batch.getByRole("button", { name: "Gerar todas as prévias de novo" });
        await start.click();
        const dialog = page.getByRole("alertdialog");
        await dialog.waitFor();
        assert.match(await dialog.textContent(), /a prévia antiga continua tocando/i);
        const confirm = dialog.getByRole("button", { name: "Gerar todas" });
        assert.equal(await confirm.isDisabled(), true);
        await dialog.getByLabel("Digite GERAR para confirmar").fill("gerar");
        await confirm.click();
        await batch.locator(".activity-item").waitFor();
        assert.deepEqual(posts, ["lote"]);
        const row = batch.locator(".activity-item");
        assert.match(await row.textContent(), /Gerando todas as prévias de novo/);
        assert.match(await row.textContent(), /2 de 8 prontas · 1 sem tag cadastrada/);
        assert.match(await row.textContent(), /25% · uma por vez/);
        assert.equal(await row.locator(".activity-ring").getAttribute("aria-label"), "Processando: 25%");
        assert.equal(await row.locator(".activity-ring__value").textContent(), "25");
        assert.equal(await batch.getByRole("button", { name: "Geração em andamento" }).isDisabled(), true);
        assert.match(await batch.locator("[role=status]").textContent(), /8 prévias na fila/);

        // An upload: thumbnail of the image, file names, size and progress, then the time it was sent.
        await page.evaluate(async () => {
            const { enqueueUpload } = await import("/js/modules/upload_tasks.js");
            const form = new FormData();
            const png = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="), c => c.charCodeAt(0));
            form.append("capa", new File([png], "capa.png", { type: "image/png" }));
            form.append("mp3", new File([new Uint8Array(2048)], "beat.mp3", { type: "audio/mpeg" }));
            await enqueueUpload("/upload-alvo", form, { label: "Beat · Noite" });
        });

        // Notification panel: "Em andamento" first, history after.
        await bell.click();
        const panel = page.locator(".portal-notifications-dialog");
        await panel.waitFor();
        const activity = panel.locator(".notifications-activity");
        await activity.waitFor();
        const items = activity.locator(".activity-item");
        await page.waitForFunction(() => document.querySelectorAll(".notifications-activity .activity-item").length === 4);
        const upload = items.filter({ hasText: "Beat · Noite" });
        assert.match(await upload.textContent(), /capa\.png, beat\.mp3 · 2,1 KB/);
        assert.match(await upload.textContent(), /Enviando 40%/);
        assert.equal(await upload.locator(".activity-ring").getAttribute("aria-label"), "Enviando: 40%");
        assert.match(await upload.locator(".activity-thumb img").getAttribute("src"), /^blob:/);
        const generating = items.filter({ hasText: "Gerando prévia com tag" });
        assert.equal(await generating.locator(".activity-ring").getAttribute("class"), "activity-ring activity-ring--processando is-indeterminate");
        assert.equal(await generating.locator("b").count(), 0, "server text is not HTML");
        assert.match(await items.filter({ hasText: "Prévia com tag pronta" }).locator(".activity-ring").getAttribute("aria-label"), /Concluído/);
        assert.match(await upload.locator("time").textContent(), /^Iniciado hoje, \d\d:\d\d$/);
        await page.evaluate(() => window.__finishUpload());
        await page.waitForFunction(() => [...document.querySelectorAll(".notifications-activity .activity-item")]
            .some(item => item.textContent.includes("Beat · Noite") && item.dataset.state === "concluido"));
        assert.match(await upload.locator("time").textContent(), /^Enviado hoje, \d\d:\d\d$/);
        assert.equal(await upload.locator(".activity-ring").getAttribute("aria-label"), "Concluído");

        // History rows: thumbnail, context and date/time.
        const history = panel.locator(".notification-row");
        await history.first().waitFor({ timeout: 5000 }).catch(async () => {
            throw new Error(`history missing: ${await panel.locator("[role=status]").textContent()} | ${errors.join(" | ")} | ${await panel.innerHTML()}`.slice(0, 2500));
        });
        assert.equal(await history.count(), 2);
        assert.equal(await history.first().locator(".activity-thumb img").getAttribute("src"), "https://res.cloudinary.com/demo/capa.png");
        assert.equal(await history.first().locator(".notification-row__context").textContent(), "Noite <img src=x>");
        assert.equal(await history.first().locator(".notification-row__context img").count(), 0);
        assert.match(await history.first().locator("time").textContent(), /\d\d\/\d\d\/\d{4},? \d\d:\d\d/);
        assert.equal(await history.nth(1).locator(".activity-thumb img").count(), 0);
        assert.equal(await history.nth(1).locator(".activity-thumb svg").count(), 1);

        // The "Envios" list shows the same rich row.
        await panel.getByRole("button", { name: "Fechar" }).click();
        const uploadsButton = page.locator(".upload-tasks-button");
        await uploadsButton.click();
        const uploads = page.locator(".upload-tasks-dialog .activity-item");
        assert.equal(await uploads.count(), 1);
        assert.equal(await uploads.first().getAttribute("data-state"), "completed");
        assert.match(await uploads.first().textContent(), /Concluído/);

        // Phone width: rows fit.
        await page.setViewportSize({ width: 390, height: 844 });
        const overflow = await page.evaluate(() => document.querySelector(".upload-tasks-dialog").scrollWidth
            - document.querySelector(".upload-tasks-dialog").clientWidth);
        assert.ok(overflow <= 1, `upload dialog overflow ${overflow}`);
        if (process.env.SHOTS) {
            await page.screenshot({ path: path.join(process.env.SHOTS, "activity-uploads-mobile.png") });
            await page.setViewportSize({ width: 1280, height: 900 });
            await page.keyboard.press("Escape");
            await bell.click();
            await page.waitForTimeout(300);
            await page.screenshot({ path: path.join(process.env.SHOTS, "activity-notifications.png") });
            await page.keyboard.press("Escape");
            await batch.scrollIntoViewIfNeeded();
            await page.screenshot({ path: path.join(process.env.SHOTS, "activity-batch.png") });
        }
        assert.deepEqual(errors, []);
        console.log("PASS: batch regeneration with progress, uploads with thumbnail/size/time/progress, Em andamento and rich history.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
