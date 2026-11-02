"""Admin "Marketing": visits, where they come from and what they turn into.

Three independent blocks (one failing never hides the others):
- Google Analytics 4 (Data API, read-only service account): visitors, sessions, channels,
  sources, campaigns, pages, places, devices, site events and people on the site now.
- Cloudflare (zone analytics): requests, page views and visitors per day, and countries;
  counts every visit, with or without analytics consent.
- The site's own records: leads (with campaign/referrer/landing when known), the commercial
  funnel, confirmed revenue, newsletter sign-ups, AI chat and beat licenses.

Credentials stay on the server (env vars); responses carry only aggregated numbers.
"""
import json
import logging
import os
import time
from base64 import b64decode
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

PERIODOS = (7, 28, 90)
CACHE_SECONDS = 600
TIMEOUT = httpx.Timeout(12.0, connect=5.0)
TOKEN_URL = "https://oauth2.googleapis.com/token"
GA_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GA_API = "https://analyticsdata.googleapis.com/v1beta"
# Events the site sends (frontend/js/analytics.js), in funnel order.
EVENTOS = ("page_view", "view_vertical", "view_service", "listen_portfolio", "begin_briefing", "generate_lead",
           "newsletter_subscribe", "ai_chat_open", "ai_chat_message", "ai_chat_handoff", "begin_checkout",
           "payment_method_selected", "payment_attempt")
_cache = {}
_token = {"value": None, "exp": 0.0}


def _agora():
    return datetime.now(timezone.utc)


def _falha(status, mensagem, **extra):
    return {"status": status, "mensagem": mensagem, **extra}


# ---------- Google Analytics 4 ----------

def _ga_config():
    prop = os.environ.get("GA4_PROPERTY_ID", "").strip().removeprefix("properties/")
    raw = os.environ.get("GA4_SERVICE_ACCOUNT_JSON", "").strip()
    if not prop or not raw:
        return None
    try:
        info = json.loads(raw if raw.startswith("{") else b64decode(raw).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("ga_credentials_invalid") from None
    if not info.get("client_email") or not info.get("private_key"):
        raise RuntimeError("ga_credentials_invalid")
    return prop, info


def _ga_token(info):
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    from jose import jwt

    now = int(time.time())
    assertion = jwt.encode({"iss": info["client_email"], "scope": GA_SCOPE, "aud": TOKEN_URL,
                            "iat": now, "exp": now + 3600}, info["private_key"], algorithm="RS256")
    response = httpx.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                           "assertion": assertion}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    _token.update(value=payload["access_token"], exp=time.time() + int(payload.get("expires_in", 3600)))
    return _token["value"]


def _ga_post(path, body, token):
    response = httpx.post(f"{GA_API}/{path}", json=body, headers={"Authorization": f"Bearer {token}"},
                          timeout=TIMEOUT)
    if response.status_code == 403:
        raise PermissionError("ga_forbidden")
    response.raise_for_status()
    return response.json()


def _linhas(report):
    dims = [item["name"] for item in report.get("dimensionHeaders", [])]
    mets = [item["name"] for item in report.get("metricHeaders", [])]
    rows = []
    for row in report.get("rows", []) or []:
        item = {name: value.get("value") for name, value in zip(dims, row.get("dimensionValues", []))}
        for name, value in zip(mets, row.get("metricValues", [])):
            try:
                number = float(value.get("value") or 0)
            except ValueError:
                number = 0.0
            item[name] = int(number) if number.is_integer() else number
        rows.append(item)
    return rows


def _faixa(dias, offset=0):
    fim = date.today() - timedelta(days=offset)
    return {"startDate": (fim - timedelta(days=dias - 1)).isoformat(), "endDate": fim.isoformat()}


def _ga_relatorio(dim, metrics, dias, *, limit=10, order=None, filtro=None):
    body = {"dateRanges": [_faixa(dias)], "metrics": [{"name": name} for name in metrics], "limit": limit}
    if dim:
        body["dimensions"] = [{"name": dim}]
        body["orderBys"] = [order or {"metric": {"metricName": metrics[0]}, "desc": True}]
    if filtro:
        body["dimensionFilter"] = filtro
    return body


