"""Catalog combos (Roadmap 3.0, 5.08). Admin-only; proposals freeze their own copy."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import ComboItemModel, ComboModel, ServicoModel
from schemas.combo import ComboWrite
from schemas.servico_estrutura import ler
from services import audit_service

CENT = Decimal("0.01")


class ComboError(Exception):
    pass


class ComboNaoEncontrado(ComboError):
    pass


class ComboInvalido(ComboError):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def carregar(db: Session, ids=None, *, somente_ativos=False):
    query = select(ComboModel).options(
        selectinload(ComboModel.itens).selectinload(ComboItemModel.servico).selectinload(ServicoModel.etapas)
    ).order_by(ComboModel.nome, ComboModel.id)
    if ids is not None:
        query = query.where(ComboModel.id.in_(sorted(set(ids))))
    if somente_ativos:
        query = query.where(ComboModel.ativo.is_(True))
    return list(db.scalars(query))


def serializar(combo: ComboModel) -> dict:
    servicos = [{
        "servico_id": item.servico_id,
        "nome": item.servico.nome,
        "valor_base": _money(item.servico.valor_base),
        "etapas": len(item.servico.etapas),
        "estrutura": ler(item.servico.estrutura_servico),
        "parametros": item.servico.parametros or "",
    } for item in combo.itens]
    parametros = []
    for servico in servicos:
        for parametro in servico["parametros"].split(","):
            if parametro.strip() and parametro.strip() not in parametros:
                parametros.append(parametro.strip())
    return {
        "id": combo.id,
        "nome": combo.nome,
        "descricao": combo.descricao,
        "subtitulo": combo.subtitulo or "",
        "preco_base": _money(combo.preco_base),
        "aplica_desconto": bool(combo.aplica_desconto),
        "destaques": list(combo.destaques or []),
        "parametros": ",".join(parametros),
        "ativo": bool(combo.ativo),
        "soma_servicos": sum((servico["valor_base"] for servico in servicos), Decimal("0.00")),
        "servicos": servicos,
        "created_at": combo.created_at,
        "updated_at": combo.updated_at,
    }


def listar(db: Session, *, somente_ativos=False):
    return [serializar(combo) for combo in carregar(db, somente_ativos=somente_ativos)]


def _aplicar(db: Session, combo: ComboModel, dados: ComboWrite):
    # No autoflush: a new combo must not be inserted before its required fields are set.
    with db.no_autoflush:
        existentes = {servico.id for servico in db.scalars(select(ServicoModel).where(ServicoModel.id.in_(dados.servicos)))}
    if existentes != set(dados.servicos):
        raise ComboInvalido("Um dos servicos do combo nao existe no catalogo.")
    combo.nome = dados.nome
    combo.descricao = dados.descricao
    combo.preco_base = dados.preco_base
    combo.ativo = dados.ativo
    combo.subtitulo = dados.subtitulo
    combo.aplica_desconto = dados.aplica_desconto
    combo.destaques = list(dados.destaques)
    combo.itens.clear()
    db.flush()
    combo.itens.extend(ComboItemModel(servico_id=servico_id, ordem=ordem)
                       for ordem, servico_id in enumerate(dados.servicos, start=1))


def criar(db: Session, dados: ComboWrite, *, actor=None, request_id=None):
    try:
        combo = ComboModel(nome=dados.nome, descricao=dados.descricao, preco_base=dados.preco_base, ativo=dados.ativo,
                           subtitulo=dados.subtitulo, aplica_desconto=dados.aplica_desconto, destaques=list(dados.destaques))
        _aplicar(db, combo, dados)
        db.add(combo)
        db.flush()
        audit_service.record(db, actor=actor, action="combo.created", entity_type="combo", entity_id=combo.id,
                             metadata={}, request_id=request_id)
        db.commit()
        return serializar(carregar(db, [combo.id])[0])
    except Exception:
        db.rollback()
        raise


def atualizar(db: Session, combo_id: int, dados: ComboWrite, *, actor=None, request_id=None):
    try:
        combo = db.get(ComboModel, combo_id)
        if combo is None:
            raise ComboNaoEncontrado("Combo nao encontrado.")
        _aplicar(db, combo, dados)
        db.flush()
        audit_service.record(db, actor=actor, action="combo.updated", entity_type="combo", entity_id=combo.id,
                             metadata={}, request_id=request_id)
        db.commit()
        db.expire_all()
        return serializar(carregar(db, [combo.id])[0])
    except Exception:
        db.rollback()
        raise


def servico_em_combo(db: Session, servico_id: int) -> bool:
    return db.scalar(select(ComboItemModel.id).where(ComboItemModel.servico_id == servico_id).limit(1)) is not None
