// Admin > Orçamentos: pause and resume new quote requests from the site, with a custom notice.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
const PADRAO = 'Mensagem padrao de agenda cheia.';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        const puts = [];
        let estado = { pausado: false, mensagem: null, mensagem_personalizada: null, desde: null, mensagem_padrao: PADRAO };
        let failNext = false;
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4173') {
                const file = url.pathname === '/acesso' ? '/acesso.html' : url.pathname;
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: '' }); }
            }
            if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
            const p = url.pathname;
            if (p === '/auth/login') return route.fulfill({ json: { access_token: 'admin-token', user: admin } });
            if (p === '/auth/me') return route.fulfill({ json: admin });
            if (p === '/orcamentos/recebimento') {
                if (request.method() === 'PUT') {
                    const body = request.postDataJSON();
                    puts.push(body);
                    if (failNext) { failNext = false; return route.fulfill({ status: 500, json: { detail: 'Falha sintetica.' } }); }
                    estado = {
                        pausado: body.pausado,
                        mensagem: body.pausado ? (body.mensagem || PADRAO) : null,
                        mensagem_personalizada: body.mensagem || null,
                        desde: body.pausado ? '2026-11-07T12:30:00Z' : null,
                        mensagem_padrao: PADRAO,
                    };
                }
                return route.fulfill({ json: estado });
            }
            if (p.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            if (p === '/dashboard') return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            return route.fulfill({ json: [] });
        });
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await openAdminSection(page, 'section-orcamentos');
        const box = page.locator('#orcamentos-recebimento');
        await box.getByRole('heading', { name: 'Recebendo pedidos' }).waitFor();
        assert.equal(await box.evaluate(el => el.classList.contains('is-paused')), false);
        assert.equal(await page.locator('#orcamentos-pausa-mensagem').getAttribute('placeholder'), PADRAO);

        // Pausing asks for confirmation; cancelling keeps everything as it was.
        await box.getByRole('button', { name: 'Pausar novos pedidos' }).click();
        const dialog = page.getByRole('alertdialog');
        await dialog.waitFor();
        assert.match(await dialog.textContent(), /já existentes não mudam/);
        await dialog.getByRole('button', { name: 'Cancelar' }).click();
        assert.equal(puts.length, 0);

        await page.locator('#orcamentos-pausa-mensagem').fill('  Voltamos dia 20!  ');
        await box.getByRole('button', { name: 'Pausar novos pedidos' }).click();
        await page.getByRole('alertdialog').getByRole('button', { name: 'Pausar pedidos' }).click();
        await box.getByRole('heading', { name: 'Novos pedidos pausados' }).waitFor();
        assert.deepEqual(puts.at(-1), { pausado: true, mensagem: 'Voltamos dia 20!' });
        assert.equal(await box.evaluate(el => el.classList.contains('is-paused')), true);
        assert.equal(await page.locator('#orcamentos-pausa-mensagem').inputValue(), 'Voltamos dia 20!');
        assert.match(await box.textContent(), /desde \d{2}\/\d{2}\/\d{4}/);

        // Editing the notice keeps the pause; a failure keeps the form and reports it.
        await page.locator('#orcamentos-pausa-mensagem').fill('Agenda cheia ate dezembro.');
        failNext = true;
        await box.getByRole('button', { name: 'Salvar aviso' }).click();
        await page.waitForFunction(() => !document.querySelector('#orcamentos-recebimento button[disabled]'));
        assert.equal(await page.locator('#orcamentos-pausa-mensagem').inputValue(), 'Agenda cheia ate dezembro.');
        await box.getByRole('button', { name: 'Salvar aviso' }).click();
        await page.waitForFunction(() => document.getElementById('orcamentos-pausa-mensagem')?.value === 'Agenda cheia ate dezembro.'
            && !document.querySelector('#orcamentos-recebimento button[disabled]'));
        assert.deepEqual(puts.at(-1), { pausado: true, mensagem: 'Agenda cheia ate dezembro.' });

        for (const width of [360, 768]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await box.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true, `intake overflow at ${width}`);
        }
        await page.setViewportSize({ width: 1280, height: 900 });

        // Resuming needs no confirmation.
        await box.getByRole('button', { name: 'Retomar pedidos' }).click();
        await box.getByRole('heading', { name: 'Recebendo pedidos' }).waitFor();
        assert.equal(puts.at(-1).pausado, false);
        assert.equal(puts.length, 4);
        assert.deepEqual(errors, []);
        console.log('PASS: admin pauses and resumes quote requests with confirmation, custom notice, failure handling and responsive layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
