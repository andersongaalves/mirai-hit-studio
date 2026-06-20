from pydantic import BaseModel, EmailStr
from datetime import datetime

class OrcamentoBase(BaseModel):

    nome_cliente: str
    email: EmailStr
    whatsapp: str
    servico: str
    valor_total: float
    link_guia: str | None = None
    detalhes: str


class OrcamentoCreate(OrcamentoBase):
    pass


class OrcamentoResponse(OrcamentoBase):

    id: int
    data_solicitacao: datetime
    model_config = {
        "from_attributes": True
    }