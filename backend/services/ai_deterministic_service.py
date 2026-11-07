"""Conservative local replies for clear public intents; no generative provider needed."""

from dataclasses import dataclass
import re
import unicodedata

from schemas.ai import ToolCall


CASE_LABELS = {
    "client_case": "case de cliente",
    "demo": "demo",
    "concept_project": "projeto conceitual",
    "study": "estudo",
}


@dataclass(frozen=True)
class DeterministicReply:
    intent: str
    text: str


def _normalize(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    ).strip()


def _intent(message):
    text = _normalize(message)
    if re.fullmatch(r"(?:oi|ola|bom dia|boa tarde|boa noite|hey|hello)[!,.? ]*", text):
        return "greeting", None
    faq = (
        ("contracting", r"\b(?:como (?:contratar|funciona a contratacao|pedir (?:um )?orcamento)|quero (?:contratar|solicitar (?:um )?orcamento))\b"),
        ("deadlines", r"\b(?:qual (?:e o )?prazo|quanto tempo (?:leva|demora)|prazo de entrega)\b"),
        ("revisions", r"\b(?:quantas revisoes|como funcionam? (?:as )?revisoes|revisoes incluidas)\b"),
        ("rights", r"\b(?:como funcionam? (?:os )?direitos|direitos autorais|licenca|exclusividade)\b"),
        ("payments", r"\b(?:formas? de pagamento|como (?:posso )?pagar|aceita (?:pix|cartao)|parcelamento)\b"),
    )
    for topic, pattern in faq:
        if re.search(pattern, text):
            return "faq", topic
    if re.search(r"\b(?:quais|que) servicos\b|\bo que voces (?:fazem|oferecem)\b|\bservicos (?:disponiveis|oferecidos)\b", text):
        return "services", None
    if re.search(r"\b(?:portfolio|portifolio)\b|\b(?:ver|mostrar|conhecer) (?:os )?(?:trabalhos|cases|demos)\b", text):
        return "portfolio", None
    return None, None


def deterministic_reply(message, registry, context, *, telemetry=None):
    intent, topic = _intent(message)
    if intent is None:
        return None
    if intent == "greeting":
        return DeterministicReply(
            intent,
            "Olá! Como posso ajudar? Posso falar de serviços, portfólio ou orçamento.",
        )
    tool_name, arguments = {
        "faq": ("get_public_faq", {"topic": topic}),
        "services": ("list_services", {"limit": 5}),
        "portfolio": ("get_public_portfolio", {"limit": 4}),
    }[intent]
    result = registry.run(
        ToolCall(id=f"deterministic_{intent}", name=tool_name, arguments=arguments),
        context,
        telemetry=telemetry,
    )
    if not result.success or not result.data:
        return None
    if intent == "faq":
        items = result.data.get("items") or []
        return DeterministicReply(intent, items[0]["answer"]) if len(items) == 1 else None
    if intent == "services":
        services = result.data.get("services") or []
        if not services:
            return DeterministicReply(intent, "Não há serviços publicados agora. Posso chamar a equipe.")
        lines = [item["name"] for item in services]
        return DeterministicReply(
            intent,
            "Serviços da Mirai:\n- " + "\n- ".join(lines) + "\nO valor final sai na proposta.",
        )
    projects = result.data.get("projects") or []
    if not projects:
        return DeterministicReply(intent, "Ainda não há trabalhos no portfólio público.")
    lines = [
        f"{item['title']} — {item['credited_artist']} ({CASE_LABELS[item['case_type']]})"
        for item in projects
    ]
    return DeterministicReply(intent, "Alguns trabalhos:\n- " + "\n- ".join(lines) + "\nVeja todos em miraihitstudio.com.br/portfolio.")
