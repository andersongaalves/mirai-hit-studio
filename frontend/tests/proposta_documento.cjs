// Synthetic API only. Real HTML/PDF fixtures are emitted by test_proposta_documento.py.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const root = path.resolve(__dirname, '..');

(async () => {
    const output = process.env.PROPOSTA_TEST_OUTPUT || path.join(os.tmpdir(), 'mirai-phase-c-layout');
    const html = await fs.readFile(path.join(output, 'layout-1.html'), 'utf8');
    const pdf = await fs.readFile(path.join(output, 'layout-1.pdf'));
    const fixture = JSON.parse(await fs.readFile(path.join(__dirname, 'fixtures/proposta.json')));
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ acceptDownloads: true });
        const page = await context.newPage();
        const saved = new Map([42, 43].map(id => [id, { ...structuredClone(fixture), id, orcamento_id: id, pdf_path: null, gerada_em: null }]));
        const calls = [], errors = [];
        let fail = false, malformed = false, delay = 0, previewDelay = 0;
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) errors.push(message.text());
        });
        await context.route('**/*', async route => {
            const request = route.request(), url = new URL(request.url());
            if (url.origin === 'http://localhost:8000') {
                calls.push(`${request.method()} ${url.pathname}`);
                const id = Number(url.pathname.split('/').findLast(part => /^\d+$/.test(part)));
                const current = saved.get(id);
                if (url.pathname.endsWith('/preview')) {
                    if (previewDelay) await new Promise(resolve => setTimeout(resolve, previewDelay));
                    return route.fulfill({ contentType: 'text/html', body: html });
                }
                if (url.pathname.endsWith('/documento')) return route.fulfill({ contentType: 'application/pdf', body: pdf });
                if (url.pathname.endsWith('/gerar-documento')) {
                    await new Promise(resolve => setTimeout(resolve, delay || 150));
                    if (fail) return route.fulfill({ status: 503, json: { detail: 'Falha sintetica no PDF' } });
                    if (malformed) return route.fulfill({ json: {} });
                    current.pdf_path = `proposta-${id}.pdf`;
                    current.gerada_em = new Date().toISOString();
                    return route.fulfill({ json: current });
                }
                if (request.method() === 'PATCH') {
                    Object.assign(current, request.postDataJSON(), { pdf_path: null, gerada_em: null, versao: current.versao + 1 });
                }
                assert.ok(current, url.pathname);
                return route.fulfill({ json: current });
            }
            if (url.origin === 'http://localhost:4173') {
                const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
                assert.ok(file.startsWith(root + path.sep));
                try {
                    return route.fulfill({ body: await fs.readFile(file), contentType:
                        { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
                } catch { return route.fulfill({ body: '' }); }
            }
            return route.fulfill({ body: '' });
        });
        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fecharEditorProposta === 'function');
        await page.evaluate(() => {
            localStorage.setItem('access_token', 'synthetic-only');
            document.getElementById('login-panel').classList.add('hidden');
        });
        const state = () => page.evaluate(async () => (await import('/js/admin/propostas/proposta_state.js')).propostaState);
        const open = id => page.evaluate(async id => (await import('/js/admin/propostas/propostas.js')).abrirEditorProposta({ id }), id);
        const tab = name => page.locator('#proposta-tabs').getByRole('button', { name, exact: true }).click();
        const generation = () => page.evaluate(async () => (await import('/js/admin/propostas/propostas.js')).gerarDocumento());
        const waitPdf = () => page.locator('.proposta-document-actions a[download]').waitFor();
        await open(42);
        assert.equal(await page.locator('#btn-gerar-pdf-proposta').isDisabled(), false);
        await tab('Preview');
        await page.frameLocator('.proposta-document-frame').getByRole('heading', { name: 'Proposta Comercial' }).waitFor();
        assert.equal(await page.locator('.proposta-document-frame').getAttribute('sandbox'), '');
        assert.equal(await page.locator('.proposta-document-frame').getAttribute('srcdoc'), html);
        const frame = page.frameLocator('.proposta-document-frame');
        assert.equal(await frame.locator('img').count(), 2);
        await page.waitForFunction(() => document.querySelector('.proposta-document-frame')?.getAttribute('srcdoc')?.includes('data:image/png;base64,'));
        await page.screenshot({ path: path.join(output, 'editor-desktop.png'), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.screenshot({ path: path.join(output, 'editor-mobile.png'), fullPage: true });
        await page.setViewportSize({ width: 1280, height: 900 });
        await tab('Proposta');
        await page.locator('#proposta_descricao').fill('Novo texto');
        assert.equal(await page.locator('#btn-gerar-pdf-proposta').isDisabled(), true);
        const before = calls.length;
        await generation();
        assert.equal(calls.length, before);
        assert.match(await page.locator('#proposta-status').textContent(), /Salve as alterações antes de gerar o PDF/);
        await page.evaluate(async () => (await import('/js/admin/propostas/propostas.js')).salvarProposta());
        assert.equal(await page.locator('#btn-gerar-pdf-proposta').isDisabled(), false);
        await page.evaluate(async () => {
            const controller = await import('/js/admin/propostas/propostas.js');
            window.generating = Promise.all([controller.gerarDocumento(), controller.gerarDocumento()]);
        });
        assert.equal((await state()).gerando, true);
        assert.equal(await page.locator('#btn-gerar-pdf-proposta').isDisabled(), true);
        await page.evaluate(() => window.generating);
        await waitPdf();
        assert.equal(calls.filter(call => call.endsWith('/gerar-documento')).length, 1);
        assert.equal((await state()).dirty, false);
        assert.equal((await state()).proposta.versao, 2);
        assert.equal((await state()).proposta.status, 'rascunho');
        const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Baixar PDF' }).click()]);
        assert.deepEqual(await fs.readFile(await download.path()), pdf);
        const view = page.getByRole('link', { name: 'Visualizar PDF' });
        assert.match(await view.getAttribute('href'), /^blob:/);
        assert.equal(await view.getAttribute('target'), '_blank');
        const [popup] = await Promise.all([page.waitForEvent('popup'), view.click()]);
        await popup.close();
        const stable = (await state()).proposta;
        fail = true;
        await generation();
        assert.deepEqual((await state()).proposta, stable);
        assert.equal((await state()).gerando, false);
        assert.equal((await state()).dirty, false);
        assert.match(await page.locator('.notification.error').last().textContent(), /Falha sintetica no PDF/);
        fail = false; malformed = true;
        await generation();
        assert.deepEqual((await state()).proposta, stable);
        malformed = false;
        delay = 500;
        await page.evaluate(async () => { window.late = (await import('/js/admin/propostas/propostas.js')).gerarDocumento(); });
        await open(43);
        await page.evaluate(() => window.late);
        assert.equal((await state()).proposta.id, 43);
        assert.equal((await state()).proposta.pdf_path, null);
        delay = 0;
        previewDelay = 500;
        await tab('Preview');
        await tab('Proposta');
        await page.waitForTimeout(600);
        assert.equal(await page.locator('.proposta-document-frame').count(), 0);
        assert.equal(await page.locator('#proposta_descricao').count(), 1);
        await open(42);
        await tab('Proposta');
        await page.locator('#proposta_descricao').fill('Editar depois de gerar');
        await page.evaluate(async () => (await import('/js/admin/propostas/propostas.js')).salvarProposta());
        assert.equal((await state()).proposta.pdf_path, null);
        await tab('Preview');
        assert.equal(await page.locator('.proposta-document-actions').count(), 0);
        assert.ok(!calls.some(call => /enviar|aprovar|status/.test(call)));
        assert.deepEqual(errors, []);
        console.log('PASS: real backend HTML/PDF fixtures, dirty guard, success, double-submit, download/view, errors, stale generation/preview, invalidation.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
