"""Groq uses the existing Responses API contract without network calls."""

import json
import unittest
from types import SimpleNamespace

import httpx

from schemas.ai import ProviderInput, ProviderToolDefinition
from services.ai_openai_provider import OpenAIProvider
from services.ai_provider import DisabledProvider, ProviderError
from services.ai_provider_factory import GROQ_BASE_URL, build_ai_provider, provider_mode


def incoming(*, tools=()):
    return ProviderInput(
        system="Responda com seguranca.",
        message="Pergunta sintetica sem dados pessoais.",
        tools=tools,
    )


class GroqProviderTests(unittest.TestCase):
    def provider(self, handler):
        return OpenAIProvider(
            "test-secret",
            "openai/gpt-oss-20b",
            transport=httpx.MockTransport(handler),
            base_url=GROQ_BASE_URL,
            provider_name="groq",
            supports_store=False,
        )

    def test_factory_modes_and_official_base_url(self):
        base = dict(AI_ENABLED=True, AI_TIMEOUT_SECONDS=8, AI_MAX_OUTPUT_TOKENS=1200,
                    AI_MODEL="openai/gpt-oss-20b", AI_API_KEY="test-secret")
        groq = SimpleNamespace(**base, AI_PROVIDER="groq", AI_BASE_URL=GROQ_BASE_URL)
        built = build_ai_provider(groq)
        self.assertEqual(provider_mode(groq), "groq")
        self.assertEqual(built.provider_name, "groq")
        self.assertEqual(built.base_url, GROQ_BASE_URL)
        self.assertFalse(built.supports_store)

        invalid = SimpleNamespace(**base, AI_PROVIDER="groq", AI_BASE_URL="https://example.invalid/v1")
        self.assertIsInstance(build_ai_provider(invalid), DisabledProvider)
        incomplete = SimpleNamespace(**{**base, "AI_API_KEY": ""}, AI_PROVIDER="groq", AI_BASE_URL="")
        self.assertEqual(provider_mode(incomplete), "disabled")

    def test_request_response_usage_and_authorization(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["authorization"] = request.headers.get("authorization")
            seen["payload"] = json.loads(request.content)
            return httpx.Response(200, json={
                "status": "completed",
                "model": "openai/gpt-oss-20b",
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": "Resposta sintetica."},
                ]}],
                "usage": {"input_tokens": 20, "output_tokens": 4, "total_tokens": 24},
            })

        tool = ProviderToolDefinition(
            name="get_public_faq",
            description="Consulta FAQ publica.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        )
        result = self.provider(handler).generate(incoming(tools=(tool,)))
        self.assertEqual(result.text, "Resposta sintetica.")
        self.assertEqual(result.usage.provider, "groq")
        self.assertEqual(result.usage.total_tokens, 24)
        self.assertEqual(seen["url"], GROQ_BASE_URL + "/responses")
        self.assertEqual(seen["authorization"], "Bearer test-secret")
        self.assertNotIn("store", seen["payload"])
        self.assertFalse(seen["payload"]["parallel_tool_calls"])
        self.assertEqual(seen["payload"]["tools"][0]["name"], "get_public_faq")

    def test_tool_call_parsing(self):
        def handler(_request):
            return httpx.Response(200, json={
                "status": "completed",
                "model": "openai/gpt-oss-20b",
                "output": [{"type": "function_call", "call_id": "call_1",
                            "name": "get_public_faq", "arguments": "{}"}],
                "usage": {},
            })

        result = self.provider(handler).generate(incoming())
        self.assertEqual(result.tool_calls[0].name, "get_public_faq")
        self.assertEqual(result.tool_calls[0].arguments, {})

    def test_429_5xx_timeout_and_malformed_response_are_safe(self):
        cases = [
            (lambda _request: httpx.Response(429, json={"error": {"message": "rate limited"}}),
             "provider_unavailable"),
            (lambda _request: httpx.Response(503, json={"error": {"message": "unavailable"}}),
             "provider_unavailable"),
            (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("timeout", request=request)),
             "provider_timeout"),
            (lambda _request: httpx.Response(200, json={"status": "completed", "output": [{}]}),
             "provider_invalid_response"),
        ]
        for handler, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(ProviderError) as raised:
                    self.provider(handler).generate(incoming())
                self.assertEqual(raised.exception.code, expected)
                self.assertNotIn("test-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
