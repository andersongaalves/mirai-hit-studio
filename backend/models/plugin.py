"""Mirai Hit Labs: audio plugins sold through the studio's checkout.

A plugin has one installer per system (Windows/macOS); buying it grants a personal license
with a key and access to every current installer. Paid licenses come from a proposal like
a catalog beat (orcamento -> proposta -> cobranca); free plugins are granted directly.
"""
from sqlalchemy import (
    DDL,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import relationship

from database import Base

PLUGIN_STATUS = ("rascunho", "publicado", "arquivado")
PLUGIN_SISTEMAS = ("windows", "macos")
LICENCA_STATUS = ("reservada", "ativa", "cancelada", "revogada")


class PluginModel(Base):
    __tablename__ = "plugins"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_plugins_slug"),
        CheckConstraint("status IN ('rascunho','publicado','arquivado')", name="ck_plugins_status"),
        CheckConstraint("preco >= 0", name="ck_plugins_preco"),
        CheckConstraint(
            "preco_promocional IS NULL OR (preco_promocional >= 0 AND preco_promocional < preco)",
            name="ck_plugins_preco_promocional",
        ),
    )

    id = Column(Integer, primary_key=True)
    slug = Column(String(60), nullable=False)
    nome = Column(String(80), nullable=False)
    tagline = Column(String(160), nullable=True)
    descricao = Column(Text, nullable=True)
    categoria = Column(String(40), nullable=True)
    versao = Column(String(20), nullable=True)
    formatos_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    recursos_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    requisitos = Column(Text, nullable=True)
    # English texts (the store is in English by default; empty falls back to Portuguese)
    tagline_en = Column(String(160), nullable=True)
    descricao_en = Column(Text, nullable=True)
    categoria_en = Column(String(40), nullable=True)
    recursos_en_json = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    requisitos_en = Column(Text, nullable=True)
    preco = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    preco_promocional = Column(Numeric(12, 2), nullable=True)
    capa_url = Column(String(500), nullable=True)
    capa_ref = Column(String(500), nullable=True)
    video_url = Column(String(300), nullable=True)
    status = Column(String(12), nullable=False, default="rascunho", server_default="rascunho")
    destaque = Column(Boolean, nullable=False, default=False, server_default="false")
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
    publicado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    arquivos = relationship(
        "PluginArquivoModel",
        back_populates="plugin",
        order_by="PluginArquivoModel.sistema",
        cascade="all, delete-orphan",
    )


class PluginArquivoModel(Base):
    """The current installer of a plugin for one system (uploaded file or external link)."""

    __tablename__ = "plugin_arquivos"
    __table_args__ = (
        UniqueConstraint("plugin_id", "sistema", name="uq_plugin_arquivos_plugin_sistema"),
        Index("uq_plugin_arquivos_ref", "arquivo_ref", unique=True),
        CheckConstraint("sistema IN ('windows','macos')", name="ck_plugin_arquivos_sistema"),
        CheckConstraint(
            "(arquivo_ref IS NOT NULL AND sha256 IS NOT NULL AND link_externo IS NULL) OR "
            "(arquivo_ref IS NULL AND sha256 IS NULL AND link_externo IS NOT NULL)",
            name="ck_plugin_arquivos_origem",
        ),
    )

    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    sistema = Column(String(10), nullable=False)
    versao = Column(String(20), nullable=True)
    nome_arquivo = Column(String(160), nullable=True)
    arquivo_ref = Column(String(500), nullable=True)
    sha256 = Column(String(64), nullable=True)
    mime = Column(String(100), nullable=True)
    tamanho_bytes = Column(BigInteger, nullable=True)
    link_externo = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plugin = relationship("PluginModel", back_populates="arquivos")


