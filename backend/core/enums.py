from enum import Enum

class OrcamentoStatus(str, Enum):
    NOVO = "novo"
    EM_ANALISE = "em_analise"
    PROPOSTA_ENVIADA = "proposta_enviada"
    APROVADO = "aprovado"
    ARQUIVADO = "arquivado"