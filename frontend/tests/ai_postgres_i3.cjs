const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const prefix = process.env.I3_PREFIX;
const username = process.env.I3_USERNAME;
const password = process.env.I3_PASSWORD;

async function sendChat(page, text) {
    const input = page.locator('#site-chat-message');
    await input.fill(text);
    await input.press('Enter');
    await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled
        || document.querySelector('.site-chat-status').textContent.includes('encaminhada'));
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    await context.addInitScript(() => localStorage.setItem('mirai.analytics_consent.v1', 'rejected'));
    const errors = [];
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:5500/index.html');
    console.log('I3_STEP home');
    await page.locator('#site-chat-launcher').click();
    await page.locator('#site-chat-message').waitFor();
    await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);

    await sendChat(page, 'Quais servicos voces oferecem?');
    assert.match(await page.locator('.site-chat-messages').innerText(), /servi/i);
    await sendChat(page, `${prefix} crie uma ideia sonora aberta para uma campanha espacial`);
    console.log('I3_STEP provider');
    assert.match(await page.locator('.site-chat-messages').innerText(), /resposta generativa sintetica/i);

    const replay = await page.evaluate(async marker => {
        const session = JSON.parse(sessionStorage.getItem('mirai.site_chat.v1'));
        const body = { message_id: crypto.randomUUID(), message: `${marker} pergunta idempotente flexivel` };
        const request = () => fetch('http://localhost:8000/ai/chat/messages', {
            method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.token}` },
            body: JSON.stringify(body),
        }).then(response => response.json());
        return [await request(), await request()];
    }, prefix);
    assert.deepEqual(replay[0], replay[1]);
    console.log('I3_STEP idempotency');

    await page.reload();
    await page.locator('#site-chat-launcher').click();
    await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
    assert.match(await page.locator('.site-chat-messages').innerText(), /resposta generativa sintetica/i);
    await sendChat(page, 'quero falar com uma pessoa');
    await page.waitForFunction(() => document.querySelector('.site-chat-status').textContent.includes('encaminhada'));
    console.log('I3_STEP handoff');

    const admin = await context.newPage();
    admin.on('pageerror', error => errors.push(error.message));
    admin.on('response', async response => {
        if (response.url().includes('/suggestions')) console.log('I3_SUGGESTION', response.status(), await response.text());
    });
    admin.on('dialog', dialog => dialog.accept());
    await admin.goto('http://127.0.0.1:5500/admin.html');
    await admin.locator('#username').fill(username);
    await admin.locator('#password').fill(password);
    await admin.getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
    await admin.locator('[data-admin-target="section-inbox"]').click();
    console.log('I3_STEP admin');
    const conversation = admin.locator('.inbox-conversation-item').first();
    await conversation.waitFor();
    await conversation.getByRole('button').click();
    await admin.waitForFunction(marker => document.querySelector('#inbox-detail')?.textContent.includes(marker), prefix);
    assert.match(await admin.locator('#inbox-detail').innerText(), new RegExp(prefix));
    console.log('I3_STEP inbox');
    await admin.getByRole('button', { name: 'Assumir atendimento' }).click();
    await page.reload();
    await page.locator('#site-chat-launcher').click();
    await page.locator('#site-chat-message').waitFor();
    await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
    await sendChat(page, `${prefix} preciso de uma resposta criativa para esta ideia`);
    await admin.reload();
    await admin.locator('[data-admin-target="section-inbox"]').click();
    const reopened = admin.locator('.inbox-conversation-item').first();
    await reopened.waitFor();
    await reopened.getByRole('button').click();
    await admin.waitForFunction(marker => document.querySelector('#inbox-detail')?.textContent.includes(marker), prefix);
    await admin.locator('#inbox-mode-select').selectOption('copilot');
    await admin.getByRole('button', { name: 'Gerar sugestão' }).click();
    await admin.getByRole('button', { name: 'Regenerar sugestão' }).waitFor();
    console.log('I3_STEP copilot');
    assert.match(await admin.locator('.inbox-message--suggestion').innerText(), /não enviado/i);
    await admin.locator('#inbox-reply-text').fill('I3_TEST resposta humana revisada');
    await admin.getByRole('button', { name: 'Enviar resposta' }).click();
    await admin.getByText('I3_TEST resposta humana revisada').waitFor();
    console.log('I3_STEP human');

    await page.reload();
    await page.locator('#site-chat-launcher').click();
    await page.locator('.site-chat-messages').waitFor();
    await page.waitForFunction(() => document.querySelector('.site-chat-messages').textContent.includes('I3_TEST resposta humana revisada'));
    console.log('I3_STEP history');
    await page.setViewportSize({ width: 390, height: 760 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await admin.setViewportSize({ width: 390, height: 800 });
    assert.equal(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    console.log('I3_RESULT ' + JSON.stringify({ browser: 'edge', chat: true, inbox: true, copilot: true }));
    await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
