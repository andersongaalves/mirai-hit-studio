const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp", ".woff2": "font/woff2", ".ttf": "font/ttf" };
let apiMode = "success";
const projects = [1, 2, 3, 4, 5, 6].map(id => ({
    id, titulo: id === 1 ? "Faixa <script>alert(1)</script>" : `Projeto ${id}`,
    artista: id === 1 ? "Artista <img src=x onerror=alert(1)>" : `Artista ${id}`,
    categoria: "Mixagem e Masterização", destaque: id !== 5,
    link_capa: id === 2 ? "" : `https://media.invalid/cover-${id}.webp`,
    link_audio: id === 1 ? "javascript:alert(1)" : "https://example.com/release",
    audio_before_url: id === 4 ? "javascript:alert(1)" : id === 6 ? "" : `https://media.invalid/before-${id}.mp3`,
    audio_after_url: id === 6 ? "" : `https://media.invalid/after-${id}.mp3`, landing_order: id,
}));

// A local PCM fixture for the native browser media test; never fetch real tracks.
const sampleRate = 8000;
const frames = sampleRate * 12;
const wav = Buffer.alloc(44 + frames * 2);
wav.write("RIFF"); wav.writeUInt32LE(wav.length - 8, 4); wav.write("WAVEfmt ", 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(sampleRate, 24); wav.writeUInt32LE(sampleRate * 2, 28);
wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write("data", 36); wav.writeUInt32LE(frames * 2, 40);
for (let i = 0; i < frames; i += 1) wav.writeInt16LE(Math.round(Math.sin(i * 2 * Math.PI * 220 / sampleRate) * 1000), 44 + i * 2);

async function serve(route) {
    const url = new URL(route.request().url());
    if (url.origin === "http://localhost:4173") {
        const file = path.resolve(root, `.${decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname)}`);
        assert.ok(file.startsWith(root + path.sep));
        try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
        catch { return route.fulfill({ status: 404, body: "" }); }
    }
    if (url.origin === "http://localhost:8000" && url.pathname === "/projetos/public/mix-comparisons") {
        if (apiMode === "failure") return route.fulfill({ status: 503, json: { detail: "indisponível" } });
        return route.fulfill({ json: apiMode === "empty" ? [] : apiMode === "invalid" ? {} : projects });
    }
    if (url.origin === "http://localhost:8000" && url.pathname === "/projetos") {
        if (apiMode === "projects_failure") return route.fulfill({ status: 503, json: {} });
        return route.fulfill({ json: apiMode === "no_hits" ? [] : projects });
    }
    if (url.origin === "https://media.invalid") {
        if (url.pathname.endsWith(".mp3")) {
            const range = /^bytes=(\d+)-(\d*)$/.exec(route.request().headers().range || "");
            if (!range) return route.fulfill({ contentType: "audio/wav", headers: { "accept-ranges": "bytes" }, body: wav });
            const start = Number(range[1]);
            const end = Math.min(range[2] ? Number(range[2]) : wav.length - 1, wav.length - 1);
            if (start > end) return route.fulfill({ status: 416, headers: { "content-range": `bytes */${wav.length}` } });
            return route.fulfill({ status: 206, contentType: "audio/wav", headers: {
                "accept-ranges": "bytes", "content-range": `bytes ${start}-${end}/${wav.length}`,
            }, body: wav.subarray(start, end + 1) });
        }
        return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 9"><rect width="16" height="9" fill="#102039"/><path d="M0 8L6 2l4 4 2-2 4 4" fill="none" stroke="#00d5ed"/></svg>' });
    }
    return route.fulfill({ status: 404, body: "" });
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
        context.setDefaultTimeout(15000);
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
                readyState: { configurable: true, get() { return 1; } },
                duration: { configurable: true, get() { return state(this).duration; } },
                currentTime: { configurable: true, get() { return state(this).currentTime; }, set(value) {
                    state(this).currentTime = Number(value) || 0; this.dispatchEvent(new Event("timeupdate"));
                } },
            });
            window.mediaDuration = (audio, duration) => { state(audio).duration = duration; };
            window.pendingPlays = [];
            HTMLMediaElement.prototype.load = function () { queueMicrotask(() => this.dispatchEvent(new Event("loadedmetadata"))); };
            HTMLMediaElement.prototype.play = function () {
                if (window.failNextPlay) { window.failNextPlay = false; return Promise.reject(new Error("synthetic media failure")); }
                const start = () => { state(this).paused = false; this.dispatchEvent(new Event("play")); };
                if (window.delayNextPlay) {
                    window.delayNextPlay = false;
                    return new Promise(resolve => window.pendingPlays.push(() => { start(); resolve(); }));
                }
                start(); return Promise.resolve();
            };
            HTMLMediaElement.prototype.pause = function () { state(this).paused = true; this.dispatchEvent(new Event("pause")); };
        });
        await context.route("**/*", serve);
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        let popups = 0;
        page.on("popup", () => { popups += 1; });
        await page.goto("http://localhost:4173/");
        await page.waitForSelector(".home-hit .hit-mix");
        assert.equal(await page.locator(".home-hit").count(), 5, "one card per hit, no cloned players");
        assert.equal(await page.locator(".hit-mix").count(), 3);
        assert.equal(await page.locator(".mix-showcase").count(), 0);
        assert.equal(await page.locator("#mix-comparison.home-portfolio").count(), 1);
        assert.equal(await page.locator(".home-hit[data-project-id='5']").count(), 0, "a comparison alone does not make a hit");
        assert.equal(await page.locator(".home-hit[data-project-id='4'] audio, .home-hit[data-project-id='6'] audio").count(), 0);
        assert.equal(await page.locator("a .hit-mix, a button, a audio").count(), 0);
        assert.equal(await page.locator(".home-hit script, .home-hit [onerror]").count(), 0);
        const first = page.locator(".home-hit[data-project-id='1']");
        const second = page.locator(".home-hit[data-project-id='2']");
        const before = first.locator('[data-mix-audio="before"]');
        const after = first.locator('[data-mix-audio="after"]');
        if (process.env.VISUAL_OUTPUT) {
            await fs.mkdir(process.env.VISUAL_OUTPUT, { recursive: true });
            await first.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, "home-hit-initial.png"), animations: "disabled" });
        }
        assert.match(await first.locator("h3").textContent(), /<script>alert\(1\)<\/script>/);
        assert.equal(await first.locator(".home-hit__release").count(), 0);
        assert.equal(await second.locator(".home-hit__release").getAttribute("href"), "https://example.com/release");
        await second.locator(".home-hit__cover").scrollIntoViewIfNeeded();
        await page.waitForFunction(() => {
            const img = document.querySelector('.home-hit[data-project-id="2"] .home-hit__cover');
            return img?.complete && img.naturalWidth > 0;
        });
        assert.ok(await second.locator(".home-hit__cover").evaluate(img => img.naturalWidth > 0), "fallback cover must load");
        assert.equal(await page.locator(".home-hit audio").evaluateAll(items => items.every(audio => audio.paused)), true);
        await page.locator("#mix-hero-link").click();
        await page.waitForTimeout(400);
        const anchor = await page.evaluate(() => ({ header: document.querySelector(".site-header")?.getBoundingClientRect().bottom || 0,
            title: document.querySelector("#mix-comparison .home-section-heading").getBoundingClientRect().top }));
        assert.ok(anchor.title >= anchor.header - 1, JSON.stringify(anchor));

        await before.evaluate(audio => { audio.currentTime = 21.42; });
        await first.locator("[data-mix-play]").click();
        await first.locator('[data-mix-version="after"]').click();
        assert.equal(await before.evaluate(audio => audio.paused), true);
        assert.equal(await after.evaluate(audio => audio.paused), false);
        assert.equal(await after.evaluate(audio => audio.currentTime), 21.42);
        await first.locator("[data-mix-play]").click();
        await first.locator('[data-mix-version="before"]').click();
        assert.equal(await before.evaluate(audio => audio.paused), true);
        assert.equal(await before.evaluate(audio => audio.currentTime), 21.42);
        await first.locator("[data-mix-progress]").evaluate(input => { input.value = "12.5"; input.dispatchEvent(new Event("input", { bubbles: true })); });
        assert.deepEqual(await first.locator("audio").evaluateAll(items => items.map(audio => audio.currentTime)), [12.5, 12.5]);
        await first.locator("[data-mix-volume]").evaluate(input => { input.value = "0.35"; input.dispatchEvent(new Event("input", { bubbles: true })); });
        assert.deepEqual(await first.locator("audio").evaluateAll(items => items.map(audio => audio.volume)), [0.35, 0.35]);
        await first.locator("[data-mix-mute]").click();
        assert.equal(await first.locator("[data-mix-mute]").getAttribute("aria-pressed"), "true");
        assert.equal(await first.locator("audio").evaluateAll(items => items.every(audio => audio.muted)), true);
        await first.locator("[data-mix-mute]").click();
        assert.deepEqual(await first.locator("audio").evaluateAll(items => items.map(audio => audio.volume)), [0.35, 0.35]);

        await first.locator("[data-mix-play]").click();
        await second.locator("[data-mix-play]").click();
        assert.equal(await first.locator("audio").evaluateAll(items => items.every(audio => audio.paused)), true);
        assert.equal(await second.locator('[data-mix-audio="before"]').evaluate(audio => audio.paused), false);
        await second.locator("[data-mix-play]").click();
        await page.evaluate(() => { window.delayNextPlay = true; });
        await first.locator("[data-mix-play]").click();
        await second.locator("[data-mix-play]").click();
        await page.evaluate(() => window.pendingPlays.shift()());
        assert.equal(await before.evaluate(audio => audio.paused), true, "late play cannot restart the previous hit");
        assert.equal(await second.locator('[data-mix-audio="before"]').evaluate(audio => audio.paused), false);
        await second.locator("[data-mix-play]").click();
        await page.evaluate(() => { window.delayNextPlay = true; });
        await first.locator("[data-mix-play]").click();
        await first.locator("[data-mix-play]").click();
        await first.locator("[data-mix-play]").click();
        await page.evaluate(() => window.pendingPlays.shift()());
        assert.equal(await before.evaluate(audio => audio.paused), false, "old promise cannot pause a new play on the same hit");
        await first.locator("[data-mix-play]").click();
        await page.evaluate(() => { window.failNextPlay = true; });
        await first.locator("[data-mix-play]").click();
        assert.match(await first.locator("[data-mix-status]").textContent(), /Não foi possível reproduzir/);
        assert.match(await first.locator("[data-mix-play]").getAttribute("aria-label"), /Reproduzir/);
        await before.evaluate(audio => { audio.currentTime = 70; });
        await after.evaluate(audio => window.mediaDuration(audio, 40));
        await first.locator('[data-mix-version="after"]').click();
        assert.equal(await after.evaluate(audio => audio.currentTime), 40, "shorter versions clamp the seek position");
        assert.equal(popups, 0, "player controls must not open external release links");

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `page overflow at ${width}`);
            for (const player of await page.locator(".hit-mix").all()) {
                assert.ok(await player.evaluate(el => el.scrollWidth <= el.clientWidth + 1), `player overflow at ${width}`);
            }
        }
        if (process.env.VISUAL_OUTPUT) {
            await fs.mkdir(process.env.VISUAL_OUTPUT, { recursive: true });
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await first.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, `home-hit-${width}.png`), animations: "disabled" });
                await page.locator("#mix-comparison").screenshot({ path: path.join(process.env.VISUAL_OUTPUT, `home-hits-${width}.png`), animations: "disabled" });
            }
        }
        for (const mode of ["empty", "failure", "invalid"]) {
            apiMode = mode;
            await page.reload();
            await page.waitForSelector(".home-hit");
            await page.waitForFunction(() => document.querySelector("#mix-comparison.home-portfolio"));
            assert.equal(await page.locator(".home-hit").count(), 5);
            assert.equal(await page.locator(".hit-mix").count(), 0);
            assert.equal(await page.locator("#mix-hero-link").isHidden(), true);
        }
        for (const mode of ["no_hits", "projects_failure"]) {
            apiMode = mode;
            await page.reload();
            await page.waitForFunction(() => !document.querySelector("#home-portfolio-track")?.textContent.includes("Carregando"));
            assert.equal(await page.locator(".home-hit, .hit-mix").count(), 0);
            assert.equal(await page.locator("#mix-hero-link").isHidden(), true);
        }
        assert.deepEqual(errors, []);
        console.log("PASS: mocked media interactions, ownership of playback, responsive layout and failure states.");
        await context.close();

        // Native HTMLMediaElement playback: no media-prototype mocks in this context.
        apiMode = "success";
        const native = await browser.newContext({ viewport: { width: 390, height: 844 } });
        native.setDefaultTimeout(15000);
        await native.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "rejected"));
        await native.route("**/*", serve);
        const real = await native.newPage();
        await real.goto("http://localhost:4173/#mix-comparison");
        await real.waitForSelector('.hit-mix');
        assert.ok(await real.locator('#mix-comparison .home-section-heading').evaluate(el => {
            const bounds = el.getBoundingClientRect();
            return bounds.top >= 0 && bounds.top < innerHeight;
        }), "direct comparison links must reach the integrated hits");
        console.log("Native media: rendered hit players.");
        const a = real.locator('.home-hit[data-project-id="1"]');
        const b = real.locator('.home-hit[data-project-id="2"]');
        const click = async control => {
            await control.evaluate(el => el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" }));
            await control.click();
        };
        await a.evaluate(el => {
            el.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
            el.querySelectorAll('audio').forEach(audio => audio.load());
        });
        await real.waitForFunction(() => [...document.querySelectorAll('.home-hit[data-project-id="1"] audio')]
            .every(audio => Number.isFinite(audio.duration) && audio.duration > 0));
        console.log("Native media: visible pair metadata loaded.");
        await click(a.locator('[data-mix-play]'));
        await real.waitForFunction(() => !document.querySelector('.home-hit[data-project-id="1"] [data-mix-audio="before"]').paused);
        await a.locator('[data-mix-audio="before"]').evaluate(audio => { audio.currentTime = 2; });
        await real.waitForFunction(() => {
            const audio = document.querySelector('.home-hit[data-project-id="1"] [data-mix-audio="before"]');
            return !audio.seeking && audio.currentTime >= 1.9;
        });
        await click(a.locator('[data-mix-version="after"]'));
        await real.waitForFunction(() => !document.querySelector('.home-hit[data-project-id="1"] [data-mix-audio="after"]').paused);
        assert.equal(await a.locator('[data-mix-audio="before"]').evaluate(audio => audio.paused), true);
        await real.waitForFunction(() => {
            const audio = document.querySelector('.home-hit[data-project-id="1"] [data-mix-audio="after"]');
            return !audio.seeking && audio.currentTime >= 1.9;
        });
        await click(b.locator('[data-mix-play]'));
        await real.waitForFunction(() => !document.querySelector('.home-hit[data-project-id="2"] [data-mix-audio="before"]').paused);
        assert.equal(await a.locator('audio').evaluateAll(items => items.every(audio => audio.paused)), true);
        await native.close();
        console.log("PASS: hit-integrated A/B players, native audio, synchronization, single playback, volume, races, safety and responsive layouts.");
    } catch (error) {
        console.error("Player regression failed before browser cleanup:", error);
        throw error;
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
