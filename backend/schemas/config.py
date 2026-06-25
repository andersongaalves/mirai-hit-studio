from pydantic import BaseModel


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

    class Config:
        from_attributes = True