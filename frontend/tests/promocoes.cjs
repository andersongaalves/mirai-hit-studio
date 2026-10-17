const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const PAGE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/css/variables.css"><link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/pages/admin.css"><link rel="stylesheet" href="/css/pages/calculator.css">
</head><body><main style="padding:16px"><div id="editor"></div><div id="cards"></div>
<p id="valorTotal"></p><span id="badge-desconto" hidden></span></main>
<script type="module">
import { promotionForm } from '/js/modules/promotion_form.js';
import { renderizarCardServico } from '/js/modules/service_renderer.js';
import { calcular } from '/js/modules/calculator.js';
import { state } from '/js/state.js';
window.form = promotionForm(null, 'synthetic');
document.getElementById('editor').append(window.form.element);
window.price = item => {
    state.configGlobal = { desconto: 10, mult_desconto: 0.9 };
    state.servicoSelecionadoOBJ = { id: 1, nome: 'Mix <img src=x>', valor_base: 100,
        parametros: '', aplica_desconto: true, ...item };
    calcular();
    document.getElementById('cards').innerHTML = renderizarCardServico(state.servicoSelecionadoOBJ, state.configGlobal);
    return state.valorTotalCalculado;
};
window.ready = true;
</script></body></html>`;

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage({ timezoneId: 'America/Sao_Paulo', viewport: { width: 390, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            assert.equal(url.origin, 'http://localhost:4173');
            if (url.pathname === '/__promocoes') return route.fulfill({ contentType: 'text/html', body: PAGE });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            try { return route.fulfill({ body: await fs.readFile(file), contentType:
                { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' }); }
            catch { return route.fulfill({ status: 404, body: '' }); }
        });
        await page.goto('http://localhost:4173/__promocoes');
        await page.waitForFunction(() => window.ready);
        assert.equal(await page.evaluate(() => window.form.read()), null);
        await page.getByLabel('Promoção ativa').check();
        assert.match(await page.evaluate(() => { try { window.form.read(); } catch (error) { return error.message; } }), /Informe um desconto/);
        await page.getByLabel('Desconto especial (%)').fill('20');
        assert.equal(await page.getByLabel('Desconto especial (%)').getAttribute('max'), '99.99');
        await page.getByLabel('Desconto especial (%)').fill('100');
        assert.match(await page.evaluate(() => { try { window.form.read(); } catch (error) { return error.message; } }), /99,99/);
        await page.getByLabel('Desconto especial (%)').fill('20');
        await page.getByLabel('Início (opcional)').fill('2026-10-17T10:00');
        await page.getByLabel('Fim (opcional)').fill('2026-10-18T10:00');
        assert.deepEqual(await page.evaluate(() => window.form.read()), {
            ativa: true, percentual: '20', inicio: '2026-10-17T13:00:00.000Z', fim: '2026-10-18T13:00:00.000Z',
        });
        await page.getByLabel('Fim (opcional)').fill('2026-10-16T10:00');
        assert.match(await page.evaluate(() => { try { window.form.read(); } catch (error) { return error.message; } }), /posterior/);
        assert.equal(await page.evaluate(() => window.price({ preco_catalogo: { desconto_percentual: '20', promocao_ativa: true } })), 80);
        assert.match(await page.locator('#cards').textContent(), /80,00.*100,00.*Promoção.*20% OFF/s);
        assert.equal(await page.locator('#cards img').count(), 0);
        assert.equal(await page.evaluate(() => window.price({ preco_catalogo: { desconto_percentual: '30', promocao_ativa: true } })), 70);
        assert.equal(await page.evaluate(() => window.price({ preco_catalogo: { desconto_percentual: '0', promocao_ativa: false } })), 100);
        assert.equal(await page.locator('#badge-desconto').isHidden(), true);
        assert.equal(await page.evaluate(() => window.price({})), 90); // Older API response.
        assert.equal(await page.evaluate(() => window.price({ preco_catalogo: { desconto_percentual: '100', promocao_ativa: true } })), 0);
        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: promotion editor, timezone, validation, calculator, largest discount and safe cards.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
