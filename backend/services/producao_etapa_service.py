"""Contract stages inside a production (Roadmap 3.0, 5.06).

Stages are instantiated once from the proposal's frozen economic snapshot (5.05) when the
production is created. Their name, weight, value and origin are contract data. During
the production only status and deadline change. Transitions follow a small state machine:

    pendente -> em_andamento -> em_revisao -> concluida
                     ^   |           |
                     |   +-----------+--> concluida (admin)
                     +-- reopen from concluida (admin)

Producers move their stages to em_andamento / em_revisao; concluding is an approval and
belongs to the admin. A stage that depends on the previous one (same contract item) can
only start or conclude after that one is concluded. Production status stays independent.
"""
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from crud import crud_producao
from models import (
    OrcamentoModel,
    ProducaoEtapaAtribuicaoModel,
    ProducaoEtapaModel,
    ProducaoModel,
    PropostaModel,
    UsuarioModel,
)
from services import audit_service, politica_service

TRANSICOES = {
    "pendente": {"em_andamento"},
    "em_andamento": {"em_revisao", "concluida", "pendente"},
    "em_revisao": {"em_andamento", "concluida"},
    "concluida": {"em_andamento"},
}
TRANSICOES_PRODUTOR = {
    "pendente": {"em_andamento"},
    "em_andamento": {"em_revisao"},
    "em_revisao": {"em_andamento"},
    "concluida": set(),
}
STATUS_ROTULOS = {
    "pendente": "Pendente",
    "em_andamento": "Em andamento",
    "em_revisao": "Em revisao",
    "concluida": "Concluida",
}


class EtapaError(Exception):
    pass


class EtapaNaoEncontrada(EtapaError):
    pass


class EtapaInvalida(EtapaError):
    pass


class EtapaConflito(EtapaError):
    pass


class EtapaProibida(EtapaError):
    pass


def _agora():
    return datetime.now(timezone.utc)


def producao_para(db: Session, papel: str, producao_id: int, usuario) -> ProducaoModel:
    query = db.query(ProducaoModel).filter(ProducaoModel.id == producao_id)
    if papel == "cliente":
        query = query.join(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id).filter(
            OrcamentoModel.cliente_id == usuario.cliente_id
        )
    elif papel == "produtor":
        query = query.filter(crud_producao.acesso_produtor(usuario.id))  # 5.07: coordinator or stage owner.
    elif papel != "admin":
        raise EtapaNaoEncontrada("Producao nao encontrada.")
    producao = query.first()
    if producao is None:
        raise EtapaNaoEncontrada("Producao nao encontrada.")
    return producao


def _etapas(db: Session, producao_id: int, *, bloquear=False):
    from models.credito_etapa import etapa_ativa
    from services import credito_producao_service

    query = select(ProducaoEtapaModel).where(ProducaoEtapaModel.producao_id == producao_id)
    query = query.where(etapa_ativa(ProducaoEtapaModel.id))
    query = query.order_by(ProducaoEtapaModel.ordem)
    if bloquear:
        query = query.with_for_update().execution_options(populate_existing=True)
    etapas = list(db.scalars(query))
    for item in etapas:
        item._credito_bloqueio = credito_producao_service.bloqueio_etapa(db, item)
    return etapas


