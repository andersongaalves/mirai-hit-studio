"""Mirai Hit Labs admin panel (labs.miraihitstudio.com.br/admin) and the public pieces it feeds:
the update feed read by the plugins, the store banner and the coupon check."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core import rate_limit
from core.dependencies import require_admin
from database import get_db
from schemas.labs_admin import (
    BannerPayload,
    CortesiaEmail,
    CupomPayload,
    CupomValidacao,
    OrdemPayload,
    Reembolso,
    VersaoPayload,
)
from services import labs_admin_service as service

router = APIRouter(tags=["Mirai Hit Labs (admin)"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]
Slug = Annotated[str, Path(max_length=60)]
Search = Annotated[str | None, Query(max_length=120)]
FEED_CACHE = {"Cache-Control": "public, max-age=300"}


def _limited(request: Request, bucket: str, limit: int, window: int):
    client = request.client.host if request.client else "unknown"
    try:
        allowed, _ = rate_limit.allow_request(f"{bucket}:{client}", limit, window)
    except Exception:  # noqa: BLE001 - the limiter fails open, like the other public routes
        allowed = True
    if not allowed:
        raise HTTPException(429, "Muitas tentativas; aguarde alguns minutos.")


# ---------------------------------------------------------------- public


@router.get("/labs/atualizacoes")
def atualizacoes(db: Db):
    """Latest stable version of every published plugin (update checker of plugins and apps)."""
    return JSONResponse(jsonable_encoder(service.publico_atualizacoes(db)), headers=FEED_CACHE)


@router.get("/labs/plugins/{slug}/atualizacao")
def atualizacao(slug: Slug, db: Db, canal: Literal["estavel", "beta"] = "estavel"):
    return JSONResponse(jsonable_encoder(service.publico_atualizacao(db, slug, canal)), headers=FEED_CACHE)


@router.get("/labs/conteudo")
def conteudo_publico(db: Db):
    return JSONResponse(jsonable_encoder(service.conteudo_publico(db)), headers={"Cache-Control": "public, max-age=60"})


@router.post("/labs/cupons/validar")
def validar_cupom(payload: CupomValidacao, request: Request, db: Db):
    _limited(request, "labs-cupom", 20, 300)
    return JSONResponse(service.validar_cupom_publico(db, payload.codigo, payload.plugin),
                        headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- admin: overview and orders


@router.get("/admin/labs/resumo")
def resumo(db: Db, user: Admin, dias: Annotated[int, Query(ge=1, le=365)] = 30):
    return service.resumo(db, dias)


@router.get("/admin/labs/pedidos")
def pedidos(db: Db, user: Admin, q: Search = None,
            moeda: Literal["brl", "usd"] | None = None,
            status: Annotated[str | None, Query(max_length=20)] = None):
    return service.pedidos(db, q, moeda, status)


@router.post("/admin/labs/pedidos/stripe/{pedido_id}/reembolsar")
def reembolsar(pedido_id: int, payload: Reembolso, request: Request, db: Db, user: Admin):
    return service.reembolsar_stripe(db, pedido_id, payload.motivo, user, getattr(request.state, "request_id", None))


# ---------------------------------------------------------------- admin: customers and licenses


@router.get("/admin/labs/clientes")
def clientes(db: Db, user: Admin, q: Search = None):
    return service.clientes(db, q)


@router.get("/admin/labs/clientes/{cliente_id}")
def cliente(cliente_id: int, db: Db, user: Admin):
    return service.cliente_detalhe(db, cliente_id)


@router.get("/admin/labs/licencas")
def licencas(db: Db, user: Admin, q: Search = None,
             status: Literal["reservada", "ativa", "cancelada", "revogada"] | None = None,
             plugin_id: Annotated[int | None, Query(gt=0)] = None,
             origem: Literal["compra", "gratuito", "cortesia", "stripe"] | None = None):
    return service.licencas(db, q, status, plugin_id, origem)


@router.post("/admin/labs/licencas/{licenca_id}/reativar")
def reativar(licenca_id: int, db: Db, user: Admin):
    return service.reativar(db, licenca_id, user)


@router.post("/admin/labs/plugins/{plugin_id}/cortesias/email", status_code=201)
def cortesia_email(plugin_id: int, payload: CortesiaEmail, db: Db, user: Admin):
    return service.cortesia_por_email(db, plugin_id, payload.email, user)


# ---------------------------------------------------------------- admin: releases


@router.get("/admin/labs/plugins/{plugin_id}/versoes")
def versoes(plugin_id: int, db: Db, user: Admin):
    return service.versoes(db, plugin_id)


@router.post("/admin/labs/plugins/{plugin_id}/versoes", status_code=201)
def criar_versao(plugin_id: int, payload: VersaoPayload, db: Db, user: Admin):
    return service.criar_versao(db, plugin_id, payload, user)


@router.put("/admin/labs/versoes/{versao_id}")
def editar_versao(versao_id: int, payload: VersaoPayload, db: Db, user: Admin):
    return service.editar_versao(db, versao_id, payload, user)


@router.delete("/admin/labs/versoes/{versao_id}")
def remover_versao(versao_id: int, db: Db, user: Admin):
    return service.remover_versao(db, versao_id, user)


# ---------------------------------------------------------------- admin: coupons


@router.get("/admin/labs/cupons")
def cupons(db: Db, user: Admin):
    return service.cupons(db)


@router.post("/admin/labs/cupons", status_code=201)
def criar_cupom(payload: CupomPayload, db: Db, user: Admin):
    return service.criar_cupom(db, payload, user)


@router.put("/admin/labs/cupons/{cupom_id}")
def editar_cupom(cupom_id: int, payload: CupomPayload, db: Db, user: Admin):
    return service.editar_cupom(db, cupom_id, payload, user)


@router.delete("/admin/labs/cupons/{cupom_id}")
def remover_cupom(cupom_id: int, db: Db, user: Admin):
    return service.remover_cupom(db, cupom_id, user)


# ---------------------------------------------------------------- admin: store


@router.get("/admin/labs/conteudo")
def conteudo(db: Db, user: Admin):
    return service.conteudo(db)


@router.put("/admin/labs/conteudo/banner")
def salvar_banner(payload: BannerPayload, db: Db, user: Admin):
    return service.salvar_banner(db, payload, user)


@router.put("/admin/labs/ordem")
def ordenar(payload: OrdemPayload, db: Db, user: Admin):
    return service.ordenar(db, payload, user)
