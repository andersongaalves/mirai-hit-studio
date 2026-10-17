"""Contractual portal policies (Roadmap 3.0, 5.10).

Inheritance for a production, per key: admin exception > contract > global > system.
- Global: append-only versions with optimistic concurrency, history and restore (as 5.01).
- Service: only the keys it overrides; the rest follows the global default.
- Contract: when a proposal is sent, every contracted service (single or in a combo) freezes
  its resolved policies in the economic snapshot (5.05). Later global or catalog changes do
  not touch it ("the contract in force prevails"). With several services the option most
  favourable to the client wins.
- Exception: the admin may override keys of one production, with a mandatory reason; it is
  audited and can be removed (back to the contract).
Policies never disable authentication, permissions or audit; the backend enforces them.
"""
from models import (
    PoliticaGlobalModel,
    ProducaoModel,
    ProducaoPoliticaModel,
    ServicoModel,
    ServicoPoliticaModel,
)
from pydantic import ValidationError
from schemas.politica import PoliticasCompletas, PoliticasParciais
from services import audit_service
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

CHAVES = tuple(PoliticasCompletas.model_fields)
# Options in order of preference for the client: the first one wins when services disagree.
FAVORAVEL = {
    "publicacao_previa": ("automatica", "aprovacao_admin"),
    "revisoes_excedentes": ("permitir", "exigir_admin"),
    "cliente_ve_etapas": (True, False),
    "cliente_ve_prazos_etapas": (True, False),
    "financeiro_cliente": ("completo", "resumido"),
    "entrega_final": ("liberada", "apos_quitacao"),
}
MAX_VERSOES_LISTADAS = 20


class PoliticaError(Exception):
    pass


class PoliticaNaoEncontrada(PoliticaError):
    pass


class PoliticaConflito(PoliticaError):
    pass


class PoliticaInvalida(PoliticaError):
    pass


def padroes() -> dict:
    return PoliticasCompletas().model_dump()


def _completas(dados) -> dict:
    """Re-validates stored values; a payload that no longer validates falls back key by key."""
    base = padroes()
    for chave, valor in (dados or {}).items():
        if chave not in base:
            continue
        try:
            base[chave] = PoliticasCompletas.model_validate({**padroes(), chave: valor}).model_dump()[chave]
        except ValidationError:
            continue
    return base


def _parciais(dados) -> dict:
    try:
        return PoliticasParciais.model_validate(dados or {}).model_dump(exclude_none=True)
    except ValidationError:
        return {}


# ---------------------------------------------------------------- global


def _ultima(db: Session):
    return db.scalar(select(PoliticaGlobalModel).order_by(PoliticaGlobalModel.versao.desc()).limit(1))


def globais(db: Session) -> dict:
    row = _ultima(db)
    if row is None:
        return {"versao": 0, "politicas": padroes()}
    return {"versao": row.versao, "politicas": _completas(row.dados)}