def instanciar(db: Session, producao: ProducaoModel, proposta: PropostaModel, *, inicio=None) -> list:
    """Creates the production's stages from the frozen snapshot. Idempotent.

    Returns the existing stages when they were already created, and an empty list when
    the proposal has no snapshot or no catalog stages (legacy checklist keeps working).
    """
    existentes = _etapas(db, producao.id)
    if existentes:
        return existentes
    snapshot = proposta.snapshot_economico or {}
    inicio = inicio or _agora()
    criadas = []
    ordem = 0
    for item in snapshot.get("itens", []):
        acumulado = 0
        for posicao, etapa in enumerate(item.get("etapas", []), start=1):
            ordem += 1
            prazo = None
            if etapa.get("prazo_dias") is not None:
                acumulado += int(etapa["prazo_dias"])
                prazo = inicio + timedelta(days=acumulado)
            modelo = ProducaoEtapaModel(
                producao_id=producao.id,
                proposta_id=proposta.id,
                item_indice=int(item["indice"]),
                # 5.08: combo stages keep their component service as origin and group label.
                item_descricao=(
                    f"{item.get('descricao', '')} — {etapa['servico_nome']}" if etapa.get("servico_nome")
                    else str(item.get("descricao", ""))
                )[:200],
                servico_id=etapa.get("servico_id") or item.get("servico_id"),
                ordem=ordem,
                ordem_no_item=posicao,
                nome=str(etapa["nome"])[:100],
                peso_percentual=Decimal(str(etapa["peso_percentual"])),
                valor=Decimal(str(etapa["valor"])),
                prazo_dias=etapa.get("prazo_dias"),
                unidade=str(etapa.get("unidade") or "")[:30],
                revisoes_incluidas=etapa.get("revisoes_incluidas"),
                depende_da_anterior=bool(etapa.get("depende_da_anterior")) and posicao > 1,
                administrativa=bool(etapa.get("administrativa")),
                status="pendente",
                prazo=prazo,
                responsavel_usuario_id=producao.produtor_id,
            )
            db.add(modelo)
            criadas.append(modelo)
    if criadas:
        db.flush()
        # 5.07: the history starts with the initial assignment of every stage.
        db.add_all([
            ProducaoEtapaAtribuicaoModel(
                etapa_id=modelo.id, producao_id=producao.id, anterior_usuario_id=None,
                novo_usuario_id=modelo.responsavel_usuario_id, motivo="Atribuicao inicial",
            )
            for modelo in criadas
        ])
        db.flush()
    return criadas


def _proposta_da_producao(db: Session, producao: ProducaoModel):
    if producao.orcamento_id is None:
        return None
    return db.scalar(select(PropostaModel).where(PropostaModel.orcamento_id == producao.orcamento_id))


