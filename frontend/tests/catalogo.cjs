// Catalog rework (after 5.10): typed limits instead of free-text sections, highlights,
// legacy conversion, the admin editor state and the public cards for services and combos.
// Browser-only: the modules are rendered on a local page; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const PAGE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/css/variables.css"><link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/pages/calculator.css"><link rel="stylesheet" href="/css/pages/admin.css"></head>
<body><main style="padding:16px">
<textarea id="builder-intro"></textarea>
<fieldset class="servico-limites"><div class="servico-limites__grid">
<label>Faixas<input type="number" id="builder-lim-faixas"></label>
<label>Duração<input type="number" id="builder-lim-duracao_min"></label>
<label>Revisões<input type="number" id="builder-lim-revisoes"></label>
<label>Melodias<input type="number" id="builder-lim-melodias"></label>
<label>Artistas<input type="number" id="builder-lim-artistas"></label>
</div></fieldset>
<textarea id="builder-destaques"></textarea>
<div id="builder-preview-render"></div>
<section id="categoria-avulso" hidden><div id="render-avulsos" class="service-selector"></div></section>
<section id="categoria-combo" hidden><div id="render-combos" class="service-selector"></div></section>
</main>
<script type="module">
import * as Builder from '/js/admin/builder/builder.js';
import { initBuilder } from '/js/admin/builder/builder_ui.js';
import { readStructure, limitLines } from '/js/modules/service_catalog.js';
import { renderizarBotoes } from '/js/ui.js';
import { state } from '/js/state.js';
window.Builder = Builder;
window.initBuilder = initBuilder;
window.readStructure = readStructure;
window.limitLines = limitLines;
window.renderCards = items => {
    state.configGlobal = { desconto: 10, mult_desconto: 0.9 };
    window.catalogFixture = items;
    renderizarBotoes(items);
};
window.ready = true;
</script></body></html>`;

const LEGACY = JSON.stringify({ intro: 'Mix <b>limpo</b>', sections: [{ icon: '', title: 'Detalhes', items: [
    '1 artista', 'Até 5 canais', 'Até 3 minutos', '1 revisão', 'Instrumentos eletrônicos'] }], benefits: ['Atendimento'] });

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== 'http://localhost:4173') return route.fulfill({ status: 404, body: '' });
            if (url.pathname === '/__catalogo.html') return route.fulfill({ contentType: 'text/html', body: PAGE });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            try {
                return route.fulfill({ body: await fs.readFile(file), contentType:
                    { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
            } catch { return route.fulfill({ status: 404, body: '' }); }
        });
        await page.goto('http://localhost:4173/__catalogo.html');
        await page.waitForFunction(() => window.ready === true);

        // Legacy conversion mirrors the backend: limits become fields, the rest highlights.
        assert.deepEqual(await page.evaluate(value => window.readStructure(value), LEGACY), {
            versao: 2, intro: 'Mix <b>limpo</b>', destaques: ['Instrumentos eletrônicos', 'Atendimento'],
            limites: { faixas: 5, duracao_min: 3, revisoes: 1, melodias: null, artistas: 1 } });
        assert.deepEqual(await page.evaluate(() => window.limitLines({ faixas: 1, duracao_min: 3, revisoes: 0, melodias: 5, artistas: 2 })),
            ['Até 1 faixa', 'Até 3 min por faixa', 'Sem revisões', 'Até 5 melodias', '2 artistas']);
        assert.equal((await page.evaluate(() => window.readStructure('{broken'))).limites.faixas, null);

        // Admin editor: loads a legacy service into fields and saves the new shape.
        await page.evaluate(value => { window.Builder.carregarBuilder(value); window.initBuilder(); }, LEGACY);
        assert.equal(await page.locator('#builder-lim-faixas').inputValue(), '5');
        assert.equal(await page.locator('#builder-lim-melodias').inputValue(), '');
        assert.equal(await page.locator('#builder-destaques').inputValue(), 'Instrumentos eletrônicos\nAtendimento');
        assert.match(await page.locator('#builder-preview-render').textContent(), /Até 5 faixas.*Até 3 min por faixa.*1 revisão.*1 artista/s);
        assert.equal(await page.locator('#builder-preview-render b').count(), 0);
        await page.locator('#builder-lim-faixas').fill('');
        await page.locator('#builder-lim-revisoes').fill('2');
        await page.locator('#builder-lim-melodias').fill('99');  // Out of range: no limit.
        await page.locator('#builder-destaques').fill('  Stems separados \n\nEntrega em WAV');
        assert.match(await page.locator('#builder-preview-render').textContent(), /2 revisões/);
        assert.deepEqual(JSON.parse(await page.evaluate(() => window.Builder.gerarJSON())), {
            versao: 2, intro: 'Mix <b>limpo</b>', destaques: ['Stems separados', 'Entrega em WAV'],
            limites: { faixas: null, duracao_min: 3, revisoes: 2, melodias: null, artistas: 1 } });

        // Public cards: single services, combos from the combos catalog; old combo services stay hidden.
        const combo = { id: 1, nome: 'Launch', descricao: 'Do beat ao master.', destaques: ['Desconto de combo'], servicos: [
            { servico_id: 7, nome: 'Instrumental', estrutura: { versao: 2, intro: '', destaques: ['Instrumentos eletrônicos'], limites: { melodias: 5, duracao_min: 3 } } },
            { servico_id: 5, nome: 'Mixagem <i>pro</i>', estrutura: LEGACY },
        ] };
        await page.evaluate(([legacy, comboData]) => window.renderCards([
            { id: 5, nome: 'Mixagem', subtitulo: '', valor_base: 60, aplica_desconto: false, categoria: 'avulso',
              prazo_estimado_dias: 7, estrutura_servico: legacy, cotas_arquivos: [{ max_arquivos: 999 }], politicas: { segredo: 'nao-expor' } },
            { id: 6, nome: 'Masterização', subtitulo: '', valor_base: 50, aplica_desconto: false, categoria: 'avulso', estrutura_servico: legacy },
            { id: 3, nome: 'Launch antigo', subtitulo: '', valor_base: 220, aplica_desconto: true, categoria: 'combo', estrutura_servico: legacy },
            { id: 'c1', tipo: 'combo', nome: 'Launch', subtitulo: 'Tudo pronto', valor_base: 220, aplica_desconto: true, parametros: 'duracao', combo: comboData },
        ]), [LEGACY, combo]);
        assert.equal(await page.locator('#render-avulsos .radio-card').count(), 2);
        assert.equal(await page.locator('#render-combos .radio-card').count(), 1);
        assert.equal(await page.locator('#categoria-combo').isHidden(), false);
        assert.equal(await page.locator('text=Launch antigo').count(), 0);
        const comboCard = page.locator('#render-combos .radio-card');
        assert.equal(await comboCard.locator('input').getAttribute('value'), 'c1');
        assert.match(await comboCard.textContent(), /Instrumental.*Até 3 min por faixa.*Até 5 melodias.*Instrumentos eletrônicos.*Mixagem <i>pro<\/i>.*Até 5 faixas.*Desconto de combo/s);
        assert.match(await comboCard.textContent(), /R\$\s198,00.*-10% OFF/s);
        assert.equal(await comboCard.locator('i, b').count(), 0);
        assert.match(await page.locator('#render-avulsos').textContent(), /Até 5 faixas.*Atendimento/s);
        const singleCard = page.locator('#render-avulsos .catalog-card').first();
        const otherCard = page.locator('#render-avulsos .catalog-card').nth(1);
        assert.equal(await singleCard.locator('.service-price').isVisible(), true);
        assert.equal(await comboCard.locator('.service-price').isVisible(), true);
        assert.equal(await singleCard.locator('.service-details').isVisible(), false);
        assert.equal(await comboCard.locator('.service-details').isVisible(), false);
        assert.match(await singleCard.textContent(), /Prazo estimado: 7 dias/);
        assert.match(await comboCard.textContent(), /Prazo a combinar na proposta/);
        assert.doesNotMatch(await page.locator('#render-avulsos').textContent(), /999|nao-expor|peso_percentual/);
        await singleCard.locator('label').click();
        assert.equal(await singleCard.locator('input').isChecked(), true);
        assert.equal(await singleCard.locator('.service-selected').isVisible(), true);
        assert.equal(await singleCard.locator('.service-details').isVisible(), true);
        await singleCard.locator('input').press('ArrowRight');
        assert.equal(await otherCard.locator('input').isChecked(), true);
        assert.equal(await singleCard.locator('.service-details').isVisible(), false);
        assert.equal(await otherCard.locator('.service-details').isVisible(), true);
        await otherCard.locator('input').press('ArrowRight');
        assert.equal(await comboCard.locator('input').isChecked(), true);
        assert.equal(await singleCard.locator('.service-selected').isVisible(), false);
        assert.equal(await singleCard.locator('.service-details').isVisible(), false);
        assert.equal(await otherCard.locator('.service-details').isVisible(), false);
        assert.equal(await comboCard.locator('.service-details').isVisible(), true);

        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            await page.evaluate(() => window.renderCards(window.catalogFixture));
            assert.equal(await page.locator('.catalog-card input:checked').count(), 0);
            assert.equal(await page.locator('.service-details:visible').count(), 0);
            const compactHeight = (await singleCard.boundingBox()).height;
            const otherHeight = (await otherCard.boundingBox()).height;
            if (process.env.VISUAL_OUTPUT) await page.locator('#categoria-avulso').screenshot({
                path: path.join(process.env.VISUAL_OUTPUT, `cards-compact-${width}.png`), animations: 'disabled',
            });
            await singleCard.locator('label').click();
            assert.equal(await singleCard.locator('input').isChecked(), true);
            assert.equal(await singleCard.locator('.service-details').isVisible(), true);
            assert.ok((await singleCard.boundingBox()).height > compactHeight);
            assert.equal((await otherCard.boundingBox()).height, otherHeight, 'unselected card must stay compact');
            if (process.env.VISUAL_OUTPUT) await page.locator('#categoria-avulso').screenshot({
                path: path.join(process.env.VISUAL_OUTPUT, `cards-expanded-${width}.png`), animations: 'disabled',
            });
            await otherCard.locator('label').click();
            assert.equal(await singleCard.locator('.service-details').isVisible(), false);
            assert.equal((await singleCard.boundingBox()).height, compactHeight);
            assert.equal(await otherCard.locator('.service-details').isVisible(), true);
            await comboCard.locator('label').click();
            assert.equal(await otherCard.locator('.service-details').isVisible(), false);
            assert.equal(await comboCard.locator('.service-details').isVisible(), true);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false,
                `catalog layout overflows at ${width}`);
            if (process.env.VISUAL_OUTPUT) await page.screenshot({
                path: path.join(process.env.VISUAL_OUTPUT, `catalog-${width}.png`), fullPage: true, animations: 'disabled',
            });
        }
        assert.deepEqual(errors, []);
        console.log('PASS: catalog, prices and compact cards expanding on selection (mouse/keyboard, desktop/mobile).');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
