"""The direct Render address (*.onrender.com) bypasses Cloudflare's WAF and rate limiting.

Everything is served through https://api.miraihitstudio.com.br; the direct address only
accepts what cannot go through Cloudflare (file uploads above its 100 MB body limit) and
what external parties may still call there (health checks, signed webhooks, the
unsubscribe link of newsletters already sent).
"""
from fastapi import params
from starlette.routing import Match

DIRECT_SUFFIX = ".onrender.com"
ALWAYS_ALLOWED = ("/health",)
ALLOWED_PREFIXES = ("/webhooks/", "/newsletter/unsubscribe")
MESSAGE = "Use https://api.miraihitstudio.com.br."

_upload_routes = None


def _has_file(dependant):
    if any(isinstance(field.field_info, params.Form) for field in dependant.body_params):
        return True
    return any(_has_file(sub) for sub in dependant.dependencies)


def upload_routes(app):
    """Routes that take form bodies (multipart uploads; File is a Form), computed once."""
    global _upload_routes
    if _upload_routes is None:
        _upload_routes = [route for route in app.routes
                          if getattr(route, "dependant", None) is not None and _has_file(route.dependant)]
    return _upload_routes


def is_direct(host):
    return (host or "").split(":", 1)[0].lower().endswith(DIRECT_SUFFIX)


def allowed(request):
    """True when the request may be served on the address it arrived at."""
    if not is_direct(request.headers.get("host")):
        return True
    path = request.url.path
    if request.method == "OPTIONS" or path.rstrip("/") in ALWAYS_ALLOWED or path in ("", "/"):
        return True
    if path.startswith(ALLOWED_PREFIXES):
        return True
    for route in upload_routes(request.app):
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return True
    return False
