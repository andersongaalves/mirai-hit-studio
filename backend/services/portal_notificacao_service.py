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
}


def _inserir(db, usuarios, tipo, chave, *, producao_id=None, proposta_id=None, arquivo_id=None, actor_id=None):
    if tipo not in TEXTOS or not (producao_id or proposta_id):
        raise ValueError("invalid_portal_notification")
    values = [{"usuario_id": user.id, "papel": user.role, "tipo": tipo, "chave_evento": chave,
               "producao_id": producao_id, "proposta_id": proposta_id, "arquivo_id": arquivo_id}
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


def _visiveis(db, user):
    query = db.query(PortalNotificacaoModel).filter(
        PortalNotificacaoModel.usuario_id == user.id, PortalNotificacaoModel.papel == user.role)
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
        query = query.filter(PortalNotificacaoModel.producao_id.in_(producoes))
        arquivos = select(ProducaoArquivoModel.id).where(ProducaoArquivoModel.visivel_produtor.is_(True))
    return query.filter(or_(PortalNotificacaoModel.arquivo_id.is_(None), PortalNotificacaoModel.arquivo_id.in_(arquivos)))


def _resposta(row, user):
    if row.producao_id is not None:
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
