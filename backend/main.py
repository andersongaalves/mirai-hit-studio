from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.http_security import SecurityMiddleware, cors_origins
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from routers.auth import router as auth_router
from routers.config import router as config_router
from routers.orcamentos import router as orcamentos_router
from routers.projetos import router as projetos_router
from routers.servicos import router as servicos_router
from services.startup_service import startup_database
from routers.newsletter import router as newsletter_router
from routers.usuarios import router as usuarios_router
from routers.producao import router as producao_router
from routers.propostas import router as propostas_router
from routers.clientes import router as clientes_router
from routers.dashboard import router as dashboard_router

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
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Pydantic's default 'input' can echo passwords and other private values.
    return JSONResponse({"detail": [{"loc": item["loc"], "msg": "Valor invalido.", "type": item["type"]}
                                    for item in error.errors()]}, status_code=422)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    return JSONResponse({"detail": "Persistencia temporariamente indisponivel."}, status_code=503)

# Rotas
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(orcamentos_router)
app.include_router(servicos_router)
app.include_router(projetos_router)
app.include_router(newsletter_router)
app.include_router(usuarios_router)
app.include_router(producao_router)
app.include_router(propostas_router)
app.include_router(clientes_router)
app.include_router(dashboard_router)


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
