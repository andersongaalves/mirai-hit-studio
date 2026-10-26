// AUD6-S02-007: every panel and public page runs under the enforced CSP from _headers
// without a single violation. Synthetic API; third-party origins answer empty.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.png': 'image/png', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.woff2': 'font/woff2' };
const pages = {
    '/': '/index.html', '/artists': '/artists.html', '/creators': '/creators.html', '/media-games': '/media-games.html',
    '/portfolio': '/portfolio.html', '/orcamento': '/calculadora.html', '/acesso': '/acesso.html', '/cadastro': '/cadastro.html',
    '/recuperar-senha': '/recuperar-senha.html', '/redefinir-senha': '/redefinir-senha.html', '/ativar': '/ativar.html',
    '/privacidade': '/privacidade.html',
};
const users = {
    admin: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true },
    produtor: { id: 2, username: 'producer-a', role: 'produtor', is_admin: false, ativo: true, painel_beats: true },
    cliente: { id: 3, username: 'client-a', role: 'cliente', is_admin: false, ativo: true, cliente_id: 1 },
};

async function policy() {
    const headers = await fs.readFile(path.join(root, '_headers'), 'utf8');
    const match = headers.match(/^\s*Content-Security-Policy:\s*(.+)$/m);
    assert.ok(match, 'enforced CSP present in _headers');
    // The synthetic API runs on http://localhost:8000; production uses HTTPS, already allowed.
    return match[1].trim().replace("connect-src 'self' https:", "connect-src 'self' https: http://localhost:8000");
}

function fileFor(pathname) {
    if (pages[pathname]) return pages[pathname];
    if (/^\/produtor(\/|$)/.test(pathname)) return '/portal-produtor.html';
    if (/^\/cliente(\/|$)/.test(pathname)) return '/portal-cliente.html';
    return pathname;
}

(async () => {
    const csp = await policy();
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const violations = [];
    try {
        for (const [role, start] of [[null, null], ['admin', '/admin.html'], ['produtor', '/produtor'], ['cliente', '/cliente']]) {
            const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
            await context.addInitScript(() => {
                document.addEventListener('securitypolicyviolation', event => {
                    (window.__csp ||= []).push(`${event.violatedDirective} ${event.blockedURI || 'inline'} ${event.sourceFile || ''}:${event.lineNumber || ''}`);
                });
                try { localStorage.setItem('mirai.analytics.consent', 'accepted'); } catch {}
            });
            await context.route('**/*', async route => {
                const request = route.request();
                const url = new URL(request.url());
                if (url.origin === 'http://localhost:4173') {
                    const file = fileFor(url.pathname);
                    try {
                        const body = await fs.readFile(path.join(root, file));
                        const headers = { 'content-type': types[path.extname(file)] || 'application/octet-stream' };
                        if (path.extname(file) === '.html') headers['content-security-policy'] = csp;
                        return route.fulfill({ body, headers });
                    } catch { return route.fulfill({ status: 404, body: '' }); }
                }
                if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
                const user = users[role] || users.cliente;
                if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: `${user.role}-token`, user } });
                if (url.pathname === '/auth/me') return route.fulfill({ json: user });
                if (url.pathname.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
                if (url.pathname === '/dashboard') return route.fulfill({ json: {
                    metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
                    pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
                    attention: {}, recent_activity: [],
                } });
                return route.fulfill({ json: [] });
            });
            const page = await context.newPage();
            const visit = async target => {
                await page.goto(`http://localhost:4173${target}`, { waitUntil: 'domcontentloaded' });
                await page.waitForTimeout(600);
                for (const entry of await page.evaluate(() => window.__csp || [])) violations.push(`${target}: ${entry}`);
            };
            if (!role) {
                for (const target of Object.keys(pages)) await visit(target);
            } else {
                await signIn(page, { next: start, username: users[role].username });
                await page.waitForTimeout(800);
                for (const entry of await page.evaluate(() => window.__csp || [])) violations.push(`${start}: ${entry}`);
                if (role === 'admin') {
                    await page.locator('[data-admin-action="novoCliente"]').count();
                }
            }
            await context.close();
        }
        assert.deepEqual(violations, []);
        console.log('PASS: public pages, access pages and the three panels run under the enforced CSP without violations.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
