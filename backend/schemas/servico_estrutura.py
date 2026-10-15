"""Public content of a catalog service.

Version 2 (catalog rework after 5.10): free-text sections are replaced by typed limits
(tracks sent by the client, max duration per track, included reviews, melodies, artists)
plus short highlights. Limits feed the contractual file quotas (5.09) and the included
reviews of the service's last stage (5.10). The legacy shape (intro/sections/benefits) is
still accepted and converted on save; readers convert it on the fly.
"""
import json
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    icon: str = Field(default="", max_length=100)
    title: str = Field(max_length=200)
    items: list[str] = Field(max_length=100)


class EstruturaServico(BaseModel):
    """Legacy shape (before the catalog rework)."""
    model_config = ConfigDict(extra="forbid", strict=True)
    intro: str = Field(default="", max_length=10000)
    sections: list[Section] = Field(default_factory=list, max_length=30)
    benefits: list[str] = Field(default_factory=list, max_length=100)


class LimitesServico(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    faixas: int | None = Field(default=None, ge=1, le=100)  # Tracks (channels) sent by the client.
    duracao_min: int | None = Field(default=None, ge=1, le=60)  # Max minutes per audio track.
    revisoes: int | None = Field(default=None, ge=0, le=20)  # Included reviews (last stage).
    melodias: int | None = Field(default=None, ge=1, le=50)  # Display only.
    artistas: int | None = Field(default=None, ge=1, le=20)  # Display only (checked by ear).


class EstruturaServicoV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    versao: int = Field(ge=2, le=2)
    intro: str = Field(default="", max_length=10000)
    destaques: list[str] = Field(default_factory=list, max_length=20)
    limites: LimitesServico = Field(default_factory=LimitesServico)


VAZIA = {"versao": 2, "intro": "", "destaques": [], "limites": LimitesServico().model_dump()}

_PADROES = (
    ("faixas", re.compile(r"^ate\s+(\d+)\s+(?:canais|canal|faixas?)\b")),
    ("duracao_min", re.compile(r"^ate\s+(\d+)\s+min(?:uto|utos)?\b")),
    ("revisoes", re.compile(r"^(\d+)\s+revis(?:ao|oes)\b")),
    ("melodias", re.compile(r"^ate\s+(\d+)\s+melodias?\b")),
    ("artistas", re.compile(r"^(\d+)\s+artistas?\b")),
)


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower().strip()


def converter_legado(dados: dict) -> dict:
    """Legacy sections -> v2: items that state a limit become limits, the rest highlights."""
    legado = EstruturaServico.model_validate(dados)
    limites = LimitesServico().model_dump()
    destaques: list[str] = []
    for item in [i for secao in legado.sections for i in secao.items] + list(legado.benefits):
        texto = item.strip()
        if not texto:
            continue
        chave, valor = next(((campo, int(m.group(1))) for campo, padrao in _PADROES
                             if (m := padrao.match(_sem_acentos(texto)))), (None, None))
        if chave is not None and limites[chave] is None:
            try:
                limites[chave] = LimitesServico.model_validate({chave: valor}).model_dump()[chave]
                continue
            except ValueError:
                pass
        if texto[:200] not in destaques and len(destaques) < 20:
            destaques.append(texto[:200])
    return EstruturaServicoV2.model_validate(
        {"versao": 2, "intro": legado.intro, "destaques": destaques, "limites": limites}
    ).model_dump()


def ler(valor) -> dict:
    """Any stored structure as v2; unreadable content falls back to an empty structure."""
    try:
        dados = json.loads(valor) if isinstance(valor, str) else (valor or {})
        if isinstance(dados, dict) and dados.get("versao") == 2:
            return EstruturaServicoV2.model_validate(dados).model_dump()
        return converter_legado(dados if isinstance(dados, dict) else {})
    except (ValueError, TypeError):
        return json.loads(json.dumps(VAZIA))


def validar_estrutura(value):
    if len(value) > 100000:
        raise ValueError("service_structure_too_large")
    parsed = json.loads(value) if value else {}
    if isinstance(parsed, dict) and parsed.get("versao") == 2:
        model = EstruturaServicoV2.model_validate(parsed)
        if any(len(item) > 200 for item in model.destaques):
            raise ValueError("service_item_too_long")
        return json.dumps(model.model_dump(), ensure_ascii=False)
    model = EstruturaServico.model_validate(parsed)
    if any(len(item) > 2000 for item in model.benefits + [i for s in model.sections for i in s.items]):
        raise ValueError("service_item_too_long")
    # Legacy payloads are stored in the new shape.
    return json.dumps(converter_legado(model.model_dump()), ensure_ascii=False)
