"""Responses API adapter. No vendor state, automatic retries or raw error logging."""
import json

import httpx

from schemas.ai import HandoffReason, ProviderResponse, ToolCall
from schemas.ai_usage import ProviderUsage
from services.ai_provider import ProviderError


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, api_key, model, *, timeout=8, transport=None, max_output_tokens=1200):
        if not 128 <= max_output_tokens <= 4096:
            raise ValueError("invalid_output_limit")
        self.api_key, self.model = api_key, model
        self.timeout, self.transport = timeout, transport
        self.max_output_tokens = max_output_tokens

    def generate(self, incoming):
        if not self.api_key or not self.model:
            raise ProviderError("provider_unavailable")
        # Tool results are bounded untrusted data, not instructions or fabricated calls.
        inputs = [{"role": entry.role, "content": entry.text} for entry in incoming.history]
        inputs.append({"role": "user", "content": incoming.message})
        inputs.append({"role": "user", "content": json.dumps({
            "knowledge": incoming.context,
            "tool_results": [item.model_dump(mode="json") for item in incoming.tool_results],
        }, ensure_ascii=False)})
        tools = [{"type": "function", "name": tool.name, "description": tool.description,
                  "parameters": tool.input_schema, "strict": False} for tool in incoming.tools]
        tools.append({"type": "function", "name": "request_handoff",
                      "description": "Solicitar atendimento humano quando necessario.",
                      "parameters": {"type": "object", "properties": {
                          "reason": {"type": "string", "enum": [item.value for item in HandoffReason]}},
                          "required": ["reason"], "additionalProperties": False}, "strict": True})
        usage = None
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post("https://api.openai.com/v1/responses", headers={
                    "Authorization": "Bearer " + self.api_key,
                }, json={"model": self.model, "instructions": incoming.system,
                         "input": inputs, "tools": tools, "parallel_tool_calls": False,
                         "store": False, "max_output_tokens": self.max_output_tokens})
            if response.status_code >= 400:
                raise ProviderError("provider_unavailable")
            data = response.json()
            raw_usage = data.get("usage") or {}
            try:
                usage = ProviderUsage(provider="openai", model=data.get("model") or self.model,
                    input_tokens=raw_usage.get("input_tokens"), output_tokens=raw_usage.get("output_tokens"),
                    total_tokens=raw_usage.get("total_tokens"),
                    cached_input_tokens=(raw_usage.get("input_tokens_details") or {}).get("cached_tokens"))
            except (ValueError, TypeError, AttributeError):
                usage = None
            if data.get("status") != "completed":
                raise ProviderError("provider_invalid_response", usage=usage)
            calls, texts = [], []
            for item in data["output"]:
                if item["type"] == "function_call":
                    arguments = json.loads(item["arguments"])
                    if item["name"] == "request_handoff":
                        return ProviderResponse(handoff_reason=HandoffReason(arguments["reason"]), usage=usage)
                    calls.append(ToolCall(id=item["call_id"], name=item["name"], arguments=arguments))
                elif item["type"] == "message":
                    texts.extend(part["text"] for part in item["content"] if part["type"] == "output_text")
            return (ProviderResponse(tool_calls=tuple(calls), usage=usage) if calls
                    else ProviderResponse(text="\n".join(texts), usage=usage))
        except httpx.TimeoutException:
            raise ProviderError("provider_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("provider_unavailable") from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("provider_invalid_response", usage=usage) from None
