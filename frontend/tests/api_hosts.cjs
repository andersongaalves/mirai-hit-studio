// Production API addresses: regular calls go through Cloudflare (api subdomain); file
// uploads (multipart) go straight to Render, because Cloudflare's free plan refuses
// request bodies above 100 MB. Previews never reach the production API.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext();
    const calls = [];
    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (['miraihitstudio.com.br', 'preview.example.test'].includes(url.hostname)) {
            if (url.pathname === '/blank.html') return route.fulfill({ body: '<!doctype html><title>t</title>', contentType: 'text/html' });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            return route.fulfill({ body: await fs.readFile(file), contentType: 'text/javascript' });
        }
        calls.push([route.request().method(), url.origin + url.pathname, route.request().headers()['content-type'] || '']);
        return route.fulfill({ json: { ok: true }, headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    try {
        const page = await context.newPage();
        await page.goto('https://miraihitstudio.com.br/blank.html');
        const config = await page.evaluate(async () => {
            const module = await import('/js/config.js');
            return {
                api: module.API_URL,
                upload: module.UPLOAD_API,
                json: module.apiPara(JSON.stringify({ a: 1 })),
                none: module.apiPara(undefined),
                form: module.apiPara(new FormData()),
            };
        });
        assert.deepEqual(config, {
            api: 'https://api.miraihitstudio.com.br',
            upload: 'https://mirai-hit-studio.onrender.com',
            json: 'https://api.miraihitstudio.com.br',
            none: 'https://api.miraihitstudio.com.br',
            form: 'https://mirai-hit-studio.onrender.com',
        });

        // authFetch picks the address by body: JSON through Cloudflare, uploads direct.
        await page.evaluate(() => localStorage.setItem('mirai.auth.admin.access_token', 'synthetic'));
        const sent = await page.evaluate(async () => {
            const { authFetch } = await import('/js/admin/auth.js');
            const out = [];
            for (const body of [undefined, JSON.stringify({ a: 1 }), (() => { const f = new FormData(); f.append('x', new Blob(['a'])); return f; })()]) {
                try {
                    await authFetch('/servicos', { method: body ? 'POST' : 'GET', body });
                    out.push('ok');
                } catch (error) {
                    out.push(error.message);
                }
            }
            return out;
        });
        assert.deepEqual(sent, ['ok', 'ok', 'ok']);
        assert.deepEqual(calls.map(([method, url]) => [method, url]), [
            ['GET', 'https://api.miraihitstudio.com.br/servicos'],
            ['POST', 'https://api.miraihitstudio.com.br/servicos'],
            ['POST', 'https://mirai-hit-studio.onrender.com/servicos'],
        ]);
        assert.match(calls[2][2], /^multipart\/form-data/);

        // Preview hosts never talk to production.
        const preview = await context.newPage();
        await preview.goto('https://preview.example.test/blank.html');
        const previewConfig = await preview.evaluate(async () => {
            const module = await import('/js/config.js');
            return [module.API_URL, module.UPLOAD_API];
        });
        assert.ok(previewConfig.every(value => value.endsWith('.invalid')), previewConfig.join(' '));
        console.log('PASS: API via Cloudflare subdomain, uploads direct to Render, previews isolated.');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
