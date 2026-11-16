"""Mirai Hit Labs admin: plugin releases, discount coupons and store content.

- plugin_versoes: the release history of a plugin (version, channel, notes). The latest
  stable release is what the update checker inside the plugins reads.
- labs_cupons / labs_cupom_usos: discount codes for the store. A use is recorded when a
  purchase starts and counts while its license is active or waiting for payment.
- labs_conteudo: small editable blocks of the store (for now, the announcement banner).
"""
from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import relationship

from database import Base

VERSAO_CANAIS = ("estavel", "beta")
CUPOM_TIPOS = ("percentual", "valor")


class PluginVersaoModel(Base):
    __tablename__ = "plugin_versoes"
    __table_args__ = (
        UniqueConstraint("plugin_id", "versao", name="uq_plugin_versoes_plugin_versao"),
        CheckConstraint("canal IN ('estavel','beta')", name="ck_plugin_versoes_canal"),
    )

    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    versao = Column(String(20), nullable=False)
    canal = Column(String(10), nullable=False, default="estavel", server_default="estavel")
    notas = Column(Text, nullable=True)
    notas_en = Column(Text, nullable=True)
    obrigatoria = Column(Boolean, nullable=False, default=False, server_default="false")
    publicada_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plugin = relationship("PluginModel")


class LabsCupomModel(Base):
    __tablename__ = "labs_cupons"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_labs_cupons_codigo"),
        CheckConstraint("tipo IN ('percentual','valor')", name="ck_labs_cupons_tipo"),
        CheckConstraint(
            "(tipo = 'percentual' AND valor > 0 AND valor <= 100) OR (tipo = 'valor' AND valor > 0)",
            name="ck_labs_cupons_valor",
        ),
        CheckConstraint("max_usos IS NULL OR max_usos > 0", name="ck_labs_cupons_max_usos"),
        CheckConstraint("valido_ate IS NULL OR valido_de IS NULL OR valido_ate > valido_de",
                        name="ck_labs_cupons_periodo"),
    )

    id = Column(Integer, primary_key=True)
    codigo = Column(String(32), nullable=False)
    descricao = Column(String(160), nullable=True)
    tipo = Column(String(12), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    # NULL: valid for every plugin.
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="CASCADE"), nullable=True, index=True)
    valido_de = Column(DateTime(timezone=True), nullable=True)
    valido_ate = Column(DateTime(timezone=True), nullable=True)
    max_usos = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plugin = relationship("PluginModel")


class LabsCupomUsoModel(Base):
    __tablename__ = "labs_cupom_usos"
    __table_args__ = (
        UniqueConstraint("orcamento_id", name="uq_labs_cupom_usos_orcamento"),
        UniqueConstraint("pedido_stripe_id", name="uq_labs_cupom_usos_pedido_stripe"),
        CheckConstraint("desconto >= 0", name="ck_labs_cupom_usos_desconto"),
    )

    id = Column(Integer, primary_key=True)
    cupom_id = Column(Integer, ForeignKey("labs_cupons.id", ondelete="RESTRICT"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False)
    licenca_id = Column(Integer, ForeignKey("plugin_licencas.id", ondelete="SET NULL"), nullable=True, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id", ondelete="SET NULL"), nullable=True)
    pedido_stripe_id = Column(Integer, ForeignKey("plugin_pedidos_stripe.id", ondelete="SET NULL"), nullable=True)
    moeda = Column(String(3), nullable=False, default="brl", server_default="brl")
    desconto = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cupom = relationship("LabsCupomModel")


class LabsConteudoModel(Base):
    __tablename__ = "labs_conteudo"

    chave = Column(String(40), primary_key=True)
    dados_json = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


for table in (PluginVersaoModel.__table__, LabsCupomModel.__table__, LabsCupomUsoModel.__table__,
              LabsConteudoModel.__table__):
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
