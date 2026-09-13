from urllib.parse import urlsplit
from pydantic import HttpUrl, TypeAdapter


def http_url(value):
    if value in (None, ""):
        return value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password:
        raise ValueError("http_https_url_required")
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("invalid_url")
    TypeAdapter(HttpUrl).validate_python(value)
    return value
