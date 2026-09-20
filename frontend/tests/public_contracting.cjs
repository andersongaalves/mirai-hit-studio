const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        const types = { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css', '.webp': 'image/webp', '.png': 'image/png' };
        return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || 'application/octet-stream' });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        await context.addInitScript(() => localStorage.setItem('mirai.analytics_consent.v1', 'rejected'));
        const page = await context.newPage();
        const errors = [];
        const payloads = [];
        let failLead = false;
        let pendingLead = false;
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text());
        });

        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4173') return staticResponse(route);
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/config') return route.fulfill({ json: { desconto: 10 } });
                if (url.pathname === '/servicos') return route.fulfill({ json: [{
                    id: 12,
                    nome: 'Trilha custom',
                    categoria: 'avulso',
                    valor_base: 500,
                    aplica_desconto: true,
                    parametros: 'descricao,duracao,guia',
                    estrutura_servico: null,
                }] });
                if (url.pathname === '/orcamentos' && request.method() === 'POST') {
                    payloads.push(request.postDataJSON());
                    if (pendingLead) await new Promise(resolve => setTimeout(resolve, 120));
                    if (failLead) return route.fulfill({ status: 500, json: { detail: 'erro sintetico' } });
                    return route.fulfill({ json: { id: payloads.length } });
                }
            }
            return route.fulfill({ status: 200, body: '' });
        });

        await page.goto('http://localhost:4173/calculadora.html');
        await page.waitForSelector('#srv_12');
        assert.equal(await page.locator('[onclick]').count(), 0);
        assert.equal(await page.getByText('Comprar agora', { exact: true }).count(), 0);
        assert.match(await page.locator('.quote-context').textContent(), /checkout seguro só é disponibilizado/i);

        await page.locator('label[for="srv_12"]').click();
        assert.equal(await page.locator('#badge-desconto').getAttribute('hidden'), null);
        await page.locator('#btn-next-1').click();
        assert.equal(await page.locator('#step-2-title').evaluate(el => el === document.activeElement), true);
        await page.locator('#descricao').fill('Trilha para abertura de canal');
        await page.locator('#duracao').fill('210');
        await page.locator('#guia').fill('https://example.com/referencia');
        await page.getByRole('button', { name: 'Revisar estimativa' }).click();
        assert.equal(await page.locator('#step-3-title').evaluate(el => el === document.activeElement), true);

        await page.locator('#btn-solicitar').click();
        assert.equal(payloads.length, 0);
        assert.equal(await page.locator('#nome_cliente').evaluate(el => el.matches(':invalid')), true);

        await page.locator('#nome_cliente').fill('Cliente Teste');
        await page.locator('#email').fill('cliente@example.com');
        await page.locator('#btn-solicitar').click();
        await page.waitForFunction(() => document.getElementById('quote-submit-status').dataset.state === 'success');
        assert.equal(payloads.length, 1);
        assert.equal(payloads[0].whatsapp, null);
        assert.equal(payloads[0].link_guia, 'https://example.com/referencia');
        assert.match(payloads[0].detalhes, /Trilha para abertura de canal/);
        assert.match(payloads[0].detalhes, /Duração: 210s/);

        failLead = true;
        await page.locator('#nome_cliente').fill('Nome preservado');
        await page.locator('#btn-solicitar').click();
        await page.waitForFunction(() => document.getElementById('quote-submit-status').dataset.state === 'error');
        assert.equal(await page.locator('#nome_cliente').inputValue(), 'Nome preservado');
        assert.equal(await page.locator('#btn-solicitar').isEnabled(), true);

        failLead = false;
        pendingLead = true;
        const beforeDoubleSubmit = payloads.length;
        await page.evaluate(() => {
            const button = document.getElementById('btn-solicitar');
            button.click();
            button.click();
        });
        await page.waitForFunction(() => document.getElementById('quote-submit-status').dataset.state === 'success');
        assert.equal(payloads.length, beforeDoubleSubmit + 1);

        for (const width of [320, 360, 375, 390, 414, 768, 1024, 1280, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(
                await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
                true,
                `overflow at ${width}`,
            );
        }
        assert.deepEqual(errors, []);
        console.log('PASS: public contracting validation, payload, errors, double-submit and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
