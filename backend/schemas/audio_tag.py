from pydantic import BaseModel, ConfigDict, Field


class AudioTagSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: int = Field(ge=0)
    intervalo_segundos: int = Field(ge=10, le=120)
    volume_percentual: int = Field(ge=1, le=100)
