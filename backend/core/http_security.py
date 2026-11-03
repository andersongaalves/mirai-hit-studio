import sqlite3
import re
import uuid
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from services.rate_limit_service import allow_shared

# path -> (counter action, limit, window seconds)
LIMITS = {
    "/auth/login": ("login", 10, 60),
    "/orcamentos": ("budget", 5, 600),
    "/newsletter": ("newsletter", 5, 600),
    "/newsletter/subscribe": ("newsletter", 5, 600),
}

CHECKOUT_PAYMENT_PATH = re.compile(
    r"^/checkout/[0-9a-fA-F-]{36}/(?:pix|card)$"
)
CHECKOUT_RESUME_PATH = re.compile(
    r"^/checkout/[0-9a-fA-F-]{36}/pending-payment$"
)
# Public catalog previews: no account is needed, so each address gets a listening budget.
PUBLIC_PREVIEW_PATH = re.compile(r"^/beats/publico/\d+/previa$")

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


# Public previews (90 every 5 minutes per address) are counted in the process-local
# limiter: a listening budget does not need a database write per play, and a limiter
# failure never blocks listening.
PUBLIC_PREVIEW_LIMIT = (90, 300)


async def _public_preview_budget(request):
    from core.rate_limit import allow_request

    count, window = PUBLIC_PREVIEW_LIMIT
    identity = f"beat_preview_public:{request.client.host if request.client else 'unknown'}"
    try:
        allowed, retry = await run_in_threadpool(allow_request, identity, count, window)
    except (sqlite3.Error, OSError):
        return None
    if allowed:
        return None
    return JSONResponse({"detail": "Muitas prévias em pouco tempo. Aguarde alguns minutos."}, status_code=429,
                        headers={"Retry-After": str(retry)})


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        response = None
        path = request.url.path.rstrip("/")
        # The direct Render address only takes uploads; the rest goes through Cloudflare.
        from core import host_direto

        if not host_direto.allowed(request):
            response = JSONResponse({"detail": host_direto.MESSAGE}, status_code=421)
        # Scanner probes get a plain 404; repeated probes or floods get a temporary block.
        if path != "/health" and response is None:
            from core.protecao import protecao

            decision, retry = protecao.avaliar(request.client.host if request.client else "unknown", path)
            if decision == "varredura":
                response = JSONResponse({"detail": "Not Found"}, status_code=404)
            elif decision in ("excesso", "bloqueado"):
                response = JSONResponse({"detail": "Muitas requisições. Aguarde alguns minutos."}, status_code=429,
                                        headers={"Retry-After": str(retry)})
        limit = LIMITS.get(path) if request.method == "POST" else None
        if request.method == "POST" and CHECKOUT_PAYMENT_PATH.fullmatch(path):
            limit = ("checkout_payment", 8, 300)
        elif request.method == "GET" and CHECKOUT_RESUME_PATH.fullmatch(path):
            limit = ("checkout_resume", 12, 60)
        if request.method == "GET" and PUBLIC_PREVIEW_PATH.fullmatch(path) and response is None:
            response = await _public_preview_budget(request)
        if limit and response is None:
            try:
                action, count, window = limit
                allowed, retry = await run_in_threadpool(
                    allow_shared,
                    action,
                    request.client.host if request.client else "unknown",
                    count,
                    window,
                )
            except (sqlite3.Error, OSError):
                response = JSONResponse({"detail": "Protecao temporariamente indisponivel."}, status_code=503)
                allowed, retry = True, 0
            if not allowed:
                response = JSONResponse({"detail": "Muitas tentativas. Aguarde para tentar novamente."}, status_code=429,
                                    headers={"Retry-After": str(retry)})
        if response is None:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Request-ID"] = request_id
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


def cors_origins(value):
    from urllib.parse import urlsplit
    origins = []
    for origin in value.split(","):
        origin = origin.strip().rstrip("/")
        parts = urlsplit(origin)
        if "*" in origin or parts.scheme not in ("http", "https") or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username:
            raise ValueError("Configure origens CORS explicitas HTTP/HTTPS.")
        if origin not in origins:
            origins.append(origin)
    return origins