def _google_analytics(dias):
    try:
        config = _ga_config()
    except RuntimeError:
        return _falha("erro", "A credencial do Google Analytics no Render não é um JSON de conta de serviço válido.")
    if config is None:
        return _falha("nao_configurado", "Conecte o Google Analytics para ver visitantes, origens e campanhas.",
                      medicao="G-W4GLJXPRDM")
    prop, info = config
    try:
        token = _ga_token(info)
        totais = {"dateRanges": [_faixa(dias), _faixa(dias, offset=dias)],
                  "metrics": [{"name": name} for name in ("activeUsers", "newUsers", "sessions", "screenPageViews",
                                                          "engagementRate", "averageSessionDuration")]}
        serie = {"dateRanges": [_faixa(dias)], "dimensions": [{"name": "date"}],
                 "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
                 "orderBys": [{"dimension": {"dimensionName": "date"}}], "limit": 100}
        lote1 = _ga_post(f"properties/{prop}:batchRunReports", {"requests": [
            totais, serie,
            _ga_relatorio("sessionDefaultChannelGroup", ["sessions", "activeUsers"], dias),
            _ga_relatorio("sessionSourceMedium", ["sessions", "activeUsers"], dias),
            _ga_relatorio("pagePath", ["screenPageViews", "activeUsers"], dias),
        ]}, token)["reports"]
        lote2 = _ga_post(f"properties/{prop}:batchRunReports", {"requests": [
            _ga_relatorio("country", ["activeUsers"], dias),
            _ga_relatorio("city", ["activeUsers"], dias),
            _ga_relatorio("deviceCategory", ["activeUsers"], dias, limit=5),
            _ga_relatorio("eventName", ["eventCount"], dias, limit=20, filtro={"filter": {
                "fieldName": "eventName", "inListFilter": {"values": list(EVENTOS)}}}),
            _ga_relatorio("sessionCampaignName", ["sessions", "activeUsers"], dias),
        ]}, token)["reports"]
        try:
            agora = _linhas(_ga_post(f"properties/{prop}:runRealtimeReport",
                                     {"metrics": [{"name": "activeUsers"}]}, token))
            no_site = agora[0]["activeUsers"] if agora else 0
        except Exception:  # noqa: BLE001 - realtime is a bonus.
            no_site = None
    except PermissionError:
        return _falha("erro", "A conta de serviço não tem acesso à propriedade do GA4. Adicione o e-mail dela como Leitor.")
    except Exception:  # noqa: BLE001 - provider errors surface as unavailable.
        logger.warning("marketing_ga_unavailable")
        return _falha("indisponivel", "O Google Analytics não respondeu agora. Tente atualizar em alguns minutos.")
    linhas_totais = _linhas(lote1[0])
    # With two date ranges GA adds a "dateRange" dimension: date_range_0 is the current period.
    atual = next((row for row in linhas_totais if row.get("dateRange") in (None, "date_range_0")), {})
    anterior = next((row for row in linhas_totais if row.get("dateRange") == "date_range_1"), {})
    metricas = ("activeUsers", "newUsers", "sessions", "screenPageViews", "engagementRate", "averageSessionDuration")
    eventos = {row["eventName"]: row["eventCount"] for row in _linhas(lote2[3])}
    return {
        "status": "ok",
        "agora_no_site": no_site,
        "totais": {name: atual.get(name, 0) for name in metricas},
        "anterior": {name: anterior.get(name, 0) for name in metricas},
        "serie": [{"data": f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:]}", "visitantes": row["activeUsers"],
                   "sessoes": row["sessions"]} for row in _linhas(lote1[1])],
        "canais": [{"nome": row["sessionDefaultChannelGroup"], "sessoes": row["sessions"],
                    "visitantes": row["activeUsers"]} for row in _linhas(lote1[2])],
        "origens": [{"nome": row["sessionSourceMedium"], "sessoes": row["sessions"],
                     "visitantes": row["activeUsers"]} for row in _linhas(lote1[3])],
        "paginas": [{"nome": row["pagePath"], "visualizacoes": row["screenPageViews"],
                     "visitantes": row["activeUsers"]} for row in _linhas(lote1[4])],
        "paises": [{"nome": row["country"], "visitantes": row["activeUsers"]} for row in _linhas(lote2[0])],
        "cidades": [{"nome": row["city"], "visitantes": row["activeUsers"]} for row in _linhas(lote2[1])],
        "dispositivos": [{"nome": row["deviceCategory"], "visitantes": row["activeUsers"]} for row in _linhas(lote2[2])],
        "eventos": [{"nome": name, "quantidade": eventos.get(name, 0)} for name in EVENTOS],
        "campanhas": [{"nome": row["sessionCampaignName"], "sessoes": row["sessions"], "visitantes": row["activeUsers"]}
                      for row in _linhas(lote2[4])],
    }


