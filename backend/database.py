from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from collections.abc import Generator
from sqlalchemy.orm import Session


from core.config import settings

"""
Configuração da camada de persistência.

Responsável por:

- Criar a conexão com o banco
- Disponibilizar sessões do SQLAlchemy
- Disponibilizar a Base para os Models
"""

DATABASE_URL = settings.DATABASE_URL

# SQLite precisa do check_same_thread
connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    """
    Dependency utilizada pelo FastAPI.

    Exemplo:

    @router.get("/")
    def listar(db: Session = Depends(get_db)):
        ...
    """

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()

def get_db() -> Generator[Session, None, None]:

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()