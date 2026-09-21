"""Small, structured knowledge layer backed by Mirai sources of truth."""

from functools import lru_cache
import json
from pathlib import Path
import unicodedata

from sqlalchemy import func, or_, select

from models import OrcamentoModel, ProducaoModel, ProjetoModel, PropostaModel, ServicoModel
from models.financeiro import CobrancaModel
from schemas.ai_tools import (
    BudgetStatusInput,
    BudgetStatusOutput,
    FAQInput,
    FAQItem,
    FAQOutput,
    ListServicesInput,
    PaymentStatusOutput,
    PortfolioInput,
    PortfolioOutput,
    ProposalReferenceInput,
    ProposalStatusOutput,
    ProductionStatusOutput,
    PublicPortfolioItem,
    PublicService,
    ServiceDetailsInput,
    ServiceDetailsOutput,
    ServiceListOutput,
)
from services import financial_service
from services.ai_tools import Tool, ToolCategory, ToolError, ToolRegistry


KNOWLEDGE_FILE = Path(__file__).resolve().parents[1] / "ai" / "knowledge" / "public.json"
PUBLIC_VERTICALS = ("artists", "creators", "media_games")
PUBLIC_CASE_TYPES = ("client_case", "demo", "concept_project", "study")
POLICY_KEYWORDS = {
    "contracting": ("contratar", "contratacao", "orcamento", "proposta", "briefing"),
    "deadlines": ("prazo", "entrega", "demora"),
    "revisions": ("revisao", "revisoes", "alteracao"),
    "rights": ("direito", "licenca", "exclusividade"),
    "payments": ("pagamento", "pix", "cartao", "parcelamento"),
}


def _normalized(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


@lru_cache(maxsize=1)
def public_knowledge():
    with KNOWLEDGE_FILE.open(encoding="utf-8") as source:
        data = json.load(source)
    if data.get("version") != 1 or not isinstance(data.get("brand"), dict):
        raise RuntimeError("invalid_public_knowledge")
    FAQOutput(items=tuple(FAQItem.model_validate(item) for item in data.get("faq", ())))
    return data


def _service_description(model):
    try:
        structure = json.loads(model.estrutura_servico or "{}")
    except (TypeError, json.JSONDecodeError):
        return None, ()
    intro = structure.get("intro")
    if not isinstance(intro, str) or not intro.strip():
        intro = None
    benefits = structure.get("benefits", ())
    if not isinstance(benefits, list):
        benefits = ()
    clean = tuple(item.strip()[:300] for item in benefits if isinstance(item, str) and item.strip())[:8]
    return intro.strip()[:2000] if intro else None, clean


def _public_service(model):
    description, benefits = _service_description(model)
    pricing_mode = getattr(model, "pricing_mode", None)
    return PublicService(
        service_id=model.id,
        name=model.nome,
        subtitle=model.subtitulo,
        category=model.categoria,
        vertical=getattr(model, "vertical", None),
        segments=tuple(getattr(model, "segmentos_json", None) or ()),
        pricing_mode=pricing_mode,
        commercial_level=getattr(model, "commercial_level", None),
        active=getattr(model, "ativo", None),
        published_base_price=None if pricing_mode == "custom" else model.valor_base,
        description=description,
        benefits=benefits,
    )


def _service_taxonomy_available():
    return all(hasattr(ServicoModel, field) for field in (
        "vertical", "segmentos_json", "pricing_mode", "commercial_level", "ativo",
    ))


def _public_services_query():
    query = select(ServicoModel)
    if hasattr(ServicoModel, "ativo"):
        query = query.where(ServicoModel.ativo.is_(True))
    return query


def _public_project(model):
    return PublicPortfolioItem(
        project_id=model.id,
        title=model.titulo,
        credited_artist=model.artista,
        category=model.categoria,
        description=model.descricao[:2000] if model.descricao else None,
        vertical=model.vertical,
        segments=tuple(model.segmentos_json or ()),
        case_type=model.case_type,
        audio_url=model.link_audio,
        cover_url=model.link_capa,
    )


def _faq(topic=None):
    items = tuple(FAQItem.model_validate(item) for item in public_knowledge()["faq"])
    return FAQOutput(items=tuple(item for item in items if topic is None or item.topic == topic))


class AIKnowledgeService:
    def __init__(self, sessions):
        self.sessions = sessions

    def context_for(self, message, *, db=None):
        if db is not None:
            return self._context_for(db, message)
        with self.sessions() as current:
            return self._context_for(current, message)

    def _context_for(self, db, message):
        normalized = _normalized(message)
        data = public_knowledge()
        context = [json.dumps({"kind": "brand", **data["brand"]}, ensure_ascii=False)]
        matched_topics = tuple(
            topic for topic, words in POLICY_KEYWORDS.items()
            if any(word in normalized for word in words)
        )
        if matched_topics:
            faq = _faq()
            selected = [item.model_dump() for item in faq.items if item.topic in matched_topics]
            context.append(json.dumps({"kind": "policies", "items": selected}, ensure_ascii=False))
        if any(word in normalized for word in ("servico", "preco", "valor", "mix", "master", "beat", "audio")):
            services = db.scalars(_public_services_query().order_by(ServicoModel.id).limit(3)).all()
            context.append(json.dumps({
                "kind": "service_candidates",
                "items": [_public_service(item).model_dump(mode="json") for item in services],
                "taxonomy_available": _service_taxonomy_available(),
            }, ensure_ascii=False))
        if any(word in normalized for word in ("portfolio", "case", "demo", "trabalho")):
            projects = db.scalars(
                select(ProjetoModel).where(
                    ProjetoModel.vertical.in_(PUBLIC_VERTICALS),
                    ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES),
                ).order_by(ProjetoModel.destaque.desc(), ProjetoModel.id).limit(3)
            ).all()
            context.append(json.dumps({
                "kind": "portfolio_candidates",
                "items": [_public_project(item).model_dump(mode="json") for item in projects],
            }, ensure_ascii=False))
        return tuple(context[:4])


