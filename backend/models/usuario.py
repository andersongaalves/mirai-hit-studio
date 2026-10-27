from database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class UsuarioModel(Base):

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "(role = 'cliente' AND cliente_id IS NOT NULL) OR "
            "(role IN ('admin', 'produtor') AND cliente_id IS NULL)",
            name="ck_usuarios_role_cliente_vinculo",
        ),
        CheckConstraint(
            "auth_version >= 0",
            name="ck_usuarios_auth_version_nao_negativa",
        ),
        UniqueConstraint("cliente_id", name="uq_usuarios_cliente_id"),
        # AUD6-S02-004: only studio accounts keep an e-mail here; clients use their client record.
        CheckConstraint("email IS NULL OR role IN ('admin', 'produtor')", name="ck_usuarios_email_interno"),
    )

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(50), unique=True, nullable=False, index=True)

    # Public name (credits, portals); changes independently of the login username.
    nome_exibicao = Column(String(80), nullable=True)

    password_hash = Column(String(255), nullable=False)

    # AUD6-S02-004: recovery e-mail and one-time reset token for studio accounts.
    email = Column(String(150), nullable=True)
    reset_token_hash = Column(String(64), nullable=True)
    reset_expires_at = Column(DateTime(timezone=True), nullable=True)

    auth_version = Column(Integer, default=0, server_default="0", nullable=False)

    is_admin = Column(Boolean, default=True)

    ativo = Column(Boolean, default=True, server_default=true(), nullable=False)
    is_test = Column(Boolean, default=False, server_default=false(), nullable=False)
    painel_beats = Column(Boolean, default=False, server_default=false(), nullable=False)

    # Producer specialties, comma separated (beatmaker, mixagem, masterizacao).
    especialidades = Column(String(100), nullable=True)
    # Only beatmakers: licensor of the beat contracts. Digits only; admin-only data.
    cpf = Column(String(11), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = Column(String(30), default="admin", nullable=False)

    cliente_id = Column(
        Integer,
        ForeignKey(
            "clientes.id",
            name="fk_usuarios_cliente_id_clientes",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    cliente = relationship("ClienteModel", back_populates="usuario", uselist=False)

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# AUD6-S02-006: "Ana" and "ana" are the same login.
Index("uq_usuarios_username_lower", func.lower(UsuarioModel.username), unique=True)
Index("uq_usuarios_email_lower", func.lower(UsuarioModel.email), unique=True)
Index("uq_usuarios_reset_token_hash", UsuarioModel.reset_token_hash, unique=True)
