from sqlalchemy import Column, Integer, Float

from database import Base


class ConfigModel(Base):

    __tablename__ = "configuracoes"

    id = Column(Integer, primary_key=True, index=True)
    desconto = Column(Float, default=10.0)
    val_extra_duracao = Column(Float, default=0.10)
    val_extra_pessoa = Column(Float, default=20.0)
    val_extra_canal_voz = Column(Float, default=5.0)
    val_extra_canal_inst = Column(Float, default=5.0)
    val_extra_melodia = Column(Float, default=10.0)
    val_inst_hibrido = Column(Float, default=40.0)
    val_inst_gravado = Column(Float, default=100.0)
    val_lease_desconto = Column(Float, default=50.0)
    val_extra_revisao = Column(Float, default=30.0)
    val_prazo_urgente = Column(Float, default=40.0)
    val_prazo_express = Column(Float, default=80.0)