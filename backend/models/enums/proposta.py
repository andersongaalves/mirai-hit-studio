from enum import Enum

class PropostaStatus(str, Enum):
    RASCUNHO = "rascunho"
    PRONTA = "pronta"
    ENVIADA = "enviada"
    ACEITA = "aceita"
    RECUSADA = "recusada"
    CANCELADA = "cancelada"