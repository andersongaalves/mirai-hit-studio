"""Email channel normalization and safe outbound threading helpers."""

from dataclasses import dataclass
from email.header import decode_header
from email.utils import parseaddr
from html.parser import HTMLParser
import hashlib
import re

from schemas.ai import InboundMessage


class _PlainTextParser(HTMLParser):
    _block_tags = {"br", "div", "li", "p", "pre", "section", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "svg", "iframe", "object"}:
            self._ignored += 1
        elif not self._ignored and tag in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "svg", "iframe", "object"} and self._ignored:
            self._ignored -= 1
        elif not self._ignored and tag in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._ignored:
            self.parts.append(data)


def html_to_text(value):
    parser = _PlainTextParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return ""
    return re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts)).strip()


def _decode_header(value):
    if not isinstance(value, str):
        return ""
    decoded = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded).replace("\r", " ").replace("\n", " ").strip()


def _header(headers, name):
    if not isinstance(headers, dict):
        return None
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return value
    return None


def normalize_sender(value):
    name, address = parseaddr(str(value or ""))
    address = address.strip().casefold()
    if "\r" in address or "\n" in address or address.count("@") != 1:
        return None
    local, domain = address.rsplit("@", 1)
    if not local or not domain or any(char.isspace() for char in address) or len(address) > 200:
        return None
    return f"{local}@{domain}"


def normalize_message_id(value):
    if not isinstance(value, str):
        return None
    value = value.replace("\r", "").replace("\n", "").strip()
    if not value:
        return None
    if len(value) > 998:
        return "hash:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip() or None
    return value.strip("<>") or None


def format_message_id(value):
    if not value or value.startswith("hash:"):
        return None
    return value if value.startswith("<") else f"<{value}>"


def _references(value):
    if isinstance(value, (list, tuple)):
        values = value
    elif isinstance(value, str):
        values = re.findall(r"<[^>]+>|\S+", value)
    else:
        values = ()
    result = []
    for item in values:
        normalized = normalize_message_id(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result[:20])


def thread_key(root_message_id):
    return "email-thread:" + hashlib.sha256(root_message_id.encode("utf-8")).hexdigest()


def external_message_id(provider_email_id, message_id):
    value = provider_email_id or message_id
    if not value:
        return None
    prefix = "resend:" if provider_email_id else "message-id:"
    result = prefix + value
    return result if len(result) <= 200 else prefix + hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class ReceivedEmail:
    provider_email_id: str
    sender_email: str
    subject: str
    message_id: str
    in_reply_to: str | None
    references: tuple[str, ...]
    text: str
    headers: dict
    received_at: object
    has_attachments: bool

    @property
    def external_message_id(self):
        return external_message_id(self.provider_email_id, self.message_id)

    @property
    def root_message_id(self):
        return self.references[0] if self.references else (self.in_reply_to or self.message_id)


class EmailChannelAdapter:
    def __init__(self, *, max_body_chars=8000):
        self.max_body_chars = max_body_chars

    def received(self, payload, received_at, *, provider_email_id, retrieved=None):
        data = dict(retrieved or {})
        data.update({key: value for key, value in (payload or {}).items() if value not in (None, "", [], {})})
        headers = data.get("headers") if isinstance(data.get("headers"), dict) else {}
        sender = normalize_sender(data.get("from"))
        if not sender:
            raise ValueError("invalid_sender")
        message_id = normalize_message_id(data.get("message_id") or _header(headers, "Message-ID"))
        if not message_id:
            message_id = "resend-" + provider_email_id
        in_reply_to = normalize_message_id(data.get("in_reply_to") or _header(headers, "In-Reply-To"))
        references = _references(data.get("references") or _header(headers, "References"))
        text = data.get("text") if isinstance(data.get("text"), str) else ""
        if not text.strip() and isinstance(data.get("html"), str):
            text = html_to_text(data["html"])
        text = text.strip()
        if not text:
            raise ValueError("email_body_unavailable")
        text = text[:self.max_body_chars]
        subject = _decode_header(data.get("subject"))[:200] or "Mensagem para a Mirai Hit Studio"
        attachments = data.get("attachments")
        return ReceivedEmail(
            provider_email_id=provider_email_id,
            sender_email=sender,
            subject=subject,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            text=text,
            headers=headers,
            received_at=received_at,
            has_attachments=isinstance(attachments, list) and bool(attachments),
        )

    def normalize(self, email, *, thread_key_value, sender_reference, request_id=None):
        from schemas.ai import SafeMetadata

        return InboundMessage(
            channel="email",
            external_message_id=email.external_message_id,
            external_thread_id=thread_key_value,
            sender_reference=sender_reference,
            text=email.text,
            received_at=email.received_at,
            metadata=SafeMetadata(request_id=request_id),
        )

    def outbound(self, message, thread, *, sender):
        subject = thread.subject if thread.subject.casefold().startswith("re:") else f"Re: {thread.subject}"
        headers = {}
        reply_to = format_message_id(thread.last_inbound_message_id)
        root = format_message_id(thread.root_message_id)
        if reply_to:
            headers["In-Reply-To"] = reply_to
        references = " ".join(item for item in (root, reply_to) if item)
        if references:
            headers["References"] = references[:998]
        return {
            "sender": sender,
            "recipient": thread.sender_email,
            "subject": subject[:200],
            "text": message.text,
            "headers": headers,
            "idempotency_key": f"ai-email/reply/{message.id}",
        }


def auto_reply(headers):
    auto_submitted = str(_header(headers, "Auto-Submitted") or "").casefold()
    precedence = str(_header(headers, "Precedence") or "").casefold()
    return (
        auto_submitted not in {"", "no"}
        or bool(_header(headers, "X-Autoreply"))
        or bool(_header(headers, "X-Autorespond"))
        or precedence in {"bulk", "list", "junk"}
    )


def looks_automated(sender_email):
    local = sender_email.split("@", 1)[0].casefold()
    return local in {"mailer-daemon", "postmaster", "no-reply", "noreply", "do-not-reply", "donotreply"}
