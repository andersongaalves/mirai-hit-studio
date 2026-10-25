"""Admin "Uso da infraestrutura": memory, Supabase, Cloudinary and Cloudflare usage.

Every block fails on its own: a provider that is down or not configured never hides the
others. Credentials stay on the server; responses carry only numbers and short status text.
"""
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from core import recursos
from core.config import settings
from sqlalchemy import text

logger = logging.getLogger(__name__)

CACHE_SECONDS = 300
TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_cache = {"at": 0.0, "data": None}


def _limite_mb(nome, padrao):
    # Free-plan defaults; set USO_LIMITE_* when the plan changes.
    try:
        return float(os.environ.get(nome, padrao))
    except ValueError:
        return float(padrao)


def _secret(value):
    getter = getattr(value, "get_secret_value", None)
    return getter() if getter else (value or "")


def _bloco(nome, **dados):
    return {"nome": nome, "status": "ok", **dados}


def _falha(nome, status, mensagem):
    return {"nome": nome, "status": status, "mensagem": mensagem}


def _memoria():
    dados = recursos.memoria()
    if not dados["usada_bytes"]:
        return _falha("Servidor (Render)", "indisponivel", "A plataforma não informou o uso de memória.")
    return _bloco("Servidor (Render)", itens=[{
        "rotulo": "Memória em uso agora",
        "usado": dados["usada_bytes"],
        "limite": dados["limite_bytes"],
        "unidade": "bytes",
    }])


def _supabase(db):
    if db.get_bind().dialect.name != "postgresql":
        return _falha("Supabase", "nao_configurado", "Disponível apenas com o banco PostgreSQL.")
    itens = []
    try:
        size = db.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
        itens.append({"rotulo": "Banco de dados", "usado": int(size),
                      "limite": int(_limite_mb("USO_LIMITE_SUPABASE_DB_MB", 500) * 1024 * 1024), "unidade": "bytes"})
    except Exception:
        db.rollback()
        logger.warning("usage_supabase_database_unavailable")
    try:
        rows = db.execute(text(
            "SELECT bucket_id, count(*), coalesce(sum((metadata->>'size')::bigint), 0) "
            "FROM storage.objects GROUP BY bucket_id ORDER BY bucket_id"
        )).all()
        total = sum(int(row[2]) for row in rows)
        itens.append({"rotulo": "Arquivos (Storage)", "usado": total,
                      "limite": int(_limite_mb("USO_LIMITE_SUPABASE_STORAGE_MB", 1024) * 1024 * 1024),
                      "unidade": "bytes", "detalhe": f"{sum(int(row[1]) for row in rows)} arquivos em {len(rows)} buckets"})
    except Exception:
        db.rollback()
        logger.warning("usage_supabase_storage_unavailable")
    if not itens:
        return _falha("Supabase", "indisponivel", "Não foi possível ler o uso do Supabase agora.")
    return _bloco("Supabase", itens=itens)