class PluginLicencaModel(Base):
    __tablename__ = "plugin_licencas"
    __table_args__ = (
        UniqueConstraint("chave", name="uq_plugin_licencas_chave"),
        UniqueConstraint("proposta_id", "plugin_id", name="uq_plugin_licencas_proposta_plugin"),
        CheckConstraint(
            "status IN ('reservada','ativa','cancelada','revogada')", name="ck_plugin_licencas_status"
        ),
        CheckConstraint("valor >= 0", name="ck_plugin_licencas_valor"),
        CheckConstraint(
            "origem IN ('compra','gratuito','cortesia','stripe')", name="ck_plugin_licencas_origem"
        ),
        CheckConstraint(
            "(origem = 'compra' AND proposta_id IS NOT NULL) OR (origem <> 'compra' AND proposta_id IS NULL)",
            name="ck_plugin_licencas_proposta",
        ),
        # One free or courtesy license per client and plugin; purchases are tracked per proposal
        # (studio checkout) or per Stripe order (English store).
        Index(
            "uq_plugin_licencas_cliente_sem_compra",
            "plugin_id",
            "cliente_id",
            unique=True,
            postgresql_where=text("origem NOT IN ('compra','stripe')"),
            sqlite_where=text("origem NOT IN ('compra','stripe')"),
        ),
    )

    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    proposta_id = Column(Integer, ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=True, index=True)
    origem = Column(String(10), nullable=False, default="compra", server_default="compra")
    status = Column(String(10), nullable=False, default="reservada", server_default="reservada")
    chave = Column(String(32), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    ativada_em = Column(DateTime(timezone=True), nullable=True)
    encerrada_em = Column(DateTime(timezone=True), nullable=True)
    motivo = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    plugin = relationship("PluginModel")


PEDIDO_STRIPE_STATUS = ("aberto", "pago", "expirado", "reembolsado", "contestado")


class PluginPedidoStripeModel(Base):
    """An international purchase on the English store: one Stripe Checkout session (USD).

    The license is reserved when the order opens and becomes active when Stripe confirms
    the payment; a refund or a dispute suspends it, like the studio checkout does."""

    __tablename__ = "plugin_pedidos_stripe"
    __table_args__ = (
        UniqueConstraint("licenca_id", name="uq_plugin_pedidos_stripe_licenca"),
        UniqueConstraint("idempotency_key", name="uq_plugin_pedidos_stripe_idempotency"),
        UniqueConstraint("stripe_session_id", name="uq_plugin_pedidos_stripe_session"),
        CheckConstraint("valor > 0", name="ck_plugin_pedidos_stripe_valor"),
        CheckConstraint("moeda = 'usd'", name="ck_plugin_pedidos_stripe_moeda"),
        CheckConstraint(
            "status IN ('aberto','pago','expirado','reembolsado','contestado')", name="ck_plugin_pedidos_stripe_status"
        ),
    )

    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    licenca_id = Column(Integer, ForeignKey("plugin_licencas.id", ondelete="RESTRICT"), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    moeda = Column(String(3), nullable=False, default="usd", server_default="usd")
    status = Column(String(12), nullable=False, default="aberto", server_default="aberto")
    idempotency_key = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    stripe_session_id = Column(String(255), nullable=True)
    stripe_payment_intent = Column(String(255), nullable=True, index=True)
    checkout_url = Column(String(1000), nullable=True)
    expira_em = Column(DateTime(timezone=True), nullable=True)
    pago_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plugin = relationship("PluginModel")
    licenca = relationship("PluginLicencaModel")


for table in (PluginModel.__table__, PluginArquivoModel.__table__, PluginLicencaModel.__table__,
              PluginPedidoStripeModel.__table__):
    event.listen(
        table,
        "after_create",
        DDL("ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
    )
    for role in ("anon", "authenticated"):
        event.listen(
            table,
            "after_create",
            DDL(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='"
                + role
                + "') THEN REVOKE ALL ON TABLE %(fullname)s FROM "
                + role
                + "; END IF; END $$"
            ).execute_if(dialect="postgresql"),
        )
