// Portal do cliente > Plugins: Labs purchase hand-off, keys, downloads and pending orders.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png' };
const routes = { '/cliente': '/portal-cliente.html', '/checkout': '/checkout.html' };
const user = { id: 9, username: 'cliente@example.test', role: 'cliente', is_admin: false, ativo: true, cliente_id: 1 };

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://localhost:4173' });
        const page = await context.newPage();
        const errors = [];
        const purchases = [];
        let owned = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4173') {
                const file = routes[url.pathname] || (url.pathname.startsWith('/cliente/') ? '/portal-cliente.html' : url.pathname);
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: '' }); }
            }
            if (url.origin === 'https://signed.example.test') return route.fulfill({ body: 'PKzip', contentType: 'application/zip', headers: { 'content-disposition': 'attachment' } });
            if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
            const p = url.pathname;
            if (p === '/auth/login') return route.fulfill({ json: { access_token: 'client-token', user } });
            if (p === '/auth/me') return route.fulfill({ json: user });
            if (p === '/portal/cliente/plugins') return route.fulfill({ json: owned });
            const buy = p.match(/^\/labs\/plugins\/([a-z0-9-]+)\/comprar$/);
            if (buy) {
                purchases.push({ slug: buy[1], key: request.headers()['idempotency-key'] });
                if (buy[1] === 'mirai-tuner') {
                    owned = [{ id: 5, status: 'ativa', plugin: 'Mirai Tuner', slug: 'mirai-tuner', capa_url: null, versao: '1.0.0',
                        formatos: ['VST3'], chave: 'MHL-TUNE-RAAA-BBBB-CCCC', origem: 'gratuito', ativada_em: null,
                        sistemas: [{ sistema: 'windows', nome: 'Windows', versao: '1.0.0', tamanho_bytes: 10, tipo: 'arquivo' }] }];
                    return route.fulfill({ status: 201, json: { gratuito: true, licenca_id: 5, destino: '/cliente/plugins' } });
                }
                if (buy[1] === 'ja-tenho') return route.fulfill({ status: 409, json: { detail: 'Você já tem este plugin. Baixe em Meus plugins.' } });
                return route.fulfill({ status: 201, json: { gratuito: false, proposta_id: 44, checkout_path: '/checkout?proposta=44' } });
            }
            if (p === '/portal/cliente/plugins/5/download/windows') {
                return route.fulfill({ json: { type: 'download', url: 'https://signed.example.test/r2/tuner.zip?X-Amz-Signature=x', filename: 'Mirai-Tuner-Windows.zip' } });
            }
            if (p.startsWith('/checkout')) return route.fulfill({ status: 404, json: { detail: 'Not found' } });
            if (p.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            return route.fulfill({ json: [] });
        });

        // Empty state points to the store.
        await signIn(page, { next: '/cliente/plugins', username: 'cliente@example.test' });
        await page.locator('#client-plugins').waitFor({ state: 'visible' });
        await page.getByText('Você ainda não tem plugins.').waitFor();
        assert.equal(await page.locator('#client-plugins a', { hasText: 'Conhecer a Mirai Hit Labs' }).getAttribute('href'), 'https://labs.miraihitstudio.com.br');
        assert.equal(await page.locator('a[data-route="plugins"]').getAttribute('aria-current'), 'page');

        // A free plugin from the store: granted and listed with the key and the download.
        await page.goto('http://localhost:4173/cliente/plugins/comprar/mirai-tuner');
        await page.getByText('Pronto! O plugin já está na sua conta.').waitFor();
        assert.equal(new URL(page.url()).pathname, '/cliente/plugins');
        assert.equal(purchases[0].slug, 'mirai-tuner');
        assert.match(purchases[0].key, /^[0-9a-f-]{36}$/);
        const card = page.locator('.client-plugin', { hasText: 'Mirai Tuner' });
        assert.match(await card.textContent(), /Licença ativa[\s\S]*Grátis[\s\S]*MHL-TUNE-RAAA-BBBB-CCCC/);
        await card.getByRole('button', { name: 'Copiar' }).click();
        await card.getByRole('button', { name: /Copiada|Selecione/ }).waitFor();
        const download = page.waitForRequest(request => request.url().startsWith('https://signed.example.test/'));
        await card.getByRole('button', { name: 'Baixar para Windows' }).click();
        await download;
        await card.getByText('Download iniciado.').waitFor();

        // A paid plugin: the portal opens the studio checkout of the order.
        await Promise.all([
            page.waitForURL(url => url.pathname === '/checkout' && url.searchParams.get('proposta') === '44'),
            page.goto('http://localhost:4173/cliente/plugins/comprar/mirai-saturator'),
        ]);
        assert.equal(purchases.at(-1).slug, 'mirai-saturator');

        // Already owned: the reason and a way to the downloads.
        await page.goto('http://localhost:4173/cliente/plugins/comprar/ja-tenho');
        await page.getByText('Você já tem este plugin. Baixe em Meus plugins.').waitFor();
        assert.equal(await page.locator('#client-plugins a', { hasText: 'Voltar para a loja' }).getAttribute('href'), 'https://labs.miraihitstudio.com.br/plugins/ja-tenho');

        // Pending payment and suspended licenses.
        owned = [
            { id: 6, status: 'aguardando_pagamento', plugin: 'Mirai Saturator', slug: 'mirai-saturator', capa_url: null, sistemas: [], checkout_path: '/checkout?proposta=44' },
            { id: 7, status: 'suspensa', plugin: 'Mirai Comp', slug: 'mirai-comp', capa_url: null, sistemas: [] },
        ];
        await page.goto('http://localhost:4173/cliente/plugins');
        await page.locator('.client-plugin', { hasText: 'Mirai Saturator' }).waitFor();
        assert.equal(await page.locator('.client-plugin', { hasText: 'Mirai Saturator' }).getByRole('link', { name: 'Concluir pagamento' }).getAttribute('href'), '/checkout?proposta=44');
        assert.match(await page.locator('.client-plugin', { hasText: 'Mirai Comp' }).textContent(), /Suspensa[\s\S]*revertido/);
        assert.equal(await page.locator('.client-plugin code').count(), 0);
        for (const width of [360, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), true, `overflow at ${width}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: client portal plugins: store hand-off (free, paid, owned), key copy, signed download, pending and suspended licenses.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
