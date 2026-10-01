import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

import models
from core.dependencies import require_admin
from database import get_db
from schemas.projeto import ProjetoCreate, ProjetoMixComparisonPublic, ProjetoResponse
from services.portfolio_audio_storage import (
    HTTPAudioValidationError,
    PortfolioAudioStorageError,
    max_audio_bytes,
    new_portfolio_audio_storage,
    validate_mp3,
)
from services.portfolio_service import (
    PUBLIC_CASE_TYPES,
    PUBLIC_VERTICALS,
    apply_project_data,
    delete_project_and_reorder,
    set_audio_key,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projetos", tags=["Projetos"])


def _response(project, storage=None):
    data = ProjetoResponse.model_validate(project).model_dump()
    if project.audio_before_key or project.audio_after_key:
        storage = storage or new_portfolio_audio_storage()
        if project.audio_before_key:
            data["audio_before_url"] = storage.public_url(project.audio_before_key)
        if project.audio_after_key:
            data["audio_after_url"] = storage.public_url(project.audio_after_key)
    return data


def _project_or_404(db, project_id):
    project = db.query(models.ProjetoModel).filter(models.ProjetoModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto nao encontrado.")
    return project


@router.get("", response_model=list[ProjetoResponse])
def listar_projetos(db: Session = Depends(get_db)):
    return (
        db.query(models.ProjetoModel)
        .filter(
            models.ProjetoModel.vertical.in_(PUBLIC_VERTICALS),
            models.ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES),
        )
        .all()
    )


@router.get("/public/mix-comparisons", response_model=list[ProjetoMixComparisonPublic])
def listar_mix_comparisons(db: Session = Depends(get_db)):
    projects = (
        db.query(models.ProjetoModel)
        .filter(
            models.ProjetoModel.vertical.in_(PUBLIC_VERTICALS),
            models.ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES),
            models.ProjetoModel.show_mix_comparison_on_landing.is_(True),
            models.ProjetoModel.audio_before_key.is_not(None),
            models.ProjetoModel.audio_after_key.is_not(None),
        )
        .order_by(models.ProjetoModel.landing_order)
        .limit(4)
        .all()
    )
    if not projects:
        return []
    try:
        storage = new_portfolio_audio_storage()
        return [
            {
                "id": project.id,
                "titulo": project.titulo,
                "artista": project.artista,
                "link_capa": project.link_capa,
                "link_audio": project.link_audio,
                "audio_before_url": storage.public_url(project.audio_before_key),
                "audio_after_url": storage.public_url(project.audio_after_key),
                "landing_order": project.landing_order,
            }
            for project in projects
        ]
    except PortfolioAudioStorageError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/admin", response_model=list[ProjetoResponse])
def listar_projetos_admin(db: Session = Depends(get_db), user=Depends(require_admin)):
    projects = db.query(models.ProjetoModel).order_by(models.ProjetoModel.id.desc()).all()
    try:
        return [_response(project) for project in projects]
    except PortfolioAudioStorageError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("", response_model=ProjetoResponse)
def criar_projeto(proj: ProjetoCreate, db: Session = Depends(get_db), user=Depends(require_admin)):
    project = models.ProjetoModel()
    db.add(project)
    try:
        apply_project_data(db, project, proj.model_dump())
        db.commit()
        db.refresh(project)
        return _response(project)
    except HTTPException:
        db.rollback()
        raise


@router.put("/{id}", response_model=ProjetoResponse)
def atualizar_projeto(
    id: int,
    proj_atualizado: ProjetoCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    project = _project_or_404(db, id)
    try:
        apply_project_data(db, project, proj_atualizado.model_dump())
        db.commit()
        db.refresh(project)
        return _response(project)
    except HTTPException:
        db.rollback()
        raise


@router.post("/{id}/audio/{slot}", response_model=ProjetoResponse)
async def upload_project_audio(
    id: int,
    slot: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    if slot not in ("before", "after"):
        raise HTTPException(status_code=404, detail="Slot de audio invalido.")
    data = await audio.read(max_audio_bytes() + 1)
    if len(data) > max_audio_bytes():
        raise HTTPException(status_code=413, detail="O audio excede o limite de 30 MB.")
    try:
        validate_mp3(data, audio.content_type)
    except HTTPAudioValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    project = _project_or_404(db, id)
    try:
        storage = new_portfolio_audio_storage()
        old_key = getattr(project, f"audio_{slot}_key")
        new_key = storage.save(data, project.id, slot)
    except PortfolioAudioStorageError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        set_audio_key(db, project, slot, new_key)
        db.commit()
        db.refresh(project)
    except Exception:
        db.rollback()
        try:
            storage.delete(new_key)
        except PortfolioAudioStorageError:
            logger.warning("portfolio_audio_compensation_failed project_id=%s slot=%s", id, slot)
        raise

    if old_key:
        try:
            storage.delete(old_key)
        except PortfolioAudioStorageError:
            logger.warning("portfolio_audio_cleanup_failed project_id=%s slot=%s", id, slot)
    return _response(project, storage)


@router.delete("/{id}/audio/{slot}", response_model=ProjetoResponse)
def delete_project_audio(
    id: int,
    slot: str,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    if slot not in ("before", "after"):
        raise HTTPException(status_code=404, detail="Slot de audio invalido.")
    project = _project_or_404(db, id)
    old_key = getattr(project, f"audio_{slot}_key")
    try:
        set_audio_key(db, project, slot, None)
        db.commit()
        db.refresh(project)
    except Exception:
        db.rollback()
        raise

    if old_key:
        try:
            new_portfolio_audio_storage().delete(old_key)
        except PortfolioAudioStorageError:
            logger.warning("portfolio_audio_cleanup_failed project_id=%s slot=%s", id, slot)
    return _response(project)


@router.delete("/{id}")
def deletar_projeto(id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    project = _project_or_404(db, id)
    audio_keys = [project.audio_before_key, project.audio_after_key]
    try:
        delete_project_and_reorder(db, project)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for key in filter(None, audio_keys):
        try:
            new_portfolio_audio_storage().delete(key)
        except PortfolioAudioStorageError:
            logger.warning("portfolio_audio_cleanup_failed project_id=%s slot=project_delete", id)
    return {"status": "ok"}
