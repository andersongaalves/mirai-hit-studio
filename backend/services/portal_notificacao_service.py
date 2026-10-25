"""Transactional portal events: no email/provider calls and no payment state changes."""
from datetime import datetime, timezone

from crud.crud_producao import acesso_produtor
from models import (
    ClienteModel,
    OrcamentoModel,
    PortalNotificacaoModel,
    ProducaoArquivoModel,
    ProducaoEtapaModel,
    ProducaoModel,
    PropostaModel,
    UsuarioModel,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

TEXTOS = {
    "nova_mensagem": "Nova mensagem na sua produção.",
    "nova_previa": "Uma nova prévia foi enviada para você.",
    "nova_entrega": "Uma entrega final foi enviada. Consulte os arquivos da produção.",
    "etapa_concluida": "Uma etapa da produção foi concluída.",
    "pagamento_confirmado": "Pagamento confirmado. Consulte o financeiro do seu projeto.",
    "proposta_enviada": "Você recebeu uma proposta do estúdio.",
    "revisao_liberada": "Uma revisão foi liberada para a sua produção.",
    "entrega_liberada": "A entrega final foi liberada. Consulte os arquivos da produção.",
    # AUD6-S04-002: the producer learns the review outcome of each beat.
    "beat_aprovado": "Seu beat foi aprovado e já aparece no catálogo.",
    "beat_rejeitado": "Seu beat precisa de ajustes. Veja o motivo em Beats.",
    # AUD6-S11-001/002: events that need the studio's attention.
    "admin_solicitacao_producao": "Nova solicitação de produção enviada por um cliente.",
    "admin_beat_revisao": "Um beat foi enviado para revisão.",
    "admin_portfolio_revisao": "Um projeto de portfólio foi proposto para revisão.",
    "admin_falha_tag": "Uma prévia ficou sem tag de áudio. Reprocesse pelo dashboard.",
}

# Admin notifications open a section of the single-page panel.
ADMIN_SECOES = {
    "admin_solicitacao_producao": "section-orcamentos",
    "admin_beat_revisao": "section-beats",
    "admin_portfolio_revisao": "section-portfolio",
    "admin_falha_tag": "dashboard-menu",
}


def _papel(user):
    return "admin" if user.is_admin else user.role


def _inserir(db, usuarios, tipo, chave, *, producao_id=None, proposta_id=None, arquivo_id=None, actor_id=None,
             beat_id=None, orcamento_id=None, portfolio_envio_id=None):
    if tipo not in TEXTOS or not (producao_id or proposta_id or beat_id or orcamento_id or portfolio_envio_id):
        raise ValueError("invalid_portal_notification")
    values = [{"usuario_id": user.id, "papel": _papel(user), "tipo": tipo, "chave_evento": chave,
               "producao_id": producao_id, "proposta_id": proposta_id, "arquivo_id": arquivo_id,
               "beat_id": beat_id, "orcamento_id": orcamento_id, "portfolio_envio_id": portfolio_envio_id}
              for user in sorted(usuarios, key=lambda user: user.id) if user.id != actor_id]
    if not values:
        return
    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise RuntimeError("unsupported_notification_database")
    db.execute(insert(PortalNotificacaoModel).values(values).on_conflict_do_nothing(
        index_elements=["usuario_id", "chave_evento"]))


def _clientes(db, orcamento):
    if orcamento is None or orcamento.cliente_id is None:
        return []
    cliente = db.get(ClienteModel, orcamento.cliente_id)
    if cliente is None or not cliente.ativo:
        return []
    return list(db.scalars(select(UsuarioModel).where(
        UsuarioModel.ativo.is_(True), UsuarioModel.is_admin.is_(False), UsuarioModel.role == "cliente",
        UsuarioModel.cliente_id == cliente.id)))


def emitir_producao(db, producao, tipo, chave, *, clientes=True, produtores=False, arquivo_id=None, actor_id=None):
    usuarios = _clientes(db, db.get(OrcamentoModel, producao.orcamento_id)) if clientes else []
    if produtores:
        from models.credito_etapa import etapa_ativa

        ids = set(db.scalars(select(ProducaoEtapaModel.responsavel_usuario_id).where(
            ProducaoEtapaModel.producao_id == producao.id, etapa_ativa(ProducaoEtapaModel.id))))
        ids.add(producao.produtor_id)
        ids.discard(None)
        usuarios += list(db.scalars(select(UsuarioModel).where(
            UsuarioModel.id.in_(ids), UsuarioModel.ativo.is_(True), UsuarioModel.is_admin.is_(False),
            UsuarioModel.role == "produtor")))
    _inserir(db, usuarios, tipo, chave, producao_id=producao.id, arquivo_id=arquivo_id, actor_id=actor_id)


def proposta_enviada(db, proposta):
    _inserir(db, _clientes(db, db.get(OrcamentoModel, proposta.orcamento_id)), "proposta_enviada",
             f"proposta:{proposta.id}:versao:{proposta.versao}", proposta_id=proposta.id)


def arquivo_compartilhado(db, arquivo, *, actor_id=None):
    if not getattr(arquivo, "visibilidade_cliente_efetiva", arquivo.visivel_cliente) or arquivo.tipo not in {"previa", "entrega"}:
        return
    if getattr(arquivo, "processamento_tag", None) in {"pendente", "erro"}:
        return
    producao = db.get(ProducaoModel, arquivo.producao_id)
    tipo = "nova_previa" if arquivo.tipo == "previa" else "nova_entrega"
    chave = f"arquivo:{arquivo.id}:compartilhado"
    if arquivo.tipo == "entrega":
        from services.portal_cliente_service import entrega_bloqueada

        if not entrega_bloqueada(db, producao):
            tipo, chave = "entrega_liberada", f"entrega:{arquivo.id}:liberada"
    emitir_producao(db, producao, tipo, chave, arquivo_id=arquivo.id, actor_id=actor_id)


def pagamento_confirmado(db, pagamento):
    if pagamento.status != "aprovado" or pagamento.reconciliation_status:
        return
    cobranca = pagamento.cobranca
    proposta = cobranca.proposta if cobranca is not None else None
    if proposta is None:
        return
    orcamento = db.get(OrcamentoModel, proposta.orcamento_id)
    if orcamento is None or cobranca.cliente_id != orcamento.cliente_id or cobranca.moeda != "BRL":
        return
    producao = db.scalar(select(ProducaoModel).where(ProducaoModel.orcamento_id == orcamento.id))
    usuarios = _clientes(db, orcamento)
    _inserir(db, usuarios, "pagamento_confirmado", f"pagamento:{pagamento.id}:aprovado",
             proposta_id=proposta.id, producao_id=producao.id if producao else None)
    if producao is not None:
        entregas_liberadas(db, producao)


def entregas_liberadas(db, producao):
    from services.portal_cliente_service import entrega_bloqueada

    if not entrega_bloqueada(db, producao):
        for arquivo in db.scalars(select(ProducaoArquivoModel).where(
            ProducaoArquivoModel.producao_id == producao.id, ProducaoArquivoModel.tipo == "entrega",
            ProducaoArquivoModel.visivel_cliente.is_(True))):
            emitir_producao(db, producao, "entrega_liberada", f"entrega:{arquivo.id}:liberada", arquivo_id=arquivo.id)


def _admins(db):
    return list(db.scalars(select(UsuarioModel).where(
        UsuarioModel.ativo.is_(True), UsuarioModel.is_admin.is_(True), UsuarioModel.role == "admin")))


def solicitacao_producao(db, orcamento):
    if getattr(orcamento, "is_test", False):
        return
    _inserir(db, _admins(db), "admin_solicitacao_producao", f"orcamento:{orcamento.id}:solicitado",
             orcamento_id=orcamento.id)


def beat_em_revisao(db, beat, *, actor_id=None):
    _inserir(db, _admins(db), "admin_beat_revisao", f"beat:{beat.id}:revisao:{_marca()}", beat_id=beat.id,
             actor_id=actor_id)


def beat_revisado(db, beat):
    produtor = db.get(UsuarioModel, beat.produtor_id) if beat.produtor_id else None
    if produtor is None or not produtor.ativo or produtor.is_admin or produtor.role != "produtor":
        return
    tipo = "beat_aprovado" if beat.status == "aprovado" else "beat_rejeitado"
    _inserir(db, [produtor], tipo, f"beat:{beat.id}:{beat.status}:{_marca(beat.revisado_em)}", beat_id=beat.id)


def portfolio_proposto(db, envio):
    _inserir(db, _admins(db), "admin_portfolio_revisao", f"portfolio_envio:{envio.id}:proposto",
             portfolio_envio_id=envio.id)


def falha_tag(db, arquivo):
    producao = db.get(ProducaoModel, arquivo.producao_id)
    if producao is None:
        return
    orcamento = db.get(OrcamentoModel, producao.orcamento_id) if producao.orcamento_id else None
    if orcamento is not None and getattr(orcamento, "is_test", False):
        return
    _inserir(db, _admins(db), "admin_falha_tag", f"arquivo:{arquivo.id}:falha_tag:{_marca()}",
             producao_id=producao.id, arquivo_id=arquivo.id)


def _marca(stamp=None):
    # Each review round or retry is a new event; the same round never repeats it.
    return int((stamp or datetime.now(timezone.utc)).timestamp())


def _visiveis(db, user):
    query = db.query(PortalNotificacaoModel).filter(
        PortalNotificacaoModel.usuario_id == user.id, PortalNotificacaoModel.papel == _papel(user))
    if user.is_admin:
        return query
    if user.role == "cliente":
        producoes = select(ProducaoModel.id).join(OrcamentoModel, OrcamentoModel.id == ProducaoModel.orcamento_id).where(
            OrcamentoModel.cliente_id == user.cliente_id)
        propostas = select(PropostaModel.id).join(OrcamentoModel, OrcamentoModel.id == PropostaModel.orcamento_id).where(
            OrcamentoModel.cliente_id == user.cliente_id)
        query = query.filter(or_(PortalNotificacaoModel.producao_id.in_(producoes), and_(
            PortalNotificacaoModel.producao_id.is_(None), PortalNotificacaoModel.proposta_id.in_(propostas))))
        from models import PreviaTagJobModel

        arquivos = select(ProducaoArquivoModel.id).outerjoin(
            PreviaTagJobModel, PreviaTagJobModel.arquivo_id == ProducaoArquivoModel.id,
        ).where(or_(ProducaoArquivoModel.visivel_cliente.is_(True), PreviaTagJobModel.visivel_cliente.is_(True)))
        from services import politica_service

        stage_types = ("etapa_concluida", "revisao_liberada")
        stage_productions = query.filter(PortalNotificacaoModel.tipo.in_(stage_types)).with_entities(
            PortalNotificacaoModel.producao_id).distinct().all()
        ocultas = [identifier for (identifier,) in stage_productions
                   if not politica_service.vigentes(db, identifier)["cliente_ve_etapas"]]
        if ocultas:
            query = query.filter(~and_(PortalNotificacaoModel.tipo.in_(stage_types),
                                      PortalNotificacaoModel.producao_id.in_(ocultas)))
    else:
        producoes = select(ProducaoModel.id).where(acesso_produtor(user.id))
        from models import BeatModel

        beats = select(BeatModel.id).where(BeatModel.produtor_id == user.id)
        query = query.filter(or_(PortalNotificacaoModel.producao_id.in_(producoes), and_(
            PortalNotificacaoModel.producao_id.is_(None), PortalNotificacaoModel.beat_id.in_(beats))))
        arquivos = select(ProducaoArquivoModel.id).where(ProducaoArquivoModel.visivel_produtor.is_(True))
    return query.filter(or_(PortalNotificacaoModel.arquivo_id.is_(None), PortalNotificacaoModel.arquivo_id.in_(arquivos)))


def _resposta(row, user):
    if user.is_admin:
        url = f"/admin.html#{ADMIN_SECOES.get(row.tipo, 'dashboard-menu')}"
    elif row.beat_id is not None and row.producao_id is None:
        url = "/produtor/beats"
    elif row.producao_id is not None:
        prefix = "/cliente/projetos" if user.role == "cliente" else "/produtor/producoes"
        url = f"{prefix}/{row.producao_id}"
    else:
        url = f"/cliente/propostas/{row.proposta_id}"
    return {"id": row.id, "tipo": row.tipo, "texto": TEXTOS.get(row.tipo, "Há uma atualização no seu projeto."),
            "url": url, "created_at": row.created_at, "vista_em": row.vista_em}


def listar(db, user, *, antes_id=None, limite=30, somente_nao_vistas=False):
    query = _visiveis(db, user)
    nao_vistas = query.filter(PortalNotificacaoModel.vista_em.is_(None)).count()
    if somente_nao_vistas:
        query = query.filter(PortalNotificacaoModel.vista_em.is_(None))
    if antes_id is not None:
        query = query.filter(PortalNotificacaoModel.id < antes_id)
    rows = query.order_by(PortalNotificacaoModel.id.desc()).limit(limite + 1).all()
    return {"itens": [_resposta(row, user) for row in rows[:limite]], "nao_vistas": nao_vistas, "tem_mais": len(rows) > limite}


def marcar_vistas(db, user, ids):
    permitidos = _visiveis(db, user).with_entities(PortalNotificacaoModel.id).filter(
        PortalNotificacaoModel.id.in_(set(ids))).statement
    # Consistent row-lock order makes competing tabs claim each unread event once.
    rows = list(db.scalars(select(PortalNotificacaoModel).where(
        PortalNotificacaoModel.id.in_(permitidos), PortalNotificacaoModel.vista_em.is_(None)
    ).order_by(PortalNotificacaoModel.id).with_for_update(of=PortalNotificacaoModel)))
    agora = datetime.now(timezone.utc)
    for row in rows:
        row.vista_em = agora
    result = [_resposta(row, user) for row in rows]
    db.commit()
    return result
