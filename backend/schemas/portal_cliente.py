from datetime import datetime
from decimal import Decimal

from models.enums.proposta import PoliticaPagamento, PropostaStatus
from pydantic import BaseModel, ConfigDict, Field

from schemas.producao_arquivo import TipoArquivoProducao
from schemas.proposta import PropostaItem, PropostaTotais


class ProducaoClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    servico: str
    status: str
    etapas: str
    prazo_entrega: datetime | None
    created_at: datetime
    updated_at: datetime


class PagamentoClienteResponse(BaseModel):
    tipo: str
    valor: Decimal
    status: str
    metodo: str | None
    aprovado_em: datetime | None
    created_at: datetime


class CobrancaClienteResponse(BaseModel):
    status: str
    valor_total: Decimal
    valor_pago: Decimal
    saldo_pendente: Decimal
    moeda: str
    vencimento: datetime | None
    pagamentos: list[PagamentoClienteResponse]


class FinanceiroClienteResponse(BaseModel):
    producao_id: int
    proposta_numero: str | None
    proposta_status: str | None
    cobranca: CobrancaClienteResponse | None
    checkout_url: str | None


class ProducaoArquivoClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producao_id: int
    tipo: TipoArquivoProducao
    nome_exibicao: str
    mime_type: str
    tamanho_bytes: int
    sha256: str
    grupo_versao: str
    versao: int
    substitui_arquivo_id: int | None
    enviado_por_mim: bool
    created_at: datetime
    updated_at: datetime


class PropostaClienteResponse(BaseModel):
    id: int
    numero: str
    versao: int
    status: PropostaStatus
    servico: str
    objeto: str
    descricao: str
    itens: list[PropostaItem]
    totais: PropostaTotais
    politica_pagamento: PoliticaPagamento
    condicoes: str
    documento_disponivel: bool
    situacao_comercial: str
    cobranca_status: str | None
    enviada_em: datetime
    aprovada_em: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class PropostaClienteAction(BaseModel):
    versao: int = Field(gt=0)
