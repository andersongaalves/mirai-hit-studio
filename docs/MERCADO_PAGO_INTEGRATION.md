# Mirai Hit Studio - Mercado Pago Integration

## Escopo e API

A integracao usa exclusivamente a **Orders API** do Checkout Transparente:

- `POST /v1/orders` para Pix e cartao tokenizado;
- `GET /v1/orders/{id}` para consulta;
- `POST /webhooks/mercado-pago` para notificacoes assinadas;
- `processing_mode=automatic`.

A Orders API e a familia recomendada atualmente para Checkout Transparente. HTTP direto com `requests` foi escolhido para manter timeout, idempotencia e testes sob controle, sem adicionar SDK ou misturar a Payments API.

Referencias oficiais:

- [Visao geral da Checkout API](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api/overview)
- [Pix com Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/pix)
- [Cartoes com Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/cards)
- [Credenciais](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/credentials)
- [Notificacoes de Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/notifications)
- [Status de Orders](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-management/status/order-status)

## Configuracao

```env
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_PUBLIC_KEY=
MERCADO_PAGO_WEBHOOK_SECRET=
MERCADO_PAGO_TIMEOUT_SECONDS=10
```

O Access Token e privado e usado somente pelo backend. O segredo de webhook e uma credencial separada, obtida na configuracao de notificacoes do Mercado Pago. A Public Key fica configuravel para a tokenizacao frontend da F3.4, mas ainda nao e exposta por endpoint. A aplicacao inicia sem essas variaveis; operacoes do gateway e o webhook retornam indisponibilidade controlada enquanto suas credenciais estiverem ausentes.

## Fluxo

1. O backend valida a cobranca e resolve o valor de `integral`, `entrada` ou `saldo`.
2. Cria e confirma no banco uma tentativa `Pagamento` pendente.
3. Persiste um UUID em `provider_idempotency_key` e usa a mesma referencia opaca em `external_reference`.
4. Envia a order com `X-Idempotency-Key`.
5. Normaliza a resposta, grava o ID da order em `provider_order_id` e recalcula a cobranca pelo `financial_service`.

O navegador nunca define o valor autoritativo. Uma cobranca parcialmente paga nao aceita nova intencao integral ou entrada; o saldo e sempre calculado pelo backend.

## Pix e cartao

Pix retorna transitoriamente codigo copia-e-cola, QR base64 e `ticket_url` no DTO normalizado. Esses dados nao sao persistidos nem registrados em log.

Cartao aceita somente token temporario, identificador do meio, tipo e parcelas. PAN, CVV e validade bruta nao fazem parte da API interna. O token e enviado ao provider e descartado, sem persistencia ou log.

## Idempotencia e falhas

A chave pertence a tentativa local, nao ao request HTTP. Retry da mesma tentativa reutiliza a mesma chave; uma tentativa financeira realmente nova recebe outra. Nao ha retry automatico.

Timeout e falha de rede deixam a tentativa pendente, pois o resultado e ambiguo. Respostas `429` retornam `provider_rate_limited` e preservam `Retry-After`; o chamador deve aguardar e reutilizar a mesma tentativa. Erros sao categorizados sem resposta bruta, credencial ou PII.

Se a tentativa ainda nao possui `provider_order_id`, a reconciliacao direta nao cria outro pagamento nem outra chave: marca `reconciliation_status=required`. Uma notificacao valida pode recuperar esse caso localizando a tentativa pela `external_reference` opaca retornada pela consulta oficial.

## Webhook e autenticidade

O endpoint publico nao usa JWT. Ele valida `x-signature` antes de qualquer mutacao financeira com o manifesto oficial:

```text
id:{data.id em minusculas};request-id:{x-request-id};ts:{ts};
```

O digest e HMAC-SHA256 com `MERCADO_PAGO_WEBHOOK_SECRET` e comparacao constante. Corpo, assinatura e credenciais nao sao persistidos. O corpo notifica apenas qual recurso mudou; status, valor, moeda e referencia sempre vem de `GET /v1/orders/{id}`.

O `ts` participa da assinatura e da deduplicacao. A documentacao oficial consultada nao define uma janela de idade para rejeicao, portanto nenhuma tolerancia arbitraria de replay foi inventada; repeticoes continuam seguras pela idempotencia persistida e de estado.

Entregas sao registradas em `provider_webhook_events` com identidade tecnica sem PII. A chave de deduplicacao usa provider, Order ID, request ID e timestamp da assinatura. Entregas terminais repetidas retornam `200` sem nova consulta. Falha temporaria retorna `503`, fica registrada como `failed` e pode ser reprocessada pelo retry do provider.

## Reconciliacao e concorrencia

A consulta HTTP ocorre sem lock de banco. Depois da resposta, a tentativa e relida com lock curto e sao validados:

- Order ID;
- `external_reference`;
- valor exato em `Decimal`;
- moeda `BRL`;
- transicao de estado permitida.

Estados finais nao regridem por notificacoes antigas. Aprovacao, reembolso integral e recalculo da cobranca ocorrem na mesma transacao local. Divergencia de identidade, valor, moeda ou sobrepagamento marca conflito e nunca aprova silenciosamente.

## Status

| Orders API | Status interno |
|---|---|
| `processed` + `accredited` | `aprovado` |
| `action_required`, `created`, `processing`, `pending` | `pendente` |
| `failed`, `rejected` | `recusado` |
| `cancelled`, `canceled`, `expired` | `cancelado` |
| `refunded` | `reembolsado` |
| `partially_refunded` | conflito operacional |
| `charged_back` | conflito operacional |
| desconhecido | conflito operacional na reconciliacao |

Status desconhecido nunca aprova pagamento. Reembolso integral e suportado; reembolso parcial e chargeback sao detectados, preservam o historico e exigem tratamento operacional futuro. Pagamento confirmado nao altera producao nem libera entrega nesta fase.

## Limites atuais

- sem endpoint publico de checkout;
- sem acao ativa de refund, suporte contabil a refund parcial/chargeback, boleto, assinatura ou split;
- sem worker/fila propria para reprocessamento;
- concorrencia foi coberta por constraints, locks e testes descartaveis; validacao de lock real em PostgreSQL continua recomendada antes da operacao financeira em producao;
- sem persistencia de payload bruto;
- sem chamada real nos testes.

F3.4 implementara checkout e tokenizacao frontend. F3.5 implementara a operacao administrativa financeira e a fila operacional de conciliacao.
