"""The direct Render address (*.onrender.com) bypasses Cloudflare's WAF and rate limiting.

Everything is served through https://api.miraihitstudio.com.br; the direct address only
accepts what cannot go through Cloudflare (file uploads above its 100 MB body limit) and
what external parties may still call there (health checks, signed webhooks, the
unsubscribe link of newsletters already sent).
"""
DIRECT_SUFFIX = ".onrender.com"
ALWAYS_ALLOWED = ("/health",)
ALLOWED_PREFIXES = ("/webhooks/", "/newsletter/unsubscribe")
# Sign-in and account routes always go through Cloudflare's rate limiting.
NEVER_DIRECT = ("/auth/",)
UPLOAD_METHODS = ("POST", "PUT", "PATCH")
MESSAGE = "Use https://api.miraihitstudio.com.br."


def is_direct(host):
    return (host or "").split(":", 1)[0].lower().endswith(DIRECT_SUFFIX)


def is_upload(request):
    """A file upload: a multipart body sent to a write method (only upload routes read it)."""
    content_type = request.headers.get("content-type", "").lower()
    return request.method in UPLOAD_METHODS and content_type.startswith("multipart/form-data")


def _from_site(request):
    """A browser call made by the site's own pages (CORS origin), e.g. an older copy of
    the site still cached in someone's browser that calls this address directly."""
    origin = (request.headers.get("origin") or "").rstrip("/").lower()
    if not origin:
        return False
    try:
        from core.config import settings
        from core.http_security import cors_origins

        return origin in {item.lower() for item in cors_origins(settings.ALLOWED_ORIGINS)}
    except Exception:  # noqa: BLE001 - misconfigured origins never open the address.
        return False


def allowed(request):
    """True when the request may be served on the address it arrived at."""
    if not is_direct(request.headers.get("host")):
        return True
    if _from_site(request):
        return True
    path = request.url.path
    if request.method == "OPTIONS" or path.rstrip("/") in ALWAYS_ALLOWED or path in ("", "/"):
        return True
    if path.startswith(ALLOWED_PREFIXES):
        return True
    if path.startswith(NEVER_DIRECT):
        return False
    return is_upload(request)
