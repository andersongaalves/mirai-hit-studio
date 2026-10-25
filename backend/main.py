import logging

from core.config import settings
from core.http_security import SecurityMiddleware, cors_origins
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers.ai_chat import router as ai_chat_router
from routers.ai_inbox import router as ai_inbox_router
from routers.audio_tags import router as audio_tags_router
from routers.audit_logs import router as audit_logs_router
from routers.auth import router as auth_router
from routers.beats import router as beats_router
from routers.carteira_creditos import router as carteira_creditos_router
from routers.checkout import router as checkout_router
from routers.client_access import router as client_access_router
from routers.clientes import router as clientes_router
from routers.combos import public_router as combos_public_router
from routers.combos import router as combos_router
from routers.config import router as config_router
from routers.cotas_arquivo import router as cotas_arquivo_router
from routers.credito_alocacao import router as credito_alocacao_router
from routers.dashboard import router as dashboard_router
from routers.financeiro import router as financeiro_router
from routers.newsletter import router as newsletter_router
from routers.orcamentos import router as orcamentos_router
from routers.politicas import router as politicas_router
from routers.portal_cliente import router as portal_cliente_router
from routers.portal_config import router as portal_config_router
from routers.portal_notificacoes import router as portal_notificacoes_router
from routers.uso_infra import router as uso_infra_router
from routers.portal_operacao_admin import router as portal_operacao_admin_router
from routers.portal_produtor import router as portal_produtor_router
from routers.portfolio_envios import router as portfolio_envios_router
from routers.producao import router as producao_router
from routers.producao_etapas import router as producao_etapas_router
from routers.producao_mensagens import router as producao_mensagens_router
from routers.projetos import router as projetos_router
from routers.propostas import router as propostas_router
from routers.repasse_etapa import router as repasse_etapa_router
from routers.servicos import router as servicos_router
from routers.usuarios import router as usuarios_router
from routers.webhooks import router as webhooks_router
from services.startup_service import startup_database
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mirai Hit Studio API", version="1.0.0", docs_url="/docs", redoc_url="/redoc"
)

# CORS
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(settings.ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    # Portals run on another origin and need the server-provided download filename.
    expose_headers=["X-Request-ID", "Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Pydantic's default 'input' can echo passwords and other private values.
    if request.url.path.startswith("/ai/chat/"):
        return JSONResponse({"detail": "Mensagem invalida. Use ate 4000 caracteres."}, status_code=400)
    return JSONResponse({"detail": [{"loc": item["loc"], "msg": "Valor invalido.", "type": item["type"]}
                                    for item in error.errors()]}, status_code=422)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    logger.error("database_error request_id=%s", getattr(request.state, "request_id", None))
    return JSONResponse({"detail": "Persistencia temporariamente indisponivel."}, status_code=503)

# Rotas
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(orcamentos_router)
app.include_router(servicos_router)
app.include_router(projetos_router)
app.include_router(portfolio_envios_router)
app.include_router(audio_tags_router)
app.include_router(carteira_creditos_router)
app.include_router(credito_alocacao_router)
app.include_router(newsletter_router)
app.include_router(usuarios_router)
app.include_router(producao_router)
app.include_router(propostas_router)
app.include_router(clientes_router)
app.include_router(dashboard_router)
app.include_router(audit_logs_router)
app.include_router(webhooks_router)
app.include_router(checkout_router)
app.include_router(client_access_router)
app.include_router(financeiro_router)
app.include_router(ai_chat_router)
app.include_router(ai_inbox_router)
app.include_router(portal_produtor_router)
app.include_router(portal_notificacoes_router)
app.include_router(uso_infra_router)
app.include_router(portal_cliente_router)
app.include_router(portal_operacao_admin_router)
app.include_router(portal_config_router)
app.include_router(producao_mensagens_router)
app.include_router(producao_etapas_router)
app.include_router(repasse_etapa_router)
app.include_router(cotas_arquivo_router)
app.include_router(politicas_router)
app.include_router(combos_router)
app.include_router(combos_public_router)
app.include_router(beats_router)


@app.get("/")
def root():
    return {"status": "online", "api": "Mirai Hit Studio API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# Inicialização
@app.on_event("startup")
async def startup():

    startup_database()
    if not getattr(settings, "AUDIO_TAG_WORKER_ENABLED", True):
        return
    import asyncio

    from core.recursos import memoria_apertada
    from database import SessionLocal
    from services.audio_tag_service import processar_um, registrar_despertador

    # AUD6-S12-002: one preview at a time; idle polling backs off and an upload wakes the loop.
    loop = asyncio.get_running_loop()
    wake = asyncio.Event()
    registrar_despertador(lambda: loop.call_soon_threadsafe(wake.set))

    async def process_previews():
        idle = 5
        while True:
            if memoria_apertada():
                logger.info("audio_tag_worker_waiting_memory")
                await asyncio.sleep(30)
                continue
            try:
                processed = await asyncio.to_thread(processar_um, SessionLocal)
            except Exception:
                logger.warning("audio_tag_worker_unavailable")
                processed = False
            if processed:
                idle = 5
                await asyncio.sleep(1)  # breathing room for API requests between renders
                continue
            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), timeout=idle)
            except asyncio.TimeoutError:
                pass
            idle = min(idle * 2, 120)

    app.state.audio_tag_worker = asyncio.create_task(process_previews())


@app.on_event("shutdown")
async def shutdown():
    import asyncio
    from contextlib import suppress

    worker = getattr(app.state, "audio_tag_worker", None)
    if worker:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
