const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "..", "..");


async function callRoute(pathname, method = "GET") {
    const moduleUrl = pathToFileURL(path.join(root, "functions", "checkout", "[[path]].js"));
    const { onRequest } = await import(moduleUrl.href);
    let assetRequest;
    const response = await onRequest({
        request: new Request(`https://mirai.example${pathname}`, { method }),
        env: {
            ASSETS: {
                fetch(request) {
                    assetRequest = request;
                    return new Response("checkout shell", { headers: { "Content-Type": "text/html" } });
                },
            },
        },
    });
    return { response, assetRequest };
}


(async () => {
    const redirects = await fs.readFile(path.join(root, "frontend", "_redirects"), "utf8");
    assert.doesNotMatch(redirects, /^\/checkout(?:\/|\s)/m, "checkout must not use an HTML rewrite");

    const tokenPath = "/checkout/test-token-routing-123?source=test";
    const routed = await callRoute(tokenPath);
    assert.equal(routed.response.status, 200);
    assert.equal(await routed.response.text(), "checkout shell");
    assert.equal(routed.response.headers.get("X-Robots-Tag"), "noindex, nofollow, noarchive");
    assert.equal(new URL(routed.assetRequest.url).pathname, "/checkout");
    assert.equal(new URL(routed.assetRequest.url).search, "?source=test");
    assert.equal(routed.assetRequest.method, "GET");

    const noToken = await callRoute("/checkout");
    assert.equal(new URL(noToken.assetRequest.url).pathname, "/checkout");

    const trailingSlash = await callRoute("/checkout/test-token-routing-123/");
    assert.equal(new URL(trailingSlash.assetRequest.url).pathname, "/checkout");

    const rejected = await callRoute("/checkout/test-token-routing-123", "POST");
    assert.equal(rejected.response.status, 405);
    assert.equal(rejected.response.headers.get("Allow"), "GET, HEAD");
    assert.equal(rejected.assetRequest, undefined);

    console.log("PASS: Pages checkout route serves the shell without redirects or token loss.");
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
