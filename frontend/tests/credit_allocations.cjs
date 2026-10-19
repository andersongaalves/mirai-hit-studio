const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const root = path.resolve(__dirname, "..");

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        await page.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin !== "http://localhost:4173") return route.abort();
            if (url.pathname === "/fixture") return route.fulfill({ contentType: "text/html", body: '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/css/main.css"><link rel="stylesheet" href="/css/pages/admin.css"><link rel="stylesheet" href="/css/integrado.css"><link rel="stylesheet" href="/css/pages/integrado-admin.css"><link rel="stylesheet" href="/css/components/service-credits.css"><body class="integrado-admin"><main class="admin-main"><div class="admin-container"><section class="producao-detail-block"><h3>Créditos vinculados</h3><div id="root"></div></section></div></main></body>' });
            const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            const types = { ".js": "text/javascript", ".css": "text/css", ".ttf": "font/ttf", ".woff2": "font/woff2" };
            return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" });
        });
        await page.goto("http://localhost:4173/fixture");
        await page.evaluate(async () => {
            const { creditAllocationsPanel } = await import("/js/modules/credit_allocations.js");
            window.calls = [];
            window.reloads = 0;
            window.fail = true;
            window.render = data => document.getElementById("root").replaceChildren(creditAllocationsPanel(data, {
                onReserve: async payload => { window.calls.push(payload); if (window.fail) throw new Error("Falha sintética; repita com segurança."); },
                onMove: async (id, payload) => window.calls.push({ id, ...payload }),
                onReload: async () => { window.reloads++; },
            }));
            window.data = { producao_status: "aguardando_inicio", pode_reservar: true, mensagem: null,
                lotes: [{ id: 1, servico_nome: "Mix <img src=x>", unidade: "canal", disponivel: "20.000" }],
                alocacoes: [{ id: 8, servico_nome: "Mix", unidade: "canal", quantidade: "5.000", estado: "reservada" }] };
            window.render(window.data);
        });
        await page.locator("#credit-allocation-quantity").fill("5");
        await page.getByRole("button", { name: "Reservar créditos" }).click();
        assert.equal(await page.evaluate(() => calls.length), 0, "Reason is mandatory");
        await page.locator("#credit-allocation-reason").fill("Reserva de teste");
        await page.getByRole("button", { name: "Reservar créditos" }).click();
        await page.getByText("Falha sintética; repita com segurança.").waitFor();
        await page.getByRole("button", { name: "Reservar créditos" }).click();
        const calls = await page.evaluate(() => calls);
        assert.equal(calls.length, 2);
        assert.equal(calls[0].idempotency_key, calls[1].idempotency_key);
        assert.equal(calls[0].quantidade, "5");
        assert.equal(await page.locator("img").count(), 0);
        await page.evaluate(() => { window.fail = false; });
        await page.getByRole("button", { name: "Reservar créditos" }).click();
        await page.waitForFunction(() => reloads === 1);
        await page.getByRole("button", { name: "Devolver reserva" }).click();
        await page.waitForFunction(() => reloads === 2);
        assert.equal((await page.evaluate(() => calls.at(-1))).tipo, "devolucao");
        await page.evaluate(() => { window.render({ ...data, producao_status: "em_producao", pode_reservar: false }); });
        assert.equal(await page.getByRole("button", { name: "Devolver reserva" }).count(), 0);
        assert.equal(await page.getByRole("button", { name: "Reservar créditos" }).count(), 0);
        await page.locator("#credit-allocation-reason").fill("Uso de teste");
        await page.getByRole("button", { name: "Confirmar uso" }).click();
        await page.waitForFunction(() => reloads === 3);
        assert.equal((await page.evaluate(() => calls.at(-1))).tipo, "consumo");
        await page.evaluate(() => { window.render({ ...data, alocacoes: [{ ...data.alocacoes[0], estado: "consumida" }] }); });
        await page.locator("#credit-allocation-reason").fill("Correção justificada");
        await page.getByRole("button", { name: "Estornar uso" }).click();
        await page.waitForFunction(() => reloads === 4);
        assert.equal((await page.evaluate(() => calls.at(-1))).tipo, "estorno");
        const output = path.join(os.tmpdir(), "mirai-credit-allocations");
        await fs.mkdir(output, { recursive: true });
        for (const width of [1280, 390]) {
            await page.setViewportSize({ width, height: 900 });
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.screenshot({ path: path.join(output, `allocation-${width}.png`), fullPage: true });
        }
        await page.evaluate(async () => {
            const { creditProductionForm } = await import("/js/modules/credit_production.js");
            window.creationCalls = [];
            window.created = null;
            window.creationFailure = true;
            document.getElementById("root").replaceChildren(creditProductionForm([
                { id: 1, servico_nome: "Mix", unidade: "canal", disponivel: "20.000" },
            ], {
                loadProducers: async () => [{ id: 9, username: "synthetic-producer", nome_exibicao: "Produtor sintético" }],
                onCreate: async payload => {
                    window.creationCalls.push(payload);
                    if (window.creationFailure) throw new Error("Resposta sintética indisponível.");
                    return { producao_id: 42 };
                },
                onCreated: async result => { window.created = result; },
            }));
        });
        await page.getByRole("button", { name: "Nova produção com créditos" }).click();
        await page.getByLabel("Título da produção").fill("Faixa sintética");
        await page.getByLabel("Quantidade", { exact: true }).fill("5");
        await page.getByLabel("Produtor responsável").selectOption("9");
        await page.getByLabel("Motivo da reserva").fill("Uso contratado");
        await page.getByRole("button", { name: "Criar produção e reservar" }).click();
        await page.getByText("Resposta sintética indisponível.").waitFor();
        await page.evaluate(() => { window.creationFailure = false; });
        await page.getByRole("button", { name: "Criar produção e reservar" }).click();
        await page.waitForFunction(() => created?.producao_id === 42);
        const creationCalls = await page.evaluate(() => creationCalls);
        assert.equal(creationCalls.length, 2);
        assert.equal(creationCalls[0].idempotency_key, creationCalls[1].idempotency_key);
        assert.equal(creationCalls[0].produtor_id, 9);
        assert.equal(creationCalls[0].quantidade, "5");
        console.log("CREDIT_ALLOCATIONS_UI_PASS");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
