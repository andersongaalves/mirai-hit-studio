# Mirai Hit Studio - Mercado Pago Integration

## Escopo e API

A integracao usa exclusivamente a **Orders API** do Checkout Transparente:

- `POST /v1/orders` para Pix e cartao tokenizado;
- `GET /v1/orders/{id}` para consulta;
- `processing_mode=automatic`.

A Orders API e a familia recomendada atualmente para Checkout Transparente. HTTP direto com `requests` foi escolhido para manter timeout, idempotencia e testes sob controle, sem adicionar SDK ou misturar a Payments API.

Referencias oficiais:

- [Visao geral da Checkout API](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api/overview)
- [Pix com Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/pix)
- [Cartoes com Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/cards)
- [Credenciais](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/credentials)

## Configuracao

```env
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_TIMEOUT_SECONDS=10
```

O Access Token e privado e usado somente pelo backend. A Public Key fica configuravel para a tokenizacao frontend da F3.4, mas ainda nao e exposta por endpoint. A aplicacao inicia normalmente sem essas variaveis; apenas uma operacao do gateway retorna `provider_not_configured`.

## Fluxo

1. O backend valida a cobranca e resolve o valor de `integral`, `entrada` ou `saldo`.
2. Cria e confirma no banco uma tentativa `Pagamento` pendente.
3. Persiste um UUID em `provider_idempotency_key` e usa a mesma referencia opaca em `external_reference`.
4. Envia a order com `X-Idempotency-Key`.
5. Normaliza a resposta, grava o ID da order em `provider_payment_id` e recalcula a cobranca pelo `financial_service`.

O navegador nunca define o valor autoritativo. Uma cobranca parcialmente paga nao aceita nova intencao integral ou entrada; o saldo e sempre calculado pelo backend.

## Pix e cartao

Pix retorna transitoriamente codigo copia-e-cola, QR base64 e `ticket_url` no DTO normalizado. Esses dados nao sao persistidos nem registrados em log.

Cartao aceita somente token temporario, identificador do meio, tipo e parcelas. PAN, CVV e validade bruta nao fazem parte da API interna. O token e enviado ao provider e descartado, sem persistencia ou log.

## Idempotencia e falhas

A chave pertence a tentativa local, nao ao request HTTP. Retry da mesma tentativa reutiliza a mesma chave; uma tentativa financeira realmente nova recebe outra. Nao ha retry automatico.

Timeout e falha de rede deixam a tentativa pendente, pois o resultado e ambiguo. Respostas `429` retornam `provider_rate_limited` e preservam `Retry-After`; o chamador deve aguardar e reutilizar a mesma tentativa. Erros sao categorizados sem resposta bruta, credencial ou PII.

## Status

| Orders API | Status interno |
|---|---|
| `processed` + `accredited` | `aprovado` |
| `action_required`, `created`, `processing`, `pending` | `pendente` |
| `failed`, `rejected` | `recusado` |
| `cancelled`, `canceled`, `expired` | `cancelado` |
| `refunded` | `reembolsado` |
| desconhecido | `pendente` |

Status desconhecido nunca aprova pagamento. A F3.2 pode refletir uma resposta sincrona aprovada na cobranca, mas nao altera producao nem libera entrega.

## Limites da F3.2

- sem endpoint publico de checkout;
- sem webhook ou reconciliacao automatica;
- sem refund ativo, chargeback, boleto, assinatura ou split;
- sem persistencia de payload bruto;
- sem chamada real nos testes.

F3.3 tratara webhook, concorrencia e reconciliacao. F3.4 implementara checkout e tokenizacao frontend. F3.5 implementara a operacao administrativa financeira.
