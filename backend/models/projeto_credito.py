from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from database import Base

# Roadmap 5.19: fixed list of roles credited on a portfolio project.
FUNCOES_CREDITO = ("producao", "mixagem", "masterizacao", "composicao", "gravacao", "beat", "outra")


class ProjetoCreditoModel(Base):
    __tablename__ = "projeto_creditos"
    __table_args__ = (
        UniqueConstraint("projeto_id", "ordem", name="uq_projeto_credito_ordem"),
        CheckConstraint(
            "funcao IN ('producao', 'mixagem', 'masterizacao', 'composicao', 'gravacao', 'beat', 'outra')",
            name="ck_projeto_credito_funcao",
        ),
        CheckConstraint(
            "(funcao = 'outra' AND funcao_outra IS NOT NULL) OR (funcao <> 'outra' AND funcao_outra IS NULL)",
            name="ck_projeto_credito_funcao_outra",
        ),
        CheckConstraint("ordem >= 1", name="ck_projeto_credito_ordem"),
    )

    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False, index=True)
    ordem = Column(Integer, nullable=False)
    funcao = Column(String(20), nullable=False)
    funcao_outra = Column(String(60), nullable=True)
    # Public credited name; a producer account is optional (external collaborators have none).
    nome = Column(String(100), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    usuario = relationship("UsuarioModel", lazy="selectin")

    @property
    def nome_publico(self) -> str:
        """A linked account always shows its current display name; otherwise the stored name."""
        if self.usuario is not None and self.usuario.nome_exibicao:
            return self.usuario.nome_exibicao
        return self.nome
