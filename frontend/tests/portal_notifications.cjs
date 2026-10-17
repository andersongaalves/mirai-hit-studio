const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        for (const role of ['cliente', 'produtor']) {
            const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
            const user = { id: role === 'cliente' ? 4 : 2, role, username: role, ativo: true, is_admin: false, cliente_id: role === 'cliente' ? 1 : null };
            const prefix = role === 'cliente' ? 'client' : 'producer';
            const target = role === 'cliente' ? '/cliente/projetos/7' : '/produtor/producoes/7';
            const events = [{ id: 1, tipo: 'nova_mensagem', texto: 'Nova mensagem <img src=x onerror=alert(1)>', url: target, created_at: new Date().toISOString(), vista_em: null }];
            const claims = [];
            let offline = false;
            const errors = [];
            await context.route('**/*', async route => {
                const url = new URL(route.request().url());
                if (url.origin === 'http://localhost:4173') {
                    let pathname = url.pathname;
                    if (pathname.startsWith(`/${role}`)) pathname = `/portal-${role}.html`;
                    const file = path.resolve(root, '.' + pathname);
                    assert.ok(file.startsWith(root + path.sep));
                    try {
                        return route.fulfill({ body: await fs.readFile(file), contentType: {
                            '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml',
                        }[path.extname(file)] || 'application/octet-stream' });
                    } catch { return route.fulfill({ status: 404, body: '' }); }
                }
                if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });
                if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: `synthetic-${role}`, user } });
                if (url.pathname === '/auth/me') return route.fulfill({ json: user });
                if (url.pathname === '/portal/notificacoes/vistas') {
                    const ids = route.request().postDataJSON().ids;
                    const claimed = events.filter(item => ids.includes(item.id) && !item.vista_em);
                    claimed.forEach(item => { item.vista_em = new Date().toISOString(); claims.push(item.id); });
                    return route.fulfill({ json: claimed });
                }
                if (url.pathname === '/portal/notificacoes') {
                    if (offline) return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
                    const unread = events.filter(item => !item.vista_em);
                    return route.fulfill({ json: { itens: url.searchParams.has('somente_nao_vistas') ? unread : events,
                        nao_vistas: unread.length, tem_mais: false } });
                }
                if (url.pathname.endsWith('/configuracao')) return route.fulfill({ status: 404, json: {} });
                return route.fulfill({ json: [] });
            });
            const page = await context.newPage();
            page.on('pageerror', error => errors.push(error.message));
            await page.goto(`http://localhost:4173/${role}`);
            await page.locator('#username').fill(role);
            await page.locator('#password').fill('synthetic-password');
            await page.getByRole('button', { name: 'Entrar', exact: true }).click();
            await page.locator('.portal-notifications-new li').waitFor();
            assert.deepEqual(claims, [1]);
            assert.equal(await page.locator('.portal-notifications-new img').count(), 0);
            assert.equal(await page.locator('.portal-notifications-new a').getAttribute('href'), target);
            await page.locator('.portal-notifications-button').click();
            await page.locator('.portal-notifications-dialog li').waitFor();
            assert.equal(await page.locator('.portal-notifications-dialog li').count(), 1);
            assert.equal(await page.locator('.portal-notifications-dialog img').count(), 0);
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('.portal-notifications-dialog').isVisible(), false);
            if (process.env.VISUAL_OUTPUT) {
                await fs.mkdir(process.env.VISUAL_OUTPUT, { recursive: true });
                await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, `notifications-${role}-1440.png`), fullPage: true });
            }
            for (const width of [390, 320]) {
                await page.setViewportSize({ width, height: 900 });
                if (!await page.locator('.portal-notifications-button').isVisible()) {
                    await page.locator('.integrado-portal__menu-toggle').click();
                }
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
                await page.locator('.portal-notifications-button').click();
                const bounds = await page.locator('.portal-notifications-dialog').boundingBox();
                assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width);
                if (process.env.VISUAL_OUTPUT) await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, `notifications-${role}-${width}.png`), fullPage: true });
                await page.keyboard.press('Escape');
            }
            await Promise.all([
                page.waitForResponse(response => response.url().includes('/portal/notificacoes')),
                page.reload(),
            ]);
            await page.locator('.portal-notifications-button').waitFor({ state: 'attached' });
            assert.equal(await page.locator('.portal-notifications-new').count(), 0);
            assert.deepEqual(claims, [1]);
            const other = await context.newPage();
            await other.goto(`http://localhost:4173/${role}`);
            await other.locator('.portal-notifications-button').waitFor();
            assert.equal(await other.locator('.portal-notifications-new').count(), 0);
            assert.deepEqual(claims, [1]);
            offline = true;
            if (!await page.locator('.portal-notifications-button').isVisible()) {
                await page.locator('.integrado-portal__menu-toggle').click();
            }
            await page.locator('.portal-notifications-button').click();
            await page.getByText('Notificações indisponíveis no momento.', { exact: true }).waitFor();
            await page.keyboard.press('Escape');
            // Session teardown clears history and late UI work, even without navigation.
            await page.evaluate(() => document.dispatchEvent(new Event('admin:logout')));
            assert.equal(await page.locator('.portal-notifications-button').count(), 0);
            assert.equal(await page.locator('.portal-notifications-dialog').count(), 0);
            assert.equal(await page.locator(`#${prefix}-username`).count(), 1);
            assert.deepEqual(errors, []);
            await context.close();
        }
        console.log('PASS: notifications, history, once-only claims, safe text, mobile, offline and logout');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
