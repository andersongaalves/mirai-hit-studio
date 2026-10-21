from datetime import datetime
from decimal import Decimal
from uuid import UUID

from models.enums.proposta import PoliticaPagamento, PropostaStatus
from pydantic import BaseModel, ConfigDict, Field

from schemas.producao_arquivo import TipoArquivoProducao
from schemas.proposta import PropostaItem, PropostaTotais


class ProducaoSolicitacaoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: UUID
    servico_id: int = Field(gt=0)
    titulo: str = Field(min_length=1, max_length=150)
    descricao: str = Field(min_length=1, max_length=10000)


class ProducaoSolicitacaoResponse(BaseModel):
    id: int
    status: str


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
    valor_total: Decimal | None  # 5.10: None in the summary view.
    valor_pago: Decimal | None
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
    resumido: bool = False  # 5.10: summary view (status, balance, due date and payment link).


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
    observacao: str | None = None
    processamento_tag: str | None = None
    # 5.14: final delivery ready but held until the balance is paid.
    bloqueado_pagamento: bool = False
    created_at: datetime
    updated_at: datetime


class PropostaClienteResponse(BaseModel):
    finalidade: str = "producao"
    contrato_creditos: dict | None = None
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
