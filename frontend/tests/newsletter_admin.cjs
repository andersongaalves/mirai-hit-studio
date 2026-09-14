const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const now = "2026-09-14T12:00:00Z";
const subscribers = [
    { id: 1, email: "<img src=x onerror=alert(1)>", nome: null, ativo: true, status: "active", source: "site_footer", consent_at: now },
    { id: 2, email: "inactive@example.com", nome: null, ativo: false, status: "unsubscribed", source: "site_footer", consent_at: now },
];
const campaigns = [{ id: 1, titulo_interno: "Novidades", assunto: "Mirai", preview_text: null, body_text: "Conteúdo", status: "draft", created_by_id: 1, created_at: now, updated_at: now, sent_at: null, eligible_subscribers: 1, total_sent: 0, total_failed: 0, total_skipped: 0, deliveries: [] }];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try { return route.fulfill({ body: await fs.readFile(file), contentType: { ".js": "text/javascript", ".css": "text/css", ".html": "text/html" }[path.extname(file)] || "application/octet-stream" }); }
    catch { return route.fulfill({ status: 404, body: "" }); }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 1024, height: 800 } });
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("dialog", dialog => dialog.accept());
        await context.route("**/*", async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 404 });
            if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "newsletter-token", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
            if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 }, pipeline: {}, attention: {}, recent_activity: [] } });
            if (url.pathname === "/newsletter/subscribers" && request.method() === "GET") return route.fulfill({ json: subscribers });
            if (url.pathname === "/newsletter/campaigns" && request.method() === "GET") return route.fulfill({ json: campaigns });
            if (url.pathname === "/newsletter/campaigns" && request.method() === "POST") {
                const payload = request.postDataJSON();
                assert.deepEqual(Object.keys(payload).sort(), ["assunto", "body_text", "preview_text", "titulo_interno"]);
                campaigns.push({ id: 2, ...payload, status: "draft", created_by_id: 1, created_at: now, updated_at: now, sent_at: null, eligible_subscribers: 1, total_sent: 0, total_failed: 0, total_skipped: 0, deliveries: [] });
                return route.fulfill({ status: 201, json: campaigns[1] });
            }
            const campaign = url.pathname.match(/^\/newsletter\/campaigns\/(\d+)$/);
            if (campaign && request.method() === "GET") return route.fulfill({ json: campaigns.find(item => item.id === Number(campaign[1])) });
            if (campaign && request.method() === "PATCH") {
                Object.assign(campaigns.find(item => item.id === Number(campaign[1])), request.postDataJSON());
                return route.fulfill({ json: campaigns.find(item => item.id === Number(campaign[1])) });
            }
            const send = url.pathname.match(/^\/newsletter\/campaigns\/(\d+)\/send$/);
            if (send) {
                const item = campaigns.find(entry => entry.id === Number(send[1]));
                Object.assign(item, { status: "sent", sent_at: now, total_sent: 1, deliveries: [{ id: 1, subscriber_id: 1, recipient_email: "private@example.com", status: "sent", sent_at: now, error_summary: null, provider_message_id: "provider" }] });
                return route.fulfill({ json: item });
            }
            const subscriber = url.pathname.match(/^\/newsletter\/subscribers\/(\d+)$/);
            if (subscriber && request.method() === "PATCH") {
                const item = subscribers.find(entry => entry.id === Number(subscriber[1]));
                Object.assign(item, { ativo: false, status: "unsubscribed" });
                return route.fulfill({ json: item });
            }
            if (["/config", "/servicos", "/projetos", "/orcamentos", "/producoes", "/clientes", "/usuarios", "/usuarios/produtores"].includes(url.pathname)) return route.fulfill({ json: url.pathname === "/config" ? {} : [] });
            return route.fulfill({ status: 404, json: { detail: "not found" } });
        });
        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("password");
        await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
        await page.locator('[data-admin-target="section-newsletter"]').click();
        await page.waitForSelector(".newsletter-campaigns-table tbody tr");
        assert.equal(await page.locator("#newsletter-campaigns-panel").isVisible(), true);
        await page.locator("#newsletter-tab-subscribers").click();
        await page.locator("#newsletter-subscribers-search").fill("img src");
        assert.equal(await page.locator("#newsletter-subscribers-list img, #newsletter-subscribers-list script").count(), 0);
        assert.match(await page.locator("#newsletter-subscribers-list").textContent(), /<img src=x/);
        await page.getByRole("button", { name: "Cancelar inscrição" }).click();
        await page.waitForFunction(() => document.querySelector('#newsletter-subscribers-list')?.textContent.includes('Cancelado'));
        await page.locator("#newsletter-tab-campaigns").click();
        await page.locator("#newsletter-new-campaign").click();
        assert.equal(await page.evaluate(() => document.activeElement?.id), "newsletter-campaign-name");
        await page.locator("#newsletter-campaign-name").fill("Novo");
        await page.locator("#newsletter-campaign-subject").fill("Assunto novo");
        await page.locator("#newsletter-campaign-body").fill("Conteúdo seguro");
        await page.locator("#newsletter-campaign-save").click();
        await page.waitForFunction(() => document.getElementById("modal-newsletter-campaign").classList.contains("hidden"));
        assert.equal(campaigns.length, 2);
        await page.locator(".newsletter-campaigns-table tbody tr").filter({ hasText: "Novidades" }).getByRole("button", { name: "Enviar" }).click();
        await page.waitForSelector("#modal-newsletter-campaign:not(.hidden)");
        await page.locator("#newsletter-campaign-send").click();
        await page.waitForFunction(() => document.getElementById("modal-newsletter-campaign").classList.contains("hidden"));
        assert.equal(campaigns[0].status, "sent");
        for (const width of [320, 768, 1024]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.locator(".newsletter-mobile-view").first().isVisible(), width <= 768);
        }
        await page.evaluate(() => window.fazerLogout());
        assert.equal(await page.locator("#newsletter-campaigns-list").textContent(), "");
        assert.deepEqual(errors, []);
        console.log("PASS: newsletter admin lists, filters, drafts, confirmation, send, cancellation, mobile, logout and XSS safety.");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
