from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class UsuarioModel(Base):

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "(role = 'cliente' AND cliente_id IS NOT NULL) OR "
            "(role IN ('admin', 'produtor') AND cliente_id IS NULL)",
            name="ck_usuarios_role_cliente_vinculo",
        ),
        UniqueConstraint("cliente_id", name="uq_usuarios_cliente_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(50), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    is_admin = Column(Boolean, default=True)

    ativo = Column(Boolean, default=True, server_default=true(), nullable=False)

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