def build_tool_registry(sessions):
    def list_services(context, data: ListServicesInput):
        del context
        with sessions() as db:
            query = _public_services_query()
            if data.query:
                term = f"%{data.query.strip().lower()}%"
                query = query.where(or_(
                    func.lower(ServicoModel.nome).like(term),
                    func.lower(ServicoModel.subtitulo).like(term),
                    func.lower(ServicoModel.categoria).like(term),
                ))
            models = db.scalars(query.order_by(ServicoModel.nome).limit(data.limit)).all()
            return ServiceListOutput(
                services=tuple(_public_service(item) for item in models),
                taxonomy_available=_service_taxonomy_available(),
            )

    def get_service(context, data: ServiceDetailsInput):
        del context
        with sessions() as db:
            query = _public_services_query().where(ServicoModel.id == data.service_id)
            model = db.scalar(query)
            if model is None:
                raise ToolError("not_found")
            mode = getattr(model, "pricing_mode", None)
            notes = {
                "fixed": "Preco fechado publicado; nao aplicar descontos ou arredondamentos.",
                "starting_at": "Valor inicial publicado; o escopo final depende de proposta.",
                "custom": "Servico sob orcamento; nao inventar valor e encaminhar briefing.",
            }
            return ServiceDetailsOutput(
                service=_public_service(model),
                taxonomy_available=_service_taxonomy_available(),
                pricing_note=notes.get(mode, (
                    "Este e o valor_base publicado. O cadastro atual nao possui pricing_mode; "
                    "nao inferir preco fechado, desconto ou valor customizado."
                )),
            )

    def get_portfolio(context, data: PortfolioInput):
        del context
        with sessions() as db:
            query = select(ProjetoModel).where(
                ProjetoModel.vertical.in_(PUBLIC_VERTICALS),
                ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES),
            )
            if data.vertical:
                query = query.where(ProjetoModel.vertical == data.vertical)
            models = db.scalars(
                query.order_by(ProjetoModel.destaque.desc(), ProjetoModel.id).limit(data.limit)
            ).all()
            return PortfolioOutput(projects=tuple(_public_project(item) for item in models))

    def get_faq(context, data: FAQInput):
        del context
        return _faq(data.topic)

    def get_budget(context, data: BudgetStatusInput):
        with sessions() as db:
            model = db.scalar(select(OrcamentoModel).where(
                OrcamentoModel.id == data.budget_id,
                OrcamentoModel.cliente_id == context.cliente_id,
            ))
            if model is None:
                raise ToolError("not_found")
            return BudgetStatusOutput(
                reference=f"orcamento-{model.id}",
                status=model.status,
                service=model.servico,
                requested_at=model.data_solicitacao,
            )

    def _proposal(db, context, number):
        model = db.scalar(
            select(PropostaModel).join(OrcamentoModel).where(
                PropostaModel.numero == number.strip(),
                OrcamentoModel.cliente_id == context.cliente_id,
            )
        )
        if model is None:
            raise ToolError("not_found")
        return model

    def get_proposal(context, data: ProposalReferenceInput):
        with sessions() as db:
            model = _proposal(db, context, data.proposal_number)
            charge = db.scalar(select(CobrancaModel).where(CobrancaModel.proposta_id == model.id))
            return ProposalStatusOutput(
                proposal_number=model.numero,
                status=model.status,
                sent_at=model.enviada_em,
                approved_at=model.aprovada_em,
                checkout_available=(
                    charge is not None and charge.status not in ("paga", "cancelada")
                ),
            )

    def get_production(context, data: ProposalReferenceInput):
        with sessions() as db:
            proposal = _proposal(db, context, data.proposal_number)
            model = db.scalar(select(ProducaoModel).where(
                ProducaoModel.orcamento_id == proposal.orcamento_id,
            ))
            if model is None:
                raise ToolError("not_found")
            try:
                steps = json.loads(model.etapas or "[]")
            except (TypeError, json.JSONDecodeError):
                steps = []
            if not isinstance(steps, list):
                steps = []
            valid = [step for step in steps if isinstance(step, dict) and isinstance(step.get("nome"), str)]
            completed = sum(step.get("feito") is True for step in valid)
            pending = next((step["nome"] for step in valid if step.get("feito") is not True), None)
            current = pending or (valid[-1]["nome"] if valid else None)
            return ProductionStatusOutput(
                proposal_number=proposal.numero,
                status=model.status,
                deadline=model.prazo_entrega,
                current_stage=current,
                completed_steps=completed,
                total_steps=len(valid),
            )

    def get_payment(context, data: ProposalReferenceInput):
        with sessions() as db:
            proposal = _proposal(db, context, data.proposal_number)
            charge = financial_service.buscar_por_proposta(db, proposal.id)
            if charge is None:
                raise ToolError("not_found")
            try:
                status = financial_service.status_calculado(charge)
                paid = financial_service.valor_pago(charge)
                balance = financial_service.saldo_pendente(charge)
            except financial_service.FinanceiroConflito:
                raise ToolError("conflict") from None
            return PaymentStatusOutput(
                proposal_number=proposal.numero,
                status=status.value,
                currency=charge.moeda,
                total=charge.valor_total,
                paid=paid,
                balance=balance,
                checkout_available=status.value not in ("paga", "cancelada") and balance > 0,
            )

    return ToolRegistry((
        Tool(
            "list_services", "Lista servicos publicados sem dados administrativos.",
            ToolCategory.PUBLIC_READ, ListServicesInput, ServiceListOutput, list_services,
        ),
        Tool(
            "get_service_details", "Consulta detalhes e valor_base publicado de um servico.",
            ToolCategory.PUBLIC_READ, ServiceDetailsInput, ServiceDetailsOutput, get_service,
        ),
        Tool(
            "get_public_portfolio", "Lista somente portfolio com taxonomia publica valida.",
            ToolCategory.PUBLIC_READ, PortfolioInput, PortfolioOutput, get_portfolio,
        ),
        Tool(
            "get_public_faq", "Consulta orientacoes publicas versionadas por topico.",
            ToolCategory.PUBLIC_READ, FAQInput, FAQOutput, get_faq,
        ),
        Tool(
            "get_budget_status", "Consulta um orcamento do cliente autenticado.",
            ToolCategory.PRIVATE_READ, BudgetStatusInput, BudgetStatusOutput, get_budget,
        ),
        Tool(
            "get_proposal_status", "Consulta uma proposta do cliente autenticado pelo numero.",
            ToolCategory.PRIVATE_READ, ProposalReferenceInput, ProposalStatusOutput, get_proposal,
        ),
        Tool(
            "get_production_status", "Consulta producao vinculada a proposta do cliente autenticado.",
            ToolCategory.PRIVATE_READ, ProposalReferenceInput, ProductionStatusOutput, get_production,
        ),
        Tool(
            "get_payment_status", "Consulta status financeiro confirmado pelo backend.",
            ToolCategory.PRIVATE_READ, ProposalReferenceInput, PaymentStatusOutput, get_payment,
        ),
    ))
