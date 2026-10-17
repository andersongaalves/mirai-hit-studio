from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from database import get_db
import models
from schemas.servico import (ServicoCreate, ServicoResponse)

from core.dependencies import require_admin
from schemas.servico_etapa import ServicoEtapaOut, ServicoEtapasUpdate
from schemas.promocao import PrecoCatalogo
from services import audit_service, catalogo_service, promocao_service

router = APIRouter(prefix="/servicos", tags=["Serviços"])


def _resposta_servico(servico, desconto=0):
    resposta = ServicoResponse.model_validate(servico)
    resposta.prazo_estimado_dias = catalogo_service.prazo_estimado(servico.etapas)
    resposta.preco_catalogo = PrecoCatalogo.model_validate(promocao_service.preco(servico, desconto))
    return resposta


@router.get("", response_model=list[ServicoResponse])
def listar_servicos(db: Session = Depends(get_db)):
    servicos = db.query(models.ServicoModel).options(selectinload(models.ServicoModel.etapas)).all()
    desconto = promocao_service.desconto_global(db)
    return [_resposta_servico(servico, desconto) for servico in servicos]


@router.post("", response_model=ServicoResponse)
def criar_servico(
    servico: ServicoCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):

    dados = servico.model_dump(mode="json")
    dados["categoria"] = dados.get("categoria") or "avulso"  # Combos live in the combos catalog (5.08).
    novo = models.ServicoModel(**dados)

    db.add(novo)
    db.flush()
    catalogo_service.sincronizar_cotas(db, novo)
    promocao_service.auditar_alteracao(db, novo, None, actor=user)
    db.commit()
    db.refresh(novo)

    return _resposta_servico(novo, promocao_service.desconto_global(db))


@router.put("/{servico_id}", response_model=ServicoResponse)
def atualizar_servico(
    servico_id: int,
    srv_atualizado: ServicoCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):

    servico = (
        db.query(models.ServicoModel)
        .filter(models.ServicoModel.id == servico_id)
        .first()
    )

    if not servico:
        raise HTTPException(status_code=404)

    promocao_anterior = servico.promocao
    for key, value in srv_atualizado.model_dump(mode="json").items():
        if key == "promocao" and key not in srv_atualizado.model_fields_set:
            continue  # Older editors must not erase a separately configured promotion.
        if key == "categoria" and value is None:
            continue  # The editor no longer chooses a category; legacy rows keep theirs.
        setattr(servico, key, value)

    db.flush()
    catalogo_service.sincronizar_cotas(db, servico)
    promocao_service.auditar_alteracao(db, servico, promocao_anterior, actor=user)
    db.commit()

    db.refresh(servico)

    return _resposta_servico(servico, promocao_service.desconto_global(db))


@router.delete("/{servico_id}")
def deletar_servico(
    servico_id: int, db: Session = Depends(get_db), user=Depends(require_admin)
):

    servico = (
        db.query(models.ServicoModel)
        .filter(models.ServicoModel.id == servico_id)
        .first()
    )

    if not servico:
        raise HTTPException(status_code=404)
    # 5.08: a service inside a combo cannot be deleted (the combo would lose a component).
    from services import combo_service

    if combo_service.servico_em_combo(db, servico_id):
        raise HTTPException(status_code=409, detail="Este servico faz parte de um combo; remova-o do combo antes.")

    db.delete(servico)
    db.commit()

    return {"status": "ok"}


# ===========================
# ETAPAS (Roadmap 3.0, 5.04)
# ===========================


def _servico_or_404(db: Session, servico_id: int):
    servico = db.get(models.ServicoModel, servico_id)
    if servico is None:
        raise HTTPException(status_code=404, detail="Servico nao encontrado.")
    return servico


@router.get("/{servico_id}/etapas", response_model=list[ServicoEtapaOut])
def listar_etapas(servico_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    return _servico_or_404(db, servico_id).etapas


@router.put("/{servico_id}/etapas", response_model=list[ServicoEtapaOut])
def substituir_etapas(
    servico_id: int,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Replace the whole stage list atomically; weights must total exactly 100%."""
    try:
        data = ServicoEtapasUpdate.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        message = str(first.get("msg", "Etapas invalidas.")).removeprefix("Value error, ")
        field = ".".join(str(part) for part in first.get("loc", ()))
        detail = message if first.get("type") == "value_error" else f"Campo invalido: {field}"
        raise HTTPException(status_code=422, detail=detail) from None

    servico = _servico_or_404(db, servico_id)
    old_count = len(servico.etapas)
    servico.etapas.clear()
    db.flush()
    for ordem, etapa in enumerate(data.etapas, start=1):
        servico.etapas.append(models.ServicoEtapaModel(ordem=ordem, **etapa.model_dump()))
    audit_service.record(
        db,
        actor=user,
        action="service.stages_updated",
        entity_type="service",
        entity_id=servico.id,
        metadata={"old_stage_count": old_count, "new_stage_count": len(data.etapas)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(servico)
    return servico.etapas
