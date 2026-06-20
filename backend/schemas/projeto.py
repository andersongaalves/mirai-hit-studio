from pydantic import BaseModel, Field


class ProjetoBase(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150)
    artista: str
    categoria: str
    link_audio: str
    link_capa: str
    descricao: str
    destaque: bool = False


class ProjetoCreate(ProjetoBase):
    pass


class ProjetoUpdate(ProjetoBase):
    pass


class ProjetoResponse(ProjetoBase):
    id: int

    class Config:
        from_attributes = True