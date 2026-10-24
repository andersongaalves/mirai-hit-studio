# Auditoria setorial - S06 Checkout e pagamentos

Status do setor: **DIAGNOSTICADO**. Mudancas derivadas: [Etapa 07](../ETAPA_07_APLICACAO_AUDITORIA.md).

## 1. Baseline

| Campo | Valor |
| --- | --- |
| SHA | `18caa5b` (main) |
| Data | 24/10/2026 |
| Ambiente | Leitura estatica; suites `checkout_routing`, `public_contracting`, `proposta_comercial` verdes; consultas agregadas somente leitura |
| Limitacoes | `checkout.cjs` exige o pacote Python `qrcode` (indisponivel aqui; roda no CI). Nenhum pagamento real ou sandbox executado |

## 2. Inventario

- Rotas publicas por token: `GET /checkout/{token}`, `/status`, `/pending-payment`,
  `POST /pix`, `/cancel-pix`, `/card`; `GET /checkout/config`. Admin: link por proposta.
- Portal do Cliente: equivalentes por proposta (`/portal/cliente/propostas/{id}/checkout*`).
- Webhook `POST /webhooks/mercado-pago` (HMAC, idempotencia por evento).
- Compra de beat: `POST /portal/cliente/beats/{id}/solicitar` cria orcamento + proposta
  aceita + reserva de licenca e devolve `checkout_path`.
- Tabelas: `cobrancas`, `pagamentos`, `provider_webhook_events`, `beat_licencas`.
- Dados (24/10): 4 beats aprovados e ativos; nenhuma licenca de beat registrada ainda.

## 3. Fluxos

- Proposta aceita -> cobranca -> Pix/cartao (integral, entrada, saldo) -> webhook ou
  consulta -> cobranca paga/parcial -> liberacoes (producao, entrega 5.14, beat).
- Compra de beat: solicitar licenca -> proposta aceita automaticamente -> checkout ->
  `confirm_paid` marca a licenca como adquirida (exclusivo retira o beat do catalogo).
- Erro: provider indisponivel (503/429), divergencia (409 "requer conciliacao"),
  tentativa pendente (retomar ou cancelar Pix).

## 4. Achados

| ID | Sev. | Categoria | Achado | Status |
| --- | --- | --- | --- | --- |
| AUD6-S06-001 | P1 | 4.7 / 4.1 | Reserva de licenca de beat nunca expira nem e cancelada; um pedido sem pagamento bloqueia o beat para sempre | Aberto |
| AUD6-S06-002 | P2 | 4.7 | Reembolso nao revoga a licenca de beat adquirida nem devolve o exclusivo ao catalogo | Aberto |
| AUD6-S06-003 | P2 | 4.7 / 4.11 | Chargeback e reembolso parcial viram "pendente" sem alerta ao Admin | Aberto |
| AUD6-S06-004 | P2 | 4.10 | Downloads de beat (WAV e multitrack) carregam o arquivo inteiro na memoria do servidor | Aberto |
| AUD6-S06-005 | P3 | 4.4 / 4.5 | Mensagens internas do backend aparecem ao cliente ("requer conciliacao", sem acentos) | Aberto |
| AUD6-S06-006 | P3 | 4.10 | Catalogo de beats faz uma consulta de licencas por beat (N+1) | Aberto |
| AUD6-S06-007 | P3 | 4.4 | Arquivo baixado chega como `beat-{id}.wav` em vez do titulo | Aberto |

### AUD6-S06-001 - Reserva de beat sem expiracao (P1)

- Evidencia: `beat_service.request_license` cria orcamento e proposta **ja aceita** e
  `reserve_for_proposal` grava `beat_licencas.status = 'reservada'`. O status `cancelada`
  existe na constraint, mas nenhum codigo o atribui (busca em `services/` e `routers/`).
  `client_list` oculta o beat com exclusivo reservado e bloqueia o exclusivo se houver
  qualquer reserva.
- Impacto: um clique em "comprar exclusivo" sem pagar retira o beat do catalogo
  indefinidamente; qualquer lease nao paga impede vender o exclusivo. Nao ha acao do Admin
  para liberar. Sem dados afetados ainda (nenhuma licenca em producao).
- Recomendacao: prazo de reserva (ex.: igual a validade da proposta) com liberacao
  automatica; cancelar a reserva quando a cobranca/proposta for cancelada; acao do Admin
  "liberar reserva" com motivo e auditoria.
- Teste: reserva expirada libera o catalogo; cancelamento libera; pagamento apos expirar
  e recusado ou reconciliado.

### AUD6-S06-002 - Reembolso nao revoga licenca (P2)

- Evidencia: `_persistir_resultado` marca `reembolsado` e recalcula a cobranca, mas
  `beat_service.confirm_paid` so atua quando paga; nada reverte `adquirida`/`vendido`.
- Impacto: cliente reembolsado continua baixando; exclusivo reembolsado fica fora do
  catalogo.
- Recomendacao: ao sair de `paga`, licencas da proposta voltam a `cancelada` (download
  bloqueado) e o exclusivo volta ao catalogo apos decisao do Admin.

### AUD6-S06-003 - Chargeback e reembolso parcial (P2)

- Evidencia: `mercado_pago_service._provider_state` mapeia `charged_back` e `partially_refunded` para
  `pendente` com motivo `*_unsupported`; nao ha notificacao ao Admin.
- Recomendacao: registrar em fila de conciliacao do financeiro (S10) e notificar o Admin.

### AUD6-S06-004 - Downloads em memoria (P2)

- Evidencia: `purchased_file`/`multitrack_delivery` fazem `storage.read()` do objeto
  inteiro e devolvem `Response(contents)`; o limite de multitrack e configuravel no Admin.
- Impacto: pico de memoria no Render com arquivos grandes; risco de queda.
- Recomendacao: streaming ou URL assinada de curta duracao (com verificacao de
  integridade no upload, nao a cada download).

### P3

- **005**: `checkout.js` mostra `detail` do backend; textos como "Pagamento em
  processamento requer conciliacao." e "Checkout indisponivel." chegam ao cliente.
  Mapear para mensagens humanas com proximo passo.
- **006**: `client_list` consulta `beat_licencas` por beat.
- **007**: nome de arquivo com o id interno; usar o titulo normalizado.

## 5-7. Corrigir, centralizar, implementar

- Corrigir: 001, 002, 004, 005.
- Centralizar: resumo financeiro e tentativas do cliente (S07) e fila de conciliacao (S10).
- Candidatas: historico de tentativas; recuperar pendencia; ajuda de liberacao.

## 8-10. Tutoriais, linguagem, links

- Tutorial: "Comprar licenca de beat e entender arquivos liberados".
- Linguagem: mensagens de conflito sem jargao ("Seu pagamento esta sendo confirmado;
  aguarde alguns minutos").
- Link contextual: compra de beat -> proposta e cobranca no Admin.

## 11. Lacunas de teste

- Expiracao/cancelamento de reserva de beat; reembolso revogando licenca; chargeback.

## 12. Dependencias

- S04 (catalogo de beats), S07 (Explorar/compras), S10 (conciliacao), S12 (memoria/Storage).

## 13. Criterios de validacao

001 e 002 corrigidos com regressao; 003 com fluxo de alerta; 004 com teste de arquivo
grande; mensagens revisadas.
