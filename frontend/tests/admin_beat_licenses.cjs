// Etapa 07, APL-S06-01/02: Admin sees beat licenses, releases a reservation and relists a refunded exclusive.
// Browser-only integration. Every request is fulfilled locally; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const CONFIG = { capa_mb: 10, mp3_mb: 50, wav_mb: 50, multitrack_mb: 50, multitrack_mode: 'arquivo' };
const base = { descricao: '', bpm: 140, tonalidade: 'Am', generos: 'Trap', ativo: true, motivo_rejeicao: null,
    created_at: '2026-10-20T12:00:00+00:00', formato_novo: true, tem_wav: false, tem_multitrack: false,
    multitrack_origem: null, capa_url: null, produtor: 'Produtor A', preco_lease_base: 100, preco_exclusivo_base: 500 };
const beats = () => [
    { ...base, id: 7, titulo: 'Reservado', status: 'aprovado', pode_voltar_ao_catalogo: false, licencas: [
        { id: 31, tipo: 'exclusivo', status: 'reservada', proposta_id: 12, expira_em: '2026-10-26T15:00:00+00:00',
          adquirida_em: null, cancelada_em: null, motivo_cancelamento: null },
    ] },
    { ...base, id: 8, titulo: 'Reembolsado', status: 'vendido', ativo: false, pode_voltar_ao_catalogo: true, licencas: [
        { id: 32, tipo: 'exclusivo', status: 'cancelada', proposta_id: 13, expira_em: null, adquirida_em: '2026-10-21T10:00:00+00:00',
          cancelada_em: '2026-10-22T10:00:00+00:00', motivo_cancelamento: 'pagamento_revertido' },
    ] },
    { ...base, id: 9, titulo: 'Sem licenca', status: 'revisao', pode_voltar_ao_catalogo: false, licencas: [] },
];

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        const posts = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const req = route.request();
            const url = new URL(req.url());
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/admin/beats' && req.method() === 'GET') return route.fulfill({ json: beats() });
                if (url.pathname === '/admin/beats/configuracao') return route.fulfill({ json: CONFIG });
                if (req.method() === 'POST' && /^\/admin\/beats\//.test(url.pathname)) {
                    posts.push({ path: url.pathname, body: req.postDataJSON() });
                    return route.fulfill({ json: {} });
                }
                return route.fulfill({ status: 404, json: { detail: 'not mocked' } });
            }
            if (url.origin === 'http://localhost:4173') {
                const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
                assert.ok(file.startsWith(root + path.sep));
                try {
                    return route.fulfill({ body: await fs.readFile(file), contentType:
                        { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
                } catch { return route.fulfill({ body: '' }); }
            }
            return route.fulfill({ body: '' });
        });
        await page.goto('http://localhost:4173/admin.html');
        await page.evaluate(() => localStorage.setItem('mirai.auth.admin.access_token', 'synthetic-only'));
        await page.waitForTimeout(300);
        await page.evaluate(async () => {
            // The admin shell keeps sections hidden until login; this suite only exercises the beats list.
            for (let element = document.getElementById('admin-beats-list'); element; element = element.parentElement) {
                element.classList.remove('hidden', 'admin-access-hidden');
                element.hidden = false;
                if (getComputedStyle(element).display === 'none') element.style.display = 'block';
            }
            const module = await import('/js/admin/beats.js');
            await module.initBeats();
        });
        const cards = page.locator('#admin-beats-list .admin-beat-card');
        await cards.first().waitFor();
        assert.equal(await cards.count(), 3);
        const reserved = cards.filter({ hasText: 'Reservado' });
        const text = await reserved.locator('.admin-beat-licenses').innerText();
        assert.match(text, /Exclusivo · Reservada · proposta #12 · reservada até/);
        assert.equal(await cards.filter({ hasText: 'Sem licenca' }).locator('.admin-beat-licenses').count(), 0);
        assert.match(await cards.filter({ hasText: 'Reembolsado' }).locator('.admin-beat-licenses').innerText(), /pagamento revertido/);

        // Cancelling the reason prompt sends nothing.
        page.once('dialog', dialog => dialog.dismiss());
        await reserved.getByRole('button', { name: 'Liberar reserva' }).click();
        await page.waitForTimeout(100);
        assert.equal(posts.length, 0);

        page.once('dialog', dialog => dialog.accept('Cliente desistiu'));
        await reserved.getByRole('button', { name: 'Liberar reserva' }).click();
        await page.waitForTimeout(150);
        assert.deepEqual(posts.shift(), { path: '/admin/beats/licencas/31/liberar', body: { motivo: 'Cliente desistiu' } });

        page.once('dialog', dialog => dialog.accept('Reembolso confirmado'));
        await cards.filter({ hasText: 'Reembolsado' }).getByRole('button', { name: 'Devolver ao catálogo' }).click();
        await page.waitForTimeout(150);
        assert.deepEqual(posts.shift(), { path: '/admin/beats/8/voltar-ao-catalogo', body: { motivo: 'Reembolso confirmado' } });
        assert.equal(await cards.filter({ hasText: 'Reservado' }).getByRole('button', { name: 'Devolver ao catálogo' }).count(), 0);

        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        assert.equal(overflow, false);
        if (process.env.SHOT_DIR) await reserved.screenshot({ path: path.join(process.env.SHOT_DIR, 'admin_beat_licenses_390.png') });
        assert.deepEqual(errors, []);
        console.log('admin beat licenses: ok');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exit(1); });
