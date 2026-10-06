const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage();
        const errors = [];
        const requests = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:8000') {
                const body = request.postDataJSON();
                requests.push({ path: url.pathname, body });
                return route.fulfill({ status: 202, json: {
                    accepted: true,
                    message: 'Se os dados puderem ser utilizados, enviaremos as próximas instruções por e-mail.',
                } });
            }
            if (url.origin === 'http://localhost:4173') {
                const aliases = { '/cadastro': '/cadastro.html', '/acesso': '/acesso.html' };
                const file = path.resolve(root, `.${aliases[url.pathname] || url.pathname}`);
                assert.ok(file.startsWith(root + path.sep));
                try {
                    return route.fulfill({
                        body: await fs.readFile(file),
                        contentType: { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png' }[path.extname(file)] || 'application/octet-stream',
                    });
                } catch { return route.fulfill({ status: 404, body: '' }); }
            }
            return route.fulfill({ status: 200, body: '' });
        });

        await page.goto('http://localhost:4173/acesso');
        assert.equal(await page.getByRole('link', { name: 'Criar conta' }).getAttribute('href'), '/cadastro');
        await page.getByRole('link', { name: 'Criar conta' }).click();
        await page.waitForURL('**/cadastro');
        await page.getByLabel('Nome').fill('Cliente Sintético');
        await page.getByLabel('E-mail').fill('CLIENTE@example.invalid');
        await page.getByLabel(/Telefone/).fill('(11) 99999-0000');
        await page.getByLabel(/Concordo/).check();
        await page.getByRole('button', { name: 'Criar conta' }).click();
        await page.locator('#signup-sent:not(.hidden)').waitFor();
        assert.deepEqual(requests[0], {
            path: '/auth/client-signup',
            body: {
                nome: 'Cliente Sintético',
                email: 'cliente@example.invalid',
                telefone: '(11) 99999-0000',
                privacy_accepted: true,
            },
        });
        assert.equal('role' in requests[0].body, false);
        assert.equal('cliente_id' in requests[0].body, false);
        await page.getByRole('button', { name: 'Reenviar confirmação' }).click();
        assert.deepEqual(requests[1], {
            path: '/auth/client-signup/resend',
            body: { email: 'cliente@example.invalid' },
        });

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 850 });
            await page.goto('http://localhost:4173/cadastro');
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
            assert.ok(overflow <= 1, `signup overflow at ${width}px: ${overflow}`);
            await page.goto('http://localhost:4173/acesso');
            assert.ok(await page.getByRole('link', { name: 'Criar conta' }).isVisible());
        }
        assert.deepEqual(errors, []);
        console.log('PASS: public client signup form, resend, access link and responsive layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
