// Mirai Hit Labs store (labs/): catalog, plugin page, purchase hand-off and states,
// in English (default, at /) and Portuguese (at /pt/), with the EN | PT switch.
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
    requisitos: 'Windows 10+ ou macOS 12+',
    en: { tagline: 'Analog saturation in one knob', descricao: 'Tape and tube warmth.\nThree modes.', categoria: 'Saturation',
          recursos: ['Three saturation modes', '4x oversampling'], requisitos: 'Windows 10+ or macOS 12+' },
    preco: '149.90', preco_vigente: '119.90', em_promocao: true, gratuito: false,
    capa_url: null, video_url: 'https://www.youtube.com/watch?v=abcdefghijk', destaque: true,
    sistemas: [{ sistema: 'windows', nome: 'Windows', versao: '1.0.0', tamanho_bytes: 10, tipo: 'arquivo' }, { sistema: 'macos', nome: 'macOS', versao: '1.0.0', tamanho_bytes: null, tipo: 'link' }],
    publicado_em: '2026-11-10T12:00:00Z',
};
// No English texts yet: the English store shows the Portuguese ones.
const tuner = { ...saturator, slug: 'mirai-tuner', nome: 'Mirai Tuner', tagline: 'Afinador preciso', en: { tagline: null, descricao: null, categoria: null, recursos: [], requisitos: null },
    preco: '0.00', preco_vigente: '0.00', em_promocao: false, gratuito: true, destaque: false, video_url: null, sistemas: [] };

function fileFor(pathname) {
    if (pathname === '/') return '/index.html';
    if (pathname === '/pt' || pathname === '/pt/') return '/pt/index.html';
    if (pathname.startsWith('/pt/plugins/')) return '/pt/plugin.html';
    if (pathname.startsWith('/plugins/')) return '/plugin.html';
    return pathname;
}

