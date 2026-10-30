"""Automatic exclusive license for a custom beat delivered in a production."""
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from models import OrcamentoModel, PropostaModel
from services.beat_contrato_service import gerar_documento
from services.pdf_service import BRASILIA, moeda
from sqlalchemy import select


def _producer_identity(producer):
    name = (
        getattr(producer, "nome_exibicao", None)
        or getattr(producer, "username", None)
        or "Mirai Hit Studio"
    )
    cpf = getattr(producer, "cpf", None) or ""
    formatted = (
        f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        if len(cpf) == 11 and cpf.isdigit()
        else None
    )
    return name, formatted


def _client_identity(budget, proposal, production):
    client = getattr(budget, "cliente", None)
    if client is not None:
        return client.nome, client.email or "-"
    snapshot = getattr(proposal, "cliente_snapshot", None) or {}
    snapshot_client = snapshot.get("cliente", snapshot) if isinstance(snapshot, dict) else {}
    return (
        snapshot_client.get("nome") or getattr(budget, "nome_cliente", None) or production.cliente,
        snapshot_client.get("email") or getattr(budget, "email", None) or "-",
    )


def _contract_value(budget, proposal):
    raw = (getattr(proposal, "totais_json", None) or {}).get("total")
    if raw is None:
        raw = getattr(budget, "valor_total", None)
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return "Conforme proposta"
    return moeda(value) if value >= 0 else "Conforme proposta"


def _filename(title):
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", plain).strip("-").lower()[:60] or "beat"
    return f"{slug}-licenca-exclusiva.pdf"


def gerar(db, *, production, producer, title, request_id, bpm, tonalidade, creditos_adicionais):
    budget = db.get(OrcamentoModel, production.orcamento_id) if production.orcamento_id else None
    proposal = db.scalar(
        select(PropostaModel).where(PropostaModel.orcamento_id == production.orcamento_id)
    ) if production.orcamento_id else None
    producer_name, producer_cpf = _producer_identity(producer)
    client_name, client_email = _client_identity(budget, proposal, production)
    issued_at = datetime.now(timezone.utc).astimezone(BRASILIA).strftime("%d/%m/%Y")
    request_suffix = str(request_id).replace("-", "")[:8].upper()
    content = gerar_documento(
        numero=f"MHS-PROD-{production.id:06d}-{request_suffix}",
        data=issued_at,
        proposta_numero=getattr(proposal, "numero", "-") or "-",
        exclusivo=True,
        licenca_rotulo="Exclusiva sob encomenda",
        formatos="MP3, WAV e multitrack (stems)",
        valor_texto=_contract_value(budget, proposal),
        valor_rotulo="Valor contratado",
        beat_titulo=title,
        produtor=producer_name,
        produtor_cpf=producer_cpf,
        cliente_nome=client_name,
        cliente_email=client_email,
        sob_encomenda=True,
        confirmacao_texto="Vigência condicionada à quitação integral da produção.",
        bpm=bpm,
        tonalidade=tonalidade,
        creditos_adicionais=creditos_adicionais,
    )
    return _filename(title), "application/pdf", content
