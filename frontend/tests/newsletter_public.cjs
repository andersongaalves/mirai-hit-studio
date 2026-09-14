const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        const contentType = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css" }[path.extname(file)] || "application/octet-stream";
        return route.fulfill({ body: await fs.readFile(file), contentType });
    } catch {
        return route.fulfill({ status: 200, body: "" });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const payloads = [];
        let fail = false;
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "https://www.googletagmanager.com") return route.fulfill({ contentType: "text/javascript", body: "" });
            if (url.origin === "http://localhost:8000" && url.pathname === "/newsletter/subscribe") {
                payloads.push(route.request().postDataJSON());
                return route.fulfill(fail ? { status: 503, json: { detail: "indisponível" } } : { json: { id: payloads.length } });
            }
            return route.fulfill({ json: [] });
        });
        await page.goto("http://localhost:4173/index.html");
        await page.waitForSelector("#newsletter-form");
        await page.getByRole("button", { name: "Aceitar metricas" }).click();
        await page.locator("#newsletter-email").fill("private@example.com");
        await page.locator("#newsletter-form").evaluate(form => form.requestSubmit());
        await page.waitForFunction(() => window.dataLayer?.some(item => item[0] === "event" && item[1] === "newsletter_subscribe"));
        assert.deepEqual(payloads[0], { email: "private@example.com", source: "site_footer" });
        const event = await page.evaluate(() => window.dataLayer.find(item => item[0] === "event" && item[1] === "newsletter_subscribe"));
        assert.deepEqual(event, ["event", "newsletter_subscribe", {}]);
        fail = true;
        await page.locator("#newsletter-email").fill("other@example.com");
        await page.locator("#newsletter-form").evaluate(form => form.requestSubmit());
        await page.waitForSelector(".notification.error");
        const events = await page.evaluate(() => window.dataLayer.filter(item => item[0] === "event" && item[1] === "newsletter_subscribe"));
        assert.equal(events.length, 1);
        assert.deepEqual(errors, []);
        console.log("PASS: public newsletter submit, success-only analytics and no PII analytics payload.");
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
