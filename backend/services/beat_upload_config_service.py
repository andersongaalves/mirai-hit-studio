from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from models import ConfigModel
from schemas.beat import BeatUploadLimits
from services import audit_service

DEFAULT_LIMITS = BeatUploadLimits()
MB = 1024 * 1024


def limits(db) -> BeatUploadLimits:
    config = db.get(ConfigModel, 1)
    raw = config.beat_upload_limits_json if config else None
    try:
        return BeatUploadLimits.model_validate(raw or DEFAULT_LIMITS.model_dump())
    except ValidationError:
        raise HTTPException(500, "A configuração de uploads de beats é inválida.") from None


def limits_bytes(db) -> dict[str, int]:
    return {
        key.removesuffix("_mb"): value * MB
        for key, value in limits(db).model_dump().items()
        if key.endswith("_mb")
    }


def update(db, payload: BeatUploadLimits, actor) -> BeatUploadLimits:
    config = db.scalar(select(ConfigModel).where(ConfigModel.id == 1).with_for_update())
    if config is None:
        config = ConfigModel(id=1)
        db.add(config)
        db.flush()
    config.beat_upload_limits_json = payload.model_dump()
    audit_service.record(
        db,
        actor=actor,
        action="beat.upload_limits_updated",
        entity_type="configuracao",
        entity_id=config.id,
        metadata={"changed_keys": "capa_mb,mp3_mb,wav_mb,multitrack_mb,multitrack_mode"},
    )
    db.commit()
    return payload
