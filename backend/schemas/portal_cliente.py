from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from schemas.producao_arquivo import TipoArquivoProducao


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
