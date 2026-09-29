"""Build the optional generative provider without exposing configuration details."""

import logging

from core.config import settings
from services.ai_openai_provider import OpenAIProvider
from services.ai_provider import DisabledProvider


logger = logging.getLogger(__name__)
SUPPORTED_PROVIDERS = {"disabled", "openai", "groq"}
OPENAI_BASE_URL = "https://api.openai.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _secret(value):
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value or "")


def provider_mode(config=settings):
    configured = str(getattr(config, "AI_PROVIDER", "") or "").strip().lower()
    key = _secret(getattr(config, "AI_API_KEY", ""))
    model = str(getattr(config, "AI_MODEL", "") or "").strip()
    if configured and configured not in SUPPORTED_PROVIDERS:
        logger.error("ai_provider_configuration_invalid")
        return "disabled"
    mode = configured or ("openai" if key and model else "disabled")
    if mode in {"openai", "groq"} and (not key or not model):
        logger.warning("ai_provider_configuration_incomplete")
        return "disabled"
    return mode


def build_ai_provider(config=settings):
    if not getattr(config, "AI_ENABLED", False) or provider_mode(config) == "disabled":
        return DisabledProvider()
    key = _secret(getattr(config, "AI_API_KEY", ""))
    mode = provider_mode(config)
    configured_base_url = str(getattr(config, "AI_BASE_URL", "") or "").strip().rstrip("/")
    base_url = OPENAI_BASE_URL
    supports_store = True
    if mode == "groq":
        base_url = configured_base_url or GROQ_BASE_URL
        if base_url != GROQ_BASE_URL:
            logger.error("ai_provider_base_url_invalid")
            return DisabledProvider()
        supports_store = False
    return OpenAIProvider(
        key,
        config.AI_MODEL,
        timeout=getattr(config, "AI_TIMEOUT_SECONDS", 8),
        max_output_tokens=getattr(config, "AI_MAX_OUTPUT_TOKENS", 1200),
        base_url=base_url,
        provider_name=mode,
        supports_store=supports_store,
    )
