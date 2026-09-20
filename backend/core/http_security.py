import sqlite3
import re
import uuid
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core.rate_limit import allow_request

LIMITS = {
    "/auth/login": (10, 60),
    "/orcamentos": (5, 600),
    "/newsletter": (5, 600),
    "/newsletter/subscribe": (5, 600),
}

CHECKOUT_PAYMENT_PATH = re.compile(
    r"^/checkout/[0-9a-fA-F-]{36}/(?:pix|card)$"
)
CHECKOUT_RESUME_PATH = re.compile(
    r"^/checkout/[0-9a-fA-F-]{36}/pending-payment$"
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


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
        limit_key = path
        limit = LIMITS.get(path) if request.method == "POST" else None
        if request.method == "POST" and CHECKOUT_PAYMENT_PATH.fullmatch(path):
            limit_key, limit = "/checkout/payment", (8, 300)
        elif request.method == "GET" and CHECKOUT_RESUME_PATH.fullmatch(path):
            limit_key, limit = "/checkout/pending-payment", (12, 60)
        if limit:
            try:
                allowed, retry = allow_request(
                    f"{limit_key}:{request.client.host if request.client else 'unknown'}",
                    *limit,
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