# ---------- Cloudflare ----------

CF_QUERY = """query Marketing($zone: string!, $since: Date!) {
  viewer { zones(filter: {zoneTag: $zone}) {
    httpRequests1dGroups(limit: 100, filter: {date_geq: $since}, orderBy: [date_ASC]) {
      dimensions { date }
      sum { requests pageViews threats countryMap { clientCountryName requests } }
      uniq { uniques }
    }
  } }
}"""


def _cloudflare(dias):
    from services.uso_infra_service import _cloudflare_graphql, _zone_id

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        return _falha("nao_configurado", "Defina CLOUDFLARE_API_TOKEN (com Zone Analytics: Read) no Render.")
    try:
        zone = _zone_id(token)
        if zone is None:
            raise RuntimeError("zone_not_found")
        since = (date.today() - timedelta(days=dias - 1)).isoformat()
        groups = _cloudflare_graphql(CF_QUERY, {"zone": zone, "since": since}, token)["viewer"]["zones"][0]["httpRequests1dGroups"]
    except Exception:  # noqa: BLE001
        logger.warning("marketing_cloudflare_unavailable")
        return _falha("indisponivel", "A Cloudflare não respondeu agora (confira a permissão Zone Analytics).")
    paises = Counter()
    serie = []
    for group in groups:
        for item in group["sum"].get("countryMap") or []:
            paises[item["clientCountryName"]] += int(item["requests"] or 0)
        serie.append({"data": group["dimensions"]["date"], "visitantes": int(group["uniq"]["uniques"] or 0),
                      "paginas": int(group["sum"]["pageViews"] or 0), "requisicoes": int(group["sum"]["requests"] or 0)})
    return {
        "status": "ok",
        "totais": {
            "visitantes": sum(item["visitantes"] for item in serie),
            "paginas": sum(item["paginas"] for item in serie),
            "requisicoes": sum(item["requisicoes"] for item in serie),
            "ameacas": sum(int(group["sum"]["threats"] or 0) for group in groups),
        },
        "serie": serie,
        "paises": [{"nome": code, "requisicoes": count} for code, count in paises.most_common(10)],
    }


# ---------- The site's own records ----------

def _origem_lead(origem):
    """A readable source for a lead: campaign/source when tagged, else the referring site."""
    if not origem:
        return "Sem informação (anterior ao registro)"
    source = (origem.get("utm_source") or "").strip()
    medium = (origem.get("utm_medium") or "").strip()
    if source:
        return f"{source} / {medium}" if medium else source
    referrer = (origem.get("referrer") or "").lower().removeprefix("www.")
    if not referrer:
        return "Direto"
    for name, hosts in (("Google (busca)", ("google.",)), ("Instagram", ("instagram.", "l.instagram.")),
                        ("Facebook", ("facebook.", "fb.", "m.facebook.")), ("YouTube", ("youtube.", "youtu.be")),
                        ("TikTok", ("tiktok.",)), ("WhatsApp", ("whatsapp.", "wa.me")), ("Bing", ("bing.",)),
                        ("X / Twitter", ("t.co", "twitter.", "x.com"))):
        if any(referrer.startswith(host) or f".{host}" in referrer for host in hosts):
            return name
    if referrer.endswith("miraihitstudio.com.br"):
        return "Direto"
    return referrer


def _contagem(items, limite=10):
    return [{"nome": name, "quantidade": count} for name, count in Counter(items).most_common(limite)]


