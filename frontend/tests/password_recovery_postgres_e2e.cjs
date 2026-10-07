const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const frontend = process.env.PUBLIC_FRONTEND_URL || 'http://localhost:4173';
const api = process.env.PUBLIC_API_URL || 'http://127.0.0.1:8000';
const recoveryFile = process.env.E2E_RECOVERY_URL_FILE;
const username = process.env.E2E_RECOVERY_USERNAME;
const email = process.env.E2E_RECOVERY_EMAIL;
const oldPassword = process.env.E2E_OLD_PASSWORD;
const newPassword = process.env.E2E_NEW_PASSWORD;
assert.ok(recoveryFile && username && email && oldPassword && newPassword);

async function waitForRecoveryUrl() {
    for (let attempt = 0; attempt < 100; attempt++) {
        if (fs.existsSync(recoveryFile)) return fs.readFileSync(recoveryFile, 'utf8').trim();
        await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error('recovery URL was not captured');
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
        await page.goto(`${frontend}/acesso`);
        await page.evaluate(() => {
            localStorage.setItem('mirai.auth.admin.access_token', 'preserve-admin');
            localStorage.setItem('mirai.auth.produtor.access_token', 'preserve-producer');
        });
        await page.getByLabel('Usuário').fill(username);
        await page.getByLabel('Senha').fill(oldPassword);
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForURL('**/cliente');
        const oldToken = await page.evaluate(() => localStorage.getItem('mirai.auth.cliente.access_token'));
        assert.ok(oldToken);

        await page.goto(`${frontend}/acesso`);
        await page.getByRole('link', { name: 'Esqueci minha senha' }).click();
        await page.waitForURL('**/recuperar-senha');
        await page.getByLabel('E-mail').fill(email);
        await page.getByRole('button', { name: 'Enviar instruções' }).click();
        await page.getByText(/Se existir uma conta elegível/).waitFor();
        const recoveryUrl = await waitForRecoveryUrl();

        await page.goto(recoveryUrl);
        await page.getByLabel('Nova senha', { exact: true }).fill(newPassword);
        await page.getByLabel('Confirmar nova senha').fill(newPassword);
        await page.getByRole('button', { name: 'Redefinir senha' }).click();
        await page.getByText('Senha redefinida com sucesso').waitFor();
        const storage = await page.evaluate(() => ({
            admin: localStorage.getItem('mirai.auth.admin.access_token'),
            producer: localStorage.getItem('mirai.auth.produtor.access_token'),
            client: localStorage.getItem('mirai.auth.cliente.access_token'),
        }));
        assert.deepEqual(storage, { admin: 'preserve-admin', producer: 'preserve-producer', client: null });

        const oldSession = await context.request.get(`${api}/auth/me`, {
            headers: { Authorization: `Bearer ${oldToken}` },
        });
        assert.equal(oldSession.status(), 401);
        assert.equal((await context.request.post(`${api}/auth/login`, {
            data: { username, password: oldPassword },
        })).status(), 401);
        assert.equal((await context.request.post(`${api}/auth/login`, {
            data: { username, password: newPassword },
        })).status(), 200);

        await page.goto(`${frontend}/acesso`);
        await page.getByLabel('Usuário').fill(username);
        await page.getByLabel('Senha').fill(newPassword);
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForURL('**/cliente');
        assert.deepEqual(errors, []);
        console.log('PASSWORD_RECOVERY_POSTGRES_E2E_PASS');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
