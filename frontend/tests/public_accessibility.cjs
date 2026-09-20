const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const checkoutToken = '11111111-1111-4111-8111-111111111111';
const aliases = {
    '/': '/index.html',
    '/artists': '/artists.html',
    '/creators': '/creators.html',
    '/media-games': '/media-games.html',
    '/portfolio': '/portfolio.html',
    '/orcamento': '/calculadora.html',
    [`/checkout/${checkoutToken}`]: '/checkout.html',
};
const contentTypes = {
    '.css': 'text/css', '.html': 'text/html', '.js': 'text/javascript',
    '.png': 'image/png', '.webp': 'image/webp', '.ttf': 'font/ttf',
};

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, `.${decodeURIComponent(aliases[url.pathname] || url.pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(file), contentType: contentTypes[path.extname(file)] || 'application/octet-stream' });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

function apiResponse(route) {
    const url = new URL(route.request().url());
    if (url.pathname === '/config') return route.fulfill({ json: { desconto: 0 } });
    if (url.pathname === '/servicos') return route.fulfill({ json: [{
        id: 1, nome: 'Produção musical', categoria: 'avulso', valor_base: 500,
        aplica_desconto: false, parametros: 'descricao,guia', estrutura_servico: null,
    }] });
    if (url.pathname === '/projetos') return route.fulfill({ json: [{
        id: 1, titulo: 'Demo Mirai', artista: 'Mirai Hit Studio', categoria: 'Trilha',
        descricao: 'Demonstração identificada.', link_audio: 'https://cdn.example.com/demo.mp3',
        link_capa: 'https://cdn.example.com/capa.webp', destaque: true,
        vertical: 'media_games', segmentos_json: ['games'], case_type: 'demo',
    }] });
    if (url.pathname === `/checkout/${checkoutToken}`) return route.fulfill({ json: {
        proposta_numero: 'MHS-001', descricao: 'Trilha original', valor_total: '500.00',
        valor_pago: '0.00', saldo: '500.00', moeda: 'BRL', status: 'pendente', tentativa: null,
        opcoes: [{ tipo: 'integral', titulo: 'Pagamento completo', valor: '500.00' }],
    } });
    return route.fulfill({ json: [] });
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        await context.addInitScript(() => localStorage.setItem('mirai.analytics_consent.v1', 'rejected'));
        await context.route('**/*', route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173') return staticResponse(route);
            if (url.origin === 'http://localhost:8000') return apiResponse(route);
            return route.fulfill({ status: 200, body: '' });
        });

        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const publicPaths = ['/', '/artists', '/creators', '/media-games', '/portfolio', '/orcamento'];
        const allPaths = [...publicPaths, `/checkout/${checkoutToken}`];
        const widths = [320, 360, 375, 390, 414, 768, 1024, 1280, 1440];

        for (const pathname of allPaths) {
            await page.setViewportSize({ width: 390, height: 900 });
            await page.goto(`http://localhost:4173${pathname}`);
            if (pathname === '/portfolio') await page.waitForSelector('.portfolio-card');
            else if (pathname === '/orcamento') await page.waitForSelector('#srv_1');
            else if (pathname.startsWith('/checkout/')) await page.waitForSelector('#checkout-content:not(.hidden)');
            else await page.waitForSelector('.site-nav[data-initialized="true"]');

            const structure = await page.evaluate(() => {
                const visible = element => {
                    const style = getComputedStyle(element);
                    return element.getClientRects().length > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                };
                const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
                    .filter(visible)
                    .map(node => Number(node.tagName.slice(1)));
                const headingJumps = headings.slice(1).filter((level, index) => level - headings[index] > 1);
                const unlabeled = [...document.querySelectorAll('input,select,textarea')]
                    .filter(element => visible(element) && element.type !== 'hidden')
                    .filter(element => !element.labels?.length && !element.getAttribute('aria-label') && !element.getAttribute('aria-labelledby'))
                    .map(element => element.id || element.name || element.tagName);
                const imagesWithoutAlt = [...document.images]
                    .filter(image => !image.hasAttribute('alt'))
                    .map(image => image.src);
                const tinyTargets = [...document.querySelectorAll('a[href],button,input[type="radio"],input[type="checkbox"]')]
                    .filter(visible)
                    .filter(element => {
                        const target = element.matches('input[type="radio"],input[type="checkbox"]') && element.labels?.length
                            ? element.labels[0]
                            : element;
                        const rect = target.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 && (rect.width < 24 || rect.height < 24);
                    })
                    .map(element => `${element.tagName}:${element.textContent.trim() || element.getAttribute('aria-label') || element.id}`);
                return {
                    main: document.querySelectorAll('main').length,
                    visibleH1: [...document.querySelectorAll('h1')].filter(visible).length,
                    headingJumps,
                    unlabeled,
                    imagesWithoutAlt,
                    tinyTargets,
                };
            });
            assert.equal(structure.main, 1, `${pathname}: main`);
            assert.equal(structure.visibleH1, 1, `${pathname}: visible h1`);
            assert.deepEqual(structure.headingJumps, [], `${pathname}: heading order`);
            assert.deepEqual(structure.unlabeled, [], `${pathname}: form labels`);
            assert.deepEqual(structure.imagesWithoutAlt, [], `${pathname}: image alt`);
            assert.deepEqual(structure.tinyTargets, [], `${pathname}: target size`);

            for (const width of widths) {
                await page.setViewportSize({ width, height: 900 });
                const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
                assert.ok(overflow <= 1, `${pathname}: overflow at ${width}px (${overflow}px)`);
            }
        }

        for (const pathname of publicPaths) {
            await page.setViewportSize({ width: 390, height: 900 });
            await page.goto(`http://localhost:4173${pathname}`);
            await page.waitForSelector('.site-nav[data-initialized="true"]');
            await page.keyboard.press('Tab');
            assert.equal(await page.evaluate(() => document.activeElement?.classList.contains('skip-link')), true, `${pathname}: skip link first`);
            const outline = await page.locator('.skip-link').evaluate(element => getComputedStyle(element).outlineStyle);
            assert.notEqual(outline, 'none', `${pathname}: visible focus`);
            await page.keyboard.press('Enter');
            assert.equal(await page.evaluate(() => document.activeElement?.id), 'main-content', `${pathname}: skip target`);

            await page.locator('#site-nav-toggle').focus();
            await page.keyboard.press('Space');
            assert.equal(await page.locator('#site-nav-toggle').getAttribute('aria-expanded'), 'true');
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('#site-nav-toggle').getAttribute('aria-expanded'), 'false');
            assert.equal(await page.evaluate(() => document.activeElement?.id), 'site-nav-toggle');
        }

        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.goto('http://localhost:4173/orcamento');
        await page.waitForSelector('#srv_1');
        const motion = await page.locator('.step-content').first().evaluate(element => ({
            duration: getComputedStyle(element).animationDuration,
            iterations: getComputedStyle(element).animationIterationCount,
        }));
        assert.ok(Number.parseFloat(motion.duration) <= 0.001, motion.duration);
        assert.equal(motion.iterations, '1');

        const contrast = await page.locator('.footer-bottom').evaluate(element => {
            const parse = value => value.match(/[\d.]+/g).slice(0, 3).map(Number);
            const luminance = rgb => {
                const values = rgb.map(value => {
                    const channel = value / 255;
                    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
                });
                return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
            };
            const foreground = luminance(parse(getComputedStyle(element).color));
            const background = luminance(parse(getComputedStyle(document.body).backgroundColor));
            return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
        });
        assert.ok(contrast >= 4.5, `footer contrast ${contrast}`);
        assert.deepEqual(errors, []);
        console.log('PASS: public WCAG structure, keyboard, focus, reduced motion, contrast and nine responsive viewports.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
