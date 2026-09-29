const { chromium } = require("playwright");
const assert = require("node:assert/strict");

const mode = process.env.I2_BROWSER_MODE;
const frontendOrigin = "http://127.0.0.1:5500";

function result(value) { console.log(`I2_RESULT ${JSON.stringify(value)}`); }

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: Number(process.env.I2_WIDTH || 1440), height: 900 } });
        await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "rejected"));
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === frontendOrigin) return route.continue();
            if (url.origin === "http://localhost:8000") return route.continue();
            if (url.origin === "http://127.0.0.1:8000") return route.continue();
            if (url.origin === "https://sdk.mercadopago.com") return route.fulfill({ contentType: "text/javascript", body: `
                window.MercadoPago = class {
                    bricks() { return { create: async (_name, id, settings) => {
                        window.__brickSettings = settings;
                        const button = document.createElement("button");
                        button.type = "button"; button.textContent = "Pagar cartao";
                        document.getElementById(id).appendChild(button);
                        settings.callbacks.onReady();
                        return { unmount: async () => document.getElementById(id).replaceChildren() };
                    } }; }
                };
            ` });
            if (url.hostname.includes("mercadopago.com")) return route.fulfill({ status: 200, body: "" });
            return route.fulfill({ status: 204, body: "" });
        });
        const page = await context.newPage();
        const errors = [];
        const failedRequests = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("requestfailed", request => failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
        page.on("console", message => { if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text()); });

        if (mode === "public") {
            await page.goto(`${frontendOrigin}/calculadora.html`);
            const service = page.locator('input[name="servico"]').first();
            await service.waitFor({ timeout: 10000 }).catch(async error => {
                throw new Error(JSON.stringify({
                    message: error.message,
                    status: await page.locator("#calculator-status").textContent(),
                    errors,
                    failedRequests,
                }));
            });
            const serviceId = await service.getAttribute("value");
            await page.locator(`label[for="${await service.getAttribute("id")}"]`).click();
            await page.locator("#btn-next-1").click();
            for (const input of await page.locator("#render-parametros input, #render-parametros textarea, #render-parametros select").all()) {
                const tag = await input.evaluate(el => el.tagName);
                const type = await input.getAttribute("type");
                if (tag === "SELECT") {
                    const value = await input.locator("option").nth(1).getAttribute("value").catch(() => null);
                    if (value) await input.selectOption(value);
                } else if (type === "checkbox" || type === "radio") await input.check();
                else if (type === "url") await input.fill("https://example.com/i2-reference");
                else if (type === "number") await input.fill(await input.getAttribute("min") || "180");
                else await input.fill("I2 Browser briefing synthetic");
            }
            await page.getByRole("button", { name: "Revisar estimativa" }).click();
            await page.locator("#nome_cliente").fill(process.env.I2_NAME);
            await page.locator("#email").fill(process.env.I2_EMAIL);
            const responsePromise = page.waitForResponse(r => new URL(r.url()).pathname === "/orcamentos" && r.request().method() === "POST");
            await page.evaluate(() => { const button = document.getElementById("btn-solicitar"); button.click(); button.click(); });
            const response = await responsePromise;
            assert.equal(response.status(), 200);
            await page.waitForFunction(() => document.getElementById("quote-submit-status").dataset.state === "success");
            const body = await response.json();
            assert.equal(await page.locator("#nome_cliente").inputValue(), process.env.I2_NAME);
            result({ budgetId: body.id, serviceId: Number(serviceId), url: page.url() });
        } else if (mode === "checkout-pix") {
            const reference = process.env.I2_REFERENCE;
            const responsePromise = page.waitForResponse(r => new URL(r.url()).pathname === `/checkout/${reference}`);
            await page.goto(`${frontendOrigin}/checkout/${reference}`);
            assert.equal((await responsePromise).status(), 200);
            assert.equal(new URL(page.url()).pathname, `/checkout/${reference}`);
            await page.locator(`input[name="payment_option"][value="${process.env.I2_OPTION}"]`).check();
            const paymentPromise = page.waitForResponse(r => new URL(r.url()).pathname === `/checkout/${reference}/pix`);
            await page.locator("#generate-pix").click();
            const paymentResponse = await paymentPromise;
            const payment = await paymentResponse.json();
            await page.waitForFunction(() => document.getElementById("pix-code")?.value.includes("I2-SYNTHETIC"), null, { timeout: 10000 }).catch(async error => {
                throw new Error(JSON.stringify({ message: error.message, status: paymentResponse.status(), payment,
                    result: await page.locator("#payment-result").textContent(), errors, failedRequests }));
            });
            const ticket = await page.locator("#pix-ticket").getAttribute("href");
            assert.equal(new URL(ticket).hostname, "www.mercadopago.com.br");
            assert.ok(!(await page.content()).includes(process.env.I2_EMAIL));
            result({ status: "pending", path: new URL(page.url()).pathname, ticket });
        } else if (mode === "checkout-state") {
            await page.goto(`${frontendOrigin}/checkout/${process.env.I2_REFERENCE}`);
            await page.locator("#checkout-content:not(.hidden)").waitFor();
            const status = await page.locator("#checkout-terminal").textContent();
            const balance = await page.locator("#balance-value").textContent();
            const description = await page.locator("#project-description").textContent();
            assert.equal(await page.locator("#project-description script, #project-description img").count(), 0);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
            assert.ok(!JSON.stringify(await page.evaluate(() => window.dataLayer || [])).includes(process.env.I2_REFERENCE));
            result({ status, balance, description });
        } else if (mode === "checkout-card") {
            await page.goto(`${frontendOrigin}/checkout/${process.env.I2_REFERENCE}`);
            await page.locator("#checkout-content:not(.hidden)").waitFor();
            await page.locator(`input[name="payment_option"][value="${process.env.I2_OPTION}"]`).check();
            await page.locator("#method-card").click();
            await page.getByRole("button", { name: "Pagar cartao" }).waitFor();
            await page.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
                token: "i2-transient-card-token", payment_method_id: "visa", installments: 1,
                payer: { email: "i2-card@example.com", identification: { type: "CPF", number: "12345678900" } },
            }, { paymentTypeId: "credit_card" }));
            const rejected = process.env.I2_EXPECT === "rejected";
            if (rejected) await page.waitForFunction(() => document.getElementById("payment-result").textContent.includes("não foi aprovado"));
            else await page.locator("#challenge-container:not(.hidden)").waitFor();
            assert.ok(!JSON.stringify(await page.evaluate(() => window.dataLayer || [])).includes(process.env.I2_REFERENCE));
            result({ rejected, challenge: await page.locator("#challenge-container").isVisible() });
        } else if (mode === "finance") {
            await page.goto(`${frontendOrigin}/admin.html`);
            await page.waitForFunction(() => typeof window.fazerLogin === "function", null, { timeout: 10000 }).catch(error => {
                throw new Error(JSON.stringify({ message: error.message, errors, failedRequests }));
            });
            await page.locator("#username").fill(process.env.I2_USERNAME);
            await page.locator("#password").fill(process.env.I2_PASSWORD);
            const loginPromise = page.waitForResponse(r => new URL(r.url()).pathname === "/auth/login");
            await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
            const loginResponse = await loginPromise;
            if (loginResponse.status() !== 200) throw new Error(`admin login failed: ${loginResponse.status()}`);
            await page.locator("#admin-area:not(.hidden)").waitFor();
            await page.locator('[data-admin-target="section-financeiro"]').click();
            await page.locator("#financeiro-search").fill(process.env.I2_PROPOSAL);
            const responsePromise = page.waitForResponse(r => new URL(r.url()).pathname === "/financeiro/cobrancas" && r.url().includes(encodeURIComponent(process.env.I2_PROPOSAL)));
            await page.locator("#financeiro-apply-filters").click();
            await responsePromise;
            const targetRow = page.locator(".financeiro-table-view tbody tr")
                .filter({ hasText: process.env.I2_PROPOSAL }).first();
            await targetRow.waitFor();
            const text = await page.locator("#financeiro-list").textContent();
            assert.ok(text.includes(process.env.I2_PROPOSAL));
            if (process.env.I2_EXPECT) {
                await targetRow.locator('[data-financeiro-charge-id]').click();
                await page.locator('#modal-financeiro:not(.hidden)').waitFor();
                assert.ok((await page.locator('#modal-financeiro').textContent()).includes(process.env.I2_EXPECT));
            }
            if (process.env.I2_SCREENSHOT) await page.screenshot({ path: process.env.I2_SCREENSHOT, fullPage: true });
            result({ visible: true });
        } else if (mode === "admin-budget") {
            await page.goto(`${frontendOrigin}/admin.html`);
            await page.waitForFunction(() => typeof window.fazerLogin === "function", null, { timeout: 10000 }).catch(error => {
                throw new Error(JSON.stringify({ message: error.message, errors, failedRequests }));
            });
            await page.locator("#username").fill(process.env.I2_USERNAME);
            await page.locator("#password").fill(process.env.I2_PASSWORD);
            const loginPromise = page.waitForResponse(r => new URL(r.url()).pathname === "/auth/login");
            await page.getByRole("button", { name: "ENTRAR NO SISTEMA" }).click();
            const loginResponse = await loginPromise;
            if (loginResponse.status() !== 200) throw new Error(`admin login failed: ${loginResponse.status()}`);
            await page.locator("#admin-area:not(.hidden)").waitFor();
            await page.locator('[data-admin-target="section-orcamentos"]').click();
            await page.locator("#orcamentos-search").fill(process.env.I2_NAME);
            const card = page.locator("#orcamentos-list .admin-list-item").first();
            await card.waitFor();
            assert.ok((await card.textContent()).includes(process.env.I2_NAME));
            await card.getByRole("button", { name: "Ver", exact: true }).click();
            assert.equal(await page.locator("#orc_nome").textContent(), process.env.I2_NAME);
            assert.ok((await page.locator("#orc_detalhes").inputValue()).includes("I2 Browser briefing synthetic"));
            result({ visible: true });
        } else throw new Error(`unknown mode: ${mode}`);

        assert.deepEqual(errors, []);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
