const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const requests = [];

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
        await context.route("**/*", async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 404 });
            if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "audit-token", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
            if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            if (url.pathname === "/audit-logs") {
                requests.push(url.search);
                const pageNumber = Number(url.searchParams.get("page") || 1);
                return route.fulfill({ json: {
                    items: pageNumber === 1 ? [{
                        id: 2,
                        actor_user_id: 1,
                        actor_username: "<img src=x onerror=alert(1)>",
                        action: "production.status_changed",
                        entity_type: "production",
                        entity_id: "9",
                        metadata: { old_status: "aguardando_inicio", new_status: "<script>alert(1)</script>", ignored: "secret" },
                        request_id: "request-001",
                        created_at: "2026-09-14T12:00:00Z",
                    }] : [{ id: 1, actor_user_id: null, actor_username: null, action: "user.created", entity_type: "user", entity_id: "3", metadata: {}, request_id: null, created_at: "2026-09-13T12:00:00Z" }],
                    total: 26,
                    page: pageNumber,
                    page_size: 25,
                    pages: 2,
                } });
            }
            if (["/config", "/servicos", "/projetos", "/orcamentos", "/producoes", "/clientes", "/usuarios", "/usuarios/produtores", "/newsletter/subscribers", "/newsletter/campaigns"].includes(url.pathname)) return route.fulfill({ json: url.pathname === "/config" ? {} : [] });
            return route.fulfill({ status: 404, json: { detail: "not found" } });
        });

        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("password");
        await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
        await page.locator('[data-admin-target="section-auditoria"]').click();
        await page.waitForSelector(".audit-table-view tbody tr");
        assert.equal(await page.locator("#audit-list img, #audit-list script").count(), 0);
        assert.match(await page.locator("#audit-list").textContent(), /<img src=x/);
        assert.match(await page.locator("#audit-list").textContent(), /<script>alert/);
        assert.doesNotMatch(await page.locator("#audit-list").textContent(), /secret/);

        await page.locator("#audit-action-filter").selectOption("production.status_changed");
        await page.locator("#audit-entity-id-filter").fill("9");
        const filteredResponse = page.waitForResponse(response => response.url().includes("action=production.status_changed") && response.url().includes("entity_id=9"));
        await page.locator("#audit-apply-filters").click();
        await filteredResponse;
        assert.ok(requests.some(query => query.includes("action=production.status_changed") && query.includes("entity_id=9")));

        const nextResponse = page.waitForResponse(response => response.url().includes("page=2"));
        await page.locator("#audit-next-page").click();
        await nextResponse;
        await page.waitForFunction(() => document.getElementById("audit-page-label")?.textContent.includes("2 de 2"));
        assert.ok(requests.some(query => query.includes("page=2")));

        for (const width of [320, 768, 1024]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.locator(".audit-mobile-view").isVisible(), width <= 768);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
        }
        await page.evaluate(() => window.fazerLogout());
        assert.equal(await page.locator("#audit-list").textContent(), "");
        assert.deepEqual(errors, []);
        console.log("PASS: audit list, filters, pagination, safe metadata, responsive cards and logout cleanup.");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
