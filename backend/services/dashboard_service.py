from datetime import datetime, timezone

from core.enums import OrcamentoStatus
from models.audio_tag import PreviaTagJobModel
from models.beat import BeatModel
from models.cliente import ClienteModel
from models.enums.proposta import PropostaStatus
from models.financeiro import CobrancaModel, PagamentoModel
from models.orcamento import OrcamentoModel
from models.portal_produtor import ProducaoArquivoModel
from models.portfolio_envio import PortfolioEnvioModel
from models.producao import ProducaoModel
from models.producao_etapa import ProducaoEtapaModel
from models.proposta import PropostaModel
from models.usuario import UsuarioModel
from schemas.dashboard import (
    DashboardActivity,
    DashboardAttention,
    DashboardMetrics,
    DashboardPipeline,
    DashboardResponse,
)
from services.classificacao_service import cliente_oficial
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

ORCAMENTOS_ABERTOS = (
    OrcamentoStatus.NOVO.value,
    OrcamentoStatus.EM_ANALISE.value,
)
PRODUCOES_ATIVAS = ("aguardando_inicio", "em_producao", "revisao")
PRODUCOES_FINAIS = ("finalizado", "entregue")
ATIVIDADE_LIMITE = 8


def _orcamento_oficial():
    return OrcamentoModel.is_test.is_(False)


def _proposta_oficial():
    return PropostaModel.orcamento.has(_orcamento_oficial())


def _producao_oficial():
    return or_(
        ProducaoModel.orcamento_id.is_(None),
        ProducaoModel.orcamento_id.in_(
            select(OrcamentoModel.id).where(_orcamento_oficial())
        ),
    )


def _contar(db: Session, model, *filtros) -> int:
    return db.query(func.count()).select_from(model).filter(*filtros).scalar() or 0


def _atividade_recente(db: Session) -> list[DashboardActivity]:
    atividades = []
    for cliente in db.query(ClienteModel).filter(cliente_oficial()).order_by(ClienteModel.created_at.desc()).limit(ATIVIDADE_LIMITE):
        if cliente.created_at:
            atividades.append(DashboardActivity(
                tipo="cliente_criado", titulo="Cliente cadastrado", data=cliente.created_at,
                secao="section-clientes",
            ))
    for orcamento in db.query(OrcamentoModel).filter(_orcamento_oficial()).order_by(OrcamentoModel.data_solicitacao.desc()).limit(ATIVIDADE_LIMITE):
        if orcamento.data_solicitacao:
            atividades.append(DashboardActivity(
                tipo="orcamento_criado", titulo=f"Orcamento #{orcamento.id} recebido",
                data=orcamento.data_solicitacao, secao="section-orcamentos",
            ))
    for proposta in db.query(PropostaModel).filter(_proposta_oficial(), PropostaModel.enviada_em.isnot(None)).order_by(PropostaModel.enviada_em.desc()).limit(ATIVIDADE_LIMITE):
        atividades.append(DashboardActivity(
            tipo="proposta_enviada", titulo=f"Proposta {proposta.numero} enviada",
            data=proposta.enviada_em, secao="section-orcamentos",
        ))
    for proposta in db.query(PropostaModel).filter(_proposta_oficial(), PropostaModel.aprovada_em.isnot(None)).order_by(PropostaModel.aprovada_em.desc()).limit(ATIVIDADE_LIMITE):
        atividades.append(DashboardActivity(
            tipo="proposta_aprovada", titulo=f"Proposta {proposta.numero} aprovada",
            data=proposta.aprovada_em, secao="section-orcamentos",
        ))
    for producao in db.query(ProducaoModel).filter(_producao_oficial()).order_by(ProducaoModel.created_at.desc()).limit(ATIVIDADE_LIMITE):
        if producao.created_at:
            atividades.append(DashboardActivity(
                tipo="producao_criada", titulo=f"Producao #{producao.id} criada",
                data=producao.created_at, secao="section-producoes",
            ))
    return sorted(atividades, key=lambda item: item.data, reverse=True)[:ATIVIDADE_LIMITE]


