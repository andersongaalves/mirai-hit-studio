const ALLOWED_METHODS = new Set(["GET", "HEAD"]);


export async function onRequest({ request, env }) {
    if (!ALLOWED_METHODS.has(request.method)) {
        return new Response("Method Not Allowed", {
            status: 405,
            headers: { Allow: "GET, HEAD" },
        });
    }

    const assetUrl = new URL(request.url);
    assetUrl.pathname = "/checkout";
    const response = await env.ASSETS.fetch(new Request(assetUrl, request));
    const headers = new Headers(response.headers);
    headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}
