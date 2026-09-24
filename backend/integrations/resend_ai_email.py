"""Small Resend adapter dedicated to the bidirectional AI email channel."""

import resend


class ResendAIEmailError(Exception):
    """Provider errors are intentionally reduced to a stable application code."""


def _mapping(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return {}


class ResendAIEmailClient:
    def __init__(self, api_key, *, client=resend):
        if not api_key:
            raise ResendAIEmailError("provider_not_configured")
        self.client = client
        self.client.api_key = api_key

    def retrieve_received(self, email_id):
        try:
            response = self.client.Emails.Receiving.get(email_id)
            return _mapping(response)
        except Exception:
            raise ResendAIEmailError("received_email_unavailable") from None

    def send_reply(self, *, sender, recipient, subject, text, headers, idempotency_key):
        try:
            response = self.client.Emails.send(
                {
                    "from": sender,
                    "to": recipient,
                    "subject": subject,
                    "text": text,
                    "headers": headers,
                },
                {"idempotency_key": idempotency_key},
            )
            result = _mapping(response)
            provider_id = result.get("id")
            if not isinstance(provider_id, str) or not provider_id.strip():
                raise ResendAIEmailError("delivery_invalid_response")
            return provider_id[:200]
        except ResendAIEmailError:
            raise
        except Exception:
            raise ResendAIEmailError("delivery_unavailable") from None
