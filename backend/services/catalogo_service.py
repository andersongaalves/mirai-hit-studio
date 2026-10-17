"""Catalog rework (after 5.10): a service's typed limits drive its file quotas.

The tracks sent by the client and the max minutes per track of a service become the
quota of client materials (5.09), so contracts freeze and enforce them. Other quota
fields (formats, sizes, other file types) stay as the admin set them.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ServicoCotaArquivoModel, ServicoModel
from schemas.servico_estrutura import ler

CAMPOS_COTA = ("max_arquivos", "max_versoes", "max_tamanho_mb", "max_total_mb", "max_duracao_min", "formatos")


def prazo_estimado(etapas) -> int | None:
    """Only publish a complete estimate, never a partial stage total."""
    etapas = list(etapas)
    if not etapas or any(etapa.prazo_dias is None for etapa in etapas):
        return None
    return sum(etapa.prazo_dias for etapa in etapas)


def sincronizar_cotas(db: Session, servico: ServicoModel) -> None:
    """Writes faixas/duracao_min into the service's 'material' quota (no commit)."""
    limites = ler(servico.estrutura_servico)["limites"]
    row = db.scalar(select(ServicoCotaArquivoModel).where(
        ServicoCotaArquivoModel.servico_id == servico.id, ServicoCotaArquivoModel.tipo == "material"))
    if row is None:
        if limites["faixas"] is None and limites["duracao_min"] is None:
            return
        row = ServicoCotaArquivoModel(servico_id=servico.id, tipo="material")
        db.add(row)
    row.max_arquivos = limites["faixas"]
    row.max_duracao_min = limites["duracao_min"]
    if all(getattr(row, campo) is None for campo in CAMPOS_COTA):
        db.delete(row)  # Nothing left to limit: the type has no contractual quota.
    db.flush()
