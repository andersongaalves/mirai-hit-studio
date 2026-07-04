from datetime import datetime
from pydantic import BaseModel


# ===========================
# BASE
# ===========================

class ProducaoBase(BaseModel):

    titulo: str

    cliente: str

    servico: str

    observacoes: str = ""

    etapas: str = "[]"


# ===========================
# CREATE
# ===========================

class ProducaoCreate(ProducaoBase):

    produtor_id: int | None = None

    orcamento_id: int | None = None


# ===========================
# UPDATE STATUS
# ===========================

class ProducaoStatusUpdate(BaseModel):

    status: str


# ===========================
# RESPONSE
# ===========================

class ProducaoResponse(ProducaoBase):

    id: int

    status: str

    produtor_id: int | None

    orcamento_id: int | None

    created_at: datetime

    updated_at: datetime

    model_config = {

        "from_attributes": True

    }

    etapas: str

    prazo_entrega: datetime | None

    created_at: datetime

    updated_at: datetime

class ProducaoEtapasUpdate(BaseModel):
    etapas: str

class ProducaoPrazoUpdate(BaseModel):
    prazo_entrega: datetime
