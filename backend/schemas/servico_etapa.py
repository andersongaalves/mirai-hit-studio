from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WEIGHT_TOTAL = Decimal("100.00")


def _clean(value: str) -> str:
    return "".join(ch for ch in value if ord(ch) >= 32 and ord(ch) != 127).strip()


class ServicoEtapaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=100)
    descricao: str = Field(default="", max_length=300)
    peso_percentual: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    prazo_dias: int | None = Field(default=None, ge=0, le=365)
    unidade: str = Field(default="", max_length=30)
    revisoes_incluidas: int | None = Field(default=None, ge=0, le=20)
    depende_da_anterior: bool = False
    administrativa: bool = False

    @field_validator("nome", "descricao", "unidade")
    @classmethod
    def _text(cls, value):
        return _clean(value)

    @model_validator(mode="after")
    def _rules(self):
        if not self.nome:
            raise ValueError("Informe o nome da etapa.")
        if self.peso_percentual == 0 and not self.administrativa:
            raise ValueError("Somente etapas administrativas podem ter peso 0%.")
        return self


class ServicoEtapasUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    etapas: list[ServicoEtapaIn] = Field(max_length=20)

    @model_validator(mode="after")
    def _sequence(self):
        if not self.etapas:
            return self
        if self.etapas[0].depende_da_anterior:
            raise ValueError("A primeira etapa não pode depender de uma anterior.")
        total = sum((item.peso_percentual for item in self.etapas), Decimal("0"))
        if total != WEIGHT_TOTAL:
            raise ValueError(f"A soma dos pesos deve ser 100%; está em {total}%.")
        names = [item.nome.casefold() for item in self.etapas]
        if len(set(names)) != len(names):
            raise ValueError("Etapas com nomes repetidos.")
        return self


class ServicoEtapaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem: int
    nome: str
    descricao: str
    peso_percentual: Decimal
    prazo_dias: int | None
    unidade: str
    revisoes_incluidas: int | None
    depende_da_anterior: bool
    administrativa: bool
