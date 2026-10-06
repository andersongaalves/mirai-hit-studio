const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

const FRONTEND = 'http://localhost:4173';
const activationFile = process.env.E2E_SIGNUP_ACTIVATION_FILE;
const password = process.env.E2E_PASSWORD;
assert.ok(activationFile && password);

async function waitForActivationUrl() {
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline) {
        try {
            const value = (await fs.readFile(activationFile, 'utf8')).trim();
            if (value) return value;
        } catch {}
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('activation email was not captured');
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 390, height: 850 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
        await page.goto(`${FRONTEND}/acesso`);
        await page.getByRole('link', { name: 'Criar conta' }).click();
        await page.waitForURL('**/cadastro');
        await page.getByLabel('Nome').fill('E2E Cadastro Público');
        await page.getByLabel('E-mail').fill('browser-signup@example.invalid');
        await page.getByLabel(/Telefone/).fill('(11) 98888-0101');
        await page.getByLabel(/Concordo/).check();
        await page.getByRole('button', { name: 'Criar conta' }).click();
        await page.locator('#signup-sent:not(.hidden)').waitFor();

        const activationUrl = await waitForActivationUrl();
        assert.equal(new URL(activationUrl).origin, FRONTEND);
        assert.equal(new URL(activationUrl).pathname, '/ativar');
        await page.goto(activationUrl);
        await page.locator('#activation-form:not(.hidden)').waitFor();
        await page.getByLabel('Nome de usuário').fill('e2e-public-client');
        await page.getByLabel('Senha', { exact: true }).fill(password);
        await page.getByLabel('Confirmar senha').fill(password);
        await page.getByRole('button', { name: 'Ativar acesso' }).click();
        await page.getByText('Conta criada com sucesso.').waitFor();
        await page.getByRole('link', { name: 'Entrar na sua conta' }).click();

        await page.getByLabel('Usuário').fill('e2e-public-client');
        await page.getByLabel('Senha').fill(password);
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForURL('**/cliente');
        await page.locator('#admin-area').waitFor({ state: 'visible' });
        await page.locator('#client-loading').waitFor({ state: 'hidden' });
        await page.getByText('Você ainda não possui projetos vinculados.').first().waitFor();
        assert.equal(await page.getByRole('link', { name: 'Começar um projeto' }).first().getAttribute('href'), '/orcamento');

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 850 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }
        await page.getByRole('button', { name: 'Sair' }).click();
        await page.locator('#login-panel').waitFor({ state: 'visible' });
        assert.deepEqual(errors, []);
        console.log('CLIENT_SIGNUP_E2E_PASS');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
