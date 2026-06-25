from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String
)
from sqlalchemy.sql import func

from database import Base


class NewsletterModel(Base):

    __tablename__ = "newsletter"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False,
        index=True
    )

    ativo = Column(
        Boolean,
        default=True,
        nullable=False
    )

    origem = Column(
        String(50),
        default="Footer",
        nullable=False
    )

    data_cadastro = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )