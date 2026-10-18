"""Append-only economic lots and service-right acquisition ledger."""

from database import Base
from sqlalchemy import (
    DDL,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
)


class CreditoContratoItemModel(Base):
    __tablename__ = "credito_contrato_itens"
    __table_args__ = (
        UniqueConstraint("proposta_id", "proposta_versao", "linha", "componente", name="uq_credito_contrato_origem"),
        CheckConstraint("unidade IN ('faixa','canal','hora')", name="ck_credito_contrato_unidade"),
        CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_contrato_quantidade"),
        CheckConstraint("unidade = 'hora' OR quantidade = floor(quantidade)", name="ck_credito_contrato_discreto"),
        CheckConstraint("valor_centavos >= 0 AND proposta_versao > 0 AND linha > 0 AND componente >= 0", name="ck_credito_contrato_origem_valor"),
        CheckConstraint("length(contrato_sha256) = 64", name="ck_credito_contrato_hash"),
    )
    id = Column(Integer, primary_key=True)
    proposta_id = Column(Integer, ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=False)
    proposta_versao = Column(Integer, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False)
    servico_nome = Column(String(100), nullable=False)
    linha = Column(Integer, nullable=False)
    componente = Column(Integer, nullable=False)
    unidade = Column(String(10), nullable=False)
    quantidade = Column(Numeric(12, 3), nullable=False)
    valor_centavos = Column(Integer, nullable=False)
    contrato_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CreditoLoteModel(Base):
    __tablename__ = "credito_lotes"
    __table_args__ = (
        UniqueConstraint("cobranca_id", "linha", "componente", name="uq_credito_lote_origem"),
        CheckConstraint("unidade IN ('faixa','canal','hora')", name="ck_credito_lote_unidade"),
        CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_lote_quantidade"),
        CheckConstraint("unidade = 'hora' OR quantidade = floor(quantidade)", name="ck_credito_lote_discreto"),
        CheckConstraint("valor_centavos >= 0 AND linha > 0 AND componente >= 0", name="ck_credito_lote_origem_valor"),
        CheckConstraint("length(contrato_sha256) = 64", name="ck_credito_lote_contrato_hash"),
    )
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    contrato_item_id = Column(Integer, ForeignKey("credito_contrato_itens.id", ondelete="RESTRICT"), nullable=False, unique=True)
    cobranca_id = Column(Integer, ForeignKey("cobrancas.id", ondelete="RESTRICT"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False)
    servico_nome = Column(String(100), nullable=False)
    linha = Column(Integer, nullable=False)
    componente = Column(Integer, nullable=False)
    unidade = Column(String(10), nullable=False)
    quantidade = Column(Numeric(12, 3), nullable=False)
    valor_centavos = Column(Integer, nullable=False)
    contrato_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CreditoLancamentoModel(Base):
    __tablename__ = "credito_lancamentos"
    __table_args__ = (
        UniqueConstraint("lote_id", name="uq_credito_aquisicao_lote"),
        CheckConstraint("tipo = 'aquisicao'", name="ck_credito_lancamento_tipo"),
        CheckConstraint("quantidade > 0", name="ck_credito_lancamento_quantidade"),
    )
    id = Column(Integer, primary_key=True)
    lote_id = Column(Integer, ForeignKey("credito_lotes.id", ondelete="RESTRICT"), nullable=False)
    tipo = Column(String(20), nullable=False, default="aquisicao")
    quantidade = Column(Numeric(12, 3), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _immutable(mapper, connection, target):
    raise ValueError("credit_record_is_immutable")


for model in (CreditoContratoItemModel, CreditoLoteModel, CreditoLancamentoModel):
    event.listen(model, "before_update", _immutable)
    event.listen(model, "before_delete", _immutable)
    table = model.__table__
    event.listen(table, "after_create", DDL("ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
    for role in ("anon", "authenticated"):
        event.listen(table, "after_create", DDL(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='" + role + "') THEN "
            "REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; "
            "REVOKE ALL ON SEQUENCE public." + table.name + "_id_seq FROM " + role + "; END IF; END $$"
        ).execute_if(dialect="postgresql"))
    event.listen(table, "after_create", DDL("""
        CREATE OR REPLACE FUNCTION public.creditos_registro_imutavel() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
            RAISE EXCEPTION 'credit_record_is_immutable'; END $$;
        REVOKE ALL ON FUNCTION public.creditos_registro_imutavel() FROM PUBLIC;
        CREATE TRIGGER credito_registro_imutavel BEFORE UPDATE OR DELETE ON %(fullname)s
        FOR EACH ROW EXECUTE FUNCTION public.creditos_registro_imutavel();
    """).execute_if(dialect="postgresql"))
