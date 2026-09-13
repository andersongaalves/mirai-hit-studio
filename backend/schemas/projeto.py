from pydantic import BaseModel, Field, field_validator
from schemas.validation import http_url


class ProjetoBase(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150)
    artista: str
    categoria: str
    link_audio: str
    link_capa: str
    descricao: str
    destaque: bool = False


class ProjetoCreate(ProjetoBase):
    artista: str = Field(max_length=150)
    categoria: str = Field(max_length=100)
    descricao: str = Field(max_length=20000)
    link_audio: str = Field(max_length=2000)
    link_capa: str = Field(max_length=2000)
    _urls = field_validator("link_audio", "link_capa")(http_url)


class ProjetoUpdate(ProjetoBase):
    pass


class ProjetoResponse(ProjetoBase):
    id: int

    class Config:
        from_attributes = True
