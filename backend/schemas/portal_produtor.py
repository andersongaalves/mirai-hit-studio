from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContatoClienteProdutor(BaseModel):
    nome: str
    email: str | None = None
    whatsapp: str | None = None


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
    # Roadmap 5.07: false when the producer only owns stages of this production.
    coordenador: bool = True
    contato_cliente: ContatoClienteProdutor | None = None
