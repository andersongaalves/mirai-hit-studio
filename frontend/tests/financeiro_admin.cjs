const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
let reconciliations = 0;
const financeQueries = [];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(file), contentType: { ".js": "text/javascript", ".css": "text/css", ".html": "text/html" }[path.extname(file)] || "application/octet-stream" });
    } catch { return route.fulfill({ status: 404, body: "" }); }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 1024, height: 800 }, permissions: ["clipboard-read", "clipboard-write"] });
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("dialog", dialog => dialog.accept());
        await context.route("**/*", async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 404 });
            if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "finance-token", user: { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true } } });
            if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            if (url.pathname === "/financeiro/resumo") return route.fulfill({ json: { valor_a_receber: "60.00", valor_recebido: "40.00", cobrancas_parciais: 1, pagamentos_em_atencao: 1, total_cobrancas: 1 } });
            if (url.pathname === "/financeiro/cobrancas/7") return route.fulfill({ json: {
                id: 7, proposta_id: 2, proposta_numero: "P-001", cliente_nome: "<img src=x onerror=alert(1)>", cliente_email: "safe@example.com",
                valor_total: "100.00", valor_pago: "40.00", saldo_pendente: "60.00", status: "parcialmente_paga", reconciliation_status: "conflict",
                vencimento: null, created_at: "2026-09-20T12:00:00Z", updated_at: "2026-09-20T12:00:00Z", checkout_url: "https://mirai.example/checkout/token",
                pagamentos: [{ id: 9, tipo: "entrada", valor: "40.00", status: "aprovado", metodo: "pix", provider: "mercado_pago", provider_order_id: "order-9", reconciliation_status: "conflict", reconciliation_reason: "amount_mismatch", aprovado_em: null, reembolsado_em: null, created_at: "2026-09-20T12:00:00Z", updated_at: "2026-09-20T12:00:00Z" }],
            } });
            if (url.pathname === "/financeiro/cobrancas") {
                financeQueries.push(url.search);
                if (url.searchParams.get("search") === "fail") return route.fulfill({ status: 503, json: { detail: "Falha sintética." } });
                const pageNumber = Number(url.searchParams.get("page") || 1);
                const items = url.searchParams.get("search") === "empty" ? [] : [{ id: 7, proposta_id: 2, proposta_numero: "P-001", cliente_nome: "<img src=x onerror=alert(1)>", valor_total: "100.00", valor_pago: "40.00", saldo_pendente: "60.00", status: "parcialmente_paga", reconciliation_status: "conflict", vencimento: null, created_at: "2026-09-20T12:00:00Z", updated_at: "2026-09-20T12:00:00Z" }];
                return route.fulfill({ json: { items, total: items.length ? 26 : 0, page: pageNumber, page_size: 25, pages: items.length ? 2 : 0 } });
            }
            if (url.pathname === "/financeiro/pagamentos/9/reconciliar") { reconciliations++; return route.fulfill({ json: { payment_id: 9, previous_status: "pendente", current_status: "aprovado", changed: true, outcome: "updated" } }); }
            if (url.pathname === "/audit-logs") return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 25, pages: 0 } });
            if (["/config", "/servicos", "/projetos/admin", "/orcamentos", "/producoes", "/clientes", "/usuarios", "/usuarios/produtores", "/newsletter/subscribers", "/newsletter/campaigns"].includes(url.pathname)) return route.fulfill({ json: url.pathname === "/config" ? {} : [] });
            return route.fulfill({ status: 404, json: { detail: "not found" } });
        });

        await page.goto("http://localhost:4173/admin.html");
        await page.locator("#username").fill("admin");
        await page.locator("#password").fill("password");
        await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
        await page.locator('[data-admin-target="section-financeiro"]').click();
        await page.waitForSelector(".financeiro-table-view tbody tr");
        assert.match(await page.locator("#financeiro-metrics").textContent(), /R\$\s*60,00/);
        assert.equal(await page.locator("#financeiro-list img, #financeiro-list script").count(), 0);
        assert.match(await page.locator("#financeiro-list").textContent(), /<img src=x/);

        await page.locator("#financeiro-status-filter").selectOption("parcialmente_paga");
        await page.locator("#financeiro-reconciliation-filter").selectOption("conflict");
        const filteredResponse = page.waitForResponse(response => {
            const url = new URL(response.url());
            return url.pathname === "/financeiro/cobrancas" &&
                url.searchParams.get("status") === "parcialmente_paga" &&
                url.searchParams.get("reconciliation_status") === "conflict";
        });
        await page.locator("#financeiro-apply-filters").click();
        await filteredResponse;
        await page.waitForFunction(() => document.getElementById("financeiro-summary")?.textContent.includes("26 cobranças"));
        assert.ok(financeQueries.some(query => query.includes("status=parcialmente_paga") && query.includes("reconciliation_status=conflict")));
        await page.locator("#financeiro-next-page").click();
        await page.waitForFunction(() => document.getElementById("financeiro-page-label")?.textContent.includes("2 de 2"));
        assert.ok(financeQueries.some(query => query.includes("page=2")));

        await page.locator(".financeiro-table-view tbody tr button").click();
        await page.waitForSelector("#modal-financeiro:not(.hidden)");
        assert.equal(await page.locator("#modal-financeiro img, #modal-financeiro script").count(), 0);
        assert.match(await page.locator("#financeiro-payments").textContent(), /Valor divergente/);
        await page.getByRole("button", { name: "Copiar link do checkout" }).click();
        assert.equal(await page.evaluate(() => navigator.clipboard.readText()), "https://mirai.example/checkout/token");
        await page.getByRole("button", { name: "Conciliar com provider" }).click();
        await page.waitForFunction(() => document.querySelector("#financeiro-payments")?.textContent.includes("Conciliar com provider"));
        assert.equal(reconciliations, 1);

        await page.keyboard.press("Escape");
        assert.equal(await page.locator("#modal-financeiro").getAttribute("aria-hidden"), "true");
        assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Detalhes");

        await page.locator("#financeiro-search").fill("empty");
        await page.locator("#financeiro-apply-filters").click();
        await page.waitForFunction(() => document.getElementById("financeiro-list")?.textContent.includes("Nenhuma cobrança encontrada"));
        await page.locator("#financeiro-search").fill("fail");
        await page.locator("#financeiro-apply-filters").click();
        await page.waitForFunction(() => document.getElementById("financeiro-list")?.textContent.includes("Falha sintética"));
        await page.locator("#financeiro-clear-filters").click();
        await page.waitForSelector(".financeiro-table-view tbody tr");
        for (const width of [320, 768, 1024]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.locator(".financeiro-mobile-view").isVisible(), width <= 768);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
        }
        await page.evaluate(() => window.fazerLogout());
        assert.equal(await page.locator("#financeiro-list").textContent(), "");
        assert.deepEqual(errors, []);
        console.log("PASS: finance summary, safe list/detail, reconciliation, responsive cards and logout cleanup.");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