def _cloudinary():
    cloud = getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
    key = getattr(settings, "CLOUDINARY_API_KEY", "")
    secret = _secret(getattr(settings, "CLOUDINARY_API_SECRET", ""))
    if not (cloud and key and secret):
        return _falha("Cloudinary", "nao_configurado", "Credenciais do Cloudinary não configuradas.")
    try:
        response = httpx.get(f"https://api.cloudinary.com/v1_1/{cloud}/usage", auth=(key, secret), timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.warning("usage_cloudinary_unavailable")
        return _falha("Cloudinary", "indisponivel", "O Cloudinary não respondeu agora.")
    credits = data.get("credits") or {}
    itens = [{"rotulo": "Créditos do mês", "usado": credits.get("usage"), "limite": credits.get("limit"), "unidade": "creditos"}]
    for chave, rotulo in (("storage", "Armazenamento"), ("bandwidth", "Banda"), ("transformations", "Transformações")):
        bloco = data.get(chave) or {}
        if bloco.get("usage") is not None:
            itens.append({"rotulo": rotulo, "usado": bloco.get("usage"), "limite": bloco.get("limit"),
                          "unidade": "bytes" if chave != "transformations" else "quantidade"})
    return _bloco("Cloudinary", plano=data.get("plan"), itens=itens)


def _cloudflare_graphql(query, variables, token):
    response = httpx.post("https://api.cloudflare.com/client/v4/graphql", json={"query": query, "variables": variables},
                          headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError("cloudflare_graphql_error")
    return payload["data"]


R2_QUERY = """query R2($account: string!, $since: Time!, $until: Time!) {
  viewer { accounts(filter: {accountTag: $account}) {
    r2StorageAdaptiveGroups(limit: 100, filter: {datetime_geq: $since, datetime_leq: $until}, orderBy: [datetime_DESC]) {
      max { objectCount payloadSize metadataSize }
      dimensions { bucketName datetime }
    }
  } }
}"""

ZONE_QUERY = """query Trafego($zone: string!, $since: Date!) {
  viewer { zones(filter: {zoneTag: $zone}) {
    httpRequests1dGroups(limit: 31, filter: {date_geq: $since}) {
      sum { requests bytes cachedRequests threats pageViews }
      uniq { uniques }
    }
  } }
}"""


def _zone_id(token):
    configured = os.environ.get("CLOUDFLARE_ZONE_ID", "").strip()
    if configured:
        return configured
    domain = os.environ.get("CLOUDFLARE_ZONE_NAME", "miraihitstudio.com.br")
    response = httpx.get("https://api.cloudflare.com/client/v4/zones", params={"name": domain},
                         headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    response.raise_for_status()
    result = response.json().get("result") or []
    return result[0]["id"] if result else None


def _cloudflare():
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip() or getattr(settings, "R2_ACCOUNT_ID", "")
    if not token or not account:
        return _falha("Cloudflare", "nao_configurado", "Defina CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID no Render.")
    itens, avisos = [], []
    agora = datetime.now(timezone.utc)
    try:
        data = _cloudflare_graphql(R2_QUERY, {"account": account, "since": (agora - timedelta(days=2)).isoformat(),
                                              "until": agora.isoformat()}, token)
        latest = {}
        for group in data["viewer"]["accounts"][0]["r2StorageAdaptiveGroups"]:
            latest.setdefault(group["dimensions"]["bucketName"], group["max"])
        size = sum(int(item.get("payloadSize") or 0) + int(item.get("metadataSize") or 0) for item in latest.values())
        objects = sum(int(item.get("objectCount") or 0) for item in latest.values())
        itens.append({"rotulo": "R2 (arquivos privados)", "usado": size,
                      "limite": int(_limite_mb("USO_LIMITE_R2_MB", 10 * 1024) * 1024 * 1024), "unidade": "bytes",
                      "detalhe": f"{objects} arquivos em {len(latest)} buckets"})
    except Exception:
        logger.warning("usage_cloudflare_r2_unavailable")
        avisos.append("Uso do R2 indisponível agora.")
    try:
        zone = _zone_id(token)
        if zone is None:
            raise RuntimeError("zone_not_found")
        since = (date.today() - timedelta(days=30)).isoformat()
        data = _cloudflare_graphql(ZONE_QUERY, {"zone": zone, "since": since}, token)
        groups = data["viewer"]["zones"][0]["httpRequests1dGroups"]
        def total(field):
            return sum(int(group["sum"].get(field) or 0) for group in groups)
        itens.append({"rotulo": "Requisições do site (30 dias)", "usado": total("requests"), "unidade": "quantidade",
                      "detalhe": f"{total('pageViews')} páginas vistas · {total('threats')} ameaças bloqueadas"})
        itens.append({"rotulo": "Tráfego do site (30 dias)", "usado": total("bytes"), "unidade": "bytes",
                      "detalhe": f"{total('cachedRequests')} respostas servidas do cache"})
    except Exception:
        logger.warning("usage_cloudflare_zone_unavailable")
        avisos.append("Tráfego do site indisponível (confira a permissão de Zone Analytics ou defina CLOUDFLARE_ZONE_ID).")
    if not itens:
        return _falha("Cloudflare", "indisponivel", " ".join(avisos))
    return _bloco("Cloudflare", itens=itens, avisos=avisos)


def carregar(db, *, atualizar=False):
    if not atualizar and _cache["data"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    blocos = []
    for funcao in (_memoria, lambda: _supabase(db), _cloudinary, _cloudflare):
        try:
            blocos.append(funcao())
        except Exception:
            logger.warning("usage_block_failed")
            blocos.append(_falha("Indisponível", "indisponivel", "Falha inesperada ao ler este bloco."))
    data = {"atualizado_em": datetime.now(timezone.utc), "blocos": blocos}
    _cache.update(at=time.monotonic(), data=data)
    return data
