from pydantic import BaseModel, Field

class ServicoBase(BaseModel):

    nome: str = Field(..., min_length=3, max_length=100)
    subtitulo: str
    valor_base: float
    categoria: str
    aplica_desconto: bool
    parametros: str
    descricao_servico: str


class ServicoCreate(ServicoBase):
    pass


class ServicoUpdate(ServicoBase):
    pass


class ServicoResponse(ServicoBase):
    id: int
    
    class Config:
        from_attributes = True