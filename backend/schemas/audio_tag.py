from pydantic import BaseModel, ConfigDict, Field, model_validator


class AudioTagLevelControls(BaseModel):
    intervalo_segundos: int = Field(ge=10, le=120)
    volume_percentual: int = Field(ge=1, le=100)
    nivelamento_automatico: bool = True
    alvo_relativo_db: float = Field(default=-3.0, ge=-30, le=12)
    ganho_min_db: float = Field(default=-40.0, ge=-60, le=0)
    ganho_max_db: float = Field(default=30.0, ge=0, le=30)
    silencio_lufs: float = Field(default=-60.0, ge=-90, le=-20)
    limiter_dbfs: float = Field(default=-0.9, ge=-12, le=-0.1)

    @model_validator(mode="after")
    def validar_faixa_ganho(self):
        if self.ganho_min_db >= self.ganho_max_db:
            raise ValueError("O ganho minimo deve ser menor que o ganho maximo.")
        return self


class AudioTagSettings(AudioTagLevelControls):
    model_config = ConfigDict(extra="forbid")
    versao: int = Field(ge=0)


class AudioTagPreviewRequest(AudioTagLevelControls):
    model_config = ConfigDict(extra="forbid")
    source_type: str = Field(pattern="^(beat|arquivo)$")
    source_id: int = Field(gt=0)
    tag_id: int = Field(gt=0)
