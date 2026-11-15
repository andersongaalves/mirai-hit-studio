// Mirai Hit Labs accounts (labs/): sign in, create a Labs account, forgot password,
// activation, new password, My plugins (keys, downloads, pending payment) and buying.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..', 'labs');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const shots = process.env.SHOT_DIR;
const GOOD_TOKEN = 'a'.repeat(48);
const USED_TOKEN = 'b'.repeat(48);
const buyer = { id: 9, username: 'buyer', role: 'cliente', is_admin: false, ativo: true, cliente_id: 4, somente_labs: true };
const plugin = {
    slug: 'mirai-saturator', nome: 'Mirai Saturator', tagline: 'Saturação analógica', descricao: null, categoria: 'Saturação', versao: '1.0.0',
    formatos: ['VST3'], recursos: [], requisitos: null, en: { tagline: 'Analog saturation', descricao: null, categoria: 'Saturation', recursos: [], requisitos: null },
    preco: '149.90', preco_vigente: '149.90', em_promocao: false, gratuito: false, capa_url: null, video_url: null, destaque: false,
    sistemas: [{ sistema: 'windows', nome: 'Windows', versao: '1.0.0', tamanho_bytes: 10, tipo: 'arquivo' }], publicado_em: null,
};
const freePlugin = { ...plugin, slug: 'mirai-tuner', nome: 'Mirai Tuner', preco: '0.00', preco_vigente: '0.00', gratuito: true };
const licenses = [
    { id: 1, status: 'ativa', plugin: 'Mirai Saturator', slug: 'mirai-saturator', capa_url: null, versao: '1.0.0', formatos: ['VST3', 'AU'],
      chave: 'MHL-AAAA-BBBB-CCCC-DDDD', origem: 'compra', ativada_em: null,
      sistemas: [{ sistema: 'windows', nome: 'Windows', versao: '1.0.0', tamanho_bytes: 10, tipo: 'arquivo' },
                 { sistema: 'macos', nome: 'macOS', versao: '1.0.0', tamanho_bytes: null, tipo: 'link' }] },
    { id: 2, status: 'aguardando_pagamento', plugin: 'Mirai Tuner Pro', slug: 'mirai-tuner-pro', capa_url: null, sistemas: [],
      checkout_path: '/checkout?proposta=12', checkout_url: 'http://localhost:4173/checkout/11111111-2222-3333-4444-555555555555' },
];

function fileFor(pathname) {
    let p = pathname.replace(/\/$/, '') || '/';
    if (p === '/') return '/index.html';
    if (p === '/pt') return '/pt/index.html';
    if (/^(\/pt)?\/plugins\/[\w-]+$/.test(p)) return p.startsWith('/pt/') ? '/pt/plugin.html' : '/plugin.html';
    return path.extname(p) ? p : `${p}.html`;
}

