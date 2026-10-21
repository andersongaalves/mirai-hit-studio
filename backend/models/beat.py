from database import Base
from sqlalchemy import (
    DDL,
    BigInteger,
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


class BeatModel(Base):
    __tablename__ = "beats"
    __table_args__ = (
        CheckConstraint(
            "status IN ('revisao','aprovado','rejeitado','vendido')",
            name="ck_beats_status",
        ),
        CheckConstraint(
            "preco_lease IS NULL OR preco_lease > 0", name="ck_beats_preco_lease"
        ),
        CheckConstraint(
            "preco_exclusivo IS NULL OR preco_exclusivo > 0",
            name="ck_beats_preco_exclusivo",
        ),
        CheckConstraint("preco_wav IS NULL OR preco_wav > 0", name="ck_beats_preco_wav"),
        CheckConstraint("preco_multitrack IS NULL OR preco_multitrack > 0", name="ck_beats_preco_multitrack"),
        CheckConstraint(
            "preco_lease IS NOT NULL OR preco_wav IS NOT NULL OR preco_multitrack IS NOT NULL OR preco_exclusivo IS NOT NULL",
            name="ck_beats_algum_preco",
        ),
        CheckConstraint(
            "length(original_sha256) = 64 AND length(preview_sha256) = 64",
            name="ck_beats_hashes",
        ),
    )
    id = Column(Integer, primary_key=True)
    produtor_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    titulo = Column(String(160), nullable=False)
    descricao = Column(Text, nullable=False, default="", server_default="")
    bpm = Column(Integer, nullable=True)
    tonalidade = Column(String(24), nullable=True)
    generos = Column(String(240), nullable=False, default="", server_default="")
    preco_lease = Column(Numeric(12, 2), nullable=True)
    preco_wav = Column(Numeric(12, 2), nullable=True)
    preco_multitrack = Column(Numeric(12, 2), nullable=True)
    preco_exclusivo = Column(Numeric(12, 2), nullable=True)
    status = Column(
        String(16),
        nullable=False,
        default="revisao",
        server_default="revisao",
        index=True,
    )
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")
    aplica_desconto = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    original_ref = Column(String(180), nullable=False, unique=True)
    original_sha256 = Column(String(64), nullable=False)
    preview_ref = Column(String(180), nullable=False, unique=True)
    preview_sha256 = Column(String(64), nullable=False)
    mp3_ref = Column(String(180), nullable=True, unique=True)
    wav_ref = Column(String(180), nullable=True, unique=True)
    wav_sha256 = Column(String(64), nullable=True)
    multitrack_ref = Column(String(180), nullable=True, unique=True)
    multitrack_sha256 = Column(String(64), nullable=True)
    multitrack_mime = Column(String(100), nullable=True)
    capa_ref = Column(String(180), nullable=True, unique=True)
    capa_url = Column(String(1000), nullable=True)
    capa_sha256 = Column(String(64), nullable=True)
    tamanho_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    revisado_por_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    revisado_em = Column(DateTime(timezone=True), nullable=True)
    motivo_rejeicao = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    produtor = relationship("UsuarioModel", foreign_keys=[produtor_id])


class BeatLicencaModel(Base):
    __tablename__ = "beat_licencas"
    __table_args__ = (
        UniqueConstraint(
            "proposta_id", "beat_id", "tipo", name="uq_beat_licenca_proposta_beat_tipo"
        ),
        CheckConstraint("tipo IN ('lease','lease_mp3','lease_wav','multitrack','exclusivo')", name="ck_beat_licencas_tipo"),
        CheckConstraint(
            "status IN ('reservada','adquirida','cancelada')",
            name="ck_beat_licencas_status",
        ),
        CheckConstraint("valor > 0", name="ck_beat_licencas_valor"),
    )
    id = Column(Integer, primary_key=True)
    beat_id = Column(
        Integer, ForeignKey("beats.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    proposta_id = Column(
        Integer,
        ForeignKey("propostas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo = Column(String(12), nullable=False)
    status = Column(
        String(12), nullable=False, default="reservada", server_default="reservada"
    )
    valor = Column(Numeric(12, 2), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    adquirida_em = Column(DateTime(timezone=True), nullable=True)


for table in (BeatModel.__table__, BeatLicencaModel.__table__):
    event.listen(
        table,
        "after_create",
        DDL("ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY").execute_if(
            dialect="postgresql"
        ),
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
