"""Pop-ups sent by the Admin to the portals."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Publico = Literal["cliente", "produtor", "todos"]
Tema = Literal["ciano", "roxo", "amarelo", "verde", "vermelho"]
Tamanho = Literal["pequeno", "medio"]
Frequencia = Literal["uma_vez", "cada_sessao"]


def _clean(value: str) -> str:
    return "".join(c for c in value if c == "\n" or (ord(c) >= 32 and ord(c) != 127)).strip()


class PopupDados(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(min_length=1, max_length=80)
    mensagem: str = Field(min_length=1, max_length=600)
    publico: Publico
    tema: Tema = "ciano"
    tamanho: Tamanho = "pequeno"
    botao_rotulo: str | None = Field(default=None, max_length=40)
    botao_url: str | None = Field(default=None, max_length=300)
    frequencia: Frequencia = "uma_vez"
    inicio: datetime | None = None
    fim: datetime | None = None
    ativo: bool = True

    @field_validator("titulo", "mensagem")
    @classmethod
    def _texto(cls, value):
        value = _clean(value)
        if not value:
            raise ValueError("required_text")
        return value

    @field_validator("botao_rotulo", "botao_url")
    @classmethod
    def _opcional(cls, value):
        return _clean(value) or None if value is not None else None

    @model_validator(mode="after")
    def _regras(self):
        if bool(self.botao_rotulo) != bool(self.botao_url):
            raise ValueError("Informe o texto e o link do botao, ou deixe os dois em branco.")
        if self.botao_url and not (
            self.botao_url.startswith("https://") or (self.botao_url.startswith("/") and not self.botao_url.startswith("//"))
        ):
            raise ValueError("O link do botao deve comecar com https:// ou ser uma pagina do site (/...).")
        if self.inicio and self.fim and self.fim <= self.inicio:
            raise ValueError("O fim deve ser depois do inicio.")
        return self


class PopupAdminResponse(PopupDados):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    fechamentos: int = 0


class PopupPortalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    mensagem: str
    tema: str
    tamanho: str
    botao_rotulo: str | None
    botao_url: str | None
    frequencia: str
