from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ProducaoArquivoModel(Base):
    __tablename__ = "producao_arquivos"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('material', 'referencia', 'previa', 'entrega', 'comprovante')",
            name="ck_producao_arquivos_tipo_valido",
        ),
        CheckConstraint(
            "tamanho_bytes > 0 AND tamanho_bytes <= 52428800",
            name="ck_producao_arquivos_tamanho_valido",
        ),
        CheckConstraint(
            "length(sha256) = 64",
            name="ck_producao_arquivos_sha256_valido",
        ),
        CheckConstraint(
            "versao > 0",
            name="ck_producao_arquivos_versao_positiva",
        ),
        CheckConstraint(
            "substitui_arquivo_id IS NULL OR substitui_arquivo_id <> id",
            name="ck_producao_arquivos_substituicao_distinta",
        ),
        UniqueConstraint("object_key", name="uq_producao_arquivos_object_key"),
        UniqueConstraint(
            "grupo_versao",
            "versao",
            name="uq_producao_arquivos_grupo_versao",
        ),
        UniqueConstraint(
            "substitui_arquivo_id",
            name="uq_producao_arquivos_substitui_arquivo_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    producao_id = Column(
        Integer,
        ForeignKey("producoes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    remetente_usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tipo = Column(String(20), nullable=False, index=True)
    nome_exibicao = Column(String(180), nullable=False)
    mime_type = Column(String(100), nullable=False)
    tamanho_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    object_key = Column(String(180), nullable=False)
    grupo_versao = Column(
        String(36),
        default=lambda: str(uuid4()),
        nullable=False,
        index=True,
    )
    versao = Column(Integer, default=1, nullable=False)
    substitui_arquivo_id = Column(
        Integer,
        ForeignKey("producao_arquivos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    visivel_produtor = Column(Boolean, default=False, server_default=false(), nullable=False)
    visivel_cliente = Column(Boolean, default=False, server_default=false(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    producao = relationship("ProducaoModel")
    remetente = relationship("UsuarioModel", foreign_keys=[remetente_usuario_id])
    substitui = relationship("ProducaoArquivoModel", remote_side=[id], uselist=False)


class RepasseProdutorModel(Base):
    __tablename__ = "repasses_produtor"
    __table_args__ = (
        CheckConstraint(
            "valor_combinado > 0",
            name="ck_repasses_produtor_valor_positivo",
        ),
        CheckConstraint(
            "moeda = 'BRL'",
            name="ck_repasses_produtor_moeda_brl",
        ),
        CheckConstraint(
            "status IN ('definido', 'liberado', 'pago')",
            name="ck_repasses_produtor_status_valido",
        ),
        CheckConstraint(
            "(status = 'definido' AND liberado_em IS NULL AND pago_em IS NULL) OR "
            "(status = 'liberado' AND liberado_em IS NOT NULL AND pago_em IS NULL) OR "
            "(status = 'pago' AND liberado_em IS NOT NULL AND pago_em IS NOT NULL)",
            name="ck_repasses_produtor_datas_coerentes",
        ),
        UniqueConstraint("producao_id", name="uq_repasses_produtor_producao_id"),
        UniqueConstraint(
            "comprovante_arquivo_id",
            name="uq_repasses_produtor_comprovante_arquivo_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    producao_id = Column(
        Integer,
        ForeignKey("producoes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    produtor_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    valor_combinado = Column(Numeric(12, 2), nullable=False)
    moeda = Column(String(3), default="BRL", nullable=False)
    status = Column(String(20), default="definido", nullable=False, index=True)
    liberado_em = Column(DateTime(timezone=True), nullable=True)
    pago_em = Column(DateTime(timezone=True), nullable=True)
    referencia_pagamento = Column(String(160), nullable=True)
    comprovante_arquivo_id = Column(
        Integer,
        ForeignKey("producao_arquivos.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    producao = relationship("ProducaoModel")
    produtor = relationship("UsuarioModel", foreign_keys=[produtor_id])
    comprovante = relationship("ProducaoArquivoModel", foreign_keys=[comprovante_arquivo_id])
