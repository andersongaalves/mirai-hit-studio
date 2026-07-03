from enum import Enum

class OrcamentoStatus(str, Enum):
    NOVO = "novo"
    EM_ANALISE = "em_analise"
    APROVADO = "aprovado"
    RECUSADO = "recusado"
    ARQUIVADO = "arquivado"