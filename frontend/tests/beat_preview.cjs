const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage();
        await page.route('http://localhost:4173/**', async route => {
            const pathname = new URL(route.request().url()).pathname;
            if (pathname === '/test') return route.fulfill({ contentType: 'text/html', body: '<main id="root"></main>' });
            const file = path.resolve(root, `.${pathname}`);
            assert.ok(file.startsWith(root + path.sep));
            return route.fulfill({ contentType: 'text/javascript', body: await fs.readFile(file) });
        });
        await page.goto('http://localhost:4173/test');
        await page.evaluate(async () => {
            const { beatPreview } = await import('/js/modules/beat_preview.js');
            window.preview = beatPreview(() => new Blob(['ID3-preview'], { type: 'audio/mpeg' }));
            document.getElementById('root').append(window.preview);
        });
        await page.getByRole('button', { name: 'Carregar prévia' }).click();
        await page.waitForSelector('audio:not([hidden])');
        assert.equal(await page.locator('audio').getAttribute('src').then(value => value.startsWith('blob:')), true);

        await page.evaluate(async () => {
            const { beatPreview } = await import('/js/modules/beat_preview.js');
            document.getElementById('root').append(beatPreview(() => new Blob([], { type: 'text/plain' })));
        });
        await page.getByRole('button', { name: 'Carregar prévia' }).click();
        assert.match(await page.getByRole('status').last().textContent(), /não é um áudio válido/);
        console.log('PASS: beat preview loads authenticated audio blobs and rejects empty or invalid responses.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
