"""Immutable audio tag versions and durable private preview rendering jobs."""

from database import Base
from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    event,
    func,
)


class AudioTagModel(Base):
    __tablename__ = "audio_tags"
    __table_args__ = (
        CheckConstraint("length(sha256) = 64", name="ck_audio_tag_sha256"),
        CheckConstraint("length(conteudo) BETWEEN 1 AND 2097152", name="ck_audio_tag_tamanho"),
        CheckConstraint("duracao > 0 AND duracao <= 10", name="ck_audio_tag_duracao"),
    )
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    nome = Column(String(180), nullable=False)
    mime_type = Column(String(100), nullable=False)
    conteudo = Column(LargeBinary, nullable=False)
    sha256 = Column(String(64), nullable=False)
    duracao = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AudioTagPerfilModel(Base):
    __tablename__ = "audio_tag_perfis"
    __table_args__ = (
        CheckConstraint("intervalo_segundos BETWEEN 10 AND 120", name="ck_audio_tag_intervalo"),
        CheckConstraint("volume_percentual BETWEEN 1 AND 100", name="ck_audio_tag_volume"),
        CheckConstraint("alvo_relativo_db BETWEEN -30 AND 12", name="ck_audio_tag_alvo_relativo"),
        CheckConstraint("ganho_min_db BETWEEN -60 AND 0", name="ck_audio_tag_ganho_min"),
        CheckConstraint("ganho_max_db BETWEEN 0 AND 30", name="ck_audio_tag_ganho_max"),
        CheckConstraint("ganho_min_db < ganho_max_db", name="ck_audio_tag_faixa_ganho"),
        CheckConstraint("silencio_lufs BETWEEN -90 AND -20", name="ck_audio_tag_silencio"),
        CheckConstraint("limiter_dbfs BETWEEN -12 AND -0.1", name="ck_audio_tag_limiter"),
        CheckConstraint("versao >= 1", name="ck_audio_tag_perfil_versao"),
    )
    chave = Column(String(40), primary_key=True)
    tag_id = Column(Integer, ForeignKey("audio_tags.id", ondelete="RESTRICT"), nullable=True)
    intervalo_segundos = Column(Integer, nullable=False, default=10, server_default="10")
    volume_percentual = Column(Integer, nullable=False, default=40, server_default="40")
    nivelamento_automatico = Column(Boolean, nullable=False, default=True, server_default="true")
    alvo_relativo_db = Column(Float, nullable=False, default=-3.0, server_default="-3")
    ganho_min_db = Column(Float, nullable=False, default=-40.0, server_default="-40")
    ganho_max_db = Column(Float, nullable=False, default=30.0, server_default="30")
    silencio_lufs = Column(Float, nullable=False, default=-60.0, server_default="-60")
    limiter_dbfs = Column(Float, nullable=False, default=-0.9, server_default="-0.9")
    versao = Column(Integer, nullable=False, default=1, server_default="1")


class PreviaTagJobModel(Base):
    __tablename__ = "previa_tag_jobs"
    __table_args__ = (
        CheckConstraint("estado IN ('pendente', 'pronto', 'erro')", name="ck_previa_tag_estado"),
        CheckConstraint("intervalo_segundos BETWEEN 10 AND 120", name="ck_previa_tag_intervalo"),
        CheckConstraint("volume_percentual BETWEEN 1 AND 100", name="ck_previa_tag_volume"),
        CheckConstraint("alvo_relativo_db BETWEEN -30 AND 12", name="ck_previa_tag_alvo_relativo"),
        CheckConstraint("ganho_min_db BETWEEN -60 AND 0", name="ck_previa_tag_ganho_min"),
        CheckConstraint("ganho_max_db BETWEEN 0 AND 30", name="ck_previa_tag_ganho_max"),
        CheckConstraint("ganho_min_db < ganho_max_db", name="ck_previa_tag_faixa_ganho"),
        CheckConstraint("silencio_lufs BETWEEN -90 AND -20", name="ck_previa_tag_silencio"),
        CheckConstraint("limiter_dbfs BETWEEN -12 AND -0.1", name="ck_previa_tag_limiter"),
        CheckConstraint("reserva_bytes BETWEEN 1 AND 52428800", name="ck_previa_tag_reserva"),
        CheckConstraint("(estado <> 'pronto') OR (object_key IS NOT NULL AND sha256 IS NOT NULL AND tamanho_bytes > 0)",
                        name="ck_previa_tag_resultado"),
    )
    arquivo_id = Column(Integer, ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("audio_tags.id", ondelete="RESTRICT"), nullable=False)
    intervalo_segundos = Column(Integer, nullable=False)
    volume_percentual = Column(Integer, nullable=False)
    nivelamento_automatico = Column(Boolean, nullable=False, default=True, server_default="true")
    alvo_relativo_db = Column(Float, nullable=False, default=-3.0, server_default="-3")
    ganho_min_db = Column(Float, nullable=False, default=-40.0, server_default="-40")
    ganho_max_db = Column(Float, nullable=False, default=30.0, server_default="30")
    silencio_lufs = Column(Float, nullable=False, default=-60.0, server_default="-60")
    limiter_dbfs = Column(Float, nullable=False, default=-0.9, server_default="-0.9")
    reserva_bytes = Column(Integer, nullable=False)
    estado = Column(String(12), nullable=False, default="pendente", server_default="pendente")
    object_key = Column(String(180), nullable=True, unique=True)
    sha256 = Column(String(64), nullable=True)
    tamanho_bytes = Column(Integer, nullable=True)
    visivel_cliente = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    concluido_em = Column(DateTime(timezone=True), nullable=True)


for table in (AudioTagModel.__table__, AudioTagPerfilModel.__table__, PreviaTagJobModel.__table__):
    event.listen(table, "after_create", DDL(
        "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
    ).execute_if(dialect="postgresql"))
    for role in ("anon", "authenticated"):
        event.listen(table, "after_create", DDL(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
            "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
        ).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(AudioTagModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON SEQUENCE public.audio_tags_id_seq FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
