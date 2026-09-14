from sqlalchemy import Boolean, Column, DateTime, Integer, String, true
from sqlalchemy.sql import func

from database import Base


class UsuarioModel(Base):

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(50), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    is_admin = Column(Boolean, default=True)

    ativo = Column(Boolean, default=True, server_default=true(), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = Column(String(30), default="admin", nullable=False)

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
