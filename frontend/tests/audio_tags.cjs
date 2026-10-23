const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const root = path.resolve(__dirname, "..");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: "block" });
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
                    task.message = response.ok ? "Envio concluído." : "O envio foi recusado.";
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
        const page = await context.newPage();
        const errors = [];
        const writes = [];
        let conflict = false;
        let state = { versao: 0, nome: null, tag_id: null, intervalo_segundos: 10, volume_percentual: 40, padrao_disponivel: false };
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/*", async route => {
            const req = route.request(), url = new URL(req.url());
            if (url.origin === "http://localhost:4173") {
                const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
                assert.ok(file.startsWith(root + path.sep));
                const types = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".ttf": "font/ttf" };
                try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
                catch { return route.fulfill({ status: 404, body: "" }); }
            }
            if (url.origin !== "http://localhost:8000") return route.abort();
            const user = { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true };
            if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "synthetic-only", user } });
            if (url.pathname === "/auth/me") return route.fulfill({ json: user });
            if (url.pathname === "/admin/audio-tag") {
                if (req.method() === "PUT") {
                    writes.push(req.postDataJSON());
                    if (conflict) return route.fulfill({ status: 409, json: { detail: "A configuração foi alterada. Recarregue antes de salvar." } });
                    state = { ...state, ...req.postDataJSON(), versao: state.versao + 1 };
                    // A slower response must not let the next action race the form reload.
                    await new Promise(resolve => setTimeout(resolve, 150));
                }
                if (req.method() === "POST") {
                    writes.push({ upload: req.postData() });
                    state = { ...state, versao: state.versao + 1, nome: "Tag sintética.wav", tag_id: 1, padrao_disponivel: true };
                }
                return route.fulfill({ json: state });
            }
            if (url.pathname === "/config") return route.fulfill({ json: {} });
            if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            if (url.pathname === "/config/portfolio-segments") return route.fulfill({ json: { segments: [] } });
            return route.fulfill({ json: [] });
        });
        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("synthetic-only");
        await page.waitForFunction(() => typeof window.fazerLogin === "function");
        await page.evaluate(() => window.fazerLogin());
        await page.waitForFunction(() => document.getElementById("admin-area")?.classList.contains("hidden") === false);
        await page.evaluate(() => window.mostrarSecao("section-custos"));
        await page.getByRole("tab", { name: "Portais", exact: true }).click();
        await page.waitForFunction(() => document.getElementById("admin-config-portals-tab")?.getAttribute("aria-selected") === "true");
        const panel = page.locator("#audio-tag-settings");
        await panel.getByText("Nenhuma tag cadastrada.", { exact: true }).waitFor();
        await panel.locator('[name="intervalo_segundos"]').fill("15");
        await panel.locator('[name="volume_percentual"]').fill("25");
        const previousParameters = await panel.locator('form').nth(1).elementHandle();
        await panel.getByRole("button", { name: "Salvar parâmetros" }).click();
        await page.waitForFunction(form => !form.isConnected, previousParameters);
        await panel.getByRole("button", { name: "Salvar parâmetros" }).waitFor();
        assert.equal(await panel.locator('[name="intervalo_segundos"]').inputValue(), "15");
        assert.equal(await panel.locator('[name="volume_percentual"]').inputValue(), "25");
        assert.deepEqual(writes[0], { versao: 0, intervalo_segundos: 15, volume_percentual: 25 });
        await panel.locator('input[type="file"]').setInputFiles({ name: "tag.wav", mimeType: "audio/wav", buffer: Buffer.from("synthetic-audio-boundary") });
        await panel.getByRole("button", { name: "Cadastrar tag" }).click();
        await panel.getByText("Tag sintética.wav", { exact: true }).waitFor();
        assert.match(writes[1].upload, /name="versao"\r\n\r\n1/);
        assert.equal(await panel.getByRole("button", { name: "Trocar tag" }).count(), 1);
        conflict = true;
        await panel.getByRole("button", { name: "Salvar parâmetros" }).click();
        await panel.getByText("A configuração foi alterada. Recarregue antes de salvar.", { exact: true }).waitFor();
        const shots = path.join(os.tmpdir(), "mirai-audio-tags");
        await fs.mkdir(shots, { recursive: true });
        await page.screenshot({ path: path.join(shots, "admin-desktop.png"), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        assert.ok(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
        await page.screenshot({ path: path.join(shots, "admin-mobile.png"), fullPage: true });
        // The client only gets the processed version, without remounting its upload form.
        await page.evaluate(async () => {
            const { renderDetail, updateProcessedPreviews } = await import("/js/cliente/ui.js");
            const host = document.createElement("div");
            host.id = "client-detail-content";
            document.body.append(host);
            const file = { id: 7, tipo: "previa", nome_exibicao: "preview.wav", mime_type: "audio/wav", versao: 1,
                tamanho_bytes: 1024, created_at: new Date().toISOString(), processamento_tag: "pendente" };
            renderDetail({ id: 1, titulo: "Faixa", status: "em_producao", etapas: "[]" }, [file], {}, {});
            window.__uploadForm = host.querySelector("form");
            if (host.querySelector('[data-preview-file-id="7"] button')) throw new Error("Pending preview exposes download");
            updateProcessedPreviews([{ ...file, processamento_tag: "pronto", mime_type: "audio/mpeg" }], { onDownload() {}, onPreview() {} });
            if (host.querySelectorAll('[data-preview-file-id="7"] button').length !== 2) throw new Error("Ready preview missing actions");
            if (host.querySelector("form") !== window.__uploadForm) throw new Error("Upload form was remounted");
        });
        assert.deepEqual(errors, []);
        console.log("audio_tags=passed; screenshots=" + shots);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
