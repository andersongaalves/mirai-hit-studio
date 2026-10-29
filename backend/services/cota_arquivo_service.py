"""File quotas per contract (Roadmap 3.0, 5.09).

Catalog services define limits per file type. When a proposal is sent, the limits of every
contracted service are frozen in the economic snapshot (5.05); when the production is
created they are aggregated into the production's quotas. Client and producer uploads are
checked on the server, inside a lock on the production row, so simultaneous uploads cannot
overshoot a quota. The admin is not limited and may adjust a production's quotas.

Aggregation for a file type across the contracted services (quantity rounded up):
- every contributing service must define the type, otherwise the type has no quota
  ("no limit" wins over "limit");
- files and total storage add up (x quantity); versions and per-file size take the
  largest value; formats are the union. A null in any service means no limit.
"""
import math
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import (
    ProducaoArquivoModel,
    ProducaoCotaArquivoModel,
    ProducaoModel,
    ServicoCotaArquivoModel,
    ServicoModel,
)
from services import audio_duracao, audit_service
from services.producao_arquivo_storage import ALLOWED_MIME_TYPES

TIPOS = ("material", "referencia", "previa", "entrega")
CAMPOS = ("max_arquivos", "max_versoes", "max_tamanho_mb", "max_total_mb", "max_duracao_min", "formatos")
LIMITES = {"max_arquivos": 100, "max_total_mb": 5000}
MB = 1024 * 1024
ROTULOS = {"material": "materiais", "referencia": "referencias", "previa": "previas", "entrega": "entregas"}


class CotaError(Exception):
    pass


class CotaNaoEncontrada(CotaError):
    pass


class CotaFormato(CotaError):
    """The file itself breaks the contract (format or size): 422."""


class CotaExcedida(CotaError):
    """The production has no room left for this upload: 409."""


def _dict(row) -> dict:
    return {"tipo": row.tipo, **{campo: getattr(row, campo) for campo in CAMPOS}}


# ---------------------------------------------------------------- catalog


def cotas_servico(db: Session, servico_id: int) -> list[dict]:
    if db.get(ServicoModel, servico_id) is None:
        raise CotaNaoEncontrada("Servico nao encontrado.")
    rows = db.scalars(select(ServicoCotaArquivoModel).where(ServicoCotaArquivoModel.servico_id == servico_id))
    return sorted((_dict(row) for row in rows), key=lambda cota: TIPOS.index(cota["tipo"]))


def carregar_cotas(db: Session, servico_ids) -> dict[int, list[dict]]:
    ids = sorted({identifier for identifier in servico_ids if identifier is not None})
    if not ids:
        return {}
    resultado: dict[int, list[dict]] = {identifier: [] for identifier in ids}
    for row in db.scalars(select(ServicoCotaArquivoModel).where(ServicoCotaArquivoModel.servico_id.in_(ids))):
        resultado[row.servico_id].append(_dict(row))
    for cotas in resultado.values():
        cotas.sort(key=lambda cota: TIPOS.index(cota["tipo"]))
    return resultado


def substituir_servico(db: Session, servico_id: int, cotas, *, actor=None, request_id=None) -> list[dict]:
    try:
        if db.get(ServicoModel, servico_id) is None:
            raise CotaNaoEncontrada("Servico nao encontrado.")
        db.query(ServicoCotaArquivoModel).filter(ServicoCotaArquivoModel.servico_id == servico_id).delete()
        db.add_all([ServicoCotaArquivoModel(servico_id=servico_id, **cota.model_dump()) for cota in cotas])
        db.flush()
        audit_service.record(db, actor=actor, action="service.file_quotas_updated", entity_type="service",
                             entity_id=servico_id, metadata={"result": "updated"}, request_id=request_id)
        db.commit()
        return cotas_servico(db, servico_id)
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------- contract aggregation


def _quantidade(valor) -> int:
    try:
        return max(1, math.ceil(Decimal(str(valor))))
    except Exception:
        return 1


def _contribuicoes(snapshot: dict) -> list[tuple[int, list[dict]]]:
    """(quantity, quotas) of every contracted catalog service that froze quotas (5.09+)."""
    contribuicoes = []
    for item in (snapshot or {}).get("itens", []):
        quantidade = _quantidade(item.get("quantidade", 1))
        if item.get("componentes"):
            for componente in item["componentes"]:
                if "cotas_arquivos" in componente:
                    contribuicoes.append((quantidade, componente["cotas_arquivos"] or []))
        elif item.get("servico_id") is not None and "cotas_arquivos" in item:
            contribuicoes.append((quantidade, item["cotas_arquivos"] or []))
    return contribuicoes