def carregar(db: Session, agora: datetime | None = None) -> DashboardResponse:
    agora = agora or datetime.now(timezone.utc)
    clientes_ativos = _contar(db, ClienteModel, ClienteModel.ativo.is_(True), cliente_oficial())
    orcamentos_abertos = _contar(db, OrcamentoModel, _orcamento_oficial(), OrcamentoModel.status.in_(ORCAMENTOS_ABERTOS))
    propostas_enviadas = _contar(db, PropostaModel, _proposta_oficial(), PropostaModel.status == PropostaStatus.ENVIADA.value)
    from core.proposta_validade import corte_expiracao

    propostas_expiradas = _contar(
        db, PropostaModel, _proposta_oficial(), PropostaModel.status == PropostaStatus.ENVIADA.value,
        PropostaModel.enviada_em < corte_expiracao(agora).astimezone(timezone.utc),
    )
    propostas_aguardando = propostas_enviadas - propostas_expiradas
    propostas_aprovadas = _contar(db, PropostaModel, _proposta_oficial(), PropostaModel.status == PropostaStatus.ACEITA.value)
    producoes_ativas = _contar(db, ProducaoModel, _producao_oficial(), ProducaoModel.status.in_(PRODUCOES_ATIVAS))
    producoes_atrasadas = _contar(
        db,
        ProducaoModel,
        _producao_oficial(),
        ProducaoModel.prazo_entrega.isnot(None),
        ProducaoModel.prazo_entrega < agora,
        ProducaoModel.status.notin_(PRODUCOES_FINAIS),
    )
    solicitacoes_producao = _contar(
        db,
        OrcamentoModel,
        _orcamento_oficial(),
        OrcamentoModel.status.in_(ORCAMENTOS_ABERTOS),
        OrcamentoModel.beat_id.is_(None),
        OrcamentoModel.detalhes.like("Solicitacao pelo Portal do Cliente%"),
    )
    beats_em_revisao = (
        db.query(func.count(BeatModel.id))
        .join(UsuarioModel, UsuarioModel.id == BeatModel.produtor_id)
        .filter(BeatModel.status == "revisao", UsuarioModel.is_test.is_(False))
        .scalar()
        or 0
    )
    portfolio_em_revisao = (
        db.query(func.count(PortfolioEnvioModel.id))
        .join(UsuarioModel, UsuarioModel.id == PortfolioEnvioModel.produtor_id)
        .filter(
            PortfolioEnvioModel.status == "pendente",
            UsuarioModel.is_test.is_(False),
        )
        .scalar()
        or 0
    )
    falhas_processamento_tag = (
        db.query(func.count(PreviaTagJobModel.arquivo_id))
        .join(
            ProducaoArquivoModel,
            ProducaoArquivoModel.id == PreviaTagJobModel.arquivo_id,
        )
        .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
        .filter(PreviaTagJobModel.estado == "erro", _producao_oficial())
        .scalar()
        or 0
    )
    pagamentos_em_conciliacao = (
        db.query(func.count(PagamentoModel.id))
        .join(CobrancaModel, CobrancaModel.id == PagamentoModel.cobranca_id)
        .join(PropostaModel, PropostaModel.id == CobrancaModel.proposta_id)
        .join(OrcamentoModel, OrcamentoModel.id == PropostaModel.orcamento_id)
        .filter(
            PagamentoModel.reconciliation_status.isnot(None),
            OrcamentoModel.is_test.is_(False),
        )
        .scalar()
        or 0
    )
    entregas_aguardando_aprovacao = (
        db.query(func.count(ProducaoEtapaModel.id))
        .join(ProducaoModel, ProducaoModel.id == ProducaoEtapaModel.producao_id)
        .filter(ProducaoEtapaModel.status == "em_revisao", _producao_oficial())
        .scalar()
        or 0
    )
    return DashboardResponse(
        metrics=DashboardMetrics(
            clientes_ativos=clientes_ativos,
            orcamentos_abertos=orcamentos_abertos,
            propostas_aguardando_decisao=propostas_aguardando,
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
            propostas_aguardando_decisao=propostas_aguardando,
            solicitacoes_producao=solicitacoes_producao,
            beats_em_revisao=beats_em_revisao,
            portfolio_em_revisao=portfolio_em_revisao,
            falhas_processamento_tag=falhas_processamento_tag,
            pagamentos_em_conciliacao=pagamentos_em_conciliacao,
            entregas_aguardando_aprovacao=entregas_aguardando_aprovacao,
            propostas_expiradas=propostas_expiradas,
        ),
        recent_activity=_atividade_recente(db),
    )
