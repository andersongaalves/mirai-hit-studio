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
        await page.waitForFunction(() => !document.querySelector('.beat-preview__play').disabled);
        assert.equal(await page.locator('audio').getAttribute('src').then(value => value.startsWith('blob:')), true);
        assert.equal(await page.getByRole('button', { name: 'Reproduzir prévia' }).count(), 1);
        assert.equal(await page.getByRole('slider', { name: 'Posição da prévia' }).count(), 1);
        assert.match(await page.getByRole('status').first().textContent(), /Prévia pronta/);

        await page.evaluate(async () => {
            const { beatPreview } = await import('/js/modules/beat_preview.js');
            document.getElementById('root').append(beatPreview(() => new Blob([], { type: 'text/plain' })));
        });
        await page.waitForFunction(() => document.querySelectorAll('[role="status"]')[1]?.textContent.includes('não é um áudio válido'));
        assert.equal(await page.getByRole('button', { name: 'Tentar novamente' }).count(), 1);
        console.log('PASS: beat preview auto-loads authenticated audio blobs, renders custom controls, and rejects invalid responses.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
