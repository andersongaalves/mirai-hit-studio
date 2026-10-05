from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from database import Base


class ClienteAcessoModel(Base):
    __tablename__ = "cliente_acessos"
    __table_args__ = (
        CheckConstraint(
            "origem IN ('admin_invite', 'public_signup')",
            name="ck_cliente_acessos_origem_valida",
        ),
        CheckConstraint(
            "token_finalidade IS NULL OR "
            "token_finalidade IN ('convite', 'verificacao', 'recuperacao')",
            name="ck_cliente_acessos_token_finalidade_valida",
        ),
        CheckConstraint(
            "(token_hash IS NULL AND token_finalidade IS NULL "
            "AND token_expires_at IS NULL) OR "
            "(token_hash IS NOT NULL AND token_finalidade IS NOT NULL "
            "AND token_expires_at IS NOT NULL)",
            name="ck_cliente_acessos_token_completo",
        ),
        CheckConstraint(
            "token_hash IS NULL OR length(token_hash) = 64",
            name="ck_cliente_acessos_token_hash_valido",
        ),
        CheckConstraint(
            "request_fingerprint_hash IS NULL "
            "OR length(request_fingerprint_hash) = 64",
            name="ck_cliente_acessos_fingerprint_valido",
        ),
        CheckConstraint(
            "token_consumed_at IS NULL OR token_revoked_at IS NULL",
            name="ck_cliente_acessos_token_estado_unico",
        ),
        CheckConstraint(
            "activation_attempts >= 0 AND send_count >= 0",
            name="ck_cliente_acessos_contadores_validos",
        ),
        CheckConstraint(
            "(origem = 'admin_invite' AND invited_by_user_id IS NOT NULL) OR "
            "(origem = 'public_signup' AND invited_by_user_id IS NULL)",
            name="ck_cliente_acessos_origem_convite_coerente",
        ),
        CheckConstraint(
            "origem <> 'public_signup' OR privacy_accepted_at IS NOT NULL",
            name="ck_cliente_acessos_privacidade_cadastro",
        ),
        UniqueConstraint("cliente_id", name="uq_cliente_acessos_cliente_id"),
        UniqueConstraint("usuario_id", name="uq_cliente_acessos_usuario_id"),
        UniqueConstraint(
            "email_normalizado",
            name="uq_cliente_acessos_email_normalizado",
        ),
        UniqueConstraint("token_hash", name="uq_cliente_acessos_token_hash"),
        Index("ix_cliente_acessos_token_expires_at", "token_expires_at"),
        Index(
            "ix_cliente_acessos_request_fingerprint_hash",
            "request_fingerprint_hash",
        ),
        Index("ix_cliente_acessos_invited_by_user_id", "invited_by_user_id"),
    )

    id = Column(Integer, primary_key=True)
    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    email_normalizado = Column(String(254), nullable=False)
    origem = Column(String(24), nullable=False)
    token_finalidade = Column(String(24), nullable=True)
    token_hash = Column(String(64), nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    token_consumed_at = Column(DateTime(timezone=True), nullable=True)
    token_revoked_at = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    privacy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    activation_attempts = Column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    send_count = Column(Integer, nullable=False, server_default=text("0"))
    request_fingerprint_hash = Column(String(64), nullable=True)
    invited_by_user_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuthRateLimitModel(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (
        CheckConstraint(
            "action IN ('signup', 'confirmation', 'resend', 'activation', 'recovery')",
            name="ck_auth_rate_limits_action_valida",
        ),
        CheckConstraint(
            "length(key_hash) = 64",
            name="ck_auth_rate_limits_key_hash_valido",
        ),
        CheckConstraint(
            "request_count >= 0",
            name="ck_auth_rate_limits_request_count_valido",
        ),
        CheckConstraint(
            "expires_at > window_started_at",
            name="ck_auth_rate_limits_expiracao_valida",
        ),
        CheckConstraint(
            "blocked_until IS NULL OR blocked_until >= window_started_at",
            name="ck_auth_rate_limits_bloqueio_valido",
        ),
        Index("ix_auth_rate_limits_expires_at", "expires_at"),
    )

    key_hash = Column(String(64), primary_key=True)
    action = Column(String(40), nullable=False)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, nullable=False, server_default=text("0"))
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