async function noOverflow(page, label) {
    for (const width of [320, 390, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `${label} overflow at ${width}`);
    }
    await page.setViewportSize({ width: 1280, height: 900 });
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
        await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://localhost:4174' });
        const page = await context.newPage();
        const errors = [];
        const calls = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4174') {
                const file = fileFor(url.pathname);
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: await fs.readFile(path.join(root, '404.html')), contentType: 'text/html' }); }
            }
            if (url.origin === 'http://localhost:4173') return route.fulfill({ status: 200, body: '<html><body>studio checkout</body></html>', contentType: 'text/html' });
            if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
            const p = url.pathname;
            const method = request.method();
            if (method === 'OPTIONS') return route.fulfill({ status: 204, body: '' });
            const body = method === 'POST' && request.postData() ? request.postDataJSON() : null;
            const auth = request.headers().authorization;
            calls.push({ method, path: p, body, auth, idem: request.headers()['idempotency-key'] });
            if (p === '/auth/login') {
                if (body.username === 'buyer' && body.password === 'secure-pass') return route.fulfill({ json: { access_token: 'buyer-token', token_type: 'bearer', user: buyer } });
                if (body.username === 'admin') return route.fulfill({ json: { access_token: 'admin-token', token_type: 'bearer', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
                return route.fulfill({ status: 401, json: { detail: 'Usuário ou senha incorretos' } });
            }
            if (p === '/auth/me') return auth === 'Bearer buyer-token' ? route.fulfill({ json: buyer }) : route.fulfill({ status: 401, json: { detail: 'Sessao invalida.' } });
            if (p === '/auth/client-signup' || p === '/auth/client-signup/resend' || p === '/auth/password-recovery') {
                return route.fulfill({ status: 202, json: { accepted: true, message: 'ok' } });
            }
            if (p === '/cliente-acessos/validar') return route.fulfill({ json: { estado: body.token === GOOD_TOKEN ? 'valido' : 'utilizado' } });
            if (p === '/cliente-acessos/ativar') {
                if (body.username === 'taken') return route.fulfill({ status: 409, json: { detail: 'Nome de usuario indisponivel.' } });
                return route.fulfill({ json: { activated: true, login_url: '/acesso' } });
            }
            if (p === '/auth/password-recovery/reset') return route.fulfill({ json: { reset: true, login_url: '/acesso' } });
            if (p === '/labs/plugins/mirai-saturator') return route.fulfill({ json: plugin });
            if (p === '/labs/plugins/mirai-tuner') return route.fulfill({ json: freePlugin });
            if (p === '/labs/plugins/mirai-saturator/comprar') {
                return route.fulfill({ status: 201, json: { gratuito: false, proposta_id: 12, checkout_path: '/checkout?proposta=12',
                    checkout_url: 'http://localhost:4173/checkout/11111111-2222-3333-4444-555555555555' } });
            }
            if (p === '/labs/plugins/mirai-tuner/comprar') return route.fulfill({ status: 201, json: { gratuito: true, licenca_id: 3, destino: '/cliente/plugins' } });
            if (p === '/labs/conta/plugins') return auth === 'Bearer buyer-token' ? route.fulfill({ json: licenses }) : route.fulfill({ status: 401, json: { detail: 'x' } });
            if (p === '/labs/conta/plugins/1/download/windows') {
                return route.fulfill({ status: 200, body: Buffer.from('PK\x03\x04installer'), headers: {
                    'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="mirai-saturator-windows.zip"',
                    'Access-Control-Expose-Headers': 'Content-Disposition' } });
            }
            if (p === '/labs/conta/plugins/1/download/macos') return route.fulfill({ json: { type: 'link', url: 'https://drive.example.test/mac' } });
            return route.fulfill({ status: 404, json: { detail: 'not mocked' } });
        });
        const last = p => [...calls].reverse().find(call => call.path === p);

        // ---- Account page (EN): sign in and create account side by side ----
        await page.goto('http://localhost:4174/account?next=%2Fplugins%2Fmirai-saturator');
        await page.getByRole('heading', { name: 'Sign in' }).waitFor();
        await page.getByRole('heading', { name: 'Create an account' }).waitFor();
        assert.equal(await page.title(), 'Your account | Mirai Hit Labs');
        assert.equal(await page.locator('meta[name="robots"]').getAttribute('content'), 'noindex');
        await noOverflow(page, 'account');
        if (shots) await page.screenshot({ path: `${shots}/labs-account.png`, fullPage: true });

        // Forgot password: the link comes back to the store, in English.
        await page.getByRole('button', { name: 'Forgot your password?' }).click();
        await page.getByRole('heading', { name: 'Reset your password' }).waitFor();
        await page.locator('input[name="email"]').first().fill('buyer@example.com');
        await page.getByRole('button', { name: 'Send link' }).click();
        await page.getByText('If this e-mail belongs to an account').waitFor();
        assert.deepEqual(last('/auth/password-recovery').body, { email: 'buyer@example.com', canal: 'labs', idioma: 'en' });
        await page.getByRole('button', { name: 'Back to sign in' }).click();

        // Studio staff accounts don't buy on the store; wrong password shows a clear message.
        const signIn = page.locator('section', { has: page.getByRole('heading', { name: 'Sign in' }) });
        await signIn.locator('input[name="username"]').fill('admin');
        await signIn.locator('input[name="password"]').fill('whatever-pass');
        await signIn.getByRole('button', { name: 'Sign in' }).click();
        await signIn.getByText("This account can't buy on the store").waitFor();
        await signIn.locator('input[name="username"]').fill('buyer');
        await signIn.locator('input[name="password"]').fill('wrong-pass');
        await signIn.getByRole('button', { name: 'Sign in' }).click();
        await signIn.getByText('Wrong username or password.').waitFor();
        await signIn.locator('input[name="password"]').fill('secure-pass');
        await signIn.getByRole('button', { name: 'Sign in' }).click();

        // Back on the plugin: buying opens the payment (opaque checkout link) with a fresh key.
        await page.waitForURL('**/plugins/mirai-saturator');
        const buy = page.locator('.buy').getByRole('button', { name: 'Buy' });
        await buy.waitFor();
        await buy.click();
        await page.waitForURL('http://localhost:4173/checkout/11111111-2222-3333-4444-555555555555');
        const order = last('/labs/plugins/mirai-saturator/comprar');
        assert.equal(order.auth, 'Bearer buyer-token');
        assert.match(order.idem, /^[0-9a-f-]{36}$/);

        // A free plugin goes straight to My plugins.
        await page.goto('http://localhost:4174/plugins/mirai-tuner');
        await page.locator('.buy').getByRole('button', { name: 'Get it free' }).click();
        await page.waitForURL('**/my-plugins');

        // ---- My plugins: key, downloads and the way back to a pending payment ----
        await page.locator('.license').first().waitFor();
        assert.equal(await page.title(), 'My plugins | Mirai Hit Labs');
        assert.equal(await page.locator('.site-nav a[aria-current="page"]').textContent(), 'My plugins');
        const active = page.locator('.license').first();
        assert.match(await active.textContent(), /Mirai Saturator[\s\S]*v1\.0\.0 · VST3 · AU[\s\S]*MHL-AAAA-BBBB-CCCC-DDDD/);
        await active.getByRole('button', { name: 'Copy' }).click();
        await active.getByRole('button', { name: 'Copied' }).waitFor();
        const [download] = await Promise.all([page.waitForEvent('download'), active.getByRole('button', { name: 'Download for Windows' }).click()]);
        assert.equal(download.suggestedFilename(), 'mirai-saturator-windows.zip');
        await page.waitForFunction(() => [...document.querySelectorAll('.license button')].every(button => !button.disabled));
        assert.equal(await active.getByRole('button', { name: 'Download for Windows' }).isEnabled(), true, 'the button comes back after the download');
        const pending = page.locator('.license').nth(1);
        assert.match(await pending.textContent(), /Mirai Tuner Pro[\s\S]*Waiting for payment/);
        assert.equal(await pending.getByRole('link', { name: 'Go to payment' }).getAttribute('href'), licenses[1].checkout_url);
        assert.match(await page.locator('.library__head').textContent(), /Signed in as buyer/);
        await noOverflow(page, 'my plugins');
        if (shots) {
            await page.screenshot({ path: `${shots}/labs-my-plugins.png`, fullPage: true });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.screenshot({ path: `${shots}/labs-my-plugins-mobile.png`, fullPage: true });
            await page.setViewportSize({ width: 1280, height: 900 });
        }

        // Signing out ends the session on this site.
        await page.getByRole('button', { name: 'Sign out' }).click();
        await page.waitForURL('http://localhost:4174/');
        assert.equal(await page.evaluate(() => localStorage.getItem('mirai.labs.access_token')), null);
        await page.goto('http://localhost:4174/my-plugins');
        await page.getByText('Sign in to see your plugins.').waitFor();
        assert.equal(await page.locator('.panel a.btn').getAttribute('href'), '/account?next=%2Fmy-plugins');

        // ---- Create a Labs account (Portuguese page) ----
        await page.goto('http://localhost:4174/pt/account');
        await page.getByRole('heading', { name: 'Criar conta' }).waitFor();
        const signUp = page.locator('section', { has: page.getByRole('heading', { name: 'Criar conta' }) });
        assert.equal(await signUp.getByRole('link', { name: 'política de privacidade' }).getAttribute('href'), 'https://miraihitstudio.com.br/privacidade');
        await signUp.locator('input[name="nome"]').fill('Ana Compradora');
        await signUp.locator('input[name="email"]').fill('ana@example.com');
        await signUp.getByRole('button', { name: 'Criar conta' }).click();
        assert.equal(last('/auth/client-signup'), undefined, 'consent is required');
        await signUp.locator('input[name="privacy"]').check();
        await signUp.getByRole('button', { name: 'Criar conta' }).click();
        await signUp.getByText('Enviamos um link de confirmação para ana@example.com').waitFor();
        assert.deepEqual(last('/auth/client-signup').body, { nome: 'Ana Compradora', email: 'ana@example.com', privacy_accepted: true, canal: 'labs', idioma: 'pt' });
        await signUp.getByRole('button', { name: 'Reenviar e-mail' }).click();
        await signUp.getByText('Se a conta estiver aguardando confirmação').waitFor();
        assert.deepEqual(last('/auth/client-signup/resend').body, { email: 'ana@example.com' });

        // ---- Activation link from the e-mail ----
        await page.goto(`http://localhost:4174/activate?token=${USED_TOKEN}`);
        await page.getByText('This link was already used.').waitFor();
        await page.goto('http://localhost:4174/activate');
        await page.getByText('This link is incomplete.').waitFor();
        await page.goto(`http://localhost:4174/activate?token=${GOOD_TOKEN}`);
        await page.getByRole('heading', { name: 'Confirm your account' }).waitFor();
        assert.equal(new URL(page.url()).search, '', 'the token leaves the address bar');
        await page.locator('input[name="username"]').fill('taken');
        await page.locator('input[name="password"]').fill('secure-pass');
        await page.locator('input[name="confirm"]').fill('different-pass');
        await page.getByRole('button', { name: 'Confirm account' }).click();
        assert.equal(last('/cliente-acessos/ativar'), undefined, 'different passwords never reach the API');
        await page.locator('input[name="confirm"]').fill('secure-pass');
        await page.getByRole('button', { name: 'Confirm account' }).click();
        await page.getByText('This username is taken. Choose another one.').waitFor();
        await page.locator('input[name="username"]').fill('buyer');
        await page.getByRole('button', { name: 'Confirm account' }).click();
        await page.waitForURL('**/my-plugins');
        assert.deepEqual(last('/cliente-acessos/ativar').body, { token: GOOD_TOKEN, username: 'buyer', password: 'secure-pass' });
        await page.locator('.license').first().waitFor();

        // ---- New password (Portuguese) ----
        await page.goto(`http://localhost:4174/pt/reset-password?token=${GOOD_TOKEN}`);
        await page.getByRole('heading', { name: 'Crie uma nova senha' }).waitFor();
        await page.locator('input[name="password"]').fill('another-pass');
        await page.locator('input[name="confirm"]').fill('another-pass');
        await page.getByRole('button', { name: 'Salvar nova senha' }).click();
        await page.getByText('Senha alterada. Entre com a nova senha.').waitFor();
        assert.deepEqual(last('/auth/password-recovery/reset').body, { token: GOOD_TOKEN, password: 'another-pass' });
        assert.equal(await page.getByRole('link', { name: 'Entrar' }).last().getAttribute('href'), '/pt/account');

        // Signed in, the account page offers My plugins and signing out.
        await page.goto('http://localhost:4174/account');
        await page.getByRole('heading', { name: 'Signed in as buyer' }).waitFor();
        assert.equal(await page.getByRole('link', { name: 'Go to My plugins' }).getAttribute('href'), '/my-plugins');

        assert.deepEqual(errors, []);
        console.log('PASS: Labs accounts: sign in, sign up, forgot password, activation, new password, My plugins, downloads and purchase.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
