"""Configurable portfolio segment catalog and historical compatibility rules."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter

from fastapi import HTTPException
from models import ConfigModel, ProjetoModel

SEGMENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
MAX_SEGMENTS = 100


def _label(value: str) -> str:
    return " ".join(value.strip().split())


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _label(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")[:40]
    if not SEGMENT_ID_PATTERN.fullmatch(slug):
        raise HTTPException(422, "Use um nome com pelo menos duas letras ou números.")
    return slug


def _label_key(value: str) -> str:
    return _slug(value)


def _humanize(segment_id: str) -> str:
    return segment_id.replace("_", " ").title()


def _stored_catalog(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(500, "Catálogo de segmentos inválido.")
    catalog = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise HTTPException(500, "Catálogo de segmentos inválido.")
        segment_id = item.get("id")
        label = item.get("label")
        active = item.get("active")
        order = item.get("order")
        retired = item.get("retired", False)
        if (
            not isinstance(segment_id, str)
            or not SEGMENT_ID_PATTERN.fullmatch(segment_id)
            or not isinstance(label, str)
            or not 2 <= len(_label(label)) <= 80
            or not isinstance(active, bool)
            or not isinstance(order, int)
            or order < 1
            or not isinstance(retired, bool)
            or segment_id in seen
        ):
            raise HTTPException(500, "Catálogo de segmentos inválido.")
        seen.add(segment_id)
        catalog.append(
            {
                "id": segment_id,
                "label": _label(label),
                "active": active,
                "order": order,
                "retired": retired,
            }
        )
    if len(catalog) > MAX_SEGMENTS:
        raise HTTPException(500, "Catálogo de segmentos excede o limite permitido.")
    return sorted(catalog, key=lambda item: (item["order"], item["id"]))


def _usage_counts(db) -> Counter:
    counts = Counter()
    for (values,) in db.query(ProjetoModel.segmentos_json).all():
        if isinstance(values, list):
            counts.update(value for value in values if isinstance(value, str))
    return counts


def _merge_historical(catalog: list[dict], usage: Counter) -> list[dict]:
    merged = [dict(item) for item in catalog]
    known = {item["id"] for item in merged}
    order = max((item["order"] for item in merged), default=0)
    for segment_id in sorted(usage):
        if segment_id in known or not SEGMENT_ID_PATTERN.fullmatch(segment_id):
            continue
        order += 1
        merged.append(
            {
                "id": segment_id,
                "label": _humanize(segment_id),
                "active": False,
                "order": order,
                "retired": False,
            }
        )
    return merged


def _revision(catalog: list[dict]) -> str:
    canonical = sorted(catalog, key=lambda item: (item["order"], item["id"]))
    payload = json.dumps(
        canonical, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _config(db, *, lock: bool = False):
    query = db.query(ConfigModel).filter(ConfigModel.id == 1)
    if lock:
        query = query.with_for_update()
    config = query.first()
    if config is None:
        raise HTTPException(503, "Configurações ainda não foram inicializadas.")
    return config


def _catalog(db, *, lock: bool = False):
    config = _config(db, lock=lock)
    usage = _usage_counts(db)
    catalog = _merge_historical(_stored_catalog(config.portfolio_segments_json), usage)
    return config, catalog, usage


def _response(catalog: list[dict], usage: Counter):
    visible = [item for item in catalog if not item["retired"]]
    return {
        "segments": [
            {
                "id": item["id"],
                "label": item["label"],
                "active": item["active"],
                "order": item["order"],
                "usage_count": usage[item["id"]],
            }
            for item in sorted(visible, key=lambda item: (item["order"], item["id"]))
        ],
        "revision": _revision(catalog),
    }


def _locked(db, expected_revision: str):
    config, catalog, usage = _catalog(db, lock=True)
    if _revision(catalog) != expected_revision:
        raise HTTPException(
            409, "O catálogo foi alterado em outra sessão. Atualize e tente novamente."
        )
    return config, catalog, usage


def _save(db, config, catalog, usage):
    config.portfolio_segments_json = catalog
    db.commit()
    db.refresh(config)
    return _response(catalog, usage)


def catalog_response(db):
    _, catalog, usage = _catalog(db)
    return _response(catalog, usage)


def public_segments(db):
    _, catalog, usage = _catalog(db)
    return [
        {"id": item["id"], "label": item["label"]}
        for item in catalog
        if not item["retired"] and (item["active"] or usage[item["id"]] > 0)
    ]


def create_segment(db, payload):
    config, catalog, usage = _locked(db, payload.expected_revision)
    label = _label(payload.label)
    segment_id = _slug(label)
    if len(catalog) >= MAX_SEGMENTS:
        raise HTTPException(409, "O limite de 100 segmentos foi atingido.")
    if any(item["id"] == segment_id for item in catalog):
        raise HTTPException(409, "Este identificador já existe ou foi aposentado.")
    key = _label_key(label)
    if any(_label_key(item["label"]) == key for item in catalog):
        raise HTTPException(409, "Já existe um segmento com este nome.")
    catalog.append(
        {
            "id": segment_id,
            "label": label,
            "active": True,
            "order": max((item["order"] for item in catalog), default=0) + 1,
            "retired": False,
        }
    )
    return _save(db, config, catalog, usage)


def update_segment(db, segment_id: str, payload):
    config, catalog, usage = _locked(db, payload.expected_revision)
    segment = next(
        (item for item in catalog if item["id"] == segment_id and not item["retired"]),
        None,
    )
    if segment is None:
        raise HTTPException(404, "Segmento não encontrado.")
    if payload.label is not None:
        label = _label(payload.label)
        key = _label_key(label)
        if any(
            item["id"] != segment_id and _label_key(item["label"]) == key
            for item in catalog
        ):
            raise HTTPException(409, "Já existe um segmento com este nome.")
        segment["label"] = label
    if payload.active is not None:
        segment["active"] = payload.active
    return _save(db, config, catalog, usage)


def reorder_segments(db, payload):
    config, catalog, usage = _locked(db, payload.expected_revision)
    visible = [item for item in catalog if not item["retired"]]
    if len(payload.segment_ids) != len(set(payload.segment_ids)):
        raise HTTPException(422, "A ordem contém segmentos duplicados.")
    if set(payload.segment_ids) != {item["id"] for item in visible}:
        raise HTTPException(409, "A lista de ordenação está desatualizada.")
    positions = {
        segment_id: index
        for index, segment_id in enumerate(payload.segment_ids, start=1)
    }
    for item in visible:
        item["order"] = positions[item["id"]]
    return _save(db, config, catalog, usage)


def retire_segment(db, segment_id: str, payload):
    config, catalog, usage = _locked(db, payload.expected_revision)
    segment = next(
        (item for item in catalog if item["id"] == segment_id and not item["retired"]),
        None,
    )
    if segment is None:
        raise HTTPException(404, "Segmento não encontrado.")
    if usage[segment_id]:
        raise HTTPException(
            409, "Desative o segmento; ele ainda está associado a projetos."
        )
    segment["active"] = False
    segment["retired"] = True
    return _save(db, config, catalog, usage)


def validate_project_segments(db, *, current: list[str], proposed: list[str]) -> None:
    _, catalog, _ = _catalog(db)
    available = {
        item["id"] for item in catalog if item["active"] and not item["retired"]
    }
    added = set(proposed) - set(current)
    invalid = sorted(added - available)
    if invalid:
        raise HTTPException(
            422,
            "Selecione apenas segmentos ativos do catálogo: " + ", ".join(invalid),
        )
