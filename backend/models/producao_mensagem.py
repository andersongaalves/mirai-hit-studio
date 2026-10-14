from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class ProducaoMensagemModel(Base):
    """Immutable message thread of a production (Roadmap 5.03)."""

    __tablename__ = "producao_mensagens"
    __table_args__ = (
        CheckConstraint("autor_papel IN ('cliente', 'produtor', 'admin')", name="ck_producao_mensagens_papel"),
        CheckConstraint("audiencia IN ('todos', 'equipe')", name="ck_producao_mensagens_audiencia"),
        CheckConstraint("length(texto) BETWEEN 1 AND 2000", name="ck_producao_mensagens_texto"),
        CheckConstraint(
            "autor_papel <> 'cliente' OR audiencia = 'todos'",
            name="ck_producao_mensagens_cliente_todos",
        ),
    )

    id = Column(Integer, primary_key=True)
    producao_id = Column(
        Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    autor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    autor_papel = Column(String(20), nullable=False)
    audiencia = Column(String(20), nullable=False)
    texto = Column(Text, nullable=False)
    responde_a_id = Column(
        Integer, ForeignKey("producao_mensagens.id", ondelete="RESTRICT"), nullable=True
    )
    arquivo_id = Column(
        Integer, ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