def agregar(snapshot: dict) -> list[dict]:
    contribuicoes = _contribuicoes(snapshot)
    if not contribuicoes:
        return []
    resultado = []
    for tipo in TIPOS:
        porcoes = []
        for quantidade, cotas in contribuicoes:
            cota = next((item for item in cotas if item.get("tipo") == tipo), None)
            if cota is None:
                porcoes = None  # A service without a quota for the type: no contractual limit.
                break
            porcoes.append((quantidade, cota))
        if not porcoes:
            continue
        agregada = {"tipo": tipo}
        for campo in ("max_arquivos", "max_total_mb"):
            valores = [cota.get(campo) for _, cota in porcoes]
            agregada[campo] = (
                None if any(valor is None for valor in valores)
                else min(LIMITES[campo], sum(quantidade * cota[campo] for quantidade, cota in porcoes))
            )
        for campo in ("max_versoes", "max_tamanho_mb", "max_duracao_min"):
            valores = [cota.get(campo) for _, cota in porcoes]
            agregada[campo] = None if any(valor is None for valor in valores) else max(valores)
        formatos = [cota.get("formatos") for _, cota in porcoes]
        agregada["formatos"] = (
            None if any(lista is None for lista in formatos)
            else sorted(set().union(*formatos) & ALLOWED_MIME_TYPES)
        )
        resultado.append(agregada)
    return resultado


def instanciar(db: Session, producao: ProducaoModel, proposta) -> list:
    """Creates the production's quotas from the frozen snapshot once. Idempotent."""
    existentes = list(db.scalars(
        select(ProducaoCotaArquivoModel).where(ProducaoCotaArquivoModel.producao_id == producao.id)
    ))
    if existentes:
        return existentes
    criadas = [
        ProducaoCotaArquivoModel(producao_id=producao.id, origem="contrato", **cota)
        for cota in agregar(getattr(proposta, "snapshot_economico", None) or {})
    ]
    if criadas:
        db.add_all(criadas)
        db.flush()
    return criadas


# ---------------------------------------------------------------- production view and admin override


def _uso(db: Session, producao_id: int) -> dict[str, tuple[int, int]]:
    from models import PreviaTagJobModel, ProducaoEntregaFinalModel

    rows = db.execute(
        select(
            ProducaoArquivoModel.tipo,
            func.count(func.distinct(ProducaoArquivoModel.grupo_versao)),
            func.coalesce(func.sum(ProducaoArquivoModel.tamanho_bytes + func.coalesce(
                PreviaTagJobModel.tamanho_bytes, PreviaTagJobModel.reserva_bytes, 0)), 0),
        )
        .outerjoin(PreviaTagJobModel, PreviaTagJobModel.arquivo_id == ProducaoArquivoModel.id)
        .where(ProducaoArquivoModel.producao_id == producao_id)
        .group_by(ProducaoArquivoModel.tipo)
    ).all()
    usage = {tipo: (int(arquivos), int(total)) for tipo, arquivos, total in rows}
    delivery = usage.get("entrega")
    if delivery is not None:
        packages = list(db.scalars(select(ProducaoEntregaFinalModel).where(
            ProducaoEntregaFinalModel.producao_id == producao_id,
        )))
        linked_ids = {
            file_id
            for package in packages
            for file_id in (
                package.arquivo_principal_id,
                package.wav_arquivo_id,
                package.multitrack_arquivo_id,
                package.licenca_arquivo_id,
            )
            if file_id is not None
        }
        # A structured package consumes one contractual delivery slot, while its
        # MP3/WAV/archive/license bytes still count in full.
        usage["entrega"] = (max(0, delivery[0] - len(linked_ids) + len(packages)), delivery[1])
    return usage


def verificar_pacote_entrega(
    db: Session,
    producao_id: int,
    arquivos: list[tuple[str, int, bytes]],
    *,
    extra_storage_bytes: int = 0,
) -> None:
    """Validate a final-delivery bundle as one logical delivery and all of its bytes."""
    from services import credito_alocacao_service, credito_producao_service

    try:
        credito_producao_service.validar_upload(db, producao_id, "entrega")
    except credito_alocacao_service.AlocacaoConflito as error:
        raise CotaExcedida(str(error)) from None
    cota = db.scalar(select(ProducaoCotaArquivoModel).where(
        ProducaoCotaArquivoModel.producao_id == producao_id,
        ProducaoCotaArquivoModel.tipo == "entrega",
    ))
    if cota is None:
        return
    usados, total = _uso(db, producao_id).get("entrega", (0, 0))
    if cota.max_arquivos is not None and usados >= cota.max_arquivos:
        raise CotaExcedida(f"Limite de {cota.max_arquivos} arquivo(s) de entregas do contrato atingido.")
    total_novo = extra_storage_bytes
    for mime_type, tamanho, data in arquivos:
        if cota.formatos is not None and mime_type not in cota.formatos:
            raise CotaFormato("Formato nao permitido pelo contrato para entregas.")
        if cota.max_tamanho_mb is not None and tamanho > cota.max_tamanho_mb * MB:
            raise CotaFormato(f"O contrato permite entregas de ate {cota.max_tamanho_mb} MB por arquivo.")
        if cota.max_duracao_min is not None and mime_type.startswith("audio/"):
            duration = audio_duracao.segundos(data)
            if duration is None:
                raise CotaFormato("Nao foi possivel conferir a duracao deste audio; envie um formato valido.")
            if duration > cota.max_duracao_min * 60 + 1:
                raise CotaFormato(f"O contrato permite entregas de ate {cota.max_duracao_min} min por faixa.")
        total_novo += tamanho
    if cota.max_total_mb is not None and total + total_novo > cota.max_total_mb * MB:
        raise CotaExcedida(f"Espaco contratado para entregas ({cota.max_total_mb} MB) esgotado.")


