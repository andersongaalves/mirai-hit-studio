const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const types = {
    ".css": "text/css",
    ".html": "text/html",
    ".js": "text/javascript",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
};

let apiMode = "success";
const projects = [
    {
        id: 1,
        titulo: "Faixa <script>alert(1)</script>",
        artista: "Artista <img src=x onerror=alert(1)>",
        link_capa: "https://media.invalid/cover-1.webp",
        link_audio: "javascript:alert(1)",
        audio_before_url: "https://media.invalid/before-1.mp3",
        audio_after_url: "https://media.invalid/after-1.mp3",
        landing_order: 1,
    },
    ...[2, 3, 4, 5].map(number => ({
        id: number,
        titulo: `Projeto ${number}`,
        artista: `Artista ${number}`,
        link_capa: number === 2 ? "" : `https://media.invalid/cover-${number}.webp`,
        link_audio: "https://example.com/release",
        audio_before_url: `https://media.invalid/before-${number}.mp3`,
        audio_after_url: `https://media.invalid/after-${number}.mp3`,
        landing_order: number,
    })),
];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: types[path.extname(file)] || "application/octet-stream",
        });
    } catch {
        return route.fulfill({ status: 404, body: "" });
    }
}

(async () => {
    const browser = await chromium.launch({
        headless: true,
        channel: process.env.BROWSER_CHANNEL || "msedge",
    });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
        await context.addInitScript(() => {
            localStorage.setItem("mirai.analytics_consent.v1", "rejected");
            const states = new WeakMap();
            const state = media => {
                if (!states.has(media)) states.set(media, { paused: true, currentTime: 0, duration: 90 });
                return states.get(media);
            };
            Object.defineProperties(HTMLMediaElement.prototype, {
                paused: { configurable: true, get() { return state(this).paused; } },
                ended: { configurable: true, get() { return false; } },
                duration: { configurable: true, get() { return state(this).duration; } },
                currentTime: {
                    configurable: true,
                    get() { return state(this).currentTime; },
                    set(value) {
                        state(this).currentTime = Number(value) || 0;
                        this.dispatchEvent(new Event("timeupdate"));
                    },
                },
            });
            HTMLMediaElement.prototype.load = function load() {
                state(this).paused = true;
                state(this).currentTime = 0;
                queueMicrotask(() => this.dispatchEvent(new Event("loadedmetadata")));
            };
            HTMLMediaElement.prototype.play = function play() {
                state(this).paused = false;
                this.dispatchEvent(new Event("play"));
                return Promise.resolve();
            };
            HTMLMediaElement.prototype.pause = function pause() {
                state(this).paused = true;
                this.dispatchEvent(new Event("pause"));
            };
        });

        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await context.route("**/*", async route => {
            const url = new URL(route.request().url());
            if (url.origin === "http://localhost:4173") return staticResponse(route);
            if (url.origin === "http://localhost:8000" && url.pathname === "/projetos/public/mix-comparisons") {
                if (apiMode === "failure") return route.fulfill({ status: 503, json: { detail: "indisponível" } });
                return route.fulfill({ json: apiMode === "empty" ? [] : projects });
            }
            if (url.origin === "http://localhost:8000" && url.pathname === "/projetos") {
                return route.fulfill({ json: [] });
            }
            if (["https://media.invalid", "https://example.com"].includes(url.origin)) {
                if (url.pathname.includes("cover-")) {
                    return route.fulfill({
                        contentType: "image/svg+xml",
                        body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 10"><rect width="16" height="10" fill="#102039"/><path d="M0 8L6 2l4 4 2-2 4 4" fill="none" stroke="#00d5ed"/></svg>',
                    });
                }
                return route.fulfill({ status: 200, body: "" });
            }
            return route.fulfill({ status: 404, body: "" });
        });

        await page.goto("http://localhost:4173/");
        await page.waitForSelector("#mix-comparison:not([hidden])");
        assert.equal(await page.locator(".home-hero__listen").getAttribute("href"), "#mix-comparison");
        await page.locator(".home-hero__listen").click();
        await page.waitForTimeout(500);
        const anchorLayout = await page.evaluate(() => ({
            headerBottom: document.querySelector(".site-header")?.getBoundingClientRect().bottom || 0,
            headingTop: document.querySelector(".mix-showcase__heading").getBoundingClientRect().top,
        }));
        assert.ok(anchorLayout.headingTop >= anchorLayout.headerBottom - 1, JSON.stringify(anchorLayout));
        assert.match(await page.locator("#mix-comparison-title").textContent(), /Resultado não se explica/);
        assert.equal(await page.locator("#mix-project-selector button").count(), 4);
        assert.equal(await page.locator('[data-mix-version="before"]').getAttribute("aria-pressed"), "true");
        assert.equal(await page.locator('[data-mix-version="after"]').getAttribute("aria-pressed"), "false");
        assert.match(await page.locator("#mix-title").textContent(), /<script>alert\(1\)<\/script>/);
        assert.equal(await page.locator("#mix-comparison script").count(), 0);
        assert.equal(await page.locator("#mix-external-link").isHidden(), true);

        await page.locator("#mix-audio-before").evaluate(audio => { audio.currentTime = 21.42; });
        await page.locator("#mix-play").click();
        await page.locator('[data-mix-version="after"]').click();
        const playingSwap = await page.evaluate(() => ({
            beforePaused: document.getElementById("mix-audio-before").paused,
            afterPaused: document.getElementById("mix-audio-after").paused,
            afterTime: document.getElementById("mix-audio-after").currentTime,
        }));
        assert.deepEqual(playingSwap, { beforePaused: true, afterPaused: false, afterTime: 21.42 });

        await page.locator("#mix-play").click();
        await page.locator('[data-mix-version="before"]').click();
        assert.equal(await page.locator("#mix-audio-before").evaluate(audio => audio.paused), true);
        assert.equal(await page.locator("#mix-audio-before").evaluate(audio => audio.currentTime), 21.42);

        await page.locator("#mix-progress").evaluate(input => {
            input.value = "12.5";
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });
        assert.deepEqual(await page.evaluate(() => [
            document.getElementById("mix-audio-before").currentTime,
            document.getElementById("mix-audio-after").currentTime,
        ]), [12.5, 12.5]);

        await page.locator('#mix-project-selector button[data-project-index="1"]').click();
        assert.equal(await page.locator("#mix-title").textContent(), "Projeto 2");
        assert.equal(await page.locator('[data-mix-version="before"]').getAttribute("aria-pressed"), "true");
        assert.equal(await page.locator("#mix-cover-wrap").isHidden(), true);
        assert.equal(await page.locator("#mix-external-link").getAttribute("href"), "https://example.com/release");

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `mix comparison overflow at ${width}px: ${overflow}px`);
        }
        if (process.env.VISUAL_OUTPUT) {
            await fs.mkdir(process.env.VISUAL_OUTPUT, { recursive: true });
            await page.locator('#mix-project-selector button[data-project-index="0"]').click();
            await page.setViewportSize({ width: 1440, height: 900 });
            await page.locator("#mix-comparison").screenshot({
                path: path.join(process.env.VISUAL_OUTPUT, "home-mix-comparison.png"),
            });
            await page.setViewportSize({ width: 390, height: 844 });
            await page.locator("#mix-comparison").screenshot({
                path: path.join(process.env.VISUAL_OUTPUT, "home-mix-comparison-mobile.png"),
            });
        }

        apiMode = "empty";
        await page.reload();
        await page.waitForSelector("#home-portfolio-track .public-empty");
        assert.equal(await page.locator("#mix-comparison").isHidden(), true);
        assert.equal(await page.locator("#mix-hero-link").isHidden(), true);

        apiMode = "failure";
        await page.reload();
        await page.waitForSelector("#home-portfolio-track .public-empty");
        assert.equal(await page.locator("#mix-comparison").isHidden(), true);
        assert.deepEqual(errors, []);
        console.log("PASS: landing A/B player rendering, synchronization, safety, empty/error states and responsiveness.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
