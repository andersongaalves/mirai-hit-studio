from enum import Enum


class CobrancaStatus(str, Enum):
    PENDENTE = "pendente"
    PARCIALMENTE_PAGA = "parcialmente_paga"
    PAGA = "paga"
    CANCELADA = "cancelada"


class PagamentoStatus(str, Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    RECUSADO = "recusado"
    CANCELADO = "cancelado"
    REEMBOLSADO = "reembolsado"


class PagamentoTipo(str, Enum):
    INTEGRAL = "integral"
    ENTRADA = "entrada"
    SALDO = "saldo"
