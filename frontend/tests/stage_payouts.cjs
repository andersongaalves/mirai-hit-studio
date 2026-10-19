const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const root = path.resolve(__dirname, "..");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const screenshots = await fs.mkdtemp(path.join(os.tmpdir(), "mirai-stage-payouts-"));
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin !== "http://localhost:4173") return route.abort();
            if (url.pathname === "/fixture") return route.fulfill({ contentType: "text/html", body: '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/css/main.css"><link rel="stylesheet" href="/css/pages/admin.css"><link rel="stylesheet" href="/css/integrado.css"><link rel="stylesheet" href="/css/pages/integrado-admin.css"><link rel="stylesheet" href="/css/components/stage-payouts.css"><body class="integrado-admin"><main class="admin-main"><div class="admin-container"><section class="producao-detail-block"><h3>Repasses por etapa</h3><div id="root"></div></section><div id="producer-payouts"></div></div></main></body>' });
            const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            const types = { ".js": "text/javascript", ".css": "text/css", ".ttf": "font/ttf", ".woff2": "font/woff2" };
            try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
            catch { return route.fulfill({ status: 404, body: "" }); }
        });
        await page.goto("http://localhost:4173/fixture");
        await page.evaluate(async () => {
            const { stagePayoutsPanel } = await import("/js/modules/stage_payouts.js");
            window.calls = [];
            window.reloads = 0;
            window.fail = true;
            window.rows = [
                { id: null, etapa_id: 1, etapa_nome: "Mix <img src=x onerror=alert(1)>", bruto_centavos: 50000, produtor_centavos: 40000, mirai_centavos: 10000, estado: "a_receber" },
                { id: null, etapa_id: 2, etapa_nome: "Masterizacao", bruto_centavos: 30000, produtor_centavos: 24000, mirai_centavos: 6000, estado: "bloqueado", bloqueio: "Quitacao pendente." },
            ];
            window.render = () => document.getElementById("root").replaceChildren(stagePayoutsPanel(rows, {
                files: [{ id: 10, tipo: "comprovante", nome_exibicao: "Recibo sintetico" }, { id: 11, tipo: "previa", nome_exibicao: "Nao usar como recibo" }],
                onIssue: async () => calls.push({ issue: true }),
                onPay: async (id, data) => { calls.push({ id, ...data }); if (fail) throw new Error("Falha sintetica; repita com seguranca."); },
                onReload: async () => { reloads++; },
            }));
            render();
        });
        await page.getByRole("button", { name: "Registrar repasses elegiveis" }).click();
        assert.equal(await page.evaluate(() => calls.length), 1);
        assert.equal(await page.getByRole("button", { name: "Registrar pagamento", exact: true }).count(), 0);
        await page.evaluate(() => { rows[0].id = 8; render(); });
        await page.getByRole("button", { name: "Registrar pagamento", exact: true }).click();
        assert.equal(await page.evaluate(() => calls.length), 1, "Transfer reference is required");
        await page.locator("#stage-payout-reference-8").fill("TRANSFERENCIA-SINTETICA");
        assert.equal(await page.locator("#stage-payout-receipt-8 option").count(), 2);
        await page.locator("#stage-payout-receipt-8").selectOption("10");
        for (let i = 0; i < 2; i++) {
            await page.getByRole("button", { name: "Registrar pagamento", exact: true }).click();
            await page.getByRole("status").getByText("Falha sintetica; repita com seguranca.").waitFor();
        }
        const calls = await page.evaluate(() => calls);
        assert.equal(calls[1].idempotency_key, calls[2].idempotency_key);
        assert.equal(calls[1].comprovante_arquivo_id, 10);
        await page.evaluate(() => { fail = false; });
        await page.getByRole("button", { name: "Registrar pagamento", exact: true }).click();
        await page.waitForFunction(() => reloads === 2);
        assert.equal(await page.locator("#root img").count(), 0);
        await page.screenshot({ path: path.join(screenshots, "desktop.png"), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, "No horizontal overflow");
        await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
        await page.evaluate(async () => {
            const { renderPayouts } = await import("/js/produtor/ui.js");
            window.receipt = null;
            renderPayouts([{ id: 8, producao_id: 1, producao_titulo: "Mixagem", etapa_nome: "Mix", por_etapa: true,
                valor_combinado: 400, status: "pago", pago_em: "2026-10-19T12:00:00Z", comprovante_arquivo_id: 10 }],
                (id, button, byStage) => { receipt = { id, byStage }; });
        });
        await page.getByRole("button", { name: "Baixar comprovante" }).click();
        assert.deepEqual(await page.evaluate(() => receipt), { id: 8, byStage: true });
        assert.deepEqual(errors, []);
        console.log("PASS: stage payout eligibility, safe text, receipt scope, mandatory reference, retry idempotency, producer receipt route and desktop/mobile layout.");
        console.log(`Screenshots: ${screenshots}`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
