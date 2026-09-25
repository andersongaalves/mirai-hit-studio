"""Conservative output checks; authorization remains exclusively in ToolRegistry.

These checks are not a general factuality classifier. Uncertain sensitive claims
are routed to an operator instead of being rewritten into an apparent guarantee.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def folded(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _prices(data):
    if isinstance(data, dict):
        value = data.get("published_base_price")
        if value is not None:
            try:
                yield Decimal(str(value))
            except InvalidOperation:
                pass
        for value in data.values():
            yield from _prices(value)
    elif isinstance(data, list):
        for value in data:
            yield from _prices(value)


def unsupported_claim(text, results):
    normalized = folded(text or "")
    if re.search(r"\b(ignore (?:as |todas |instrucoes)|system prompt|execute sql|access.token|secret.key)\b", normalized):
        return True
    # Never endorse financial mutations, negotiated prices or delivery promises.
    if re.search(r"\b(reembolso (?:feito|aprovado)|estorno (?:feito|aprovado)|desconto (?:aplicado|aprovado)|"
                 r"pagamento (?:confirmado|aprovado)|proposta aprovada|garantimos|garanto|entregaremos|"
                 r"sera entregue|politica (?:garante|permite)|milhoes? de plays|depoimento do cliente|"
                 r"fechamos por|preco fechado|valor final)\b", normalized):
        return True
    successful = [item for item in results if item.success]
    prices = {price for item in successful if item.name in {"list_services", "get_service_details"}
              for price in _prices(item.data)}
    for amount in re.findall(r"(?:r\$|brl)\s*([\d.,]+)", normalized):
        try:
            price = Decimal(amount.replace(".", "").replace(",", ".") if "," in amount else amount)
        except InvalidOperation:
            return True
        if price not in prices:
            return True
    # A failed lookup cannot ground an affirmative status/case claim.
    if any(not item.success for item in results) and re.search(
            r"\b(seu status e|esta aprovado|cliente e|case e|servico e|prazo e)\b", normalized):
        return True
    for item in successful:
        if item.name == "get_public_portfolio":
            for project in item.data.get("projects", []):
                title = folded(str(project.get("title", "")))
                kind = project.get("case_type")
                labels = {"demo": "demo", "concept_project": "conceit", "study": "estudo"}
                if title and title in normalized and kind in labels:
                    if labels[kind] not in normalized and kind not in normalized:
                        return True
    return False