def _site(db, dias):
    from models import (
        AIConversationModel,
        BeatLicencaModel,
        NewsletterModel,
        OrcamentoModel,
        PagamentoModel,
        PropostaModel,
    )
    from sqlalchemy import func, select

    desde = _agora() - timedelta(days=dias)
    antes = desde - timedelta(days=dias)
    real = OrcamentoModel.is_test.is_(False)
    leads = db.execute(select(OrcamentoModel.data_solicitacao, OrcamentoModel.servico, OrcamentoModel.status,
                              OrcamentoModel.origem_marketing)
                       .where(real, OrcamentoModel.data_solicitacao >= desde)).all()
    leads_antes = db.scalar(select(func.count()).select_from(OrcamentoModel).where(
        real, OrcamentoModel.data_solicitacao >= antes, OrcamentoModel.data_solicitacao < desde)) or 0
    por_dia = Counter(row.data_solicitacao.date().isoformat() for row in leads if row.data_solicitacao)
    hoje = date.today()
    serie = [{"data": (hoje - timedelta(days=offset)).isoformat(),
              "leads": por_dia.get((hoje - timedelta(days=offset)).isoformat(), 0)} for offset in range(dias - 1, -1, -1)]
    campanhas = [row.origem_marketing.get("utm_campaign") for row in leads
                 if row.origem_marketing and row.origem_marketing.get("utm_campaign")]
    entradas = [row.origem_marketing.get("landing") for row in leads
                if row.origem_marketing and row.origem_marketing.get("landing")]

    def _count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    enviadas = _count(PropostaModel, PropostaModel.enviada_em >= desde)
    aceitas = _count(PropostaModel, PropostaModel.aprovada_em >= desde)
    pagos = db.execute(select(func.count(), func.coalesce(func.sum(PagamentoModel.valor), 0)).where(
        PagamentoModel.status == "aprovado", PagamentoModel.aprovado_em >= desde)).one()
    newsletter = db.execute(select(NewsletterModel.origem).where(NewsletterModel.data_cadastro >= desde)).scalars().all()
    ativos = _count(NewsletterModel, NewsletterModel.ativo.is_(True))
    conversas = db.execute(select(AIConversationModel.channel, AIConversationModel.handoff_reason)
                           .where(AIConversationModel.created_at >= desde)).all()
    licencas = db.execute(select(BeatLicencaModel.status).where(BeatLicencaModel.created_at >= desde)).scalars().all()
    return {
        "status": "ok",
        "leads": {
            "total": len(leads),
            "anterior": leads_antes,
            "serie": serie,
            "por_origem": _contagem(_origem_lead(row.origem_marketing) for row in leads),
            "por_servico": _contagem(row.servico for row in leads),
            "por_campanha": _contagem(campanhas),
            "paginas_de_entrada": _contagem(entradas),
            "com_origem": sum(1 for row in leads if row.origem_marketing),
        },
        "funil": [
            {"etapa": "Pedidos de orçamento", "quantidade": len(leads)},
            {"etapa": "Propostas enviadas", "quantidade": enviadas},
            {"etapa": "Propostas aceitas", "quantidade": aceitas},
            {"etapa": "Pagamentos confirmados", "quantidade": int(pagos[0] or 0)},
        ],
        "receita_confirmada": float(pagos[1] or 0),
        "newsletter": {"novos": len(newsletter), "ativos": ativos, "por_origem": _contagem(newsletter)},
        "chat": {"conversas": len(conversas), "encaminhadas": sum(1 for row in conversas if row.handoff_reason),
                 "por_canal": _contagem("Site" if row.channel == "site" else "E-mail" for row in conversas)},
        "beats": {"licencas": len(licencas), "por_status": _contagem(licencas)},
    }


def carregar(db, dias=28, *, atualizar=False):
    dias = dias if dias in PERIODOS else 28
    cached = _cache.get(dias)
    if not atualizar and cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        site = _site(db, dias)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("marketing_site_unavailable")
        site = _falha("indisponivel", "Os dados do site não carregaram agora.")
    data = {"dias": dias, "atualizado_em": _agora().isoformat(), "google_analytics": _google_analytics(dias),
            "cloudflare": _cloudflare(dias), "site": site}
    _cache[dias] = (time.monotonic(), data)
    return data


def host_de(url):
    """Referrer host only (no path or query), for the lead's origin."""
    try:
        return (urlsplit(url).hostname or "")[:120] or None
    except ValueError:
        return None
