from pydantic import BaseModel, Field, ConfigDict, field_validator
from schemas.servico_estrutura import validar_estrutura


class ServicoBase(BaseModel):

    nome: str = Field(..., min_length=3, max_length=100)
    subtitulo: str
    valor_base: float
    categoria: str
    aplica_desconto: bool
    parametros: str
    estrutura_servico: str


class ServicoCreate(ServicoBase):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    subtitulo: str = Field(max_length=1000)
    categoria: str = Field(max_length=100)
    valor_base: float = Field(ge=0)
    parametros: str = Field(max_length=500)
    _estrutura = field_validator("estrutura_servico")(validar_estrutura)

    @field_validator("parametros")
    @classmethod
    def known_parameters(cls, value):
        allowed = {"duracao", "pessoas", "canais_voz", "inst_aberto", "canais_inst", "melodias", "instrumentacao", "exclusividade", "revisoes", "prazo", "descricao", "guia"}
        if any(p.strip() not in allowed for p in value.split(",") if p.strip()):
            raise ValueError("unknown_service_parameter")
        return value


class ServicoUpdate(ServicoCreate):
    pass


class ServicoResponse(ServicoBase):
    id: int

    class Config:
        from_attributes = True
