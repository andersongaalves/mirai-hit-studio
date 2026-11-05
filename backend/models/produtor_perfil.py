"""Public producer page: what each producer customises (the rest comes from their work)."""

from database import Base
from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
    text,
)

ABAS_PERFIL = ("portfolio", "beats")


class ProdutorPerfilModel(Base):
    __tablename__ = "produtor_perfis"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_produtor_perfis_slug"),
        CheckConstraint("aba_inicial IN ('portfolio', 'beats')", name="ck_produtor_perfis_aba_inicial"),
        CheckConstraint("cor IS NULL OR length(cor) = 7", name="ck_produtor_perfis_cor"),
    )

    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    slug = Column(String(40), nullable=False)
    headline = Column(String(120), nullable=True)
    bio = Column(String(1500), nullable=True)
    cidade = Column(String(80), nullable=True)
    foto_url = Column(String(500), nullable=True)
    foto_ref = Column(String(500), nullable=True)
    capa_url = Column(String(500), nullable=True)
    capa_ref = Column(String(500), nullable=True)
    cor = Column(String(7), nullable=True)
    links_json = Column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    aba_inicial = Column(String(12), nullable=False, default="portfolio", server_default="portfolio")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# Clean bootstraps stay as private as the Alembic migration.
event.listen(ProdutorPerfilModel.__table__, "after_create", DDL(
    "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(ProdutorPerfilModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
