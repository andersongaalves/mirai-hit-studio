from enum import Enum


class PropostaStatus(str, Enum):
    RASCUNHO = "rascunho"
    PRONTA = "pronta"
    ENVIADA = "enviada"
    ACEITA = "aceita"
    RECUSADA = "recusada"
    CANCELADA = "cancelada"


class PoliticaPagamento(str, Enum):
    INTEGRAL = "integral"
    ENTRADA_50_50 = "entrada_50_50"
