import json
from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    icon: str = Field(default="", max_length=100)
    title: str = Field(max_length=200)
    items: list[str] = Field(max_length=100)


class EstruturaServico(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    intro: str = Field(default="", max_length=10000)
    sections: list[Section] = Field(default_factory=list, max_length=30)
    benefits: list[str] = Field(default_factory=list, max_length=100)


def validar_estrutura(value):
    if len(value) > 100000:
        raise ValueError("service_structure_too_large")
    parsed = json.loads(value) if value else {}
    model = EstruturaServico.model_validate(parsed)
    if any(len(item) > 2000 for item in model.benefits + [i for s in model.sections for i in s.items]):
        raise ValueError("service_item_too_long")
    return json.dumps(model.model_dump(), ensure_ascii=False)
