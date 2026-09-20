from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


Money = Decimal
PaymentOption = Literal["integral", "entrada", "saldo"]


class CheckoutContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckoutOption(CheckoutContract):
    tipo: PaymentOption
    titulo: str
    valor: Money = Field(gt=0, allow_inf_nan=False)


class CheckoutAttempt(CheckoutContract):
    metodo: Literal["pix", "cartao"]
    tipo: PaymentOption
    status: Literal["processando", "recusado"]
    recuperavel: bool


class CheckoutSummary(CheckoutContract):
    proposta_numero: str
    descricao: str
    valor_total: Money = Field(gt=0, allow_inf_nan=False)
    valor_pago: Money = Field(ge=0, allow_inf_nan=False)
    saldo: Money = Field(ge=0, allow_inf_nan=False)
    moeda: Literal["BRL"]
    status: Literal["pendente", "parcialmente_paga", "paga", "cancelada"]
    opcoes: list[CheckoutOption]
    tentativa: CheckoutAttempt | None = None


class CheckoutStatus(CheckoutContract):
    status: Literal["pendente", "parcialmente_paga", "paga", "cancelada"]
    valor_pago: Money = Field(ge=0, allow_inf_nan=False)
    saldo: Money = Field(ge=0, allow_inf_nan=False)
    pagamento_status: Literal["processando", "recusado", "aprovado"] | None = None


class CheckoutConfig(CheckoutContract):
    mercado_pago_public_key: str = Field(min_length=1, max_length=200)


class CheckoutPaymentRequest(CheckoutContract):
    payment_option: PaymentOption


class CheckoutCardRequest(CheckoutPaymentRequest):
    card_token: str = Field(min_length=1, max_length=256)
    payment_method_id: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    payment_method_type: Literal["credit_card", "debit_card"] = "credit_card"
    installments: int = Field(ge=1, le=24, strict=True)
    payer_email: EmailStr | None = Field(default=None, max_length=254)
    identification_type: str | None = Field(default=None, min_length=1, max_length=20)
    identification_number: str | None = Field(default=None, min_length=1, max_length=40)

    @model_validator(mode="after")
    def identification_pair(self):
        if bool(self.identification_number) != bool(self.identification_type):
            raise ValueError("identification_pair_required")
        return self


class CheckoutPixData(CheckoutContract):
    qr_code: str | None = Field(default=None, max_length=10000)
    qr_code_base64: str | None = Field(default=None, max_length=200000)
    ticket_url: str | None = Field(default=None, max_length=2000)
    expiration_time: str | None = Field(default=None, max_length=40)


class CheckoutPaymentResponse(CheckoutContract):
    status: Literal["approved", "pending", "rejected", "action_required"]
    checkout_status: Literal["pendente", "parcialmente_paga", "paga", "cancelada"]
    payment_option: PaymentOption
    valor: Money = Field(gt=0, allow_inf_nan=False)
    moeda: Literal["BRL"]
    pix: CheckoutPixData | None = None
    challenge_url: str | None = Field(default=None, max_length=2000)


class CheckoutLinkResponse(CheckoutContract):
    checkout_url: str = Field(min_length=1, max_length=2000)
