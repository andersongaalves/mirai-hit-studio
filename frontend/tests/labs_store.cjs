// Mirai Hit Labs store (labs/): catalog, plugin page, purchase hand-off and states.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..', 'labs');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.xml': 'application/xml', '.txt': 'text/plain' };
const shots = process.env.SHOT_DIR;
const saturator = {
    slug: 'mirai-saturator', nome: 'Mirai Saturator', tagline: 'Saturação analógica em um botão', descricao: 'Calor de fita e válvula.\nTrês modos.',
    categoria: 'Saturação', versao: '1.0.0', formatos: ['VST3', 'AU'], recursos: ['Três modos de saturação', 'Oversampling 4x'],
    requisitos: 'Windows 10+ ou macOS 12+', preco: '149.90', preco_vigente: '119.90', em_promocao: true, gratuito: false,
    capa_url: null, video_url: 'https://www.youtube.com/watch?v=abcdefghijk', destaque: true,
    sistemas: [{ sistema: 'windows', nome: 'Windows', versao: '1.0.0', tamanho_bytes: 10, tipo: 'arquivo' }, { sistema: 'macos', nome: 'macOS', versao: '1.0.0', tamanho_bytes: null, tipo: 'link' }],
    publicado_em: '2026-11-10T12:00:00Z',
};
const tuner = { ...saturator, slug: 'mirai-tuner', nome: 'Mirai Tuner', tagline: 'Afinador preciso', preco: '0.00', preco_vigente: '0.00', em_promocao: false, gratuito: true, destaque: false, video_url: null, sistemas: [] };

(async () => {
    const redirects = await fs.readFile(path.join(root, '_redirects'), 'utf8');
    assert.match(redirects, /^\/plugins\/\* \/plugin 200$/m, 'plugin pages rewrite to an extensionless target');
    const headers = await fs.readFile(path.join(root, '_headers'), 'utf8');
    assert.match(headers, /connect-src https:\/\/api\.miraihitstudio\.com\.br/);
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        let catalog = [saturator, tuner];
        let failCatalog = false;
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4174') {
                let pathname = url.pathname === '/' ? '/index.html' : url.pathname;
                if (pathname.startsWith('/plugins/')) pathname = '/plugin.html';
                try { return route.fulfill({ body: await fs.readFile(path.join(root, pathname)), contentType: types[path.extname(pathname)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: await fs.readFile(path.join(root, '404.html')), contentType: 'text/html' }); }
            }
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/labs/plugins') return failCatalog ? route.fulfill({ status: 503, json: { detail: 'x' } }) : route.fulfill({ json: catalog });
                const one = catalog.find(item => url.pathname === `/labs/plugins/${item.slug}`);
                return one ? route.fulfill({ json: one }) : route.fulfill({ status: 404, json: { detail: 'Plugin não encontrado.' } });
            }
            if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') return route.fulfill({ status: 200, body: '', contentType: 'text/css' });
            if (url.hostname === 'www.youtube-nocookie.com') return route.fulfill({ status: 200, body: '<html></html>', contentType: 'text/html' });
            return route.fulfill({ status: 204, body: '' });
        });

        // Home: brand, catalog cards (featured first) and the purchase story.
        await page.goto('http://localhost:4174/');
        await page.locator('.plugin-card').first().waitFor();
        assert.equal(await page.title(), 'Mirai Hit Labs | Plugins de áudio da Mirai Hit Studio');
        assert.equal(await page.locator('h1').textContent(), 'Ferramentas para o seu som');
        assert.deepEqual(await page.locator('.plugin-card__title').allTextContents(), ['Mirai Saturator', 'Mirai Tuner']);
        const first = page.locator('.plugin-card').first();
        assert.match(await first.textContent(), /Promoção[\s\S]*Saturação[\s\S]*R\$\s?149,90[\s\S]*R\$\s?119,90[\s\S]*VST3[\s\S]*AU/);
        assert.match(await page.locator('.plugin-card').nth(1).textContent(), /Grátis/);
        assert.equal(await page.locator('#catalog-count').textContent(), '2 plugins');
        assert.equal(await page.locator('.site-nav a', { hasText: 'Meus plugins' }).getAttribute('href'), 'https://miraihitstudio.com.br/cliente/plugins');
        for (const width of [320, 390, 768, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `home overflow at ${width}`);
        }
        if (shots) {
            await page.setViewportSize({ width: 1280, height: 900 });
            await page.screenshot({ path: `${shots}/labs-home.png`, fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: `${shots}/labs-home-mobile.png`, fullPage: true });
        }
        await page.setViewportSize({ width: 1280, height: 900 });

        // The whole card opens the plugin page.
        await page.locator('.plugin-card').first().click({ position: { x: 40, y: 40 } });
        await page.waitForURL('**/plugins/mirai-saturator');
        await page.locator('.product__title').waitFor();
        assert.equal(await page.title(), 'Mirai Saturator | Mirai Hit Labs');
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/plugins/mirai-saturator');
        const buy = page.locator('.buy');
        assert.match(await buy.textContent(), /R\$\s?149,90[\s\S]*R\$\s?119,90[\s\S]*pagamento único/);
        assert.equal(await buy.getByRole('link', { name: 'Comprar' }).getAttribute('href'), 'http://localhost:4173/cliente/plugins/comprar/mirai-saturator');
        assert.match(await page.locator('.facts').textContent(), /VST3 · AU[\s\S]*Windows e macOS[\s\S]*1\.0\.0[\s\S]*Pessoal/);
        assert.deepEqual(await page.locator('.features li').allTextContents(), ['Três modos de saturação', 'Oversampling 4x']);
        assert.equal(await page.locator('.video iframe').getAttribute('src'), 'https://www.youtube-nocookie.com/embed/abcdefghijk');
        for (const width of [320, 390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `plugin overflow at ${width}`);
        }
        if (shots) {
            await page.setViewportSize({ width: 1280, height: 900 });
            await page.screenshot({ path: `${shots}/labs-plugin.png`, fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: `${shots}/labs-plugin-mobile.png`, fullPage: true });
        }
        await page.setViewportSize({ width: 1280, height: 900 });

        // A free plugin without installers yet cannot be taken.
        await page.goto('http://localhost:4174/plugins/mirai-tuner');
        await page.locator('.product__title').waitFor();
        assert.equal(await page.locator('.buy .btn').getAttribute('aria-disabled'), 'true');
        assert.equal(await page.locator('.buy .btn').textContent(), 'Em breve');
        assert.equal(await page.locator('.buy .btn').getAttribute('href'), null);

        // Unknown plugin and unknown page.
        await page.goto('http://localhost:4174/plugins/nao-existe');
        await page.getByRole('heading', { name: 'Plugin não encontrado' }).waitFor();
        assert.equal(await page.title(), 'Plugin não encontrado | Mirai Hit Labs');

        // Empty and unavailable catalog.
        catalog = [];
        await page.goto('http://localhost:4174/');
        await page.getByText('Os primeiros plugins estão a caminho').waitFor();
        failCatalog = true;
        await page.reload();
        await page.getByText('Catálogo indisponível').waitFor();
        failCatalog = false;
        catalog = [tuner];
        await page.getByRole('button', { name: 'Tentar de novo' }).click();
        await page.locator('.plugin-card').waitFor();
        assert.deepEqual(errors, []);
        console.log('PASS: Labs store home, catalog states, plugin page, purchase hand-off, 404 and responsive layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
