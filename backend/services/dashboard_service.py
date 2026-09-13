from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.enums import OrcamentoStatus
from models.cliente import ClienteModel
from models.enums.proposta import PropostaStatus
from models.orcamento import OrcamentoModel
from models.producao import ProducaoModel
from models.proposta import PropostaModel
from schemas.dashboard import (
    DashboardActivity,
    DashboardAttention,
    DashboardMetrics,
    DashboardPipeline,
    DashboardResponse,
)


ORCAMENTOS_ABERTOS = (
    OrcamentoStatus.NOVO.value,
    OrcamentoStatus.EM_ANALISE.value,
)
PRODUCOES_ATIVAS = ("aguardando_inicio", "em_producao", "revisao")
PRODUCOES_FINAIS = ("finalizado", "entregue")
ATIVIDADE_LIMITE = 8


def _contar(db: Session, model, *filtros) -> int:
    return db.query(func.count()).select_from(model).filter(*filtros).scalar() or 0


def _atividade_recente(db: Session) -> list[DashboardActivity]:
    atividades = []
    for cliente in db.query(ClienteModel).order_by(ClienteModel.created_at.desc()).limit(ATIVIDADE_LIMITE):
        if cliente.created_at:
            atividades.append(DashboardActivity(
                tipo="cliente_criado", titulo="Cliente cadastrado", data=cliente.created_at,
                secao="section-clientes",
            ))
    for orcamento in db.query(OrcamentoModel).order_by(OrcamentoModel.data_solicitacao.desc()).limit(ATIVIDADE_LIMITE):
        if orcamento.data_solicitacao:
            atividades.append(DashboardActivity(
                tipo="orcamento_criado", titulo=f"Orcamento #{orcamento.id} recebido",
                data=orcamento.data_solicitacao, secao="section-orcamentos",
            ))
    for proposta in db.query(PropostaModel).filter(PropostaModel.enviada_em.isnot(None)).order_by(PropostaModel.enviada_em.desc()).limit(ATIVIDADE_LIMITE):
        atividades.append(DashboardActivity(
            tipo="proposta_enviada", titulo=f"Proposta {proposta.numero} enviada",
            data=proposta.enviada_em, secao="section-orcamentos",
        ))
    for proposta in db.query(PropostaModel).filter(PropostaModel.aprovada_em.isnot(None)).order_by(PropostaModel.aprovada_em.desc()).limit(ATIVIDADE_LIMITE):
        atividades.append(DashboardActivity(
            tipo="proposta_aprovada", titulo=f"Proposta {proposta.numero} aprovada",
            data=proposta.aprovada_em, secao="section-orcamentos",
        ))
    for producao in db.query(ProducaoModel).order_by(ProducaoModel.created_at.desc()).limit(ATIVIDADE_LIMITE):
        if producao.created_at:
            atividades.append(DashboardActivity(
                tipo="producao_criada", titulo=f"Producao #{producao.id} criada",
                data=producao.created_at, secao="section-producoes",
            ))
    return sorted(atividades, key=lambda item: item.data, reverse=True)[:ATIVIDADE_LIMITE]


def carregar(db: Session, agora: datetime | None = None) -> DashboardResponse:
    agora = agora or datetime.now(timezone.utc)
    clientes_ativos = _contar(db, ClienteModel, ClienteModel.ativo.is_(True))
    orcamentos_abertos = _contar(db, OrcamentoModel, OrcamentoModel.status.in_(ORCAMENTOS_ABERTOS))
    propostas_enviadas = _contar(db, PropostaModel, PropostaModel.status == PropostaStatus.ENVIADA.value)
    propostas_aprovadas = _contar(db, PropostaModel, PropostaModel.status == PropostaStatus.ACEITA.value)
    producoes_ativas = _contar(db, ProducaoModel, ProducaoModel.status.in_(PRODUCOES_ATIVAS))
    producoes_atrasadas = _contar(
        db,
        ProducaoModel,
        ProducaoModel.prazo_entrega.isnot(None),
        ProducaoModel.prazo_entrega < agora,
        ProducaoModel.status.notin_(PRODUCOES_FINAIS),
    )
    return DashboardResponse(
        metrics=DashboardMetrics(
            clientes_ativos=clientes_ativos,
            orcamentos_abertos=orcamentos_abertos,
            propostas_aguardando_decisao=propostas_enviadas,
            producoes_ativas=producoes_ativas,
            producoes_atrasadas=producoes_atrasadas,
        ),
        pipeline=DashboardPipeline(
            orcamentos_abertos=orcamentos_abertos,
            propostas_enviadas=propostas_enviadas,
            propostas_aprovadas=propostas_aprovadas,
            producoes_ativas=producoes_ativas,
        ),
        attention=DashboardAttention(
            producoes_atrasadas=producoes_atrasadas,
            propostas_aguardando_decisao=propostas_enviadas,
        ),
        recent_activity=_atividade_recente(db),
    )
