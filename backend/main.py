from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from core.config import settings

from routers.auth import router as auth_router
from routers.config import router as config_router
from routers.orcamentos import router as orcamentos_router
from routers.projetos import router as projetos_router
from routers.servicos import router as servicos_router
from services.startup_service import startup_database
from routers.newsletter import router as newsletter_router

# Criação das tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Mirai Hit Studio API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(orcamentos_router)
app.include_router(servicos_router)
app.include_router(projetos_router)
app.include_router(newsletter_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "api": "Mirai Hit Studio API",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

# Inicialização
@app.on_event("startup")
async def startup():

    startup_database()