def listar_producao(db: Session, producao: ProducaoModel, *, tipos=TIPOS) -> dict:
    uso = _uso(db, producao.id)
    rows = db.scalars(select(ProducaoCotaArquivoModel).where(ProducaoCotaArquivoModel.producao_id == producao.id))
    cotas = []
    for row in sorted(rows, key=lambda item: TIPOS.index(item.tipo)):
        if row.tipo not in tipos:
            continue
        arquivos, total = uso.get(row.tipo, (0, 0))
        cotas.append({**_dict(row), "origem": row.origem, "arquivos_usados": arquivos, "total_usado_bytes": total})
    return {"producao_id": producao.id, "cotas": cotas, "formatos_disponiveis": sorted(ALLOWED_MIME_TYPES)}


def substituir_producao(db: Session, producao: ProducaoModel, cotas, *, actor=None, request_id=None) -> dict:
    """Admin exception: replaces the production's quotas (an empty list removes all limits)."""
    try:
        db.query(ProducaoCotaArquivoModel).filter(ProducaoCotaArquivoModel.producao_id == producao.id).delete()
        db.add_all([
            ProducaoCotaArquivoModel(producao_id=producao.id, origem="admin", **cota.model_dump()) for cota in cotas
        ])
        db.flush()
        audit_service.record(db, actor=actor, action="production.file_quotas_updated", entity_type="production",
                             entity_id=producao.id, metadata={"result": "updated"}, request_id=request_id)
        db.commit()
        return listar_producao(db, producao)
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------- upload check


def travar_producao(db: Session, producao_id: int) -> None:
    """Serializes uploads of one production until the caller commits or rolls back."""
    db.execute(select(ProducaoModel.id).where(ProducaoModel.id == producao_id).with_for_update())


def verificar(db: Session, producao_id: int, *, tipo: str, mime_type: str, tamanho: int, nova_versao: int | None,
              data: bytes | None = None, extra_storage_bytes: int = 0):
    """Raises when a client/producer upload breaks the production's quota for its type.

    nova_versao is None for a new logical file, or the version number being created.
    The production row must already be locked (travar_producao).
    """
    from services import credito_alocacao_service, credito_producao_service

    try:
        credito_producao_service.validar_upload(db, producao_id, tipo)
    except credito_alocacao_service.AlocacaoConflito as error:
        raise CotaExcedida(str(error)) from None
    cota = db.scalar(select(ProducaoCotaArquivoModel).where(
        ProducaoCotaArquivoModel.producao_id == producao_id, ProducaoCotaArquivoModel.tipo == tipo,
    ))
    if cota is None:
        return
    rotulo = ROTULOS.get(tipo, tipo)
    if cota.formatos is not None and mime_type not in cota.formatos:
        raise CotaFormato(f"Formato nao permitido pelo contrato para {rotulo}.")
    if cota.max_tamanho_mb is not None and tamanho > cota.max_tamanho_mb * MB:
        raise CotaFormato(f"O contrato permite {rotulo} de ate {cota.max_tamanho_mb} MB por arquivo.")
    if cota.max_duracao_min is not None and mime_type.startswith("audio/") and data is not None:
        # Catalog rework: tracks longer than the contract allows are refused.
        duracao = audio_duracao.segundos(data)
        if duracao is None:
            raise CotaFormato(f"Nao foi possivel conferir a duracao deste audio ({rotulo}); envie um MP3, WAV, FLAC ou M4A valido.")
        if duracao > cota.max_duracao_min * 60 + 1:  # One second of tolerance for encoder padding.
            raise CotaFormato(f"O contrato permite {rotulo} de ate {cota.max_duracao_min} min por faixa.")
    arquivos, total = _uso(db, producao_id).get(tipo, (0, 0))
    if nova_versao is None and cota.max_arquivos is not None and arquivos >= cota.max_arquivos:
        raise CotaExcedida(f"Limite de {cota.max_arquivos} arquivo(s) de {rotulo} do contrato atingido.")
    if nova_versao is not None and cota.max_versoes is not None and nova_versao > cota.max_versoes:
        raise CotaExcedida(f"Limite de {cota.max_versoes} versao(oes) por arquivo de {rotulo} do contrato atingido.")
    if cota.max_total_mb is not None and total + tamanho + extra_storage_bytes > cota.max_total_mb * MB:
        raise CotaExcedida(f"Espaco contratado para {rotulo} ({cota.max_total_mb} MB) esgotado.")
