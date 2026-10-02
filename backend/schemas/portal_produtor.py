from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProducaoProdutorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    cliente: str
    servico: str
    status: str
    etapas: str
    prazo_entrega: datetime | None
    created_at: datetime
    updated_at: datetime
