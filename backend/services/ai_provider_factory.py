"""Build the optional generative provider without exposing configuration details."""

import logging

from core.config import settings
from services.ai_openai_provider import OpenAIProvider
from services.ai_provider import DisabledProvider


logger = logging.getLogger(__name__)
SUPPORTED_PROVIDERS = {"disabled", "openai"}


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
    if mode == "openai" and (not key or not model):
        logger.warning("ai_provider_configuration_incomplete")
        return "disabled"
    return mode


def build_ai_provider(config=settings):
    if not getattr(config, "AI_ENABLED", False) or provider_mode(config) == "disabled":
        return DisabledProvider()
    key = _secret(getattr(config, "AI_API_KEY", ""))
    return OpenAIProvider(
        key,
        config.AI_MODEL,
        timeout=getattr(config, "AI_TIMEOUT_SECONDS", 8),
        max_output_tokens=getattr(config, "AI_MAX_OUTPUT_TOKENS", 1200),
    )