async function noOverflow(page, label, widths) {
    for (const width of widths) {
        await page.setViewportSize({ width, height: 900 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `${label} overflow at ${width}`);
    }
    await page.setViewportSize({ width: 1280, height: 900 });
}

(async () => {
    const redirects = await fs.readFile(path.join(root, '_redirects'), 'utf8');
    assert.match(redirects, /^\/plugins\/\* \/plugin 200$/m, 'plugin pages rewrite to an extensionless target');
    assert.match(redirects, /^\/pt\/plugins\/\* \/pt\/plugin 200$/m, 'Portuguese plugin pages rewrite too');
    assert.ok(redirects.indexOf('/pt/plugins/*') < redirects.indexOf('\n/plugins/*'), 'the Portuguese rule comes first');
    const headers = await fs.readFile(path.join(root, '_headers'), 'utf8');
    assert.match(headers, /connect-src https:\/\/api\.miraihitstudio\.com\.br/);
    const sitemap = await fs.readFile(path.join(root, 'sitemap.xml'), 'utf8');
    assert.match(sitemap, /<loc>https:\/\/labs\.miraihitstudio\.com\.br\/pt\/<\/loc>/);
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
                const pathname = fileFor(url.pathname);
                const notFound = url.pathname.startsWith('/pt/') ? 'pt/404.html' : '404.html';
                try { return route.fulfill({ body: await fs.readFile(path.join(root, pathname)), contentType: types[path.extname(pathname)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: await fs.readFile(path.join(root, notFound)), contentType: 'text/html' }); }
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

        // ---- English (default) ----
        await page.goto('http://localhost:4174/');
        await page.locator('.plugin-card').first().waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
        assert.equal(await page.title(), 'Mirai Hit Labs | Audio plugins by Mirai Hit Studio');
        assert.equal(await page.locator('h1').textContent(), 'Tools for your sound');
        assert.equal(await page.locator('link[rel="alternate"][hreflang="pt-BR"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/pt/');
        assert.deepEqual(await page.locator('.plugin-card__title').allTextContents(), ['Mirai Saturator', 'Mirai Tuner']);
        const first = page.locator('.plugin-card').first();
        assert.match(await first.textContent(), /Sale[\s\S]*Saturation[\s\S]*Analog saturation in one knob[\s\S]*\$149\.90[\s\S]*\$119\.90[\s\S]*VST3[\s\S]*AU/);
        assert.doesNotMatch(await first.textContent(), /R\$/, 'the English store shows dollars');
        assert.equal(await first.locator('.plugin-card__link').getAttribute('href'), '/plugins/mirai-saturator');
        // no English text yet: the Portuguese one shows
        assert.match(await page.locator('.plugin-card').nth(1).textContent(), /Free[\s\S]*Afinador preciso/);
        assert.equal(await page.locator('#catalog-count').textContent(), '2 plugins');
        assert.equal(await page.locator('.site-nav a', { hasText: 'My plugins' }).getAttribute('href'), '/my-plugins');
        assert.equal(await page.locator('.site-nav .lang__link').getAttribute('href'), '/pt/');
        await noOverflow(page, 'home', [320, 390, 768, 1280]);
        await page.setViewportSize({ width: 320, height: 900 });
        assert.equal(await page.locator('.site-nav .lang__link').isVisible(), true, 'the language switch stays on small screens');
        await page.setViewportSize({ width: 1280, height: 900 });
        if (shots) {
            await page.screenshot({ path: `${shots}/labs-home.png`, fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: `${shots}/labs-home-mobile.png`, fullPage: true });
            await page.setViewportSize({ width: 1280, height: 900 });
        }

        // The whole card opens the plugin page.
        await page.locator('.plugin-card').first().click({ position: { x: 40, y: 40 } });
        await page.waitForURL('**/plugins/mirai-saturator');
        await page.locator('.product__title').waitFor();
        assert.equal(await page.title(), 'Mirai Saturator | Mirai Hit Labs');
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/plugins/mirai-saturator');
        assert.equal(await page.locator('link[rel="alternate"][hreflang="pt-BR"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/pt/plugins/mirai-saturator');
        const buy = page.locator('.buy');
        assert.match(await buy.textContent(), /\$149\.90[\s\S]*\$119\.90[\s\S]*one-time payment[\s\S]*card with Stripe, in US dollars/);
        // signed out: sign in (or create the account) and come back to this plugin
        assert.equal(await buy.getByRole('link', { name: 'Sign in to buy' }).getAttribute('href'), '/account?next=%2Fplugins%2Fmirai-saturator');
        assert.match(await buy.textContent(), /Mirai Hit Labs account[\s\S]*Mirai Hit Studio customers use the same login/);
        assert.match(await page.locator('.facts').textContent(), /VST3 · AU[\s\S]*Windows and macOS[\s\S]*1\.0\.0[\s\S]*Personal/);
        assert.deepEqual(await page.locator('.features li').allTextContents(), ['Three saturation modes', '4x oversampling']);
        assert.equal(await page.locator('.product__tagline').textContent(), 'Analog saturation in one knob');
        assert.equal(await page.locator('.video iframe').getAttribute('src'), 'https://www.youtube-nocookie.com/embed/abcdefghijk');
        assert.equal(await page.locator('.site-nav .lang__link').getAttribute('href'), '/pt/plugins/mirai-saturator');
        await noOverflow(page, 'plugin', [320, 390, 1280]);
        if (shots) {
            await page.screenshot({ path: `${shots}/labs-plugin.png`, fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: `${shots}/labs-plugin-mobile.png`, fullPage: true });
            await page.setViewportSize({ width: 1280, height: 900 });
        }

        // A free plugin without installers yet cannot be taken.
        await page.goto('http://localhost:4174/plugins/mirai-tuner');
        await page.locator('.product__title').waitFor();
        assert.equal(await page.locator('.buy .btn').getAttribute('aria-disabled'), 'true');
        assert.equal(await page.locator('.buy .btn').textContent(), 'Coming soon');
        assert.equal(await page.locator('.buy .btn').getAttribute('href'), null);
        assert.deepEqual(await page.locator('.features li').allTextContents(), ['Três modos de saturação', 'Oversampling 4x']);

        // Unknown plugin and unknown page.
        await page.goto('http://localhost:4174/plugins/nao-existe');
        await page.getByRole('heading', { name: 'Plugin not found' }).waitFor();
        assert.equal(await page.title(), 'Plugin not found | Mirai Hit Labs');
        await page.goto('http://localhost:4174/nada-aqui');
        await page.getByRole('heading', { name: 'Page not found' }).waitFor();

        // Empty and unavailable catalog.
        catalog = [];
        await page.goto('http://localhost:4174/');
        await page.getByText('The first plugins are on the way').waitFor();
        failCatalog = true;
        await page.reload();
        await page.getByText('Catalog unavailable').waitFor();
        failCatalog = false;
        catalog = [tuner];
        await page.getByRole('button', { name: 'Try again' }).click();
        await page.locator('.plugin-card').waitFor();
        catalog = [saturator, tuner];

        // ---- Portuguese at /pt/ ----
        await page.goto('http://localhost:4174/pt/');
        await page.locator('.plugin-card').first().waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.lang), 'pt-BR');
        assert.equal(await page.title(), 'Mirai Hit Labs | Plugins de áudio da Mirai Hit Studio');
        assert.equal(await page.locator('h1').textContent(), 'Ferramentas para o seu som');
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/pt/');
        const primeiro = page.locator('.plugin-card').first();
        assert.match(await primeiro.textContent(), /Promoção[\s\S]*Saturação[\s\S]*Saturação analógica em um botão[\s\S]*R\$\s?149,90[\s\S]*R\$\s?119,90/);
        assert.equal(await primeiro.locator('.plugin-card__link').getAttribute('href'), '/pt/plugins/mirai-saturator');
        assert.equal(await page.locator('#catalog-count').textContent(), '2 plugins');
        assert.equal(await page.locator('.site-nav').getByRole('link', { name: 'Plugins', exact: true }).getAttribute('href'), '/pt/#plugins');
        assert.equal(await page.locator('.site-nav .lang__link').getAttribute('href'), '/');
        await noOverflow(page, 'pt home', [320, 390, 1280]);
        await primeiro.click({ position: { x: 40, y: 40 } });
        await page.waitForURL('**/pt/plugins/mirai-saturator');
        await page.locator('.product__title').waitFor();
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'), 'https://labs.miraihitstudio.com.br/pt/plugins/mirai-saturator');
        assert.match(await page.locator('.buy').textContent(), /R\$\s?149,90[\s\S]*R\$\s?119,90[\s\S]*pagamento único/);
        assert.equal(await page.locator('.buy').getByRole('link', { name: 'Entrar para comprar' }).getAttribute('href'), '/pt/account?next=%2Fpt%2Fplugins%2Fmirai-saturator');
        assert.equal(await page.locator('.site-nav a', { hasText: 'Meus plugins' }).getAttribute('href'), '/pt/my-plugins');
        assert.match(await page.locator('.facts').textContent(), /Windows e macOS[\s\S]*Pessoal/);
        assert.deepEqual(await page.locator('.features li').allTextContents(), ['Três modos de saturação', 'Oversampling 4x']);
        assert.equal(await page.locator('.crumbs a').getAttribute('href'), '/pt/#plugins');
        await page.goto('http://localhost:4174/pt/plugins/nao-existe');
        await page.getByRole('heading', { name: 'Plugin não encontrado' }).waitFor();
        assert.equal(await page.title(), 'Plugin não encontrado | Mirai Hit Labs');

        // ---- Switching language: same page in the other language, and the choice is remembered ----
        await page.goto('http://localhost:4174/plugins/mirai-saturator');
        await page.locator('.product__title').waitFor();
        await page.locator('.site-nav .lang__link').click();
        await page.waitForURL('**/pt/plugins/mirai-saturator');
        await page.locator('.product__title').waitFor();
        await page.goto('http://localhost:4174/');
        await page.waitForURL('http://localhost:4174/pt/');
        await page.locator('.plugin-card').first().waitFor();
        await page.locator('.site-nav .lang__link').click();
        await page.waitForURL('http://localhost:4174/');
        await page.locator('.plugin-card').first().waitFor();
        await page.reload();
        await page.locator('.plugin-card').first().waitFor();
        assert.equal(page.url(), 'http://localhost:4174/', 'choosing English again stays in English');

        assert.deepEqual(errors, []);
        console.log('PASS: Labs store in English and Portuguese: catalog states, plugin page, purchase hand-off, language switch, 404 and responsive layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