def versoes(db: Session) -> list[dict]:
    rows = db.scalars(
        select(PoliticaGlobalModel).order_by(PoliticaGlobalModel.versao.desc()).limit(MAX_VERSOES_LISTADAS)
    ).all()
    return [
        {
            "versao": row.versao,
            "autor_usuario_id": row.autor_usuario_id,
            "restaurada_de_versao": row.restaurada_de_versao,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


def publicar_globais(db: Session, politicas: dict, *, actor, base_versao: int, restaurada_de=None,
                     request_id=None) -> dict:
    dados = PoliticasCompletas.model_validate(politicas).model_dump()
    if dados["entrega_final"] != "apos_quitacao":
        raise PoliticaInvalida("Liberacao sem quitacao exige excecao por producao com motivo.")
    atual = globais(db)
    if base_versao != atual["versao"]:
        raise PoliticaConflito("As politicas foram alteradas por outra pessoa. Recarregue antes de publicar.")
    if dados == atual["politicas"] and atual["versao"] > 0:
        return atual
    proxima = (db.scalar(select(func.max(PoliticaGlobalModel.versao))) or 0) + 1
    try:
        row = PoliticaGlobalModel(versao=proxima, dados=dados, autor_usuario_id=getattr(actor, "id", None),
                                  restaurada_de_versao=restaurada_de)
        db.add(row)
        db.flush()
        audit_service.record(
            db, actor=actor,
            action="policy.global_restored" if restaurada_de else "policy.global_published",
            entity_type="policy", entity_id=row.id,
            metadata={"old_version": atual["versao"], "new_version": proxima, "restored_from_version": restaurada_de,
                      "changed_keys": ",".join(sorted(chave for chave in CHAVES if dados[chave] != atual["politicas"][chave]))},
            request_id=request_id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PoliticaConflito("Outra versao foi publicada ao mesmo tempo. Recarregue e tente novamente.") from None
    return {"versao": proxima, "politicas": dados}


def restaurar_globais(db: Session, versao: int, *, actor, base_versao: int, request_id=None) -> dict:
    row = db.scalar(select(PoliticaGlobalModel).where(PoliticaGlobalModel.versao == versao))
    if row is None:
        raise PoliticaNaoEncontrada("Versao nao encontrada.")
    return publicar_globais(db, _completas(row.dados), actor=actor, base_versao=base_versao,
                            restaurada_de=versao, request_id=request_id)


# ---------------------------------------------------------------- service


def politicas_servico(db: Session, servico_id: int) -> dict:
    if db.get(ServicoModel, servico_id) is None:
        raise PoliticaNaoEncontrada("Servico nao encontrado.")
    row = db.get(ServicoPoliticaModel, servico_id)
    return _parciais(row.dados if row else None)


def salvar_servico(db: Session, servico_id: int, politicas: dict, *, actor, request_id=None) -> dict:
    try:
        if db.get(ServicoModel, servico_id) is None:
            raise PoliticaNaoEncontrada("Servico nao encontrado.")
        dados = PoliticasParciais.model_validate(politicas).model_dump(exclude_none=True)
        if dados.get("entrega_final", "apos_quitacao") != "apos_quitacao":
            raise PoliticaInvalida("Liberacao sem quitacao exige excecao por producao com motivo.")
        row = db.get(ServicoPoliticaModel, servico_id)
        anterior = _parciais(row.dados if row else None)
        if row is None:
            row = ServicoPoliticaModel(servico_id=servico_id, dados=dados)
            db.add(row)
        else:
            row.dados = dados
        db.flush()
        audit_service.record(
            db, actor=actor, action="service.policies_updated", entity_type="service", entity_id=servico_id,
            metadata={"changed_keys": ",".join(sorted(chave for chave in CHAVES if anterior.get(chave) != dados.get(chave)))},
            request_id=request_id,
        )
        db.commit()
        return dados
    except Exception:
        db.rollback()
        raise


def resolver_servicos(db: Session, servico_ids) -> dict[int, dict]:
    """Complete policies (global + service overrides) of each service, for the snapshot."""
    ids = sorted({identifier for identifier in servico_ids if identifier is not None})
    if not ids:
        return {}
    base = globais(db)["politicas"]
    rows = {row.servico_id: row for row in db.scalars(
        select(ServicoPoliticaModel).where(ServicoPoliticaModel.servico_id.in_(ids)))}
    return {identifier: {**base, **_parciais(rows[identifier].dados if identifier in rows else None)}
            for identifier in ids}


# ---------------------------------------------------------------- contract


def _contribuicoes(snapshot: dict) -> list[dict]:
    contribuicoes = []
    for item in (snapshot or {}).get("itens", []):
        if item.get("componentes"):
            contribuicoes += [componente["politicas"] for componente in item["componentes"]
                              if componente.get("politicas")]
        elif item.get("servico_id") is not None and item.get("politicas"):
            contribuicoes.append(item["politicas"])
    return contribuicoes


def agregar(snapshot: dict) -> dict | None:
    """Contract policies: per key, the option most favourable to the client among services."""
    contribuicoes = [_completas(politicas) for politicas in _contribuicoes(snapshot)]
    if not contribuicoes:
        return None
    return {chave: next(opcao for opcao in FAVORAVEL[chave]
                        if any(politicas[chave] == opcao for politicas in contribuicoes))
            for chave in CHAVES}


def instanciar(db: Session, producao: ProducaoModel, proposta) -> ProducaoPoliticaModel | None:
    """Freezes the contract policies on the production once. Idempotent."""
    existente = db.get(ProducaoPoliticaModel, producao.id)
    if existente is not None:
        return existente
    contrato = agregar(getattr(proposta, "snapshot_economico", None) or {})
    if contrato is None:
        return None
    row = ProducaoPoliticaModel(producao_id=producao.id, contrato=contrato)
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------- production


def detalhar(db: Session, producao_id: int) -> dict:
    row = db.get(ProducaoPoliticaModel, producao_id)
    ultima = _ultima(db)
    global_atual = _completas(ultima.dados) if ultima is not None else None
    contrato = _completas(row.contrato) if row is not None and row.contrato is not None else None
    excecao = _parciais(row.excecao) if row is not None and row.excecao else None
    vigentes, origens = {}, {}
    for chave in CHAVES:
        if excecao and chave in excecao:
            vigentes[chave], origens[chave] = excecao[chave], "excecao"
        elif contrato is not None:
            vigentes[chave], origens[chave] = contrato[chave], "contrato"
        elif global_atual is not None:
            vigentes[chave], origens[chave] = global_atual[chave], "global"
        else:
            vigentes[chave], origens[chave] = padroes()[chave], "sistema"
    return {
        "producao_id": producao_id,
        "vigentes": vigentes,
        "origens": origens,
        "contrato": contrato,
        "excecao": excecao,
        "motivo": row.motivo if row is not None and excecao else None,
        "atualizado_em": row.updated_at if row is not None and excecao else None,
    }


def vigentes(db: Session, producao_id: int) -> dict:
    return detalhar(db, producao_id)["vigentes"]


def definir_excecao(db: Session, producao: ProducaoModel, politicas: dict, motivo: str, *, actor,
                    request_id=None) -> dict:
    try:
        dados = PoliticasParciais.model_validate(politicas).model_dump(exclude_none=True)
        if not dados:
            raise PoliticaInvalida("Informe ao menos uma politica.")
        if dados.get("entrega_final") == "liberada" and len((motivo or "").strip()) < 5:
            raise PoliticaInvalida("Explique o motivo da liberacao da entrega final.")
        antes = detalhar(db, producao.id)["vigentes"]
        row = db.get(ProducaoPoliticaModel, producao.id)
        if row is None:
            row = ProducaoPoliticaModel(producao_id=producao.id, contrato=None)
            db.add(row)
        row.excecao = dados
        row.motivo = motivo
        row.atualizado_por_usuario_id = getattr(actor, "id", None)
        db.flush()
        depois = detalhar(db, producao.id)
        audit_service.record(
            db, actor=actor, action="production.policies_exception_set", entity_type="production",
            entity_id=producao.id,
            metadata={
                "policy_keys": ",".join(sorted(dados)),
                "changed_keys": ",".join(sorted(c for c in CHAVES if antes[c] != depois["vigentes"][c])),
            },
            request_id=request_id,
        )
        db.commit()
        return detalhar(db, producao.id)
    except Exception:
        db.rollback()
        raise


def remover_excecao(db: Session, producao: ProducaoModel, *, actor, request_id=None) -> dict:
    try:
        row = db.get(ProducaoPoliticaModel, producao.id)
        if row is None or not row.excecao:
            raise PoliticaNaoEncontrada("Esta producao nao tem excecao de politicas.")
        chaves = sorted(_parciais(row.excecao))
        row.excecao = None
        row.motivo = None
        row.atualizado_por_usuario_id = getattr(actor, "id", None)
        db.flush()
        audit_service.record(
            db, actor=actor, action="production.policies_exception_removed", entity_type="production",
            entity_id=producao.id, metadata={"policy_keys": ",".join(chaves)}, request_id=request_id,
        )
        db.commit()
        return detalhar(db, producao.id)
    except Exception:
        db.rollback()
        raise
