from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigResponse(BaseModel):
    desconto: float
    val_extra_duracao: float
    val_extra_pessoa: float
    val_extra_canal_voz: float
    val_extra_canal_inst: float
    val_extra_melodia: float
    val_inst_hibrido: float
    val_inst_gravado: float
    val_lease_desconto: float
    val_extra_revisao: float
    val_prazo_urgente: float
    val_prazo_express: float

    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)


class PortfolioSegmentResponse(BaseModel):
    id: str
    label: str
    active: bool
    order: int
    usage_count: int = 0


class PortfolioSegmentCatalogResponse(BaseModel):
    segments: list[PortfolioSegmentResponse]
    revision: str


class PortfolioSegmentPublicResponse(BaseModel):
    id: str
    label: str


class PortfolioSegmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., min_length=2, max_length=80)
    expected_revision: str = Field(..., min_length=64, max_length=64)


class PortfolioSegmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, min_length=2, max_length=80)
    active: bool | None = None
    expected_revision: str = Field(..., min_length=64, max_length=64)

    @model_validator(mode="after")
    def require_change(self):
        if self.label is None and self.active is None:
            raise ValueError("segment_change_required")
        return self


class PortfolioSegmentOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment_ids: list[str] = Field(..., max_length=100)
    expected_revision: str = Field(..., min_length=64, max_length=64)


class PortfolioSegmentDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(..., min_length=64, max_length=64)