def gerar(db: Session, producao_id: int, *, actor=None, request_id=None):
    """Admin recovery for productions created before 5.06 from a snapshotted proposal."""
    try:
        producao = db.scalar(
            select(ProducaoModel).where(ProducaoModel.id == producao_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if producao is None:
            raise EtapaNaoEncontrada("Producao nao encontrada.")
        if _etapas(db, producao.id):
            raise EtapaConflito("Esta producao ja possui etapas do contrato.")
        proposta = _proposta_da_producao(db, producao)
        if proposta is None or not proposta.snapshot_economico:
            raise EtapaInvalida("A proposta desta producao nao tem valores congelados (5.05).")
        criadas = instanciar(db, producao, proposta, inicio=_agora())
        if not criadas:
            raise EtapaInvalida("O contrato desta producao nao tem etapas de catalogo.")
        audit_service.record(
            db, actor=actor, action="production.stages_created", entity_type="production",
            entity_id=producao.id, metadata={"proposal_id": proposta.id, "result": "created"},
            request_id=request_id,
        )
        resposta = listar(db, producao, papel="admin", usuario=actor)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def _anterior(etapas, etapa):
    return next(
        (item for item in etapas if item.item_indice == etapa.item_indice and item.ordem_no_item == etapa.ordem_no_item - 1),
        None,
    )


def _seguinte(etapas, etapa):
    return next(
        (item for item in etapas if item.item_indice == etapa.item_indice and item.ordem_no_item == etapa.ordem_no_item + 1),
        None,
    )


def _bloqueio(etapas, etapa, destino):
    """Returns why a transition is blocked by dependencies, or None."""
    if destino != "pendente" and etapa.depende_da_anterior:
        anterior = _anterior(etapas, etapa)
        if anterior is not None and anterior.status != "concluida":
            return f"Conclua antes a etapa '{anterior.nome}'."
    if etapa.status == "concluida" and destino != "concluida":
        seguinte = _seguinte(etapas, etapa)
        if seguinte is not None and seguinte.depende_da_anterior and seguinte.status != "pendente":
            return f"A etapa '{seguinte.nome}' ja comecou; volte-a para pendente primeiro."
    return None


def _revisao_bloqueada(etapa, papel, politicas) -> bool:
    """5.10: with 'exigir_admin', only the admin reopens a stage whose included reviews are used up."""
    return (
        papel != "admin"
        and (politicas or {}).get("revisoes_excedentes") == "exigir_admin"
        and etapa.revisoes_incluidas is not None
        and (etapa.revisoes_usadas or 0) >= etapa.revisoes_incluidas
    )


def _acoes(etapas, etapa, papel, usuario=None, politicas=None):
    if getattr(etapa, "_credito_bloqueio", None):
        return []
    if papel == "admin":
        possiveis = TRANSICOES[etapa.status]
    elif papel == "produtor":
        # 5.07: only the stage's responsible acts on it; coordinating gives no extra power.
        if usuario is None or etapa.responsavel_usuario_id != usuario.id:
            return []
        possiveis = TRANSICOES_PRODUTOR[etapa.status]
    else:
        return []
    return [destino for destino in ("pendente", "em_andamento", "em_revisao", "concluida")
            if destino in possiveis and _bloqueio(etapas, etapa, destino) is None
            and not (etapa.status == "em_revisao" and destino == "em_andamento"
                     and _revisao_bloqueada(etapa, papel, politicas))]


def _progresso(etapas) -> int:
    if not etapas:
        return 0
    total = sum((etapa.valor for etapa in etapas), Decimal("0"))
    if total > 0:
        concluido = sum((etapa.valor for etapa in etapas if etapa.status == "concluida"), Decimal("0"))
        return int((concluido * 100 / total).to_integral_value(rounding=ROUND_HALF_UP))
    concluidas = sum(1 for etapa in etapas if etapa.status == "concluida")
    return int((Decimal(concluidas) * 100 / len(etapas)).to_integral_value(rounding=ROUND_HALF_UP))


def _rotulo_responsavel(etapa, usuario):
    if etapa.responsavel_usuario_id is None:
        return "Sem responsavel"
    if usuario is not None and etapa.responsavel_usuario_id == usuario.id:
        return "Voce"
    return "Outro produtor"


def _serializar(etapas, etapa, papel, usuario=None, nomes=None, politicas=None):
    dados = {
        "id": etapa.id,
        "ordem": etapa.ordem,
        "item_indice": etapa.item_indice,
        "item_descricao": etapa.item_descricao,
        "ordem_no_item": etapa.ordem_no_item,
        "nome": etapa.nome,
        "status": etapa.status,
        "prazo": etapa.prazo,
        "iniciada_em": etapa.iniciada_em,
        "concluida_em": etapa.concluida_em,
        "depende_da_anterior": etapa.depende_da_anterior,
        "administrativa": etapa.administrativa,
    }
    if papel in ("admin", "produtor"):
        dados.update(
            bloqueio_creditos=getattr(etapa, "_credito_bloqueio", None),
            unidade=etapa.unidade,
            revisoes_incluidas=etapa.revisoes_incluidas,
            revisoes_usadas=etapa.revisoes_usadas or 0,
            prazo_dias=etapa.prazo_dias,
            acoes=_acoes(etapas, etapa, papel, usuario, politicas),
        )
    elif papel == "cliente" and not (politicas or {}).get("cliente_ve_prazos_etapas", True):
        dados["prazo"] = None  # 5.10: stage deadlines hidden from the client by policy.
    if papel == "produtor":
        dados.update(
            minha=usuario is not None and etapa.responsavel_usuario_id == usuario.id,
            responsavel_rotulo=_rotulo_responsavel(etapa, usuario),
        )
    if papel == "admin":
        # Contract economics stay with the admin (producer payouts arrive in 5.13).
        dados.update(
            servico_id=etapa.servico_id,
            peso_percentual=etapa.peso_percentual,
            valor=etapa.valor,
            responsavel_usuario_id=etapa.responsavel_usuario_id,
            responsavel_nome=(nomes or {}).get(etapa.responsavel_usuario_id),
            executor_usuario_id=etapa.executor_usuario_id,
            executor_nome=(nomes or {}).get(etapa.executor_usuario_id),
        )
    return dados


def _nomes(db: Session, ids) -> dict:
    ids = {id_ for id_ in ids if id_ is not None}
    if not ids:
        return {}
    return dict(db.execute(select(UsuarioModel.id, UsuarioModel.username).where(UsuarioModel.id.in_(ids))).all())


def listar(db: Session, producao: ProducaoModel, *, papel: str, usuario=None):
    etapas = _etapas(db, producao.id)
    politicas = politica_service.vigentes(db, producao.id)  # 5.10
    nomes = {}
    if papel == "admin":
        nomes = _nomes(db, [id_ for etapa in etapas for id_ in (etapa.responsavel_usuario_id, etapa.executor_usuario_id)])
    resposta = {
        "producao_id": producao.id,
        "progresso_percentual": _progresso(etapas),
        "etapas": [_serializar(etapas, etapa, papel, usuario, nomes, politicas) for etapa in etapas],
    }
    if papel == "cliente" and not politicas["cliente_ve_etapas"]:
        # 5.10: the contract hides the stages from the client; only the overall progress remains.
        resposta["etapas"] = []
        resposta["etapas_ocultas"] = True
    if papel in ("admin", "produtor"):
        resposta["revisoes_excedentes"] = politicas["revisoes_excedentes"]
    if papel == "admin":
        resposta["pode_gerar"] = not etapas and bool(
            (proposta := _proposta_da_producao(db, producao)) is not None and proposta.snapshot_economico
            and any(item.get("etapas") for item in proposta.snapshot_economico.get("itens", []))
        )
    return resposta


def atualizar(db: Session, producao: ProducaoModel, etapa_id: int, *, papel: str, usuario,
              status=None, status_atual=None, prazo=None, alterar_prazo=False, request_id=None):
    try:
        # Serialize a work start with credit reversal before locking its stages.
        db.scalar(select(ProducaoModel).where(ProducaoModel.id == producao.id).with_for_update()
                  .execution_options(populate_existing=True))
        etapas = _etapas(db, producao.id, bloquear=True)
        etapa = next((item for item in etapas if item.id == etapa_id), None)
        if etapa is None:
            raise EtapaNaoEncontrada("Etapa nao encontrada.")
        if alterar_prazo and papel != "admin":
            raise EtapaNaoEncontrada("Etapa nao encontrada.")
        if papel == "produtor" and etapa.responsavel_usuario_id != usuario.id:
            raise EtapaProibida("Esta etapa esta atribuida a outro produtor.")
        if status is not None:
            if status_atual is not None and status_atual != etapa.status:
                raise EtapaConflito("A etapa foi atualizada por outra pessoa. Recarregue antes de continuar.")
            if status != etapa.status:
                if getattr(etapa, "_credito_bloqueio", None):
                    raise EtapaConflito(etapa._credito_bloqueio)
                permitidas = TRANSICOES if papel == "admin" else TRANSICOES_PRODUTOR
                if status not in permitidas.get(etapa.status, set()):
                    raise EtapaInvalida(
                        f"Transicao nao permitida: {STATUS_ROTULOS[etapa.status]} -> {STATUS_ROTULOS[status]}."
                    )
                motivo = _bloqueio(etapas, etapa, status)
                if motivo:
                    raise EtapaConflito(motivo)
                revisao = etapa.status == "em_revisao" and status == "em_andamento"
                if revisao and _revisao_bloqueada(etapa, papel, politica_service.vigentes(db, producao.id)):
                    raise EtapaConflito(
                        "As revisoes incluidas nesta etapa acabaram; o estudio precisa liberar uma revisao extra."
                    )
                anterior = etapa.status
                agora = _agora()
                etapa.status = status
                if status == "em_andamento" and etapa.iniciada_em is None:
                    etapa.iniciada_em = agora
                etapa.concluida_em = agora if status == "concluida" else None
                # 5.07: the executor is whoever was responsible at conclusion; reopening clears it.
                etapa.executor_usuario_id = etapa.responsavel_usuario_id if status == "concluida" else None
                metadata = {"old_status": anterior, "new_status": status, "stage_order": etapa.ordem}
                if revisao:
                    # 5.10: each return from review is one review round; beyond the included ones it is extra.
                    etapa.revisoes_usadas = (etapa.revisoes_usadas or 0) + 1
                    metadata["review_round"] = etapa.revisoes_usadas
                    metadata["extra_review"] = (
                        etapa.revisoes_incluidas is not None and etapa.revisoes_usadas > etapa.revisoes_incluidas
                    )
                event = audit_service.record(
                    db, actor=usuario, action="production.stage_status_changed", entity_type="production",
                    entity_id=producao.id, metadata=metadata, request_id=request_id,
                )
                if status == "concluida" or revisao:
                    from services import portal_notificacao_service

                    portal_notificacao_service.emitir_producao(
                        db, producao, "revisao_liberada" if revisao else "etapa_concluida",
                        f"etapa-evento:{event.id}",
                        clientes=politica_service.vigentes(db, producao.id)["cliente_ve_etapas"],
                        produtores=True, actor_id=usuario.id,
                    )
        if alterar_prazo and prazo != etapa.prazo:
            etapa.prazo = prazo
            audit_service.record(
                db, actor=usuario, action="production.stage_deadline_changed", entity_type="production",
                entity_id=producao.id, metadata={"stage_order": etapa.ordem}, request_id=request_id,
            )
        db.flush()
        resposta = listar(db, producao, papel=papel, usuario=usuario)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def _produtor_ativo(db: Session, usuario_id: int):
    usuario = db.get(UsuarioModel, usuario_id)
    if usuario is None or not usuario.ativo or usuario.role != "produtor":
        raise EtapaInvalida("Escolha um produtor ativo.")
    return usuario


def atribuir(db: Session, producao: ProducaoModel, etapa_id: int, *, novo_usuario_id, responsavel_atual,
             motivo: str = "", usuario=None, request_id=None):
    """Admin (re)assigns the responsible of one stage, keeping an append-only history.

    Concluded stages keep who executed them and cannot be reassigned until reopened.
    """
    try:
        etapas = _etapas(db, producao.id, bloquear=True)
        etapa = next((item for item in etapas if item.id == etapa_id), None)
        if etapa is None:
            raise EtapaNaoEncontrada("Etapa nao encontrada.")
        if etapa.responsavel_usuario_id != responsavel_atual:
            raise EtapaConflito("O responsavel desta etapa mudou. Recarregue antes de continuar.")
        if etapa.status == "concluida":
            raise EtapaConflito("Etapa concluida preserva quem executou; reabra-a antes de reatribuir.")
        if novo_usuario_id is not None:
            _produtor_ativo(db, novo_usuario_id)
        if novo_usuario_id != etapa.responsavel_usuario_id:
            anterior = etapa.responsavel_usuario_id
            etapa.responsavel_usuario_id = novo_usuario_id
            db.add(ProducaoEtapaAtribuicaoModel(
                etapa_id=etapa.id, producao_id=producao.id, anterior_usuario_id=anterior,
                novo_usuario_id=novo_usuario_id, atribuido_por_usuario_id=getattr(usuario, "id", None),
                motivo=motivo,
            ))
            audit_service.record(
                db, actor=usuario, action="production.stage_assigned", entity_type="production",
                entity_id=producao.id,
                metadata={"stage_order": etapa.ordem, "old_assigned_user_id": anterior,
                          "new_assigned_user_id": novo_usuario_id},
                request_id=request_id,
            )
            db.flush()
        resposta = listar(db, producao, papel="admin", usuario=usuario)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def historico(db: Session, producao: ProducaoModel, etapa_id: int):
    etapa = db.get(ProducaoEtapaModel, etapa_id)
    if etapa is None or etapa.producao_id != producao.id:
        raise EtapaNaoEncontrada("Etapa nao encontrada.")
    linhas = list(db.scalars(
        select(ProducaoEtapaAtribuicaoModel)
        .where(ProducaoEtapaAtribuicaoModel.etapa_id == etapa_id)
        .order_by(ProducaoEtapaAtribuicaoModel.id)
    ))
    nomes = _nomes(db, [id_ for linha in linhas for id_ in
                        (linha.anterior_usuario_id, linha.novo_usuario_id, linha.atribuido_por_usuario_id)])
    return [{
        "id": linha.id,
        "anterior_usuario_id": linha.anterior_usuario_id,
        "anterior_nome": nomes.get(linha.anterior_usuario_id),
        "novo_usuario_id": linha.novo_usuario_id,
        "novo_nome": nomes.get(linha.novo_usuario_id),
        "atribuido_por_nome": nomes.get(linha.atribuido_por_usuario_id),
        "motivo": linha.motivo,
        "created_at": linha.created_at,
    } for linha in linhas]
